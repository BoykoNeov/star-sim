"""The Lane-Emden interior-structure solver (STAR_SIM_SPEC.md §8).

This is a *sibling* to the StellarState spine (§3), **not** a provider and **not**
a `StellarState`. Lane-Emden gives a single *static* polytrope — `P = K ρ^(1+1/n)`
— with no time, no temperature history, no burning. The spec is emphatic that it
"belongs as an 'interior structure' panel, never as the evolution engine," so it
never routes through `StellarStateProvider`: the panel is driven by the polytropic
index `n` alone, independent of which star the rest of the UI is showing.

Why it lives in the backend (not the frontend): §8 demands validation against the
exact closed forms (n=0,1,5) and Chandrasekhar's tabulated ξ₁ — that validation is
pytest territory, and this project gates correctness in pytest. The frontend panel
is a thin consumer of `polytrope_profile()` over `/polytrope`.

The dimensionless Lane-Emden equation (θ = (ρ/ρ_c)^(1/n), ξ = r/r_n):

    (1/ξ²) d/dξ (ξ² dθ/dξ) = −θ^n,   θ(0)=1,  θ'(0)=0

Equivalently  θ'' + (2/ξ) θ' = −θ^n.  We integrate it outward from the centre and
stop at the first zero ξ₁ (the surface). Closed forms exist for n = 0, 1, 5 and
anchor the tests.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.integrate import solve_ivp

# n ≥ N_NO_SURFACE has no finite surface (n=5 reaches θ=0 only as ξ→∞; n>5 never).
# We still integrate, but report ξ₁ = None and plot against raw ξ.
N_NO_SURFACE = 5.0

# Integration / surface-search cap. ξ₁ grows steeply as n→5 (n=3 → 6.9, n=4 → 15,
# n=4.5 → 32, n=4.8 → ~70), so the cap is set well past that: a finite surface is
# found out to ~n=4.85, beyond which it genuinely diverges and we honestly report
# "no finite surface". (There's always *some* threshold near 5 — ξ₁→∞ as n→5 — so
# this just pushes it close enough that the slider doesn't mislabel a real surface.)
XI_MAX = 100.0

# How far out to *plot* the no-finite-surface case (n ≥ 5). The profile is already
# near-zero by ξ~10, so a tight window reads better than the full search cap (which
# would bury all the structure near the origin in dead space).
XI_NO_SURFACE_DISPLAY = 20.0

# Step off the r=0 singularity (the 2/ξ term) with the series expansion rather than
# evaluating the RHS at ξ=0. ξ0 small enough that the series IC is accurate to far
# better than the integrator tolerance, large enough to avoid 1/ξ blowup.
XI0 = 1e-4

# Tight tolerances: a weak integrator can hit ξ₁ while the profile is subtly wrong,
# so we integrate to ~1e-10 and let the pointwise closed-form tests be the gate.
_RTOL = 1e-10
_ATOL = 1e-12


def _series_theta(n: float, xi: float) -> float:
    """θ(ξ) near the centre, from the series θ ≈ 1 − ξ²/6 + n ξ⁴/120 − …"""
    x2 = xi * xi
    return 1.0 - x2 / 6.0 + n * x2 * x2 / 120.0


def _series_dtheta(n: float, xi: float) -> float:
    """θ'(ξ) near the centre — term-by-term derivative of `_series_theta`."""
    return -xi / 3.0 + n * xi * xi * xi / 30.0


def _rhs(xi: float, y: np.ndarray, n: float) -> list[float]:
    """[θ', θ''] for the first-order system. The source term clamps θ to ≥ 0:
    the terminal event stops us at θ=0, but the solver still *probes* trial points
    where θ dips slightly negative, and (negative)^(non-integer n) is NaN — which
    would poison the step. Clamping keeps the RHS finite without changing the
    solution up to ξ₁ (where θ ≥ 0 holds anyway)."""
    theta, dtheta = y
    base = theta if theta > 0.0 else 0.0
    return [dtheta, -(base**n) - 2.0 / xi * dtheta]


def _surface_event(xi: float, y: np.ndarray, n: float) -> float:
    """Zero-crossing of θ = the stellar surface ξ₁ (terminal, falling through 0)."""
    return y[0]


_surface_event.terminal = True
_surface_event.direction = -1


@dataclass
class LaneEmdenSolution:
    """The integrated polytrope. `_sol` carries SciPy's dense output so callers
    (tests) can evaluate θ(ξ) pointwise across the whole domain — getting ξ₁ right
    while the profile is subtly wrong is a real failure mode an endpoint-only check
    would miss."""

    n: float
    xi1: float | None                 # surface (first zero); None if none ≤ XI_MAX
    theta_prime_xi1: float | None     # θ'(ξ₁)
    mass_invariant: float | None      # −ξ₁² θ'(ξ₁) — Chandrasekhar's mass quantity
    has_finite_surface: bool
    xi_max: float                     # integration cap actually used
    _sol: object                      # scipy OdeSolution (dense); θ(ξ) for ξ≥XI0

    def theta(self, xi):
        """θ at arbitrary ξ — series for ξ ≤ XI0, the dense ODE solution above it.
        Accepts a scalar or array; returns the same shape."""
        xi_arr = np.atleast_1d(np.asarray(xi, dtype=float))
        out = np.empty_like(xi_arr)
        near = xi_arr <= XI0
        out[near] = [_series_theta(self.n, x) for x in xi_arr[near]]
        if np.any(~near):
            out[~near] = self._sol(xi_arr[~near])[0]
        return out.reshape(np.shape(xi)) if np.ndim(xi) else float(out[0])


def solve_lane_emden(
    n: float,
    *,
    xi_max: float = XI_MAX,
    xi0: float = XI0,
    rtol: float = _RTOL,
    atol: float = _ATOL,
) -> LaneEmdenSolution:
    """Integrate the Lane-Emden equation for index `n` and locate the surface ξ₁.

    Raises ValueError for n < 0 (unphysical). For 0 ≤ n < 5 the surface is finite;
    for n ≥ 5 there is no finite surface and `xi1`/`mass_invariant` come back None.
    """
    if n < 0:
        raise ValueError(f"polytropic index n must be ≥ 0, got {n}")

    y0 = [_series_theta(n, xi0), _series_dtheta(n, xi0)]
    sol = solve_ivp(
        _rhs,
        (xi0, xi_max),
        y0,
        method="DOP853",
        rtol=rtol,
        atol=atol,
        dense_output=True,
        events=_surface_event,
        args=(n,),
    )

    if sol.t_events[0].size > 0:
        xi1 = float(sol.t_events[0][0])
        theta_prime = float(sol.y_events[0][0][1])
        return LaneEmdenSolution(
            n=n,
            xi1=xi1,
            theta_prime_xi1=theta_prime,
            mass_invariant=-(xi1**2) * theta_prime,
            has_finite_surface=True,
            xi_max=xi_max,
            _sol=sol.sol,
        )

    return LaneEmdenSolution(
        n=n,
        xi1=None,
        theta_prime_xi1=None,
        mass_invariant=None,
        has_finite_surface=False,
        xi_max=xi_max,
        _sol=sol.sol,
    )


def polytrope_profile(n: float, *, num_points: int = 240) -> dict:
    """The JSON-friendly profile the `/polytrope` endpoint serves and the panel
    plots. Pure numbers, no StellarState — this is a sibling to the §3 spine.

    Returns
    -------
    dict with:
      n                  : the polytropic index
      xi                 : ξ samples (centre → surface, or → XI_MAX if no surface)
      theta              : θ(ξ) — the Lane-Emden function
      rho_over_rhoc      : (ρ/ρ_c) = θ^n — the density profile (§8's payoff plot:
                           central concentration jumps dramatically n=1.5 → n=3)
      xi1                : surface ξ₁ (null when no finite surface)
      mass_invariant     : −ξ₁² θ'(ξ₁), null when no finite surface
      has_finite_surface : bool — false for n ≥ 5 (surface at infinity)
    """
    s = solve_lane_emden(n)

    # Sample to the surface when it's finite, else out to a readable plotting
    # window (the search cap is far larger). ξ=0 is included exactly (θ=1) since the
    # integration starts a hair above it.
    upper = s.xi1 if s.has_finite_surface else XI_NO_SURFACE_DISPLAY
    xi = np.linspace(0.0, upper, num_points)
    theta = s.theta(xi)
    theta = np.clip(theta, 0.0, None)        # guard the ~0 surface point from −ε
    rho = theta**n                           # ρ/ρ_c

    return {
        "n": n,
        "xi": xi.tolist(),
        "theta": theta.tolist(),
        "rho_over_rhoc": rho.tolist(),
        "xi1": s.xi1,
        "mass_invariant": s.mass_invariant,
        "has_finite_surface": s.has_finite_surface,
    }
