"""§10 sanity checks for the core-collapse supernova sibling (Chunk 1 of the SN arc —
docs/plans/radioactive-afterglow-requiem.md).

Unlike WD/WR, a supernova is NOT on the MIST tracks — it is a **computed** semi-analytic
model (`supernova.py`), fed by progenitor scalars `MISTProvider.endgame()` exposes for the
`type="SN"` branch. So these split in two:

  * the light-curve *physics* is unit-tested deterministically on a fixed canonical
    progenitor (no grids needed) — the Tier-1 ⁵⁶Co slope, the Tier-3 M_Ni linearity, the
    plateau⊕tail handoff, the no-plateau fallback;
  * the *runtime path* (endgame → scalars → sibling → /supernova route) is tested through
    the real provider where the grids are present (`requires_mist_data`).

Landmarks are the Chunk-0 gate's measured values (re-verify if the grids change):
  * canonical 15 M☉ solar: M_fin ≈ 11.98, CO core ≈ 2.8 (< 7 → NS, 1.4 M☉), M_ej ≈ 10.6,
    R₀ in the RSG range → plateau ~1.5×10⁴² erg/s, t_p ~130 d.
  * Tier-1 ⁵⁶Co tail slope = 2.5/ln10/τ_Co = 0.00975 mag/day (= textbook 0.0098), set only
    by τ_Co = 111.3 d — parameter-free, the verification jewel.
"""

from __future__ import annotations

import numpy as np
import pytest

from fastapi.testclient import TestClient

from star_sim.api import app
from star_sim.providers import MISTProvider
from star_sim.state import StellarState
from star_sim.supernova import (
    M_NI_DEFAULT,
    Progenitor,
    supernova_model,
)

from .conftest import requires_mist_data
from .test_stub_provider import EXPECTED_KEYS


# A fixed canonical 15 M☉ solar Type-II progenitor (the gate's measured scalars), so the
# light-curve physics is tested without depending on the MIST grids. he_core is echoed
# only (it doesn't enter the light curve); the curve is driven by final_mass (M_ej), CO
# core (remnant cut), R₀ (plateau), M_Ni and E.
CANONICAL = Progenitor(
    mass_init_msun=15.0,
    final_mass_msun=11.98,
    he_core_msun=4.5,
    co_core_msun=2.8,
    pre_sn_radius_rsun=900.0,
    h_retained=True,
    feh_init=0.0,
)

# The bulletproof anchor: 2.5 / (ln10 · τ_Co), τ_Co = 111.3 d.
_CO_SLOPE = 0.0097550


def _arrs(model):
    lc = model.light_curve
    return (
        np.array(lc["time_days"]),
        np.array(lc["L_total_erg_s"]),
        np.array(lc["L_radio_erg_s"]),
    )


# === Tier 1 — the ⁵⁶Co tail slope (zero free parameters, THE anchor) ============
def test_co_tail_slope_is_the_tier1_anchor():
    """The decline rate of the radioactive tail is set ONLY by τ_Co — no free parameters.
    The served `co_tail_slope_mag_day` is the analytic value, and the served `L_radio`
    array reproduces it over 200→300 d (where the ⁵⁶Ni term is long dead): 0.00975 mag/day,
    the textbook SN 1987A tail."""
    m = supernova_model(CANONICAL)
    assert m.co_tail_slope_mag_day == pytest.approx(_CO_SLOPE, abs=2e-5)

    t, _, l_radio = _arrs(m)
    i1, i2 = int(np.argmin(np.abs(t - 200.0))), int(np.argmin(np.abs(t - 300.0)))
    slope = -2.5 * np.log10(l_radio[i2] / l_radio[i1]) / (t[i2] - t[i1])
    assert slope == pytest.approx(_CO_SLOPE, abs=2e-4)   # measured off the served curve


# === Tier 3 — M_Ni scales the radioactive tail linearly (NOT the plateau peak) ===
def test_m_ni_scales_radioactive_tail_linearly():
    """The honest Tier-3 statement: ⁵⁶Ni mass scales the **radioactive tail** linearly
    (L_radio ∝ M_Ni exactly). The IIP **peak is the plateau**, which is recombination-
    powered and carries NO M_Ni term — so doubling M_Ni doubles the tail but leaves the
    plateau luminosity untouched. (This is why the plan's shorthand 'peak ∝ M_Ni' is true
    only for the no-plateau case.)"""
    a = supernova_model(CANONICAL, m_ni=0.06)
    b = supernova_model(CANONICAL, m_ni=0.12)
    _, _, la = _arrs(a)
    _, _, lb = _arrs(b)
    assert np.allclose(lb / la, 2.0, rtol=1e-9)              # exactly linear in M_Ni
    assert b.plateau_L_erg_s == a.plateau_L_erg_s            # the plateau is M_Ni-independent


# === composition: the plateau hands off to the radioactive tail =================
def test_light_curve_hands_off_to_the_radioactive_tail():
    """Past ~2·t_p the recombination plateau has switched off and the light curve IS the
    radioactive tail (L_total → L_radio). This is the §6-style honest composition check:
    the two components blend, they don't double-count at late times."""
    m = supernova_model(CANONICAL)
    t, l_total, l_radio = _arrs(m)
    i = int(np.argmin(np.abs(t - 2.0 * m.plateau_duration_days)))
    assert l_total[i] == pytest.approx(l_radio[i], rel=0.01)


# === Tier 2 — the plateau lands in the observed IIP regime ======================
def test_plateau_in_regime_for_canonical():
    """Kasen–Woosley plateau for the canonical progenitor: L_p ~1.5×10⁴² erg/s and a
    duration in the observed IIP band. The level is ±dex (Tier-2), the duration runs a
    bit long (the documented R₀/T_ion/κ uncertainty — the gate's 70–150 d band, NOT pinned
    near 100), so we assert *regime*, not a sharp prediction."""
    m = supernova_model(CANONICAL)
    assert m.has_plateau is True
    assert 5.0e41 < m.plateau_L_erg_s < 5.0e42            # gate ~1.5e42; ±dex
    assert 70.0 < m.plateau_duration_days < 150.0        # gate 133 d


# === type + ejecta/remnant split ===============================================
def test_type_ii_and_ejecta_remnant_split():
    """An H-retained progenitor is a Type II; its CO core (2.8 < 7 M☉) leaves a neutron
    star, and the ejecta are everything above the remnant (M_ej = M_fin − M_remnant)."""
    m = supernova_model(CANONICAL)
    assert m.type == "II"
    assert m.remnant_type == "NS"
    assert m.remnant_mass_msun == pytest.approx(1.4)
    assert m.m_ej_msun == pytest.approx(CANONICAL.final_mass_msun - m.remnant_mass_msun)
    assert m.m_ej_msun == pytest.approx(10.58, abs=0.1)


def test_black_hole_remnant_for_a_heavy_co_core():
    """A heavy CO core (> 7 M☉) collapses to a black hole; the ejecta stay strictly
    positive (the remnant can't exceed the star). A labeled mass cut — Chunk 5 refines."""
    heavy = Progenitor(40.0, 20.0, 16.0, 10.0, 800.0, True, 0.0)
    m = supernova_model(heavy)
    assert m.remnant_type == "BH"
    assert m.remnant_mass_msun == pytest.approx(10.0)
    assert m.m_ej_msun == pytest.approx(10.0)
    assert m.m_ej_msun > 0.0


# === the no-plateau fallback (compact, no RSG envelope) =========================
def test_no_plateau_fallback_for_compact_progenitor():
    """A compact very-massive low-Z progenitor (R₀ < 300 R☉) has no red-supergiant
    envelope, so the recombination-plateau model does not apply: the curve is honestly
    radioactive-only (L_total == L_radio, no plateau fields), and the Tier-1 ⁵⁶Co slope
    still holds."""
    compact = Progenitor(150.0, 30.0, 28.0, 12.0, 150.0, True, -1.0)
    m = supernova_model(compact)
    assert m.has_plateau is False
    assert m.plateau_L_erg_s is None and m.plateau_duration_days is None
    assert m.light_curve["L_plateau_erg_s"] is None
    _, l_total, l_radio = _arrs(m)
    assert np.allclose(l_total, l_radio)
    assert m.co_tail_slope_mag_day == pytest.approx(_CO_SLOPE, abs=2e-5)


# === the homologous photosphere states (StellarStates the 3D/SED consume) =======
def test_photosphere_states_are_homologous_stellarstates():
    """The sibling emits StellarStates whose radius expands homologously (R = v·t, so
    monotonically) and whose ejecta cool as they expand (late Teff < early). logg is
    honestly tiny→negative at late times — freely-expanding ejecta have no stellar surface
    gravity (Chunk 2's {endgame:'sn'} signal, not a logg gate, drives the renderers)."""
    m = supernova_model(CANONICAL)
    assert all(isinstance(s, StellarState) for s in m.states)
    assert len(m.states) == len(m.light_curve["time_days"])
    radii = [s.R_rsun for s in m.states]
    assert radii == sorted(radii)                        # homologous expansion
    assert m.states[-1].Teff_K < m.states[0].Teff_K      # cooling ejecta
    assert m.states[-1].logg < 0.0                       # not a stellar surface
    assert m.m_ni_default == M_NI_DEFAULT


def test_m_ni_clamped_to_observed_range():
    """The Tier-3 nickel knob is clamped to the observed 0.001–0.3 M☉ window, so the
    served curve always corresponds to a physical yield."""
    assert supernova_model(CANONICAL, m_ni=99.0).m_ni_msun == pytest.approx(0.3)
    assert supernova_model(CANONICAL, m_ni=0.0).m_ni_msun == pytest.approx(0.001)


# === runtime path: provider scalars + the /supernova route ======================
@pytest.fixture(scope="module")
def provider() -> MISTProvider:
    return MISTProvider()


@requires_mist_data
def test_progenitor_scalars_only_on_the_sn_branch(provider):
    """`endgame()` populates the core-collapse scalars (R₀, He/CO cores, surface-H flag)
    ONLY for the SN branch; WD / WR / none leave them None. The SN values are physical."""
    sn = provider.endgame(15.0, 0.0)
    assert sn.type == "SN"
    assert sn.pre_sn_radius_rsun is not None and sn.pre_sn_radius_rsun > 100.0
    assert sn.he_core_msun is not None and sn.co_core_msun is not None
    assert 0.0 < sn.co_core_msun <= sn.he_core_msun < sn.final_mass_msun
    assert sn.h_retained is True                          # the SN bucket is purely Type II

    for mass, fate in ((1.0, "WD"), (60.0, "WR"), (0.1, "none")):
        e = provider.endgame(mass, 0.0)
        assert e.type == fate
        assert e.pre_sn_radius_rsun is None
        assert e.he_core_msun is None and e.co_core_msun is None
        assert e.h_retained is None


@requires_mist_data
def test_plateau_in_regime_through_the_runtime_path(provider):
    """The canonical 15 M☉ curve, built from the REAL snapped progenitor (not a fixture):
    a Type II with a plateau in the observed regime and the ejecta split M_ej = M_fin −
    M_remnant. The end-to-end measure-through-the-runtime-path gate."""
    eg = provider.endgame(15.0, 0.0)
    prog = Progenitor(
        eg.mass_init_msun, eg.final_mass_msun, eg.he_core_msun,
        eg.co_core_msun, eg.pre_sn_radius_rsun, eg.h_retained, eg.feh_init,
    )
    m = supernova_model(prog)
    assert m.type == "II" and m.has_plateau
    assert 5.0e41 < m.plateau_L_erg_s < 5.0e42
    assert 70.0 < m.plateau_duration_days < 150.0
    assert m.remnant_type == "NS"
    assert m.m_ej_msun == pytest.approx(eg.final_mass_msun - m.remnant_mass_msun)


@requires_mist_data
def test_api_supernova_sn_payload():
    """The /supernova route for an SN progenitor: is_supernova, a three-component light
    curve over a shared time grid, and photosphere states in the exact §3 StellarState
    shape (the API adds no fields of its own)."""
    client = TestClient(app)
    resp = client.get("/supernova", params={"mass": 15.0, "feh": 0.0})
    assert resp.status_code == 200
    body = resp.json()
    assert body["is_supernova"] is True
    assert body["type"] == "II"
    assert body["has_plateau"] is True
    lc = body["light_curve"]
    n = len(lc["time_days"])
    assert n > 100
    assert len(lc["L_total_erg_s"]) == n and len(lc["L_radio_erg_s"]) == n
    assert len(body["states"]) == n
    assert all(set(s.keys()) == EXPECTED_KEYS for s in body["states"])
    # the M_Ni slider metadata the panel needs
    assert body["m_ni_default"] == M_NI_DEFAULT
    assert body["m_ni_min"] < body["m_ni_default"] < body["m_ni_max"]


@requires_mist_data
def test_api_supernova_m_ni_scales_the_tail():
    """Dragging the M_Ni knob through the route doubles the radioactive tail (Tier-3)."""
    client = TestClient(app)
    a = client.get("/supernova", params={"mass": 15.0, "feh": 0.0, "m_ni": 0.06}).json()
    b = client.get("/supernova", params={"mass": 15.0, "feh": 0.0, "m_ni": 0.12}).json()
    la = np.array(a["light_curve"]["L_radio_erg_s"])
    lb = np.array(b["light_curve"]["L_radio_erg_s"])
    assert np.allclose(lb / la, 2.0, rtol=1e-9)


@requires_mist_data
def test_api_supernova_non_sn_is_honest_empty():
    """A non-SN progenitor (a 1 M☉ white dwarf) gets an honest empty payload: the real
    fate echoed, no light curve, no states — the gateway shows the WD renderer instead."""
    client = TestClient(app)
    body = client.get("/supernova", params={"mass": 1.0, "feh": 0.0}).json()
    assert body["is_supernova"] is False
    assert body["type"] == "WD"
    assert body["states"] == []
    assert body["light_curve"] is None


@requires_mist_data
def test_api_supernova_out_of_range_is_422():
    client = TestClient(app)
    resp = client.get("/supernova", params={"mass": 999.0, "feh": 0.0})
    assert resp.status_code == 422
