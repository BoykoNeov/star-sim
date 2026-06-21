"""Validation for the Lane-Emden polytrope solver (STAR_SIM_SPEC.md §8, §10).

These need no MIST grids — Lane-Emden is a self-contained ODE, a sibling to the
StellarState spine — so they always run (no skip markers).

Two tiers, per the spec and on purpose:

* **Closed forms (bedrock).** n = 0, 1, 5 have exact analytic solutions. We check
  θ(ξ) *pointwise across the whole domain*, plus ξ₁ AND the second invariant
  −ξ₁²θ'(ξ₁). A subtly wrong profile can still land ξ₁; the pointwise + 2nd-invariant
  checks are what actually gate the integrator.
* **Chandrasekhar table (secondary cross-check).** n = 1.5, 2, 3, 4 from
  Chandrasekhar, *An Introduction to the Study of Stellar Structure* (1939), Table 4.
  Looser tolerance and recited from a table, so if one of these fails while every
  closed form passes, suspect a mistyped digit here, not the code.
"""

from __future__ import annotations

import math

import numpy as np
import pytest
from fastapi.testclient import TestClient

from star_sim.api import app
from star_sim.lane_emden import polytrope_profile, solve_lane_emden


# --- closed forms (exact) ----------------------------------------------------

def _theta_exact(n: float, xi: np.ndarray) -> np.ndarray:
    """The three analytic Lane-Emden solutions."""
    if n == 0:
        return 1.0 - xi**2 / 6.0
    if n == 1:
        # sin ξ / ξ, with the ξ→0 limit handled.
        return np.where(xi == 0.0, 1.0, np.sin(xi) / np.where(xi == 0.0, 1.0, xi))
    if n == 5:
        return (1.0 + xi**2 / 3.0) ** -0.5
    raise ValueError(f"no closed form wired for n={n}")


def test_n0_closed_form():
    """n=0: θ = 1 − ξ²/6, ξ₁ = √6, −ξ₁²θ'(ξ₁) = 2√6."""
    s = solve_lane_emden(0.0)
    assert s.has_finite_surface
    assert s.xi1 == pytest.approx(math.sqrt(6.0), abs=1e-6)
    assert s.mass_invariant == pytest.approx(2.0 * math.sqrt(6.0), abs=1e-5)
    # pointwise over the whole domain, not just the surface
    xi = np.linspace(0.0, s.xi1, 50)
    assert np.allclose(s.theta(xi), _theta_exact(0.0, xi), atol=1e-7)


def test_n1_closed_form():
    """n=1: θ = sin ξ / ξ, ξ₁ = π, −ξ₁²θ'(ξ₁) = π."""
    s = solve_lane_emden(1.0)
    assert s.has_finite_surface
    assert s.xi1 == pytest.approx(math.pi, abs=1e-6)
    assert s.mass_invariant == pytest.approx(math.pi, abs=1e-5)
    xi = np.linspace(0.0, s.xi1, 50)
    assert np.allclose(s.theta(xi), _theta_exact(1.0, xi), atol=1e-7)


def test_n5_no_finite_surface():
    """n=5: θ = (1 + ξ²/3)^(−1/2) never reaches 0 — the surface is at infinity."""
    s = solve_lane_emden(5.0)
    assert not s.has_finite_surface
    assert s.xi1 is None
    assert s.mass_invariant is None
    # the profile still matches the closed form across the integrated domain
    xi = np.linspace(0.0, 30.0, 60)
    assert np.allclose(s.theta(xi), _theta_exact(5.0, xi), atol=1e-6)


# --- Chandrasekhar (1939) Table 4 — secondary cross-check --------------------
# (n, ξ₁, −ξ₁²θ'(ξ₁)). Recited from the table; looser tolerance so a mistyped
# digit can't masquerade as an integrator bug.
_CHANDRA = [
    (1.5, 3.65375, 2.71406),
    (2.0, 4.35287, 2.41105),
    (3.0, 6.89685, 2.01824),
    (4.0, 14.97155, 1.79723),
]


@pytest.mark.parametrize("n, xi1, invariant", _CHANDRA)
def test_chandrasekhar_table(n, xi1, invariant):
    s = solve_lane_emden(n)
    assert s.has_finite_surface
    assert s.xi1 == pytest.approx(xi1, abs=2e-3)
    assert s.mass_invariant == pytest.approx(invariant, abs=5e-3)


# --- monotonicity / general sanity across the family -------------------------

@pytest.mark.parametrize("n", [0.0, 1.0, 1.5, 3.0])
def test_theta_decreases_monotonically(n):
    """θ falls monotonically from 1 at the centre to 0 at the surface."""
    s = solve_lane_emden(n)
    xi = np.linspace(0.0, s.xi1, 200)
    th = s.theta(xi)
    assert th[0] == pytest.approx(1.0, abs=1e-6)
    assert th[-1] == pytest.approx(0.0, abs=1e-5)
    assert np.all(np.diff(th) < 1e-9)   # non-increasing


def test_high_n_finite_surface_found_past_old_cap():
    """ξ₁ grows steeply near n=5 (n=4.7 → ~55). The search cap must reach far
    enough that a real surface isn't mislabeled "no finite surface" — guards the
    cap against being shrunk back below where reachable slider values need it."""
    s = solve_lane_emden(4.7)
    assert s.has_finite_surface
    assert s.xi1 > 50.0   # past the naive cap; the surface is real, just far out


def test_negative_n_rejected():
    with pytest.raises(ValueError):
        solve_lane_emden(-1.0)


# --- the profile payload the endpoint serves ---------------------------------

def test_profile_payload_shape():
    p = polytrope_profile(3.0, num_points=120)
    assert len(p["xi"]) == len(p["theta"]) == len(p["rho_over_rhoc"]) == 120
    assert p["theta"][0] == pytest.approx(1.0, abs=1e-9)         # θ(0) = 1
    assert p["rho_over_rhoc"][0] == pytest.approx(1.0, abs=1e-9)  # ρ/ρ_c(0) = 1
    assert p["has_finite_surface"] is True
    assert p["xi1"] == pytest.approx(6.89685, abs=2e-3)


def test_profile_central_concentration_grows_with_n():
    """§8's teaching payoff: a higher n is far more centrally concentrated. Compare
    ρ/ρ_c at the half-radius r/R = 0.5 — it should drop sharply from n=1.5 to n=3."""
    half_density = {}
    for n in (1.5, 3.0):
        p = polytrope_profile(n, num_points=400)
        xi = np.asarray(p["xi"])
        rho = np.asarray(p["rho_over_rhoc"])
        r_over_R = xi / p["xi1"]
        half_density[n] = float(np.interp(0.5, r_over_R, rho))
    assert half_density[3.0] < half_density[1.5]


def test_n5_profile_uses_raw_xi():
    """No finite surface ⇒ xi1 is null and we sample out to the integration cap."""
    p = polytrope_profile(5.0, num_points=100)
    assert p["has_finite_surface"] is False
    assert p["xi1"] is None
    assert p["mass_invariant"] is None
    assert p["xi"][-1] > 10.0   # sampled well past where a finite surface would be


# --- the /polytrope endpoint (no PROVIDER, no MIST data) ---------------------

def test_polytrope_endpoint_ok():
    client = TestClient(app)
    r = client.get("/polytrope", params={"n": 3.0})
    assert r.status_code == 200
    body = r.json()
    assert body["xi1"] == pytest.approx(6.89685, abs=2e-3)
    assert len(body["xi"]) == len(body["theta"])


def test_polytrope_endpoint_rejects_negative_n():
    client = TestClient(app)
    r = client.get("/polytrope", params={"n": -1.0})
    assert r.status_code == 422
