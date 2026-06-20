"""§10 sanity checks against the real MISTProvider — the regression for the
stub -> MIST swap.

These mirror tests/test_stub_provider.py but with *empirical* tolerances: the
stub returned Sun values by construction (rel=1e-6), whereas MIST's solar
calibration sits slightly hot/luminous at 4.6 Gyr (measured: L=1.07, Teff=5834 K,
R=1.01, logg=4.43). Tolerances below are set to comfortably contain the measured
MIST values while still pinning "this renders the Sun." Skipped when the grids
aren't fetched (see conftest.requires_mist_data).
"""

from __future__ import annotations

import math
import os

import numpy as np
import pytest

from star_sim.provider import ParameterOutOfRange, StellarStateProvider
from star_sim.providers import MISTProvider
from star_sim.providers.mist import DATA_DIR, _find_eep_dir

from .conftest import requires_mist_data

pytestmark = requires_mist_data

SUN_AGE_YR = 4.6e9


@pytest.fixture(scope="module")
def provider() -> MISTProvider:
    return MISTProvider()


# --- a tiny ground-truth loader for the interpolation test -------------------
def _real_track(mass_code: str):
    """Read a raw MIST track via the vendored parser (test ground truth only)."""
    from star_sim.providers._vendor import read_mist_models as rmm

    path = os.path.join(str(_find_eep_dir(DATA_DIR)), f"{mass_code}M.track.eep")
    return rmm.EEP(path, verbose=False).eeps


def test_mist_satisfies_provider_protocol(provider):
    # runtime_checkable Protocol: structural conformance to the §3 boundary.
    assert isinstance(provider, StellarStateProvider)


def test_sun_anchor(provider):
    """1 M_sun, [Fe/H]=0 at ~4.6 Gyr renders the Sun (§10), MIST tolerances."""
    st = provider.state_at(1.0, 0.0, SUN_AGE_YR)
    assert st.L_lsun == pytest.approx(1.0, rel=0.10)     # measured 1.07
    assert st.Teff_K == pytest.approx(5772.0, abs=100.0)  # measured 5834
    assert st.R_rsun == pytest.approx(1.0, rel=0.06)      # measured 1.01
    assert st.logg == pytest.approx(4.44, abs=0.05)       # measured 4.43
    assert st.phase == "MS"


def test_composition_sums_to_one(provider):
    st = provider.state_at(1.0, 0.0, SUN_AGE_YR)
    assert st.X_surf + st.Y_surf + st.Z_surf == pytest.approx(1.0, abs=1e-6)
    assert st.X_core + st.Y_core + st.Z_core == pytest.approx(1.0, abs=1e-6)
    # A 4.6 Gyr Sun has burned core H below its surface value.
    assert st.X_core < st.X_surf


def test_zams_spread_is_dramatic(provider):
    """Across the mass range, L spans ~8+ orders and Teff sweeps red->blue (§10)."""
    lo = provider.state_at(0.1, 0.0, 0.0)    # age 0 clamps to ZAMS
    hi = provider.state_at(40.0, 0.0, 0.0)
    orders = math.log10(hi.L_lsun) - math.log10(lo.L_lsun)
    assert orders > 8.0                       # measured 8.42
    assert lo.Teff_K < 3500.0                 # measured 2809 (cool red dwarf)
    assert hi.Teff_K > 30000.0                # measured 44607 (hot blue O star)


def test_zams_luminosity_monotonic_in_mass(provider):
    masses = [0.2, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0]
    lums = [provider.state_at(m, 0.0, 0.0).L_lsun for m in masses]
    assert lums == sorted(lums)


def test_age_zero_clamps_to_zams(provider):
    """age 0 -> ZAMS (EEP 202), not pre-MS; and age never extrapolates below it."""
    st = provider.state_at(1.0, 0.0, 0.0)
    assert st.eep == pytest.approx(202.0, abs=0.5)
    lo, _ = provider.age_range(1.0, 0.0)
    assert st.age_yr == pytest.approx(lo, rel=1e-9)


def test_evolves_off_main_sequence(provider):
    """The point of MIST over the stub: real post-MS drama (subgiant/RGB)."""
    lo, hi = provider.age_range(1.0, 0.0)
    zams = provider.state_at(1.0, 0.0, lo)
    tip = provider.state_at(1.0, 0.0, hi)
    assert tip.eep > zams.eep
    assert tip.R_rsun > 10.0 * zams.R_rsun    # swells into a giant (measured ~146 R_sun)
    assert tip.Teff_K < zams.Teff_K           # and cools
    assert tip.phase in ("RGB", "CHeB")
    assert tip.X_core < 1e-3                   # core H exhausted


def test_out_of_range_raises(provider):
    with pytest.raises(ParameterOutOfRange):
        provider.state_at(1000.0, 0.0, 0.0)   # mass past the grid
    with pytest.raises(ParameterOutOfRange):
        provider.state_at(1.0, 0.5, 0.0)      # [Fe/H] off the single-metallicity grid


def test_eep_interpolation_lies_between_neighbors(provider):
    """The direct §6/§10 test: interpolate on EEP, not age.

    1.5 M_sun is absent from the curated grid, so it's interpolated from the 1.4
    and 1.6 tracks. At the EEP the interpolated star reports, its HR position
    must sit between those neighbors — and track the *real* 1.5 M_sun run, which
    an age-based (phase-blending) interpolation would not.
    """
    t14 = _real_track("00140")
    t16 = _real_track("00160")
    t15 = _real_track("00150")  # ground truth

    lo, hi = provider.age_range(1.5, 0.0)
    rel_errs = []
    for frac in np.linspace(0.02, 0.98, 25):
        st = provider.state_at(1.5, 0.0, lo + frac * (hi - lo))
        row = int(round(st.eep)) - 1  # EEP n == row n-1, the same phase across masses

        logL, logL14, logL16 = math.log10(st.L_lsun), t14["log_L"][row], t16["log_L"][row]
        logT, logT14, logT16 = math.log10(st.Teff_K), t14["log_Teff"][row], t16["log_Teff"][row]
        # lies between the bracketing tracks at this EEP (small slack for rounding)
        assert min(logL14, logL16) - 0.03 <= logL <= max(logL14, logL16) + 0.03
        assert min(logT14, logT16) - 0.01 <= logT <= max(logT14, logT16) + 0.01

        rel_errs.append(abs(st.L_lsun - 10 ** t15["log_L"][row]) / 10 ** t15["log_L"][row])

    # Tracks the real 1.5 track closely (median ~1%); an age-interp would not.
    assert float(np.median(rel_errs)) < 0.05
