"""MESA-vs-MIST cross-validation — the "validate MIST" payoff (spec §5/§6 Phase 4+).

This is the point of shipping `MESAProvider`: a second, independent stellar-
evolution code (MESA, run with its own physics) read through the *same* §3
boundary, diffed against `MISTProvider`. The comparison is done entirely through
the public `track()` API (lists of `StellarState`) — it never touches either
provider's internals, so it doubles as a §3 boundary demonstration.

Two confounds are controlled so the residual is genuine physics-choice scatter,
not bookkeeping:
  * **Matched on Z, not on [Fe/H].** MESA's derived [Fe/H] (log10(Z/Z_sun)) and
    MIST's [Fe/H]->Z mapping use different Z_sun and Y(Z) laws, so equal "[Fe/H]"
    means *different Z*. We instead solve for the MIST [Fe/H] whose ZAMS surface
    Z equals the MESA run's (the sample grid's Z=0.00218 sits between MIST's
    m100 Zinit=0.00171 and m075 Zinit=0.00303). Verified: the matched MIST Z
    reproduces the MESA Z to <1%, and Yinit agrees (~0.2518 both) — so Y, whose
    leverage on L is large, is not a confound here.
  * **Compared at shared central hydrogen Xc, not at each code's ZAMS label.**
    The two codes' ZAMS criteria differ; Xc is a physical clock both report and
    is monotonic on the MS, so we interpolate L/Teff/R at Xc = 0.6/0.4/0.2.

MEASURED discrepancy (masses 1/2/6 M_sun, sample grid, this MIST v2.5 build) —
tolerances below contain these with margin (the deliverable is the *number*, not
the green check):
                       early MS (Xc=0.6)     late MS (Xc=0.2)
    |Δ log L|            <= 0.036 dex          <= 0.126 dex
    |Δ Teff / Teff|      <= 2.3 %              <= 4.4 %
    |Δ R / R|            <= 8.2 %              <= 20.3 %
MESA is systematically the more luminous / larger of the two, and the gap GROWS
as the star evolves off ZAMS — consistent with the late-MS structure's known
sensitivity to overshoot / mixing-length / opacity, which differ between the MESA
r12115 tutorial inlist and MIST v2.5. The two agree tightly near ZAMS, where
those choices matter least. This is a *consistency* result within physics scatter,
not a bit-for-bit match (the tutorial grid was never tuned to MIST).

Gated by both data sets: the MESA runs (`fetch_mesa`) and the bracketing MIST
grids m100/m075 (`fetch_mist --feh m075,m100`).
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from star_sim.providers import MESAProvider, MISTProvider

from .conftest import requires_mesa_data, requires_mist_lowz

pytestmark = [requires_mesa_data, requires_mist_lowz]

# Masses to cross-check (all exact grid points in both providers).
MASSES = (1, 2, 6)

# The two MIST grids that bracket the MESA sample Z (=0.00218).
FEH_LO, FEH_HI = -1.0, -0.75

# Central-H clocks to compare at (descending: ZAMS -> late MS, before the hook).
XC_EARLY = 0.6
XC_LATE = (0.4, 0.2)

# Tolerances chosen to contain the MEASURED gaps (see module docstring) with margin.
DLOGL_EARLY, DTEFF_EARLY, DR_EARLY = 0.06, 0.04, 0.12
DLOGL_MAX, DTEFF_MAX, DR_MAX = 0.15, 0.06, 0.26


@pytest.fixture(scope="module")
def mesa() -> MESAProvider:
    return MESAProvider()


@pytest.fixture(scope="module")
def mist() -> MISTProvider:
    # Only the two bracketing grids, so the [Fe/H] blend stays inside [-1.0, -0.75].
    return MISTProvider(fehs=(FEH_LO, FEH_HI))


def _at_xc(states, xc_target: float, attr: str) -> float:
    """Interpolate `attr` along the MS at central hydrogen `xc_target`.

    Xc decreases on the MS, so restrict to the H-burning rows and sort ascending
    for np.interp. Public StellarState fields only — no provider internals."""
    xc = np.array([s.X_core for s in states])
    q = np.array([getattr(s, attr) for s in states])
    keep = xc > 1e-3
    xc, q = xc[keep], q[keep]
    order = np.argsort(xc)
    return float(np.interp(xc_target, xc[order], q[order]))


def _matched_mist_feh(mist: MISTProvider, mesa_z: float, mass: float) -> float:
    """MIST [Fe/H] whose ZAMS surface Z equals the MESA run's (Z is ~linear in the
    [Fe/H] blend weight, so a single linear solve hits it)."""
    z_lo = mist.track(mass, FEH_LO)[0].Z_surf
    z_hi = mist.track(mass, FEH_HI)[0].Z_surf
    w = (mesa_z - z_lo) / (z_hi - z_lo)
    return FEH_LO + w * (FEH_HI - FEH_LO)


@pytest.fixture(scope="module")
def matched_tracks(mesa, mist):
    """Per-mass (mesa_track, mist_track) where the MIST track is Z-matched to MESA."""
    mesa_feh = mesa.parameter_ranges()["feh"]["min"]
    out = {}
    for m in MASSES:
        mtr = mesa.track(m, mesa_feh)
        feh = _matched_mist_feh(mist, mtr[0].Z_surf, m)
        out[m] = (mtr, mist.track(m, feh))
    return out


@pytest.mark.parametrize("mass", MASSES)
def test_z_and_y_matched_not_confounded(matched_tracks, mass):
    """Precondition: the Z-match works and Yinit agrees, so the L/Teff/R gaps below
    are physics, not a metallicity/helium offset."""
    mtr, itr = matched_tracks[mass]
    assert itr[0].Z_surf == pytest.approx(mtr[0].Z_surf, rel=0.02)
    assert itr[0].Y_surf == pytest.approx(mtr[0].Y_surf, abs=0.002)


@pytest.mark.parametrize("mass", MASSES)
def test_mesa_mist_agree_near_zams(matched_tracks, mass):
    """Near ZAMS (Xc=0.6) the two codes agree tightly — physics-choice differences
    are smallest here, so this is the check with teeth."""
    mtr, itr = matched_tracks[mass]
    mL, iL = _at_xc(mtr, XC_EARLY, "L_lsun"), _at_xc(itr, XC_EARLY, "L_lsun")
    mT, iT = _at_xc(mtr, XC_EARLY, "Teff_K"), _at_xc(itr, XC_EARLY, "Teff_K")
    mR, iR = _at_xc(mtr, XC_EARLY, "R_rsun"), _at_xc(itr, XC_EARLY, "R_rsun")
    assert abs(math.log10(iL) - math.log10(mL)) <= DLOGL_EARLY
    assert abs(iT - mT) / mT <= DTEFF_EARLY
    assert abs(iR - mR) / mR <= DR_EARLY


@pytest.mark.parametrize("mass", MASSES)
def test_mesa_mist_bounded_through_late_ms(matched_tracks, mass):
    """Through the late MS (Xc=0.4, 0.2) the gap grows but stays within the measured
    envelope — consistency within physics scatter, not a bit-for-bit match."""
    mtr, itr = matched_tracks[mass]
    for xc in XC_LATE:
        mL, iL = _at_xc(mtr, xc, "L_lsun"), _at_xc(itr, xc, "L_lsun")
        mT, iT = _at_xc(mtr, xc, "Teff_K"), _at_xc(itr, xc, "Teff_K")
        mR, iR = _at_xc(mtr, xc, "R_rsun"), _at_xc(itr, xc, "R_rsun")
        assert abs(math.log10(iL) - math.log10(mL)) <= DLOGL_MAX
        assert abs(iT - mT) / mT <= DTEFF_MAX
        assert abs(iR - mR) / mR <= DR_MAX


def test_mesa_is_systematically_more_luminous(matched_tracks):
    """The documented direction of the discrepancy: across all masses/clocks MESA
    is at least as luminous as MIST (MIST never brighter by more than noise). A
    regression here means the comparison or a provider changed character."""
    for mass in MASSES:
        mtr, itr = matched_tracks[mass]
        for xc in (XC_EARLY, *XC_LATE):
            dlogL = math.log10(_at_xc(itr, xc, "L_lsun")) - math.log10(_at_xc(mtr, xc, "L_lsun"))
            assert dlogL <= 0.02     # MIST not meaningfully brighter than MESA
