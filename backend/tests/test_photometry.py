"""Axis A — the observer's view: synthetic photometry + reddening (`photometry.py`).

The load-bearing check is **Gate 0**: the absolute pipeline must anchor on an
*absolute* magnitude with the R/d scaling made explicit — a colour alone survives any
true-shape flux (the (R/d)² and absolute-flux scaling cancel), so a colour-only test
would pass even with a broken absolute pipeline. So the Sun (R=1 R☉, d=10 pc, A_V=0)
must land at **M_V ≈ 4.81** and the distance modulus must be *exactly* 10.000 over a
10 pc → 1 kpc move. B−V is the shape check (looser tolerance — the synthetic solar
B−V is a known ~0.04 blue of the observed 0.65 from a B-band zero-point convention).

Like the other siblings, `photometry.py` never routes through PROVIDER (a magnitude is
a *view*, not a StellarState) — asserted at the AST level.
"""

from __future__ import annotations

import ast

import numpy as np
import pytest
from fastapi.testclient import TestClient

from star_sim import photometry
from star_sim.api import app
from star_sim.spectra import spectrum_data

from .conftest import requires_spectra_data

client = TestClient(app)


def _sun_spectrum():
    d = spectrum_data(5772.0, 4.44, 0.0)
    return np.asarray(d["wavelength"]), np.asarray(d["flux"])


# --- Gate 0: the absolute anchor with teeth ---------------------------------

@requires_spectra_data
def test_gate0_solar_absolute_mv() -> None:
    """The Sun at 10 pc, no dust → M_V ≈ 4.81. This is the anchor that catches R/d
    units and zero-point errors (a colour would hide them)."""
    lam, flux = _sun_spectrum()
    p = photometry.photometry_point(lam, flux, radius_rsun=1.0, distance_pc=10.0, av=0.0)
    assert p["mv_abs"] == pytest.approx(4.81, abs=0.05)


@requires_spectra_data
def test_gate0_solar_color_shape() -> None:
    """B−V shape check — looser (±0.05) to absorb the known B-band Vega zero-point
    convention offset (SVO Bessell.B 3908.5 Jy vs literature ~4000–4060 → ~0.04 blue)."""
    lam, flux = _sun_spectrum()
    p = photometry.photometry_point(lam, flux, radius_rsun=1.0, distance_pc=10.0, av=0.0)
    assert p["bv0"] == pytest.approx(0.65, abs=0.05)


@requires_spectra_data
def test_distance_modulus_is_exact() -> None:
    """10 pc → 1000 pc dims every magnitude by exactly μ = 5·log₁₀(100) = 10.000 —
    pure arithmetic, isolating the distance path from all atmosphere physics."""
    lam, flux = _sun_spectrum()
    near = photometry.photometry_point(lam, flux, 1.0, distance_pc=10.0, av=0.0)
    far = photometry.photometry_point(lam, flux, 1.0, distance_pc=1000.0, av=0.0)
    assert far["distance_modulus"] == pytest.approx(10.0, abs=1e-9)
    # apparent V dims by exactly the modulus; absolute V is unchanged by distance.
    assert far["mv_app"] - near["mv_app"] == pytest.approx(10.0, abs=1e-6)
    assert far["mv_abs"] == pytest.approx(near["mv_abs"], abs=1e-9)


@requires_spectra_data
def test_reddening_reddens_and_dims() -> None:
    """A_V = 1 (R_V = 3.1) reddens B−V by ~E(B−V)=A_V/R_V≈0.32 (band-integrated a hair
    lower, ~0.30) and dims V. A_V = 0 leaves the colour intrinsic (E(B−V)=0)."""
    lam, flux = _sun_spectrum()
    clean = photometry.photometry_point(lam, flux, 1.0, distance_pc=10.0, av=0.0)
    red = photometry.photometry_point(lam, flux, 1.0, distance_pc=10.0, av=1.0, rv=3.1)
    assert clean["ebv"] == pytest.approx(0.0, abs=1e-9)
    assert red["ebv"] == pytest.approx(0.30, abs=0.05)      # source-dependent, < 0.322
    assert red["bv_obs"] > clean["bv0"]                     # reddened
    assert red["mv_app"] > clean["mv_abs"]                  # dimmed by extinction


@requires_spectra_data
def test_hotter_star_is_bluer() -> None:
    """A hot star has a smaller (bluer) B−V than the Sun — the CMD's whole point."""
    lam, sun = _sun_spectrum()
    d_hot = spectrum_data(15000.0, 4.0, 0.0)
    hot = np.asarray(d_hot["flux"])
    bv_sun = photometry.photometry_point(lam, sun, 1.0)["bv0"]
    bv_hot = photometry.photometry_point(lam, hot, 1.0)["bv0"]
    assert bv_hot < bv_sun


@requires_spectra_data
def test_vectorized_stack_matches_scalar() -> None:
    """The vectorized core (A3 draws a whole track/isochrone through it) agrees with the
    single-star path and is order-independent."""
    lam, flux = _sun_spectrum()
    stack = np.vstack([flux, flux, flux])
    mags = photometry.band_mags_stack(lam, stack, np.array([1.0, 1.0, 1.0]), 10.0, 0.0, 3.1)
    scalar = photometry.photometry_point(lam, flux, 1.0)["absolute_mag"]["V"]
    assert np.allclose(mags["V"], scalar, atol=1e-9)


# --- reddening law is monotone in A_V (no dependence on the cube) -------------

def test_ccm89_shape() -> None:
    """CCM89 A(λ)/A(V) is ~1 at V (5500 Å) and larger in the blue (a redder star is a
    star with MORE blue light removed)."""
    a = photometry.ccm89(np.array([5500.0, 4400.0, 3600.0]), rv=3.1)
    assert a[0] == pytest.approx(1.0, abs=0.05)   # A(V)/A(V) ≈ 1 by construction
    assert a[1] > a[0] and a[2] > a[1]            # bluer → more extinction


# --- route shape --------------------------------------------------------------

@requires_spectra_data
def test_photometry_route_ok() -> None:
    r = client.get("/photometry", params=dict(
        teff=5772, logg=4.44, feh=0.0, radius_rsun=1.0, distance_pc=10.0, av=0.0))
    assert r.status_code == 200
    j = r.json()
    assert j["mv_abs"] == pytest.approx(4.81, abs=0.05)
    assert set(j["bands"]) == {"B", "V", "BP"}
    assert "absolute_mag" in j and "apparent_mag" in j
    assert j["grid_name"]


def test_photometry_route_422_on_bad_radius() -> None:
    """A non-positive radius is structurally invalid (422, not a silent snap)."""
    assert client.get("/photometry", params=dict(
        teff=5772, logg=4.44, radius_rsun=0.0)).status_code == 422
    assert client.get("/photometry", params=dict(
        teff=5772, logg=4.44)).status_code == 422   # radius is required


# --- A3: the observational-CMD locus (/photometry_track) ----------------------

@requires_spectra_data
def test_photometry_track_shape_and_decimation() -> None:
    """The whole-track locus: (B−V)₀ + M_V per state, decimated to <= n_max. The CMD's
    whole point — a solar track must span from a bluer, fainter ZAMS to a redder, brighter
    giant tip (bluer ZAMS, larger M_V number = fainter) — is asserted through the runtime."""
    r = client.get("/photometry_track", params=dict(mass=1.0, feh=0.0, n_max=60))
    assert r.status_code == 200
    j = r.json()
    assert j["has_bv"] is True
    assert set(j["bands"]) == {"B", "V", "BP"}
    pts = j["points"]
    assert 0 < len(pts) <= 60                       # decimated
    zams, tip = pts[0], pts[-1]
    assert zams["bv0"] < tip["bv0"]                 # giant tip is REDDER than the ZAMS
    assert tip["mv"] < zams["mv"]                    # and BRIGHTER (smaller magnitude number)
    for p in pts:                                    # every row is a real, finite CMD point
        assert p["bv0"] == p["bv0"] and p["mv"] == p["mv"]


@requires_spectra_data
def test_photometry_track_matches_point_at_zams() -> None:
    """The locus and the single-star /photometry share one physics: the ZAMS locus point's
    colour/magnitude agree with photometry_point on the same state (no drift between the
    backdrop the panel draws and the exact marker it overlays)."""
    from star_sim.api import PROVIDER
    st0 = PROVIDER.track(1.0, 0.0, 0.0)[0]
    lam, flux = np.asarray(spectrum_data(st0.Teff_K, st0.logg, st0.feh_init)["wavelength"]), \
        np.asarray(spectrum_data(st0.Teff_K, st0.logg, st0.feh_init)["flux"])
    p = photometry.photometry_point(lam, flux, st0.R_rsun)
    j = client.get("/photometry_track", params=dict(mass=1.0, feh=0.0, n_max=606)).json()
    assert j["points"][0]["mv"] == pytest.approx(p["mv_abs"], abs=1e-6)
    assert j["points"][0]["bv0"] == pytest.approx(p["bv0"], abs=1e-6)


def test_photometry_track_422_on_bad_mass() -> None:
    """A mass off the provider grid is 422 (routing error), not a silent snap or crash."""
    assert client.get("/photometry_track", params=dict(mass=99999.0, feh=0.0)).status_code == 422


# --- the §3 boundary: the sibling never routes through PROVIDER ----------------

def test_sibling_does_not_import_provider() -> None:
    """photometry.py is a pure numpy/stdlib sibling (an apparent magnitude is a view,
    not a StellarState) — no provider, and not even StellarState. Asserted at the AST
    level like bpass/spectra/isochrone."""
    with open(photometry.__file__, "r", encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    imported = {
        (node.module or "")
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    assert "api" not in imported and "star_sim.api" not in imported
    assert not any("provider" == m.rsplit(".", 1)[-1] for m in imported)
    assert not any("state" == m.rsplit(".", 1)[-1] for m in imported)
