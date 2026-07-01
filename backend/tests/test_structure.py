"""Validation for the real interior-structure sibling (`structure.py`, `/structure`).

This is the honest successor to the Lane-Emden panel: `structure.py` serves a *real*
MESA radial profile — ρ(r), T(r), P(r), composition(r), and the true convective
boundaries — so the anchors here are the physics that must hold for a 1 M☉ solar-Z
main-sequence star, cross-checked against textbook interior-structure numbers.

Crucially the tolerances are LOOSE. The generating run (see mesa_structure_recipe.md)
is deliberately *not* a calibrated standard solar model (no α_MLT/Y tuning to force
L=1/R=1 at 4.6 Gyr — same stance as the MESA history bucket, see mesa_solar_recipe.md).
So exact SSM numbers (ρ_c≈150, base of convection zone 0.713 R☉) will NOT land on the
nose; we gate on structure that must be true regardless of calibration:

  * a convective envelope exists in the outer radius fraction (the one thing the
    polytrope genuinely can't fake — the panel's reason to exist),
  * a radiative core (so the canonical overlay is n=3, the Eddington standard model),
  * monotone, hugely centrally-concentrated density (ρ_c/ρ_surf ≳ 10^6),
  * ρ_c within a factor of the standard ~150 g/cm³, T_c of order 1.5×10⁷ K.

Data-gated by `requires_structure_data` — skips on a checkout without the offline
MESA profiles (they're never committed; generate them per the recipe).
"""

from __future__ import annotations

import numpy as np
import pytest
from fastapi.testclient import TestClient

from star_sim.api import app
from star_sim.structure import interior_structure

from .conftest import requires_structure_data

client = TestClient(app)

pytestmark = requires_structure_data


# --- the core physics anchor -------------------------------------------------

@requires_structure_data
def test_solar_snapshot_has_convective_envelope_over_radiative_core():
    """The 1 M☉ solar structure is the textbook case: a radiative core with a
    convective envelope. The envelope base sits in the outer half of the star
    (SSM ≈ 0.71 R☉; loose here because the run is not solar-calibrated), and it
    reaches the surface. This is the feature the polytrope cannot represent."""
    s = interior_structure(1.0, 0.0, 4.6e9)

    zones = s["convective_zones"]
    assert zones, "a 1 M☉ star must have a convective envelope"
    # the outermost convective zone should reach the surface (r/R ~ 1)...
    outer = max(zones, key=lambda z: z[1])
    assert outer[1] > 0.99, f"convective envelope should reach the surface, got {outer}"
    # ...and its base should be in the outer half (radiative interior below it).
    assert 0.5 < outer[0] < 0.95, f"envelope base out of physical range: {outer[0]}"

    # innermost zone radiative -> the canonical overlay is n=3 (Eddington model).
    assert s["convective"][0] is False, "the core of a 1 M☉ MS star is radiative"
    assert s["expected_n"] == 3.0


@requires_structure_data
def test_central_values_of_order_the_standard_solar_model():
    """Absolute central density/temperature within a factor of the SSM values
    (~150 g/cm³, ~1.5×10⁷ K). Not exact — the run isn't solar-calibrated — but a
    parser/units bug (log vs linear, wrong column) would blow these out by orders
    of magnitude, so an order-of-magnitude gate is a real check."""
    s = interior_structure(1.0, 0.0, 4.6e9)
    c = s["central"]
    assert 50.0 < c["rho_c_gcc"] < 500.0, c["rho_c_gcc"]
    assert 1.0e7 < c["T_c_K"] < 3.0e7, c["T_c_K"]
    assert 0.5 < c["R_surface_rsun"] < 2.0, c["R_surface_rsun"]
    assert abs(c["M_total_msun"] - 1.0) < 0.05, c["M_total_msun"]


@requires_structure_data
def test_density_is_monotone_and_centrally_concentrated():
    """ρ(r) falls monotonically from centre to surface and spans ≳ 6 decades — the
    §8 central-concentration payoff. rho_over_rhoc is normalized so it starts at 1.0."""
    s = interior_structure(1.0, 0.0, 4.6e9)
    rho = np.array(s["rho_over_rhoc"])
    assert rho[0] == pytest.approx(1.0, abs=1e-9), "centre is normalized to ρ/ρ_c = 1"
    # non-increasing outward (allow a hair of numerical noise).
    assert np.all(np.diff(rho) <= 1e-9), "density must not increase outward"
    assert rho[-1] < 1e-5, f"surface/centre density ratio too large: {rho[-1]}"


@requires_structure_data
def test_radius_fraction_monotone_and_spans_unit_interval():
    """r/R runs 0 (centre) → 1 (surface), monotone increasing — the abscissa the
    polytrope overlay is compared against."""
    s = interior_structure(1.0, 0.0, 4.6e9)
    x = np.array(s["r_over_R"])
    assert x[0] == pytest.approx(0.0, abs=1e-3)
    assert x[-1] == pytest.approx(1.0, abs=1e-9)
    assert np.all(np.diff(x) >= -1e-9), "r/R must be non-decreasing centre→surface"


# --- the polytrope overlay (canonical, not fitted) ---------------------------

@requires_structure_data
def test_polytrope_overlays_are_canonical_and_bracket_the_profile():
    """The overlay returns the two CANONICAL polytropes (n=1.5, n=3) — never a best
    fit. Each is a valid (r/R, ρ/ρ_c) curve on [0,1]. The higher-n polytrope (n=3) is
    more centrally concentrated, so at mid-radius its ρ/ρ_c is below n=1.5 — the very
    'central concentration' contrast §8 exists to show."""
    s = interior_structure(1.0, 0.0, 4.6e9)
    polys = {p["n"]: p for p in s["polytropes"]}
    assert set(polys) == {1.5, 3.0}
    for p in polys.values():
        x = np.array(p["r_over_R"])
        rho = np.array(p["rho_over_rhoc"])
        assert x[0] == pytest.approx(0.0) and x[-1] == pytest.approx(1.0, abs=1e-6)
        assert rho[0] == pytest.approx(1.0, abs=1e-6)
        assert np.all(np.diff(rho) <= 1e-9)  # monotone

    # n=3 is more centrally concentrated than n=1.5 at the same r/R (mid-star).
    def rho_at(p, frac):
        return float(np.interp(frac, p["r_over_R"], p["rho_over_rhoc"]))

    assert rho_at(polys[3.0], 0.5) < rho_at(polys[1.5], 0.5)


# --- honest snapping ---------------------------------------------------------

@requires_structure_data
def test_snaps_to_nearest_saved_age_and_reports_true_values():
    """The request age is SNAPPED to the nearest saved snapshot (no interpolation
    across profiles). Two nearby request ages that fall closest to the same saved
    snapshot must return byte-identical structure — the honest 'nearest snapshot'
    contract the panel labels."""
    ages = interior_structure(1.0, 0.0, 4.6e9)["available_ages_yr"]
    assert len(ages) >= 3, "need a handful of snapshots for a usable slider"
    target = ages[len(ages) // 2]

    a = interior_structure(1.0, 0.0, target * 0.98)
    b = interior_structure(1.0, 0.0, target * 1.02)
    assert a["snapped"]["age_yr"] == b["snapped"]["age_yr"] == target
    assert a["central"]["rho_c_gcc"] == b["central"]["rho_c_gcc"]


@requires_structure_data
def test_out_of_grid_mass_snaps_not_extrapolates():
    """A far-off-grid mass snaps to the nearest available run and reports that run's
    TRUE mass — never a silently extrapolated value (§3/§6 honesty). With only the
    1 M☉ slice on disk, any mass returns the 1 M☉ structure, honestly labeled."""
    s = interior_structure(7.3, 0.0, 1.0e8)
    assert s["snapped"]["mass_msun"] == 1.0


# --- the route ---------------------------------------------------------------

@requires_structure_data
def test_route_returns_structure_payload():
    r = client.get("/structure", params={"mass": 1.0, "feh": 0.0, "age": 4.6e9})
    assert r.status_code == 200
    body = r.json()
    for key in ("r_over_R", "rho_over_rhoc", "T_over_Tc", "P_over_Pc",
                "convective_zones", "polytropes", "snapped", "central"):
        assert key in body, f"missing {key}"
    assert len(body["r_over_R"]) == len(body["rho_over_rhoc"]) > 100


@requires_structure_data
def test_route_rejects_nonsense_params():
    """Query bounds: mass and age must be positive (mirrors /polytrope's 422s)."""
    assert client.get("/structure", params={"mass": -1, "age": 1e9}).status_code == 422
    assert client.get("/structure", params={"mass": 1.0, "age": 0}).status_code == 422
