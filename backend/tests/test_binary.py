"""Validation for the binary-stripped-star sibling (`binary.py`, `/binary`).

The stripped star is the hot, He-rich core a close companion exposes by Case-B
Roche-lobe overflow — the ~70% binary WR/subdwarf channel (Götberg+2018). Like the
supernova / structure / spectra siblings it bypasses `PROVIDER` and emits a plain
`StellarState`, so the anchors here are:

  * the parse + snap honesty (a request lands on a TRUE grid node, never an
    interpolation — §6), and the committed table's internal validity;
  * **the visibility gate** — the discipline check that this is a *feature*: a stripped
    star must read visibly distinct from the MIST single-star of the SAME initial mass
    through the real runtime path, or there is nothing to show. It keys on **Teff and
    Y_surf only, never luminosity** — a stripped star is sub-luminous *for its Teff*, but
    because M_strip ≪ M_init it is a He-star of a different mass, so the L comparison
    flips sign across the grid (sub-luminous at 2 M☉, over-luminous at 18 M☉). Hotter +
    He-enriched are the robust discriminators;
  * the SED-consistency regression — the *entire basis for trusting the LLM-transcribed
    table*: table L vs the ground-truth SED-integrated L, Stefan-Boltzmann L(Teff,R) vs
    SED L, and logg vs (M_strip, R). Gated `requires_gotberg_data` (reads the gitignored
    SEDs); the parameter table itself is committed, so every other test always runs.
"""

from __future__ import annotations

import math
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from star_sim import binary as b
from star_sim.api import app
from star_sim.state import StellarState

from .conftest import requires_gotberg_data, requires_mist_data

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SED_GRID = _REPO_ROOT / "data" / "gotberg_stripped" / "grid_014"

# The three mid/high-grid nodes used for the visibility gate (He-rich surface; the
# low-mass end is still H-rich sdB-like, so it is not where the He headline lives).
_VISIBILITY_MASSES = [4.04, 9.0, 14.87]


# --- parse + committed-table validity (always run — data is committed) --------

def test_grid_parses_23_solar_models():
    models = b.available_models()
    solar = [m for m in models if abs(m.grid_z - 0.014) < 1e-9]
    assert len(solar) == 23
    assert all(2.0 <= m.m_init <= 18.17 for m in solar)


def test_grid_is_ordered_and_he_enriches_with_mass():
    """Down the grid the stripped stars get hotter, bigger, and more He-surfaced —
    the physical trend (heavier progenitor → deeper stripping → more exposed He)."""
    solar = sorted((m for m in b.available_models() if abs(m.grid_z - 0.014) < 1e-9),
                   key=lambda m: m.m_init)
    teffs = [m.teff_kK for m in solar]
    assert teffs == sorted(teffs)                       # monotone hotter
    # He surface fraction (raw table X_He) rises from ~0 (low mass, H-rich) to ~0.87.
    assert solar[0].x_he < 0.05 and solar[-1].x_he > 0.8


# --- snap honesty (never interpolate — §6) ------------------------------------

def test_snap_returns_a_true_grid_node():
    node_masses = {m.m_init for m in b.available_models() if abs(m.grid_z - 0.014) < 1e-9}
    # a request off any node snaps to the nearest real node, reported verbatim
    r = b.stripped_star(8.5, 0.0)
    assert r.m_init_msun in node_masses
    assert r.state.mass_init_msun == r.m_init_msun    # the state carries the snapped node
    # 8.5 is between 8.15 and 9.0 -> nearest is 8.15
    assert r.m_init_msun == 8.15


def test_snap_far_flags_out_of_range():
    lo, hi = b.eligible_mass_range(0.0)
    assert b.stripped_star(hi + 5.0, 0.0).mass_snapped_far is True    # above the grid
    assert b.stripped_star(lo - 0.5, 0.0).mass_snapped_far is True    # below the grid
    assert b.stripped_star(9.0, 0.0).mass_snapped_far is False        # in range
    # with only the solar bucket on disk, [Fe/H] off ~solar snaps to Z=0.014 and is flagged
    assert b.stripped_star(9.0, 0.5).feh_snapped_far is True
    assert b.stripped_star(9.0, 0.0).feh_snapped_far is False


def test_snap_reports_true_grid_z_as_feh():
    r = b.stripped_star(9.0, -0.8)
    assert r.grid_z == 0.014                          # only solar on disk -> snaps to it
    assert r.feh_snapped == pytest.approx(0.0, abs=1e-9)


# --- StellarState validity (composition closes; scalars sane) -----------------

def test_state_is_valid_stellar_state():
    for mass in [2.0, 4.04, 9.0, 14.87, 18.17]:
        s = b.stripped_star(mass, 0.0).state
        assert isinstance(s, StellarState)
        # mass fractions close at 1 (Z_surf = grid Z, X/Y renormalized to 1−Z)
        assert s.X_surf + s.Y_surf + s.Z_surf == pytest.approx(1.0, abs=1e-9)
        assert 0.0 <= s.X_surf <= 1.0 and 0.0 <= s.Y_surf <= 1.0
        assert s.Z_surf == pytest.approx(0.014, abs=1e-9)
        # hot, compact, luminous He-star: Teff tens of kK, high surface gravity
        assert 15_000.0 < s.Teff_K < 120_000.0
        assert 5.0 < s.logg < 6.0
        assert s.L_lsun > 1.0
        assert s.R_rsun < 1.0                          # compact (sub-R☉)
        assert s.phase == "stripped-envelope star"
        assert s.mdot_msun_yr is None                  # not in the verified 8-column table


def test_current_mass_rides_as_a_routing_scalar():
    """M_strip (current mass) has no home on StellarState (only mass_init) — it must come
    back as a scalar, and it is far below the progenitor mass (the envelope is gone)."""
    r = b.stripped_star(9.0, 0.0)
    assert r.m_strip_msun == pytest.approx(2.49, abs=1e-6)
    assert r.m_strip_msun < r.m_init_msun              # stripped: current ≪ initial
    assert not hasattr(r.state, "m_strip_msun")


# --- the visibility gate (the "is this a feature" discipline check) -----------

@requires_mist_data
def test_stripped_is_off_relation_vs_single_star():
    """Through the REAL runtime path: the stripped star is hotter AND He-enriched vs the
    MIST single-star of the same initial mass (its ZAMS). Keys on Teff + Y_surf only —
    NOT L (which flips sign across the grid; see the module docstring)."""
    from star_sim.api import PROVIDER

    for mass in _VISIBILITY_MASSES:
        stripped = b.stripped_star(mass, 0.0).state       # the shipped path, not inline
        lo, hi = PROVIDER.age_range(mass, 0.0)
        single_zams = PROVIDER.state_at(mass, 0.0, lo + 0.02 * (hi - lo))

        d_teff = stripped.Teff_K - single_zams.Teff_K
        d_y = stripped.Y_surf - single_zams.Y_surf
        assert d_teff > 5000.0, f"M={mass}: stripped not hotter (ΔTeff={d_teff:.0f})"
        assert d_y > 0.2, f"M={mass}: stripped surface not He-enriched (ΔY={d_y:.2f})"


# --- /binary route smoke ------------------------------------------------------

def test_route_payload_shape():
    c = TestClient(app)
    r = c.get("/binary", params={"mass": 9.0, "feh": 0.0})
    assert r.status_code == 200
    d = r.json()
    # the §3 StellarState under `state`, routing scalars flattened alongside
    assert set(d) >= {
        "state", "m_strip_msun", "m_init_msun", "grid_z", "feh_snapped",
        "mass_snapped_far", "feh_snapped_far", "mass_grid_min", "mass_grid_max",
    }
    assert set(d["state"]) >= {"Teff_K", "L_lsun", "R_rsun", "logg", "X_surf", "Y_surf", "Z_surf"}
    assert d["state"]["Teff_K"] == pytest.approx(65500.0)
    assert d["m_strip_msun"] == pytest.approx(2.49)


def test_route_snaps_far_in_band_not_422():
    c = TestClient(app)
    r = c.get("/binary", params={"mass": 25.0, "feh": 0.5})   # out of grid both axes
    assert r.status_code == 200                                 # snap-always, not 422
    d = r.json()
    assert d["mass_snapped_far"] is True and d["feh_snapped_far"] is True
    assert d["m_init_msun"] == pytest.approx(18.17)             # snapped to the top node


def test_route_422_on_invalid_mass():
    c = TestClient(app)
    assert c.get("/binary", params={"mass": -1.0}).status_code == 422
    assert c.get("/binary", params={"mass": 0.0}).status_code == 422


# --- the SED-consistency regression (why we trust the transcribed table) ------

_KPC_CM = 3.0856775814913673e21
_LSUN_ERGS = 3.828e33
_TEFF_SUN = 5772.0
_LOGG_SUN = 4.438


def _sed_logL(model_dir: Path) -> float:
    """log10(L/L_sun) from a Götberg SED (flux at 1 kpc). λ-sorted (CMFGEN concatenates
    frequency bands → file order isn't monotone) and clipped at 5 µm (all real luminosity
    of these hot compact stars is blueward; the clip neutralizes the spurious >5 µm
    free-free tail in the 3.65 M☉ file)."""
    pts = set()
    for line in (model_dir / "SED.txt").read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        a, c = line.split()
        pts.add((float(a), float(c)))
    lam_flx = sorted(pts)
    fbol = 0.0
    for i in range(1, len(lam_flx)):
        lam, flx = lam_flx[i]
        if lam > 50_000.0:
            break
        fbol += 0.5 * (flx + lam_flx[i - 1][1]) * (lam - lam_flx[i - 1][0])
    return math.log10(4.0 * math.pi * _KPC_CM**2 * fbol / _LSUN_ERGS)


def _sed_dir_for(m_init: float) -> Path | None:
    for d in _SED_GRID.iterdir():
        mt = re.match(r"M1_([0-9.]+)q", d.name)
        if mt and abs(float(mt.group(1)) - m_init) < 1e-6:
            return d
    return None


@requires_gotberg_data
def test_table_matches_seds():
    """Every committed Z=0.014 row is self-consistent with its ground-truth SED — the
    check that makes the LLM-transcribed table trustworthy. Measured max |Δ| = 0.070 dex
    (table-L vs SED-L), 0.063 (SB vs SED-L), 0.017 (logg). The bounds are tightened to
    ~0.10 (L) / 0.05 (logg) — headroom over the measured maxima, but tight enough that a
    single-digit transcription slip in a row still trips it. Do not edit a table row
    without re-running this."""
    solar = [m for m in b.available_models() if abs(m.grid_z - 0.014) < 1e-9]
    checked = 0
    for m in solar:
        d = _sed_dir_for(m.m_init)
        assert d is not None, f"no SED dir for M_init={m.m_init}"
        sed_logL = _sed_logL(d)
        sb_logL = math.log10(m.r_eff**2 * (m.teff_kK * 1000.0 / _TEFF_SUN) ** 4)
        calc_logg = _LOGG_SUN + math.log10(m.m_strip) - 2.0 * math.log10(m.r_eff)
        assert abs(m.logL - sed_logL) < 0.10, f"M={m.m_init}: tblL vs sedL = {abs(m.logL - sed_logL):.3f}"
        assert abs(sb_logL - sed_logL) < 0.10, f"M={m.m_init}: SB(Teff,R) vs sedL = {abs(sb_logL - sed_logL):.3f}"
        assert abs(m.logg - calc_logg) < 0.05, f"M={m.m_init}: logg vs (Mstrip,R) = {abs(m.logg - calc_logg):.3f}"
        checked += 1
    assert checked == 23
