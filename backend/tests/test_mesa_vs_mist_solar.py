"""Solar MESA-vs-MIST cross-validation — the near-solar counterpart to
`test_mesa_vs_mist.py` (which validates the metal-poor bearums grid).

The bearums grid sits 0.84 dex below solar, where MESA (a tutorial r12115 inlist)
and MIST v2.5 diverge substantially off ZAMS (late-MS |Δlog L| up to 0.13,
|ΔR| up to 20%). This test exercises the **solar** MESAProvider bucket — a
1 M_sun run made at Z=0.0152 with MESA r24.03.1 (see backend/docs/
mesa_solar_recipe.md) — and finds the two codes agree FAR more tightly there.

Same two confounds controlled as the metal-poor test:
  * **Matched on Z, not [Fe/H].** The solar run's ZAMS surface Z=0.01523 is
    *below* MIST p000's ZAMS Z=0.01635, so p000 alone cannot bracket it; the
    straddling MIST grids are m050 (Z~0.005) and p000, and we solve for the MIST
    [Fe/H] (~-0.05) whose ZAMS Z equals the MESA run's. Yinit agrees (~0.269
    both), so helium is not a confound.
  * **Compared at shared central Xc** (0.6/0.4/0.2), not each code's ZAMS label.

MEASURED discrepancy (1 M_sun, this MESA r24.03.1 solar run vs MIST v2.5) —
tolerances below contain these with margin (the deliverable is the *number*):
                       Xc=0.6        Xc=0.4        Xc=0.2
    |Δ log L|          0.014         0.014         0.004
    |Δ Teff / Teff|    0.00 %        0.04 %        0.04 %
    |Δ R / R|          1.5 %         1.4 %         0.4 %
An order of magnitude tighter than the metal-poor bracket — at solar Z, with
matched Z + Y + Xc, the two independent codes are nearly indistinguishable on
the MS. (MESA stays marginally the more luminous of the two, as documented for
the metal-poor case, but the gap is ~0.01 dex here rather than ~0.13.)

Gated by the solar MESA bucket (a manual drop-in) and the bracketing MIST grids
m050 + p000.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from star_sim.providers import MESAProvider, MISTProvider

from .conftest import requires_mesa_solar, requires_mist_solar_bracket

pytestmark = [requires_mesa_solar, requires_mist_solar_bracket]

MASS = 1.0
FEH_LO, FEH_HI = -0.5, 0.0   # straddle the solar run's ZAMS Z=0.01523
XC = (0.6, 0.4, 0.2)

# Tolerances chosen to contain the MEASURED gaps (see module docstring) with
# margin. Deliberately ~5x tighter than test_mesa_vs_mist.py's metal-poor values
# (0.15 / 0.06 / 0.26) — encoding the finding that solar agreement is far better.
DLOGL_TOL, DTEFF_TOL, DR_TOL = 0.04, 0.005, 0.03


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


def _matched_mist_feh(mist: MISTProvider, mesa_z: float) -> float:
    """MIST [Fe/H] whose ZAMS surface Z equals the MESA run's (Z ~ linear in the
    [Fe/H] blend weight, so one linear solve hits it)."""
    z_lo = mist.track(MASS, FEH_LO)[0].Z_surf
    z_hi = mist.track(MASS, FEH_HI)[0].Z_surf
    w = (mesa_z - z_lo) / (z_hi - z_lo)
    return FEH_LO + w * (FEH_HI - FEH_LO)


@pytest.fixture(scope="module")
def matched(mesa, mist):
    """(mesa_track, mist_track) with the MIST track Z-matched to the solar MESA run."""
    mtr = mesa.track(MASS, 0.0)
    feh = _matched_mist_feh(mist, mtr[0].Z_surf)
    return mtr, mist.track(MASS, feh)


def test_z_and_y_matched_not_confounded(matched):
    """Precondition: the Z-match works and Yinit agrees, so the L/Teff/R gaps are
    physics, not a metallicity/helium offset."""
    mtr, itr = matched
    assert itr[0].Z_surf == pytest.approx(mtr[0].Z_surf, rel=0.02)
    assert itr[0].Y_surf == pytest.approx(mtr[0].Y_surf, abs=0.003)


def test_solar_mesa_mist_agree_tightly(matched):
    """The payoff: at solar Z the two codes agree to ~0.01 dex / <0.1% Teff / <2% R
    across the MS — an order of magnitude tighter than the metal-poor bracket."""
    mtr, itr = matched
    for xc in XC:
        mL, iL = _at_xc(mtr, xc, "L_lsun"), _at_xc(itr, xc, "L_lsun")
        mT, iT = _at_xc(mtr, xc, "Teff_K"), _at_xc(itr, xc, "Teff_K")
        mR, iR = _at_xc(mtr, xc, "R_rsun"), _at_xc(itr, xc, "R_rsun")
        assert abs(math.log10(iL) - math.log10(mL)) <= DLOGL_TOL
        assert abs(iT - mT) / mT <= DTEFF_TOL
        assert abs(iR - mR) / mR <= DR_TOL
