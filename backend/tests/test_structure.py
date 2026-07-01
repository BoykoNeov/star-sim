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
from star_sim.structure import _INDEX, interior_structure

from .conftest import requires_structure_data, requires_structure_massive

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
    TRUE mass — never a silently extrapolated value (§3/§6 honesty). The snapped mass
    is whatever slice is closest and on disk (1 M☉ alone, or the nearest of the
    1/2/6 M☉ grid), and it is always one of the *saved* masses, never an interpolant."""
    s = interior_structure(0.3, 0.0, 1.0e8)          # far below the grid floor
    masses = {m.mass_init for m in _INDEX.available()}
    assert s["snapped"]["mass_msun"] in masses
    assert s["snapped"]["mass_msun"] == min(masses)   # snaps to the lightest saved run


# --- the convective-core <-> radiative-envelope flip (the 2/6 M☉ slice) -------

def _conv_at(zones, frac):
    """True if radius fraction `frac` falls inside a convective zone."""
    return any(a <= frac <= b for a, b in zones)


@requires_structure_massive
def test_massive_star_flips_to_convective_core_radiative_envelope():
    """The whole point of the 2/6 M☉ slice: an intermediate-mass MS star is the
    *mirror* of the Sun — a **convective core** (CNO burning is fiercely
    temperature-sensitive) under a **radiative envelope**. So at mid-MS the flip
    must show on the served data:

      * the innermost zone is convective  -> the canonical overlay is n=3/2,
      * a convective zone is anchored at the centre and is a sizeable fraction of R,
      * the envelope is radiative: no *deep* convective envelope like the Sun's
        (a razor-thin sub-surface convection sliver is allowed, but the bulk of the
        outer star at r/R≈0.9 must be radiative — the opposite of the 1 M☉ case).

    Uses the mid-MS 6 M☉ snapshot (Xc≈0.4), where a massive-star convective core is
    at its healthiest — it shrinks toward TAMS (see mesa_structure_recipe.md §6)."""
    s = interior_structure(6.0, 0.0, 3.4e7)
    assert s["snapped"]["mass_msun"] == 6.0

    # core convective -> n=3/2 (fully-mixed adiabatic core), the flipped overlay hint.
    assert s["convective"][0] is True, "a 6 M☉ MS star has a convective core"
    assert s["expected_n"] == 1.5

    zones = s["convective_zones"]
    core = [z for z in zones if z[0] < 0.02]
    assert core, f"expected a convective core anchored at r/R~0, got {zones}"
    assert core[0][1] > 0.05, f"convective core should be a sizeable fraction of R: {core}"

    # radiative envelope: r/R=0.9 must be radiative (the Sun is convective there).
    assert not _conv_at(zones, 0.9), f"6 M☉ envelope should be radiative at r/R=0.9: {zones}"


@requires_structure_massive
def test_flip_is_the_mirror_of_the_solar_case():
    """Directly contrast the 6 M☉ flip against the 1 M☉ Sun on the SAME two probe
    radii — the pedagogy the slice exists to teach, locked as a regression:

        core (r/R≈0)      envelope (r/R≈0.9)
      Sun (1 M☉):  radiative           convective
      6 M☉      :  convective          radiative      <- mirrored
    """
    sun = interior_structure(1.0, 0.0, 4.6e9)
    massive = interior_structure(6.0, 0.0, 3.4e7)

    assert sun["convective"][0] is False and massive["convective"][0] is True
    assert sun["expected_n"] == 3.0 and massive["expected_n"] == 1.5
    assert _conv_at(sun["convective_zones"], 0.9) is True       # Sun: deep convective envelope
    assert _conv_at(massive["convective_zones"], 0.9) is False  # 6 M☉: radiative envelope


@requires_structure_massive
def test_intermediate_mass_also_has_a_convective_core():
    """The 2 M☉ slice sits at the low-mass end of the convective-core regime (just
    above the ~1.1 M☉ onset) — it too has a convective core under a radiative
    envelope, a milder version of the 6 M☉ flip. Guards the whole 1/2/6 progression."""
    s = interior_structure(2.0, 0.0, 5.0e8)
    assert s["snapped"]["mass_msun"] == 2.0
    assert s["convective"][0] is True
    assert s["expected_n"] == 1.5
    assert not _conv_at(s["convective_zones"], 0.9), "2 M☉ envelope should be radiative at r/R=0.9"


@requires_structure_massive
def test_massive_15msun_has_the_deepest_convective_core():
    """The 15 M☉ slice — the SN arc's *canonical* progenitor mass — is the most
    extreme convective-core case, and it makes the structure panel honest exactly
    where the core-collapse feature lives (a 15 M☉ progenitor no longer snaps to the
    6 M☉ run). Same flip as 6 M☉ but bigger: a hot, low-density CNO-burning core
    (ε ∝ T^~17) drives a convective core reaching a *larger* fraction of R than the
    6 M☉ core (~0.13), still under a radiative envelope.

    Uses the mid-MS 15 M☉ snapshot (Xc≈0.41) — a massive-star convective core recedes
    fastest here, so the shipped slice deliberately anchors mid-MS (recipe §6)."""
    s = interior_structure(15.0, 0.0, 6.8e6)
    assert s["snapped"]["mass_msun"] == 15.0

    # core convective -> n=3/2, the flipped overlay hint (mirror of the Sun).
    assert s["convective"][0] is True, "a 15 M☉ MS star has a convective core"
    assert s["expected_n"] == 1.5

    zones = s["convective_zones"]
    core = [z for z in zones if z[0] < 0.02]
    assert core, f"expected a convective core anchored at r/R~0, got {zones}"
    # the 15 M☉ core is a larger fraction of R than the 6 M☉ core (~0.13, measured ~0.18).
    assert core[0][1] > 0.15, f"15 M☉ convective core should be the deepest: {core}"

    # radiative envelope: r/R=0.9 must be radiative (the Sun is convective there).
    assert not _conv_at(zones, 0.9), f"15 M☉ envelope should be radiative at r/R=0.9: {zones}"

    # central values of the right order for a hot massive-star core — hotter and less
    # dense than the 6 M☉ core (CNO burning at higher T, lower ρ). A parser/units bug
    # would blow these out by orders of magnitude.
    c = s["central"]
    assert 2.0e7 < c["T_c_K"] < 5.0e7, c["T_c_K"]
    assert abs(c["M_total_msun"] - 15.0) < 0.1, c["M_total_msun"]


@requires_structure_massive
def test_massive_25msun_brackets_the_upper_sn_range():
    """The 25 M☉ slice brackets the *upper* end of the core-collapse SN progenitor
    range (the arc is anchored at 15 M☉; heavier progenitors extend past it). It is
    the deepest convective core of the whole 1→2→6→15→25 ladder: a hotter, even
    lower-density CNO-burning core drives a convective core reaching a *larger*
    fraction of R than the 15 M☉ core (~0.18, measured ~0.23), still under a
    radiative envelope.

    Uses the mid-MS 25 M☉ snapshot (Xc≈0.46) — a massive-star convective core recedes
    fastest here, so the shipped slice deliberately anchors mid-MS (recipe §6/§8)."""
    s = interior_structure(25.0, 0.0, 3.2e6)
    assert s["snapped"]["mass_msun"] == 25.0

    # core convective -> n=3/2, the flipped overlay hint (mirror of the Sun).
    assert s["convective"][0] is True, "a 25 M☉ MS star has a convective core"
    assert s["expected_n"] == 1.5

    zones = s["convective_zones"]
    core = [z for z in zones if z[0] < 0.02]
    assert core, f"expected a convective core anchored at r/R~0, got {zones}"
    # the 25 M☉ core is the deepest of the ladder — larger than the 15 M☉ core
    # (~0.18, measured ~0.23).
    assert core[0][1] > 0.20, f"25 M☉ convective core should be the deepest: {core}"

    # radiative envelope: r/R=0.9 must be radiative (the Sun is convective there).
    assert not _conv_at(zones, 0.9), f"25 M☉ envelope should be radiative at r/R=0.9: {zones}"

    # central values of the right order for the hottest massive-star core of the set —
    # hotter and less dense than the 15 M☉ core (CNO burning at higher T, lower ρ).
    c = s["central"]
    assert 2.5e7 < c["T_c_K"] < 5.0e7, c["T_c_K"]
    assert abs(c["M_total_msun"] - 25.0) < 0.1, c["M_total_msun"]


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
