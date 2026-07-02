"""§10 sanity checks for the [alpha/Fe] spectrum panel (atlas Tier B).

The mirror of test_spectra.py / test_wd_spectra.py, for the FOURTH spectrum sibling
`/alpha_spectrum` (the Coelho-2014 4-axis cube). Two layers:

* Always-on (no baked cube needed): the route contract — generous `Query` bounds
  reject absurd inputs with 422, and a missing cube surfaces a clean 503.

* Data-gated (`requires_alpha_spectra_data`): the [alpha/Fe] line physics, **measured
  through the runtime path** (`alpha_spectrum_data()` → RGI on the Coelho cube), NOT
  copied from raw grid numbers. This is Gate 1 turned into a regression test:
    - raising [alpha/Fe] 0 → 0.4 at fixed (Teff, log g, [Fe/H]) DEEPENS the alpha-element
      features (Ca I 4227, Mg b, Ca II triplet) in the cool/solar window.
    - the Na D control (odd-Z, NOT an alpha element) does NOT deepen with alpha — it
      moves the opposite way (shallower) — so the effect is genuine differential
      chemistry, not a global normalization/flux shift (which would move everything the
      same way). This is the "don't label a non-feature" gate made into a test.
    - the effect is Teff-gated: much weaker toward the hot end of the cube (~9000 K)
      than at 5000 K — the metals wash out, why the cube is the cool subset only.
    - both baselines (alpha 0 and 0.4) come from THIS cube (same grid_name) — a toggle
      flips two Coelho spectra, never Coelho-alpha vs a CAP18-solar one.
"""

from __future__ import annotations

import numpy as np
import pytest
from fastapi.testclient import TestClient

from star_sim import spectra
from star_sim.api import app
from star_sim.spectra import SpectraDataMissing, alpha_spectrum_data

from .conftest import requires_alpha_spectra_data

client = TestClient(app)

# alpha-sensitive features + a Na D control (air Å): (core_lo, core_hi, [continua]).
# Same windows the Gate-1 measurement used, so the pinned deltas trace to real numbers.
CA_I_4227 = (4222, 4232, [(4200, 4215), (4240, 4255)])
MG_B = (5160, 5190, [(5120, 5145), (5195, 5220)])
CA_T_8542 = (8535, 8550, [(8560, 8590), (8480, 8500)])
NA_D = (5885, 5900, [(5860, 5878), (5905, 5925)])


def _band_depth(d: dict, feature: tuple) -> float:
    """Band absorption depth (1 - mean(core)/mean(local continuum)) on a served
    spectrum — the same idiom Gate 1 used (bands, because individual lines blend at the
    2.5 Å runtime resolution). `feature` = (core_lo, core_hi, [continuum windows])."""
    lam = np.asarray(d["wavelength"])
    flux = np.asarray(d["flux"])
    clo, chi, cwins = feature

    def mean_in(lo, hi):
        return flux[(lam >= lo) & (lam <= hi)].mean()

    cont = np.mean([mean_in(lo, hi) for lo, hi in cwins])
    return 1.0 - mean_in(clo, chi) / cont


# --- always-on: the route contract (no baked cube required) ------------------

@pytest.mark.parametrize("params", [
    {"teff": 500, "logg": 4.5},          # Teff below the wide bounds
    {"teff": 300000, "logg": 4.5},       # Teff above the wide bounds
    {"teff": 5000, "logg": 9.0},         # log g above the bounds
    {"teff": 5000, "logg": 4.5, "afe": 0.9},   # afe above the 0.4 bound
    {"teff": 5000, "logg": 4.5, "afe": -0.2},  # afe below 0
    {"logg": 4.5},                       # missing required teff
    {"teff": 5000},                      # missing required logg
])
def test_alpha_spectrum_out_of_range_is_422(params):
    assert client.get("/alpha_spectrum", params=params).status_code == 422


def test_alpha_spectrum_not_baked_is_503(tmp_path, monkeypatch):
    """If the alpha cube hasn't been baked, /alpha_spectrum returns a clean 503
    (actionable), not a 500 — the app stays up; only the alpha panel is unavailable."""
    monkeypatch.setattr(spectra, "SPECTRA_DATA_DIR", tmp_path)  # empty dir
    monkeypatch.setattr(spectra, "_ALPHA_CACHE", None)          # force a reload
    r = client.get("/alpha_spectrum", params={"teff": 5000, "logg": 4.5})
    assert r.status_code == 503
    assert "bake" in r.json()["detail"].lower()


def test_alpha_spectrum_data_raises_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(spectra, "SPECTRA_DATA_DIR", tmp_path)
    monkeypatch.setattr(spectra, "_ALPHA_CACHE", None)
    with pytest.raises(SpectraDataMissing):
        alpha_spectrum_data(5000, 4.5, 0.0, 0.0)


# --- data-gated: well-formed + provenance ------------------------------------

@requires_alpha_spectra_data
def test_alpha_spectrum_endpoint_well_formed():
    r = client.get("/alpha_spectrum", params={"teff": 5000, "logg": 4.5, "feh": -0.5, "afe": 0.4})
    assert r.status_code == 200
    d = r.json()
    lam = np.asarray(d["wavelength"]); flux = np.asarray(d["flux"])
    assert lam.size == flux.size > 100
    assert np.all(np.diff(lam) > 0)
    assert np.all(np.isfinite(flux)) and np.all(flux >= 0) and flux.max() > 0
    assert d["afe_varies"] is True             # this cube exists to vary alpha
    assert d["feh_varies"] is True             # Coelho carries a real [Fe/H] axis
    assert "coelho" in d["grid_name"].lower()


@requires_alpha_spectra_data
def test_alpha_shares_the_main_cube_wavelength_grid():
    """The alpha cube is baked onto the SAME 3000–9000 Å @ 2.5 Å grid as the main cube,
    so the panel's x-axis and line guides don't jump when it switches cubes (the
    cool→hot handoff)."""
    a = alpha_spectrum_data(5000, 4.5, -0.5, 0.0)
    main = spectra.spectrum_data(5000, 4.5, -0.5)
    assert np.allclose(np.asarray(a["wavelength"]), np.asarray(main["wavelength"]))


# --- data-gated: the [alpha/Fe] line physics (measured through the runtime path) ---

@requires_alpha_spectra_data
def test_alpha_deepens_alpha_element_lines_cool_star():
    """Gate 1, as a regression test: at a cool/solar star, raising [alpha/Fe] 0 → 0.4
    (at fixed Teff/log g/[Fe/H]) DEEPENS the alpha-element features — Ca I 4227, Mg b,
    Ca II triplet — measured through the runtime at the 2.5 Å resolution. Deltas pinned
    with margin below the Gate-1 measured values (Ca4227 ~+0.12, Mg b ~+0.06, CaT
    ~+0.03 at 5000 K / log g 4.5 / [Fe/H] −0.5)."""
    a0 = alpha_spectrum_data(5000, 4.5, -0.5, 0.0)
    a4 = alpha_spectrum_data(5000, 4.5, -0.5, 0.4)
    assert _band_depth(a4, CA_I_4227) > _band_depth(a0, CA_I_4227) + 0.04
    assert _band_depth(a4, MG_B) > _band_depth(a0, MG_B) + 0.02
    assert _band_depth(a4, CA_T_8542) > _band_depth(a0, CA_T_8542) + 0.015

    # And at the OTHER cube [Fe/H] node (0.0) — Gate 1 showed it comparably strong,
    # so this also insures the second [Fe/H] slab baked correctly (advisor's ask).
    s0 = alpha_spectrum_data(5000, 4.5, 0.0, 0.0)
    s4 = alpha_spectrum_data(5000, 4.5, 0.0, 0.4)
    assert _band_depth(s4, CA_I_4227) > _band_depth(s0, CA_I_4227) + 0.04
    assert _band_depth(s4, MG_B) > _band_depth(s0, MG_B) + 0.02


@requires_alpha_spectra_data
def test_na_control_does_not_deepen_with_alpha():
    """The load-bearing 'don't label a non-feature' gate: Na D (odd-Z, NOT an alpha
    element) must NOT deepen with [alpha/Fe] — measured, it moves the OPPOSITE way
    (shallower, an alpha-heavier mix raises the H⁻ continuum and weakens non-alpha
    lines). This rules out a global normalization/flux artifact, which would deepen
    everything alike. So Ca I 4227 deepens while Na D does not — genuine differential
    chemistry."""
    a0 = alpha_spectrum_data(5000, 4.5, -0.5, 0.0)
    a4 = alpha_spectrum_data(5000, 4.5, -0.5, 0.4)
    d_ca0, d_ca4 = _band_depth(a0, CA_I_4227), _band_depth(a4, CA_I_4227)
    d_na0, d_na4 = _band_depth(a0, NA_D), _band_depth(a4, NA_D)
    assert d_ca4 - d_ca0 > 0.04                 # alpha element deepens
    assert d_na4 - d_na0 < 0.01                 # Na control does NOT deepen (measured < 0)
    assert (d_ca4 - d_ca0) > (d_na4 - d_na0) + 0.05   # clearly differential


@requires_alpha_spectra_data
def test_alpha_effect_is_teff_gated_weaker_hot():
    """The alpha effect is Teff-gated — strong at 5000 K, much weaker at the hot end of
    the cube (~9000 K), where the metal lines wash out. This is why the cube is the cool
    subset and the panel hands hotter stars to the main cube. Pin that the Ca I 4227
    alpha-deepening at 5000 K far exceeds that at 9000 K (measured ~+0.12 vs ~+0.00)."""
    def ca_delta(teff):
        a0 = alpha_spectrum_data(teff, 4.5, -0.5, 0.0)
        a4 = alpha_spectrum_data(teff, 4.5, -0.5, 0.4)
        return _band_depth(a4, CA_I_4227) - _band_depth(a0, CA_I_4227)
    assert ca_delta(5000) > ca_delta(9000) + 0.05


@requires_alpha_spectra_data
def test_both_alpha_baselines_from_the_same_coelho_cube():
    """A toggle flips between two spectra from THIS Coelho cube (never Coelho-alpha vs a
    CAP18-solar spectrum, whose atmosphere-code seam would masquerade as the alpha
    signal — the advisor-settled load-bearing rule). Both alpha states must serve
    in-grid from the same grid, at the requested afe."""
    a0 = alpha_spectrum_data(5000, 4.5, -0.5, 0.0)
    a4 = alpha_spectrum_data(5000, 4.5, -0.5, 0.4)
    assert a0["grid_name"] == a4["grid_name"]
    assert "coelho" in a0["grid_name"].lower()
    assert a0["afe"] == pytest.approx(0.0)
    assert a4["afe"] == pytest.approx(0.4)
