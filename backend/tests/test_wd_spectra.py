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
    - the ~100–190 kK post-AGB central star (CSPN) is the TMAP NLTE slab (Chunk 6b):
      a real spectrum (regime "CSPN"), spliced continuously onto Koester at 80 kK,
      and (measured) the optical is log g-insensitive there so the cube's log g clamp
      on the lowest-gravity central stars is honest.
    - only above TMAP's 190000 K ceiling (the most massive progenitors' central
      stars) does teff_requested > teff_max trip the residual no-model path.
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
    {"teff": 600000, "logg": 8.0},     # Teff above the wide WD bounds (500000)
    {"teff": 13000, "logg": 2.0},      # log g below the WD bounds (a giant, not a WD)
    {"teff": 13000, "logg": 12.0},     # log g absurd
    {"logg": 8.0},                     # missing required teff
    {"teff": 13000},                   # missing required logg
])
def test_wd_spectrum_out_of_range_is_422(params):
    assert client.get("/wd_spectrum", params=params).status_code == 422


def test_wd_spectrum_hot_central_star_does_not_422():
    """The post-AGB central star reaches ~107 kK (low-mass) up to ~400 kK (the most
    massive WD progenitors) — the bounds must be wide enough that scrubbing there
    never 422s (in-grid → a real CSPN spectrum; past TMAP's ceiling → the honest
    no-model frame). 200 if baked, 503 if not — never 422."""
    for teff in (107000, 190000, 405000):
        r = client.get("/wd_spectrum", params={"teff": teff, "logg": 7.0})
        assert r.status_code in (200, 503), f"teff={teff} -> {r.status_code}"


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
def test_hot_central_star_has_real_cspn_spectrum():
    """The ~107 kK post-AGB central star is past the Koester DA ceiling (80000 K) but
    inside the TMAP NLTE slab (Chunk 6b), so it returns a REAL spectrum — regime
    "CSPN", in-grid (not clamped), and a steep BLUE continuum (a ~100 kK star peaks
    far in the UV, so within the optical window flux falls toward the red — the
    opposite slope to the cold DC cinder)."""
    d = wd_spectrum_data(107000, 7.0)
    assert d["regime"] == "CSPN"
    assert d["teff"] == pytest.approx(107000.0, abs=1.0)     # in-grid, NOT clamped
    assert d["teff_requested"] <= d["teff_max"]              # below TMAP's ceiling
    assert d["teff_max"] == pytest.approx(190000.0, abs=1.0)  # TMAP's ceiling now
    flux = np.asarray(d["flux"]); lam = np.asarray(d["wavelength"])
    assert np.all(np.isfinite(flux)) and np.all(flux >= 0) and flux.max() > 0
    blue = flux[(lam > 3100) & (lam < 3500)].mean()
    red = flux[(lam > 8000) & (lam < 8500)].mean()
    assert blue > red                                        # steep blue continuum


@requires_wd_spectra_data
def test_contraction_rise_is_cspn_a_hot_wd_is_da():
    """On the post-AGB rise to the central-star spike, a 55–80 kK star is still
    contracting at LOW gravity (log g ~5–6 — measured ~74 kK/log g 5.6 for a 1 M☉
    progenitor); it routes to the WD cube (the MAIN cube's ceiling is 55 kK) and is
    labeled CSPN, NOT a cooling DA — so the scrub narrates the central-star phase
    coherently instead of flashing "no model" or calling a 74 kK star a white dwarf.
    The SAME Teff at WD gravity (a hot young cooling DA) stays DA — the regime reads
    the TRUE gravity, not just Teff."""
    rise = wd_spectrum_data(70000, 5.6)     # contracting central star (low g)
    hotwd = wd_spectrum_data(70000, 8.5)    # hot young white dwarf (high g)
    assert rise["regime"] == "CSPN"
    assert hotwd["regime"] == "DA"
    # both are real in-grid spectra (not no-model): the 55–80 kK band is fully covered
    assert rise["teff_requested"] <= rise["teff_max"]
    assert np.asarray(rise["flux"]).max() > 0


@requires_wd_spectra_data
def test_cspn_seam_is_continuous_across_the_koester_tmap_splice():
    """Koester (LTE, ≤80 kK) and TMAP (NLTE, ≥90 kK) are spliced at 80 kK with NO
    rescale because they already agree (~1% at the overlap). Measured through the
    runtime: the normalized continuum slope must march smoothly across the seam — no
    step from 80 kK (Koester) to 90 kK (TMAP), so the cooling scrub doesn't flicker."""
    def slope(teff):
        d = wd_spectrum_data(teff, 8.0)
        f = np.asarray(d["flux"]); f = f / f.max()
        lam = np.asarray(d["wavelength"])
        return f[(lam > 6900) & (lam < 7100)].mean() / f[(lam > 3900) & (lam < 4100)].mean()
    s70, s80, s90, s100 = (slope(t) for t in (70000, 80000, 90000, 100000))
    # monotone, tiny step-to-step change (measured ~0.001 across the seam)
    assert s70 > s80 > s90 > s100
    assert abs(s80 - s90) < 0.01            # the Koester→TMAP seam, no jump


@requires_wd_spectra_data
def test_cspn_optical_is_logg_insensitive_so_the_clamp_is_honest():
    """The cube's log g axis floors at 6.5 (Koester); the lowest-gravity central
    stars (log g ~5.4 for massive progenitors) clamp up to it. That's honest ONLY if
    the optical is log g-insensitive at CSPN temperatures — verify it here, and
    contrast with a cooling DA where log g visibly changes the Balmer profile (so the
    near-flatness below isn't a measurement artifact)."""
    def norm(teff, logg):
        d = wd_spectrum_data(teff, logg)
        f = np.asarray(d["flux"]); return f / f.max()
    lam = np.asarray(wd_spectrum_data(100000, 7.0)["wavelength"])
    opt = (lam > 3500) & (lam < 8500)
    hot_spread = np.abs(norm(100000, 6.5) - norm(100000, 9.5))[opt].max()
    da_spread = np.abs(norm(13000, 6.5) - norm(13000, 9.5))[opt].max()
    assert hot_spread < 0.10               # CSPN optical ~flat in log g (measured ~0.03)
    assert da_spread > 0.25                # cooling-DA Balmer profile DOES move (~0.41)


@requires_wd_spectra_data
def test_above_tmap_ceiling_reports_no_model():
    """The most massive WD progenitors' central stars peak above TMAP's 190000 K
    ceiling (a 5–6 M☉ progenitor reaches ~300–400 kK). There the response reports
    teff_requested > teff_max with teff pinned to teff_max — the residual no-model
    frame, now keyed off TMAP's ceiling (a much narrower gap than the old 80 kK one)."""
    d = wd_spectrum_data(330000, 7.0)
    assert d["teff_requested"] == pytest.approx(330000.0)
    assert d["teff_requested"] > d["teff_max"]
    assert d["teff"] == pytest.approx(d["teff_max"], abs=1.0)
    assert d["teff_max"] == pytest.approx(190000.0, abs=1.0)   # TMAP's NLTE ceiling
