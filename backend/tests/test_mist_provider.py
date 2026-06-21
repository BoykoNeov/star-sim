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
from star_sim.providers.mist import DATA_DIR
from star_sim.state import StellarState

from .conftest import (
    requires_mist_data,
    requires_mist_heldout_feh,
    requires_mist_multifeh,
)

pytestmark = requires_mist_data

SUN_AGE_YR = 4.6e9


@pytest.fixture(scope="module")
def provider() -> MISTProvider:
    return MISTProvider()


# --- a tiny ground-truth loader for the interpolation tests ------------------
def _feh_to_code(feh: float) -> str:
    """0.0 -> 'p000', -0.5 -> 'm050', 0.5 -> 'p050' (MIST dir-name [Fe/H] code)."""
    sign = "m" if feh < 0 else "p"
    return f"{sign}{round(abs(feh) * 100):03d}"


def _real_track(mass_code: str, feh: float = 0.0):
    """Read a raw MIST track via the vendored parser (test ground truth only).

    Defaults to the solar grid; the [Fe/H] tests pass a metallicity so they read
    the *right* grid (with multiple grids on disk `_find_eep_dir` is ambiguous).
    """
    import glob

    from star_sim.providers._vendor import read_mist_models as rmm

    hits = glob.glob(
        str(DATA_DIR / f"feh_{_feh_to_code(feh)}_*" / "**" / f"{mass_code}M.track.eep"),
        recursive=True,
    )
    return rmm.EEP(hits[0], verbose=False).eeps


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
    """The point of MIST over the stub: real post-MS drama (RGB tip giant, then
    the He flash / horizontal branch).

    The window now runs *past* the RGB tip to the end of core-He burning, so the
    tip — the biggest, coolest the star ever gets — is a mid-track state, not the
    age-window endpoint. Pull it explicitly (max radius on the track) so this keeps
    verifying the star reaches *giant* dimensions; a regression that flattened the
    RGB tip would otherwise slip past (the endpoint alone is the smaller red-clump
    star, ~13 R_sun)."""
    lo, hi = provider.age_range(1.0, 0.0)
    zams = provider.state_at(1.0, 0.0, lo)
    track = provider.track(1.0, 0.0)
    tip = max(track, key=lambda s: s.R_rsun)   # RGB tip == max radius on the track
    assert tip.eep > zams.eep
    assert tip.R_rsun > 50.0 * zams.R_rsun     # swells into a giant (measured ~154 R_sun)
    assert tip.Teff_K < zams.Teff_K            # and is cool
    assert tip.phase in ("RGB", "CHeB")
    assert tip.X_core < 1e-3                    # core H exhausted

    # ...and the window keeps going *past* the tip into core-He burning, where the
    # star shrinks back off the giant branch (the new, widened payload).
    end = provider.state_at(1.0, 0.0, hi)
    assert end.phase == "CHeB"
    assert end.R_rsun < tip.R_rsun


# --- the evolutionary track (the §5.2/§5.4 input: HR track + composition panel) --
def test_track_is_ordered_stellarstate_list(provider):
    """track() returns StellarStates from ZAMS through core-He burning (CHeB),
    ordered by EEP, age strictly increasing — the §3-clean input the HR track and
    composition panel consume. Each element is a StellarState (no window internals
    leak out)."""
    t = provider.track(1.0, 0.0)
    assert len(t) > 1
    assert all(isinstance(s, StellarState) for s in t)
    eeps = [s.eep for s in t]
    ages = [s.age_yr for s in t]
    assert eeps == sorted(eeps)
    assert all(ages[i] < ages[i + 1] for i in range(len(ages) - 1))
    for s in t:
        assert s.X_surf + s.Y_surf + s.Z_surf == pytest.approx(1.0, abs=1e-6)


def test_track_endpoints_match_state_at(provider):
    """The track is the same read surface as state_at — its endpoints equal a
    state_at call at the age-window bounds, so marker and track can't disagree."""
    t = provider.track(1.0, 0.0)
    lo, hi = provider.age_range(1.0, 0.0)
    zams = provider.state_at(1.0, 0.0, lo)
    tip = provider.state_at(1.0, 0.0, hi)
    assert t[0].age_yr == pytest.approx(lo, rel=1e-9)
    assert t[-1].age_yr == pytest.approx(hi, rel=1e-9)
    assert t[0].eep == pytest.approx(zams.eep, abs=1e-9)
    assert t[0].L_lsun == pytest.approx(zams.L_lsun, rel=1e-9)
    assert t[-1].L_lsun == pytest.approx(tip.L_lsun, rel=1e-9)


def test_track_core_hydrogen_depletes_monotonically(provider):
    """The teaching payload: core H falls from its ZAMS value to ~0 (exhausted by
    the RGB tip, and stays ~0 through core-He burning) and never rises — core
    burning is one-way over this window."""
    xc = [s.X_core for s in provider.track(1.0, 0.0)]
    assert xc[0] > 0.6            # ZAMS core H ~0.71
    assert xc[-1] < 1e-3          # exhausted by the tip
    assert all(xc[i] >= xc[i + 1] - 1e-6 for i in range(len(xc) - 1))


def test_out_of_range_raises(provider):
    with pytest.raises(ParameterOutOfRange):
        provider.state_at(1000.0, 0.0, 0.0)   # mass past the grid
    feh_max = provider.parameter_ranges()["feh"]["max"]
    with pytest.raises(ParameterOutOfRange):
        provider.state_at(1.0, feh_max + 1.0, 0.0)   # [Fe/H] past the grid


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


def test_cheb_interpolation_sampled_by_eep(provider):
    """The widened CHeB span (EEP 605..706), sampled by *EEP*, not age.

    The lies-between/accuracy tests above sample by age, but core-He burning is a
    ~1% age-sliver at the far end of the window — almost no age sample lands there,
    so the newly-exposed region would otherwise ship untested. track() emits one
    state per EEP row, so we can walk the post-RGB-tip rows directly. 1.5 M_sun is
    interpolated from the 1.4/1.6 neighbors — a *narrow* bracket on purpose: the
    transition-mass cliff (~2.0-2.1 M_sun, where even fine spacing is poor) is a
    documented limitation, not something this test pretends is accurate.
    """
    t14 = _real_track("00140")
    t16 = _real_track("00160")
    t15 = _real_track("00150")  # ground truth

    by_eep = {int(round(s.eep)): s for s in provider.track(1.5, 0.0)}
    cheb_eeps = sorted(e for e in by_eep if 605 <= e <= 706)
    assert len(cheb_eeps) > 40   # the window genuinely reaches into CHeB

    rel_errs = []
    for eep in cheb_eeps:
        st = by_eep[eep]
        row = eep - 1  # EEP n == MIST row n-1, the same phase across masses
        logL, logL14, logL16 = math.log10(st.L_lsun), t14["log_L"][row], t16["log_L"][row]
        logT, logT14, logT16 = math.log10(st.Teff_K), t14["log_Teff"][row], t16["log_Teff"][row]
        # lies-between is structural (the blend is convex at every EEP); tiny slack.
        assert min(logL14, logL16) - 0.03 <= logL <= max(logL14, logL16) + 0.03
        assert min(logT14, logT16) - 0.01 <= logT <= max(logT14, logT16) + 0.01
        rel_errs.append(abs(st.L_lsun - 10 ** t15["log_L"][row]) / 10 ** t15["log_L"][row])

    # Narrow bracket tracks the real 1.5 CHeB closely (measured median ~1%); the
    # He-flash/red-clump region is steeper than the MS, so a few points are worse,
    # but the median stays small.
    assert float(np.median(rel_errs)) < 0.05


# --- the [Fe/H] axis (§6 outer loop) -----------------------------------------
@requires_mist_multifeh
def test_parameter_ranges_expose_feh_span(provider):
    """With >=2 grids the feh range is a real interval, not a pinned point."""
    feh = provider.parameter_ranges()["feh"]
    assert feh["min"] < feh["max"]


@requires_mist_multifeh
def test_feh_interpolation_lies_between_metallicities(provider):
    """The rigorous §6/§10 property for the metallicity axis: at a fixed EEP, an
    interpolated [Fe/H] must lie *between* its bracketing grids on the HR diagram.

    Blend-then-invert makes the blended logL/logT a convex combination of the two
    grids at every row, so this is provably preserved — assert it tightly. (1.0
    M_sun is a grid point, so each bracket's window is its raw track.)
    """
    provider._ensure_loaded()
    fehs = provider._fehs
    f_lo, f_hi = float(fehs[0]), float(fehs[1])     # first metallicity bracket
    f_mid = 0.5 * (f_lo + f_hi)
    t_lo = _real_track("00100", f_lo)
    t_hi = _real_track("00100", f_hi)

    lo, hi = provider.age_range(1.0, f_mid)
    for frac in np.linspace(0.05, 0.95, 15):
        st = provider.state_at(1.0, f_mid, lo + frac * (hi - lo))
        row = int(round(st.eep)) - 1
        logL, logT = math.log10(st.L_lsun), math.log10(st.Teff_K)
        lL_lo, lL_hi = t_lo["log_L"][row], t_hi["log_L"][row]
        lT_lo, lT_hi = t_lo["log_Teff"][row], t_hi["log_Teff"][row]
        assert min(lL_lo, lL_hi) - 0.03 <= logL <= max(lL_lo, lL_hi) + 0.03
        assert min(lT_lo, lT_hi) - 0.01 <= logT <= max(lT_lo, lT_hi) + 0.01


@requires_mist_multifeh
def test_metal_poor_is_hotter_and_brighter(provider):
    """Physics sanity (§6): at fixed mass & age, lower [Fe/H] -> lower opacity ->
    a hotter, more luminous star. The axis must reproduce this direction."""
    feh = provider.parameter_ranges()["feh"]
    poor = provider.state_at(1.0, feh["min"], SUN_AGE_YR)
    rich = provider.state_at(1.0, feh["max"], SUN_AGE_YR)
    assert poor.Teff_K > rich.Teff_K
    assert poor.L_lsun > rich.L_lsun


@requires_mist_heldout_feh
def test_feh_interpolation_tracks_held_out_grid():
    """Hold the solar grid out: interpolate at [Fe/H]=0 from only the m050/p050
    grids and check it reproduces the *real* p000 run.

    Empirical tolerance: a full 1.0-dex [Fe/H] bracket has real curvature (unlike
    the near-linear 0.2-M_sun mass bracket), so this is looser than the mass test.
    Measured L median ~3.3% (max ~11%); Teff median ~0.7%. The lies-between test
    above is the *tight* guarantee; this one checks accuracy, not just bounds.
    """
    p = MISTProvider(fehs=(-0.5, 0.5))     # solar grid deliberately excluded
    real = _real_track("00100", 0.0)        # ground truth: the real p000 1.0 track

    lo, hi = p.age_range(1.0, 0.0)
    L_errs, T_errs = [], []
    for frac in np.linspace(0.05, 0.95, 25):
        st = p.state_at(1.0, 0.0, lo + frac * (hi - lo))
        row = int(round(st.eep)) - 1
        L_real, T_real = 10 ** real["log_L"][row], 10 ** real["log_Teff"][row]
        L_errs.append(abs(st.L_lsun - L_real) / L_real)
        T_errs.append(abs(st.Teff_K - T_real) / T_real)

    assert float(np.median(L_errs)) < 0.06    # measured 3.3%
    assert float(np.median(T_errs)) < 0.015   # measured 0.7%


@requires_mist_heldout_feh
def test_dead_corner_excluded_per_metallicity():
    """The valid (mass, [Fe/H]) domain isn't rectangular: super-solar low-mass
    M-dwarfs have no evolved tracks, so mass_range tightens and the corner raises.
    The §10 red dwarf survives at solar/sub-solar [Fe/H], where it does exist.
    """
    p = MISTProvider()
    assert p.mass_range(0.0)[0] < 0.5          # red dwarfs available at solar [Fe/H]
    assert p.mass_range(0.5)[0] >= 0.5         # ...but not super-solar
    # the surviving red dwarf is the cool §10 anchor
    assert p.state_at(0.1, 0.0, 0.0).Teff_K < 3500.0
    with pytest.raises(ParameterOutOfRange):
        p.state_at(0.1, 0.5, 0.0)              # the dead corner
