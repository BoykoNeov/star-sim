"""Solar MESA-vs-MIST cross-validation — the near-solar counterpart to
`test_mesa_vs_mist.py` (which validates the metal-poor bearums grid).

The bearums grid sits 0.84 dex below solar. This test exercises the **solar**
MESAProvider bucket — 1/2/6 M_sun runs made at Z=0.0152 with MESA r24.03.1 (see
backend/docs/mesa_solar_recipe.md) — against MIST v2.5.

Same two confounds controlled as the metal-poor test:
  * **Matched on Z, not [Fe/H].** The solar runs' ZAMS surface Z=0.01523 is
    *below* MIST p000's ZAMS Z=0.01635, so p000 alone cannot bracket it; the
    straddling MIST grids are m050 (Z~0.005) and p000, and we solve per mass for
    the MIST [Fe/H] (~-0.05) whose ZAMS Z equals the MESA run's. Yinit agrees
    (~0.269 both), so helium is not a confound.
  * **Compared at shared central Xc** (0.6/0.4/0.2), not each code's ZAMS label.

MEASURED |discrepancy| (MIST - MESA; this MESA r24.03.1 solar grid vs MIST v2.5):
                  |Δ log L|     |Δ Teff/Teff|   |Δ R/R|
    M=1 (Sun)     <= 0.014       <= 0.04 %       <= 1.5 %     <- dramatically tight
    M=2           <= 0.045       <= 2.0  %       <= 9.9 %
    M=6           <= 0.069       <= 1.4  %       <= 8.5 %
  by clock:  early MS (Xc=0.6) is tight for ALL masses (|Δlog L|<=0.016,
  |ΔR|<=1.5%); the gap GROWS off ZAMS for the intermediate masses (Xc=0.2:
  |Δlog L| up to 0.069, |ΔR| up to 9.9%) — the convective-core-hook regime where
  overshoot/mixing choices bite. Still inside, but approaching, the metal-poor
  envelope (late-MS |Δlog L|<=0.13, |ΔR|<=20%).

Two honest notes vs the metal-poor case:
  * The **1 M_sun Sun stays an order of magnitude tighter** than the metal-poor
    bracket at every clock — the real payoff of a solar anchor (own test below).
  * The Δlog L **sign is not uniform** (MESA brighter at 1 M_sun, MIST brighter
    at 2/6), so there is NO "MESA systematically more luminous" assertion here
    (unlike test_mesa_vs_mist.py, where it holds for the metal-poor grid).

Tolerances below contain the measured numbers with margin (the deliverable is
the *number*). Gated by the solar MESA bucket (a manual drop-in) and the
bracketing MIST grids m050 + p000.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from star_sim.providers import MESAProvider, MISTProvider

from .conftest import requires_mesa_solar, requires_mist_solar_bracket

pytestmark = [requires_mesa_solar, requires_mist_solar_bracket]

MASSES = (1, 2, 6)
FEH_LO, FEH_HI = -0.5, 0.0   # straddle the solar runs' ZAMS Z=0.01523
XC_EARLY = 0.6
XC_LATE = (0.4, 0.2)

# Tolerances contain the MEASURED gaps (see docstring) with margin. Early MS is
# tight for all masses; the late-MS envelope is looser (the hook). Both stay
# meaningfully under test_mesa_vs_mist.py's metal-poor values (0.06/0.04/0.12
# early, 0.15/0.06/0.26 late).
DLOGL_EARLY, DTEFF_EARLY, DR_EARLY = 0.04, 0.02, 0.04
DLOGL_MAX, DTEFF_MAX, DR_MAX = 0.10, 0.03, 0.13

# The Sun (1 M_sun) specifically stays an order of magnitude tighter, all clocks.
DLOGL_SUN, DTEFF_SUN, DR_SUN = 0.03, 0.005, 0.03


@pytest.fixture(scope="module")
def mesa() -> MESAProvider:
    return MESAProvider()


@pytest.fixture(scope="module")
def mist() -> MISTProvider:
    return MISTProvider(fehs=(FEH_LO, FEH_HI))


def _at_xc(states, xc_target: float, attr: str) -> float:
    """Interpolate `attr` along the MS at central hydrogen `xc_target` (public
    StellarState fields only). Xc decreases on the MS, so sort ascending."""
    xc = np.array([s.X_core for s in states])
    q = np.array([getattr(s, attr) for s in states])
    keep = xc > 1e-3
    xc, q = xc[keep], q[keep]
    order = np.argsort(xc)
    return float(np.interp(xc_target, xc[order], q[order]))


def _matched_mist_feh(mist: MISTProvider, mass: float, mesa_z: float) -> float:
    """MIST [Fe/H] whose ZAMS surface Z equals the MESA run's (Z ~ linear in the
    [Fe/H] blend weight, so one linear solve hits it)."""
    z_lo = mist.track(mass, FEH_LO)[0].Z_surf
    z_hi = mist.track(mass, FEH_HI)[0].Z_surf
    w = (mesa_z - z_lo) / (z_hi - z_lo)
    return FEH_LO + w * (FEH_HI - FEH_LO)


@pytest.fixture(scope="module")
def matched(mesa, mist):
    """Per-mass (mesa_track, mist_track) with the MIST track Z-matched to MESA."""
    out = {}
    for m in MASSES:
        mtr = mesa.track(float(m), 0.0)
        feh = _matched_mist_feh(mist, float(m), mtr[0].Z_surf)
        out[m] = (mtr, mist.track(float(m), feh))
    return out


@pytest.mark.parametrize("mass", MASSES)
def test_z_and_y_matched_not_confounded(matched, mass):
    """Precondition: the Z-match works and Yinit agrees, so the L/Teff/R gaps are
    physics, not a metallicity/helium offset."""
    mtr, itr = matched[mass]
    assert itr[0].Z_surf == pytest.approx(mtr[0].Z_surf, rel=0.02)
    assert itr[0].Y_surf == pytest.approx(mtr[0].Y_surf, abs=0.003)


@pytest.mark.parametrize("mass", MASSES)
def test_solar_agree_near_zams(matched, mass):
    """Near ZAMS (Xc=0.6) the codes agree tightly at solar Z for every mass."""
    mtr, itr = matched[mass]
    mL, iL = _at_xc(mtr, XC_EARLY, "L_lsun"), _at_xc(itr, XC_EARLY, "L_lsun")
    mT, iT = _at_xc(mtr, XC_EARLY, "Teff_K"), _at_xc(itr, XC_EARLY, "Teff_K")
    mR, iR = _at_xc(mtr, XC_EARLY, "R_rsun"), _at_xc(itr, XC_EARLY, "R_rsun")
    assert abs(math.log10(iL) - math.log10(mL)) <= DLOGL_EARLY
    assert abs(iT - mT) / mT <= DTEFF_EARLY
    assert abs(iR - mR) / mR <= DR_EARLY


@pytest.mark.parametrize("mass", MASSES)
def test_solar_bounded_through_late_ms(matched, mass):
    """Through the late MS (Xc=0.4, 0.2) the gap grows for the intermediate
    masses (the hook) but stays within the measured solar envelope."""
    mtr, itr = matched[mass]
    for xc in XC_LATE:
        mL, iL = _at_xc(mtr, xc, "L_lsun"), _at_xc(itr, xc, "L_lsun")
        mT, iT = _at_xc(mtr, xc, "Teff_K"), _at_xc(itr, xc, "Teff_K")
        mR, iR = _at_xc(mtr, xc, "R_rsun"), _at_xc(itr, xc, "R_rsun")
        assert abs(math.log10(iL) - math.log10(mL)) <= DLOGL_MAX
        assert abs(iT - mT) / mT <= DTEFF_MAX
        assert abs(iR - mR) / mR <= DR_MAX


def test_one_msun_sun_is_exceptionally_tight(matched):
    """The payoff: the 1 M_sun Sun anchor agrees to ~0.01 dex / <0.1% Teff / <2% R
    across the whole MS — an order of magnitude tighter than the metal-poor
    bracket. This is the reason a solar bucket is worth having."""
    mtr, itr = matched[1]
    for xc in (XC_EARLY, *XC_LATE):
        mL, iL = _at_xc(mtr, xc, "L_lsun"), _at_xc(itr, xc, "L_lsun")
        mT, iT = _at_xc(mtr, xc, "Teff_K"), _at_xc(itr, xc, "Teff_K")
        mR, iR = _at_xc(mtr, xc, "R_rsun"), _at_xc(itr, xc, "R_rsun")
        assert abs(math.log10(iL) - math.log10(mL)) <= DLOGL_SUN
        assert abs(iT - mT) / mT <= DTEFF_SUN
        assert abs(iR - mR) / mR <= DR_SUN
