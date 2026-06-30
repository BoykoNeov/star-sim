"""§10 sanity checks for the white-dwarf spectrum panel (endgame Chunk 6).

The mirror of test_spectra.py, for the SECOND spectrum sibling `/wd_spectrum` (the
Koester DA cube). Two layers:

* Always-on (no baked cube needed): the route contract — generous `Query` bounds
  reject absurd inputs with 422, the hot central star (~107 kK) does NOT 422, and a
  missing cube surfaces a clean 503. These pin the API a fresh checkout still has.

* Data-gated (`requires_wd_spectra_data`): the DA physics, **measured through the
  runtime path** (`wd_spectrum_data()` → RGI on the Koester cube), NOT copied from
  raw grid numbers. The robust orderings are pinned with margin:
    - Balmer absorption peaks at intermediate Teff (~11–13 kK) and fades both ways.
    - higher log g → pressure broadening redistributes the Balmer core into the
      wings → a shallower core (this is how DA gravities are measured).
    - below the ~5000 K Koester floor the DA → DC: an honest blackbody continuum,
      no Balmer lines (the cold-cinder honesty edge).
    - above the 80000 K Koester ceiling the ~107 kK central star reports
      teff_requested > teff_max (the existing no-model path; TMAP fills it in 6b).
"""

from __future__ import annotations

import numpy as np
import pytest
from fastapi.testclient import TestClient

from star_sim import spectra
from star_sim.api import app
from star_sim.spectra import SpectraDataMissing, wd_spectrum_data

from .conftest import requires_wd_spectra_data

client = TestClient(app)

HA, HB = 6562.79, 4861.35   # Balmer Hα / Hβ — the DA's only spectral features


def _line_depth(d: dict, center: float, core_hw: float = 6.0,
                cont_lo: float = 20.0, cont_hi: float = 45.0) -> float:
    """Fractional absorption depth at `center` (1 - core/continuum), measured on a
    served spectrum — same idiom as test_spectra._line_depth. The core is the MIN
    within ±core_hw; the continuum is the mean of blue+red offset windows. (DA Balmer
    wings are broad, so the continuum windows sit just past the steep wings — close
    enough to track the core trend, the quantity we pin.)"""
    lam = np.asarray(d["wavelength"])
    flux = np.asarray(d["flux"])
    core = flux[(lam > center - core_hw) & (lam < center + core_hw)].min()
    blue = flux[(lam > center - cont_hi) & (lam < center - cont_lo)]
    red = flux[(lam > center + cont_lo) & (lam < center + cont_hi)]
    cont = np.concatenate([blue, red]).mean()
    return 1.0 - core / cont


# --- always-on: the route contract (no baked cube required) ------------------

@pytest.mark.parametrize("params", [
    {"teff": 500, "logg": 8.0},        # Teff below any real star
    {"teff": 500000, "logg": 8.0},     # Teff above the bounds
    {"teff": 13000, "logg": 2.0},      # log g below the WD bounds (a giant, not a WD)
    {"teff": 13000, "logg": 12.0},     # log g absurd
    {"logg": 8.0},                     # missing required teff
    {"teff": 13000},                   # missing required logg
])
def test_wd_spectrum_out_of_range_is_422(params):
    assert client.get("/wd_spectrum", params=params).status_code == 422


def test_wd_spectrum_hot_central_star_does_not_422():
    """The post-AGB central star reaches ~107 kK — above the Koester DA ceiling
    (80000 K), but the bounds must be wide enough that scrubbing there never 422s
    (the panel shows the honest no-model frame instead). 200 if baked, 503 if not."""
    r = client.get("/wd_spectrum", params={"teff": 107000, "logg": 7.0})
    assert r.status_code in (200, 503)


def test_wd_spectrum_not_baked_is_503(tmp_path, monkeypatch):
    """If the WD cube hasn't been baked, /wd_spectrum returns a clean 503 (actionable),
    not a 500 — the app stays up; only the WD spectrum panel is unavailable."""
    monkeypatch.setattr(spectra, "SPECTRA_DATA_DIR", tmp_path)  # empty dir
    monkeypatch.setattr(spectra, "_WD_CACHE", None)             # force a reload
    r = client.get("/wd_spectrum", params={"teff": 13000, "logg": 8.0})
    assert r.status_code == 503
    assert "bake" in r.json()["detail"].lower()


def test_wd_spectrum_data_raises_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(spectra, "SPECTRA_DATA_DIR", tmp_path)
    monkeypatch.setattr(spectra, "_WD_CACHE", None)
    with pytest.raises(SpectraDataMissing):
        wd_spectrum_data(13000, 8.0)


# --- data-gated: well-formed + provenance ------------------------------------

@requires_wd_spectra_data
def test_wd_spectrum_endpoint_well_formed():
    r = client.get("/wd_spectrum", params={"teff": 13000, "logg": 8.0})
    assert r.status_code == 200
    d = r.json()
    lam = np.asarray(d["wavelength"]); flux = np.asarray(d["flux"])
    assert lam.size == flux.size > 100
    assert np.all(np.diff(lam) > 0)
    assert np.all(np.isfinite(flux)) and np.all(flux >= 0) and flux.max() > 0
    assert d["regime"] == "DA"
    assert d["feh_varies"] is False           # a DA is pure hydrogen — no [Fe/H] axis
    assert "koester" in d["grid_name"].lower()


@requires_wd_spectra_data
def test_wd_shares_the_main_cube_wavelength_grid():
    """The WD cube is baked onto the SAME 3000–9000 Å @ 2.5 Å grid as the main cube,
    so the panel's x-axis and line guides don't jump when it switches cubes."""
    wd = wd_spectrum_data(13000, 8.0)
    main = spectra.spectrum_data(9500, 4.0, 0.0)
    assert np.allclose(np.asarray(wd["wavelength"]), np.asarray(main["wavelength"]))


# --- data-gated: the DA line physics (measured through the runtime path) ------

@requires_wd_spectra_data
def test_balmer_peaks_at_intermediate_teff_and_fades_both_ways():
    """A DA white dwarf's Balmer absorption is strongest at intermediate Teff
    (~11–13 kK) and shallower in both a cool DA and a hot one (where hydrogen is
    increasingly ionized) — measured here on the baked+interpolated Koester spectra.
    Hβ is the cleanly-peaked line (Hα is already strong at the cool end), so we pin
    it; the orderings hold with margin (measured Δ ≳ 0.08 both ways)."""
    peak = wd_spectrum_data(11000, 8.0)     # near the DA Balmer maximum
    cool = wd_spectrum_data(6000, 8.0)
    hot = wd_spectrum_data(40000, 8.0)
    d_peak = _line_depth(peak, HB)
    assert d_peak > 0.3                       # a real, deep Balmer line (~0.52)
    assert d_peak > _line_depth(cool, HB) + 0.08   # fades toward the cool end
    assert d_peak > _line_depth(hot, HB) + 0.08    # fades toward the hot end


@requires_wd_spectra_data
def test_higher_logg_broadens_balmer_shallower_core():
    """Surface gravity is written in the Balmer line PROFILE: higher log g (denser
    photosphere) Stark-broadens the line, redistributing the core absorption into the
    wings → a shallower core. This monotonic core trend with log g is the basis of
    spectroscopic WD gravities; we pin it at fixed Teff (measured core 0.52 → 0.43
    from log g 6.5 → 9.5)."""
    teff = 13000.0
    d_lowg = wd_spectrum_data(teff, 6.5)      # lowest WD gravity — deepest core
    d_midg = wd_spectrum_data(teff, 8.0)
    d_highg = wd_spectrum_data(teff, 9.5)     # highest gravity — most broadened
    c_lo = _line_depth(d_lowg, HB)
    c_mid = _line_depth(d_midg, HB)
    c_hi = _line_depth(d_highg, HB)
    assert c_lo > c_hi + 0.04                  # broadened away from the core at high g
    assert c_lo > c_mid > c_hi                 # monotonic in between


@requires_wd_spectra_data
def test_cold_cinder_is_dc_continuum_not_clamped_balmer():
    """Below the ~5000 K Koester floor a real DA loses its Balmer lines and becomes a
    featureless DC white dwarf. The runtime returns an honest Planck continuum at the
    requested Teff (regime="DC"), NOT the clamped 5000 K Koester spectrum — so no H
    lines are painted onto the cinder, and the continuum slope is right for a cold
    star (the "don't label a non-feature" rule)."""
    floor = wd_spectrum_data(13000, 8.0)["teff_min"]
    cinder = wd_spectrum_data(2393, 8.0)       # the cold cinder at the end of cooling
    assert cinder["teff_requested"] < floor    # genuinely below the model floor
    assert cinder["regime"] == "DC"
    assert cinder["teff"] == pytest.approx(2393.0, abs=1.0)   # the real Teff, not clamped
    flux = np.asarray(cinder["flux"])
    assert np.all(np.isfinite(flux)) and np.all(flux >= 0) and flux.max() > 0
    assert _line_depth(cinder, HA) < 0.02      # lines have faded (measured ~0.004)
    assert _line_depth(cinder, HB) < 0.02

    # And the cold continuum is REDDER than a hot DA's (more flux at 8000 vs 4000 Å):
    # the honest slope a clamped 5000 K spectrum would get wrong.
    lam = np.asarray(cinder["wavelength"]); cf = np.asarray(cinder["flux"])
    red = cf[(lam > 7800) & (lam < 8200)].mean()
    blue = cf[(lam > 3800) & (lam < 4200)].mean()
    assert red > blue                          # a cold blackbody rises to the red


@requires_wd_spectra_data
def test_hot_central_star_reports_no_model():
    """The ~107 kK post-AGB central star is past the Koester ceiling (80000 K). The
    response reports teff_requested > teff_max with teff pinned to teff_max — the same
    contract the panel's existing no-model frame keys off (that gap is what the TMAP
    hot-WD grid fills in Chunk 6b)."""
    d = wd_spectrum_data(107000, 7.0)
    assert d["teff_requested"] == pytest.approx(107000.0)
    assert d["teff_requested"] > d["teff_max"]
    assert d["teff"] == pytest.approx(d["teff_max"], abs=1.0)
    assert d["teff_max"] == pytest.approx(80000.0, abs=1.0)   # the Koester DA ceiling
