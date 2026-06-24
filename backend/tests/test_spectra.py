"""§10 sanity checks for the Phase 5 spectrum panel.

Two layers, like the MIST/MESA tests:

* Always-on (no baked grid needed): the `/spectrum` route's contract — generous
  `Query` bounds reject absurd inputs with 422, and a missing baked grid surfaces
  a clean 503 (not a 500). These pin the API surface a fresh checkout still has.

* Data-gated (`requires_spectra_data`): the physics. The line-depth anchors are
  **measured through the runtime path** — `spectrum_data()` → RGI interpolation on
  the baked cube — at non-grid test temperatures, NOT copied from the recipe's
  raw-pymsg numbers (interpolation at a non-node star differs by a few %). We pin
  the robust spectral-sequence ORDERINGS (Balmer peaks at A; Ca II K strong cool,
  gone hot) with margin — the same "measure, don't assume tolerances" discipline
  as the MESA-vs-MIST cross-validation.
"""

from __future__ import annotations

import numpy as np
import pytest
from fastapi.testclient import TestClient

from star_sim import spectra
from star_sim.api import app
from star_sim.spectra import SpectraDataMissing, spectrum_data

from .conftest import requires_spectra_data

client = TestClient(app)

# Principal lines (Å). Balmer Hα/Hβ peak at A stars; Ca II K and Na D are strong
# in cool stars (Ca K vanishes when hot; Na D deepens with metallicity). He II 4686
# / He I 4471 are the defining O-star features the OSTAR2002 splice unlocks (>30000 K).
HA, HB, CA_K, NA_D = 6563.0, 4861.0, 3933.0, 5893.0
HE2_4686, HE1_4471 = 4686.0, 4471.0


def _line_depth(d: dict, center: float, core_hw: float = 5.0,
                cont_lo: float = 20.0, cont_hi: float = 45.0) -> float:
    """Fractional absorption depth at `center`, measured on a served spectrum:
    1 - (line core) / (local continuum). The core is the MIN flux within ±core_hw
    of the line (robust to the line not landing on a bin centre); the continuum is
    the mean over windows offset to the blue and red."""
    lam = np.asarray(d["wavelength"])
    flux = np.asarray(d["flux"])
    core = flux[(lam > center - core_hw) & (lam < center + core_hw)].min()
    blue = flux[(lam > center - cont_hi) & (lam < center - cont_lo)]
    red = flux[(lam > center + cont_lo) & (lam < center + cont_hi)]
    cont = np.concatenate([blue, red]).mean()
    return 1.0 - core / cont


# --- always-on: the route contract (no baked grid required) ------------------

@pytest.mark.parametrize("params", [
    {"teff": 500, "logg": 4.0},        # Teff below any real star
    {"teff": 500000, "logg": 4.0},     # Teff above any real star
    {"teff": 5772, "logg": 12.0},      # log g absurd
    {"teff": 5772, "logg": 4.0, "feh": 9.0},  # [Fe/H] absurd
    {"logg": 4.0},                     # missing required teff
    {"teff": 5772},                    # missing required logg
])
def test_spectrum_out_of_range_is_422(params):
    assert client.get("/spectrum", params=params).status_code == 422


def test_spectrum_hot_star_does_not_422_and_clamps():
    """A massive O star reaches ~80000 K — still above even the OSTAR2002-spliced
    grid's 55000 K ceiling (CAP18 alone stopped at 30000 K; the splice extends the
    hot end to 55000 K). The bounds must be wide enough that dragging there never
    422s; the hot end clamps to the grid max, symmetric with the cool floor (so the
    panel never silently freezes on a hot star). Always-on: never a 422 (200 if
    baked, 503 if not)."""
    r = client.get("/spectrum", params={"teff": 80000, "logg": 4.0})
    assert r.status_code in (200, 503)


def test_spectrum_not_baked_is_503(tmp_path, monkeypatch):
    """If the grid hasn't been baked, /spectrum returns a clean 503 (actionable),
    not a 500 — the app stays up; only the spectrum panel is unavailable."""
    monkeypatch.setattr(spectra, "SPECTRA_DATA_DIR", tmp_path)  # empty dir
    monkeypatch.setattr(spectra, "_CACHE", None)                # force a reload
    r = client.get("/spectrum", params={"teff": 5772, "logg": 4.44})
    assert r.status_code == 503
    assert "bake" in r.json()["detail"].lower()


def test_spectrum_data_raises_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(spectra, "SPECTRA_DATA_DIR", tmp_path)
    monkeypatch.setattr(spectra, "_CACHE", None)
    with pytest.raises(SpectraDataMissing):
        spectrum_data(5772, 4.44, 0.0)


# --- data-gated: the spectrum is well-formed ---------------------------------

@requires_spectra_data
def test_spectrum_endpoint_well_formed():
    r = client.get("/spectrum", params={"teff": 9500, "logg": 4.0, "feh": 0.0})
    assert r.status_code == 200
    d = r.json()
    lam = np.asarray(d["wavelength"]); flux = np.asarray(d["flux"])
    assert lam.size == flux.size > 100
    assert np.all(np.diff(lam) > 0)               # wavelengths strictly increasing
    assert np.all(np.isfinite(flux))
    assert np.all(flux >= 0)
    assert flux.max() > 0                          # not an all-zero spectrum


@requires_spectra_data
def test_cool_params_clamp_to_grid_floor():
    """A star below the grid's Teff floor shows the floor spectrum (the used Teff
    is reported honestly, never a silent extrapolation)."""
    d = spectrum_data(2500, 5.2, 0.0)             # below the 3500 K grid floor
    assert d["teff"] == pytest.approx(3500.0, abs=1.0)
    assert np.all(np.asarray(d["flux"]) >= 0)


@requires_spectra_data
def test_void_region_query_is_filled():
    """A hot + low-gravity point sits in a grid void (OSTAR has no log g < 3.5
    model at 40000 K); the void-filled bake means the runtime still returns a
    finite, positive spectrum (no LookupError leaks)."""
    d = spectrum_data(40000, 0.5, 0.0)
    flux = np.asarray(d["flux"])
    assert np.all(np.isfinite(flux)) and np.all(flux >= 0) and flux.max() > 0


# --- data-gated: the line physics (measured through the runtime path) ---------

@requires_spectra_data
def test_balmer_lines_peak_at_a_stars():
    """Hydrogen Balmer absorption (Hα, Hβ) is deepest around A stars (~9500 K) and
    shallower in both the cooler Sun and a hot star — the classic spectral sequence,
    measured here on the baked+interpolated spectra. The hot query (40000 K) is now a
    real OSTAR2002 sample (post-splice; it used to clamp to CAP18's 30000 K ceiling),
    where Balmer is well past its peak, so the ordering holds."""
    a = spectrum_data(9500, 4.0, 0.0)
    sun = spectrum_data(5772, 4.44, 0.0)
    hot = spectrum_data(40000, 4.5, 0.0)           # a real OSTAR O-star spectrum now

    for line in (HA, HB):
        d_a = _line_depth(a, line)
        d_sun = _line_depth(sun, line)
        d_hot = _line_depth(hot, line)
        assert d_a > 0.2                           # a real, deep line at A (~0.5–0.7)
        assert d_a > d_sun + 0.1                    # deeper than the Sun, with margin
        assert d_a > d_hot + 0.1                     # deeper than the hot star


@requires_spectra_data
def test_ca_k_strong_in_cool_stars_gone_when_hot():
    """Ca II K (3933 Å) is one of the deepest features in a cool-star spectrum and
    essentially absent in hot stars (Ca is too ionized)."""
    sun = spectrum_data(5772, 4.44, 0.0)
    a = spectrum_data(9500, 4.0, 0.0)
    hot = spectrum_data(40000, 4.5, 0.0)           # a real OSTAR O-star spectrum now

    d_sun = _line_depth(sun, CA_K)
    d_a = _line_depth(a, CA_K)
    d_hot = _line_depth(hot, CA_K)
    assert d_sun > 0.3                              # deep in the Sun (~0.8)
    assert d_sun > d_a + 0.2                        # far deeper than at A
    assert d_sun > d_hot + 0.2                       # far deeper than in the hot star (Ca ionized)


@requires_spectra_data
def test_solar_grid_ignores_feh():
    """On a solar-only grid the [Fe/H] argument changes nothing and the response
    says so (feh_varies=False) — the panel labels it honestly rather than faking a
    metallicity response. The complement is test_feh_axis_deepens_metal_lines; one
    of the two runs depending on which cube is baked (solar sg-demo vs 3-D CAP18),
    and the suite stays green either way."""
    d0 = spectrum_data(5772, 4.44, 0.0)
    d1 = spectrum_data(5772, 4.44, -0.5)
    if not d0["feh_varies"]:
        assert d0["flux"] == d1["flux"]


@requires_spectra_data
def test_feh_axis_deepens_metal_lines():
    """The CAP18 swap's payoff (the whole point of a 3-D grid): at a fixed COOL Teff,
    raising [Fe/H] deepens the METAL lines (Na D, Ca II K — more metals, more
    absorption), while the hydrogen Balmer lines barely move.

    Balmer is the CONTROL: it is set by temperature/density and is ~insensitive to
    metallicity, so its near-constancy proves the [Fe/H] axis carves *real metal
    features* rather than globally rescaling the spectrum (which a weaker "the flux
    array changed" assertion would not catch). Measured through the runtime path
    with margin, in the same spirit as the spectral-sequence tests.

    Self-skips on a solar-only grid (feh_varies=False) — the mirror of
    test_solar_grid_ignores_feh."""
    poor = spectrum_data(5000, 4.5, -1.0)          # metal-poor
    rich = spectrum_data(5000, 4.5, +0.5)          # metal-rich (the grid's [Fe/H] max)
    if not poor["feh_varies"]:
        pytest.skip("solar-only grid has no [Fe/H] axis")

    # Na D swings strongly with metallicity (measured ~+0.24 on the CAP18 cube); Ca
    # II K is already near-saturated at 5000 K so it deepens more modestly (~+0.05)
    # but unambiguously. Both are well clear of their margins.
    na_swing = _line_depth(rich, NA_D) - _line_depth(poor, NA_D)
    assert na_swing > 0.1
    assert _line_depth(rich, CA_K) > _line_depth(poor, CA_K) + 0.02

    # The control: Balmer barely moves (|Δ| measured ≤0.055) AND moves far less than
    # Na D — the contrast, not the absolute, is the metallicity signal.
    for line in (HA, HB):
        balmer_shift = abs(_line_depth(rich, line) - _line_depth(poor, line))
        assert balmer_shift < 0.12
        assert balmer_shift < na_swing


@requires_spectra_data
def test_hot_grid_extends_above_30000_with_helium():
    """The OSTAR2002 splice's payoff (the analogue of test_feh_axis_deepens_metal_lines):
    above CAP18's old 30000 K ceiling the panel now shows *real O-star spectra* — and
    the defining O-star feature is He II 4686 Å absorption (singly-ionized helium needs
    the hottest stars). Measured through the runtime path:

      1. A 45000 K query returns a 45000 K spectrum, NOT the old 30000 K clamp — the
         splice genuinely extended the Teff axis (used teff == 45000, and the He II
         line is far deeper than at the seam).
      2. He II 4686 deepens monotonically into the hot regime (30000 -> 45000 K,
         measured Δ ~0.13), and is a hot-star-only line: far deeper than in the Sun
         (where it is essentially a weak metal blend, ~0.06).

    He I 4471 (which *peaks* near mid-O and weakens at the hottest as He doubly ionizes)
    is the complement; we pin the cleaner, monotonic He II line here."""
    hot = spectrum_data(45000, 4.0, 0.0)
    assert hot["teff"] == pytest.approx(45000.0, abs=1.0)   # a real sample, not clamped to 30000

    d_seam = _line_depth(spectrum_data(30000, 4.0, 0.0), HE2_4686)
    d_hot = _line_depth(hot, HE2_4686)
    d_sun = _line_depth(spectrum_data(5772, 4.44, 0.0), HE2_4686)

    assert d_hot > 0.1                  # a real, deep He II line in the O star (~0.15)
    assert d_hot > d_seam + 0.05         # deepens into the hot extension (measured Δ ~0.13)
    assert d_hot > d_sun + 0.05          # a hot-star-only line, far deeper than the Sun

    # And He I 4471 is present (not a flat continuum) in a mid-O star — the splice
    # carved real helium features, not just a bluer blackbody.
    assert _line_depth(spectrum_data(35000, 4.0, 0.0), HE1_4471) > 0.08
