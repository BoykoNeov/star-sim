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
from star_sim.providers.mist import (
    DATA_DIR,
    _TRACK_COLS,
    _cache_path,
    _find_eep_dirs,
    _grid_fingerprint,
    _parse_all_tracks,
    _read_cache,
)
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


@pytest.fixture(scope="module")
def interp_provider() -> MISTProvider:
    """A provider whose mass axis is *only* {1.4, 1.6}, so 1.5 M_sun is genuinely
    interpolated from those two neighbors.

    The default provider now loads the full grid, where 1.5 is itself a grid point
    — its `state_at(1.5, ...)` would read the raw 1.5 track, testing nothing about
    interpolation. Pinning a tight bracket keeps the §6/§10 lies-between and
    accuracy checks meaningful (and is exactly what the curated-subset path is for).
    """
    return MISTProvider(masses=(1.4, 1.6))


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

    The window now runs *past* the RGB tip — through core-He burning and on into the
    early-AGB (EAGB) — so the RGB tip, the biggest the star gets on its *first*
    ascent, is a mid-track state, not the age-window endpoint. Pull it explicitly
    (for 1 M_sun it is still the global max radius, ~154 R_sun, well above the EAGB's
    ~83) so this keeps verifying the star reaches *giant* dimensions; a regression
    that flattened the RGB tip would otherwise slip past."""
    lo, hi = provider.age_range(1.0, 0.0)
    zams = provider.state_at(1.0, 0.0, lo)
    track = provider.track(1.0, 0.0)
    tip = max(track, key=lambda s: s.R_rsun)   # RGB tip == max radius (1 M_sun: > EAGB)
    assert tip.eep > zams.eep
    assert tip.R_rsun > 50.0 * zams.R_rsun     # swells into a giant (measured ~154 R_sun)
    assert tip.Teff_K < zams.Teff_K            # and is cool
    assert tip.phase in ("RGB", "CHeB")
    assert tip.X_core < 1e-3                    # core H exhausted

    # ...and the window keeps going *past* the tip — through core-He burning and into
    # the early-AGB, the second giant ascent, where the marker now ends (the new,
    # widened payload). The EAGB endpoint is smaller than the first-ascent RGB tip.
    end = provider.state_at(1.0, 0.0, hi)
    assert end.phase == "EAGB"
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


# --- per-element composition (Phase 4: the §5.4 CNO-detail view) -------------
def test_metal_breakdown_present_and_bounded(provider):
    """metals_surf/metals_core carry Li, Be, C, N, O, F, Ne, Na, Mg, Al, Si, P, S, Ca,
    Ti, Fe — each a sub-fraction of Z.

    The dict is a *breakdown* of the lumped metals: every element is in [0, Z] and
    their sum can't exceed Z (only the exposed elements, not every metal — Cl/Ar/K/
    Cr/Ni/… stay folded into Z, and MIST's network doesn't even track those). This is
    the invariant that keeps the §5.4 detail/light views honest — the lines can never
    out-sum the Z sliver they subdivide. The sixteen sum to ~0.99 of solar Z (measured:
    surface 0.988, core 0.989 — Be adds only ~1e-8 and F ~2e-5, far below the headroom),
    so the headroom is still ~2e-4 but comfortably above the 1e-9 slack. (The bound is
    physically guaranteed — the named elements are a disjoint subset of the metals —
    so a sum *over* Z would mean a double-counted isotope, not a tolerance issue;
    re-measuring the real sum/Z, not the green assert, is the actual correctness check
    as the headroom keeps shrinking.) Boron is deliberately NOT in the set: MIST v2.5's
    only B isotope is the radioactive b8 (~1e-83, a numerical-zero transient), not
    stable boron — so a "B" key would carry meaningless ~0 data.
    """
    s = provider.state_at(1.0, 0.0, SUN_AGE_YR)
    expected = {"Li", "Be", "C", "N", "O", "F", "Ne", "Na", "Mg", "Al", "Si", "P", "S", "Ca", "Ti", "Fe"}
    for metals, z in ((s.metals_surf, s.Z_surf), (s.metals_core, s.Z_core)):
        assert set(metals) == expected
        for frac in metals.values():
            assert 0.0 <= frac <= z + 1e-9
        assert sum(metals.values()) <= z + 1e-9


def test_sun_surface_cno_solar_ballpark(provider):
    """The Sun's surface C/N/O land near the known solar mass fractions (§10).

    Measured off MIST v2.5 at 1 M_sun / [Fe/H]=0 / 4.6 Gyr; solar references
    (Asplund+ 2009) in comments. MIST uses its own protosolar mixture, so this is a
    ballpark anchor, not a precise match — it pins "these are really C, N, O at
    roughly solar abundance," catching an isotope-summing or column-mapping slip.
    """
    m = provider.state_at(1.0, 0.0, SUN_AGE_YR).metals_surf
    assert m["C"] == pytest.approx(0.0026, rel=0.20)   # measured 0.00259 (solar ~0.0024)
    assert m["N"] == pytest.approx(0.0008, rel=0.20)   # measured 0.00076 (solar ~0.0007)
    assert m["O"] == pytest.approx(0.0071, rel=0.20)   # measured 0.00708 (solar ~0.0057)


def test_first_dredge_up_surface_signature(provider):
    """The Phase 4 payoff: first dredge-up enriches surface N and depletes surface C.

    As an intermediate-mass star ascends the RGB, its deepening convective envelope
    dredges CN-cycle-processed material up: surface ¹⁴N rises, ¹²C falls. We check a
    *grid-point* mass (3.0 M_sun — raw MIST, no interpolation, well clear of the
    ~2 M_sun He-ignition roughness) from ZAMS to the **first-ascent RGB tip** (max R
    among the RGB-phase rows). The tip is pulled from the RGB phase specifically, not
    the global max radius: now that the window reaches the early-AGB (whose radius can
    exceed the RGB tip for intermediate masses), the global max would land on the
    EAGB and conflate *first* dredge-up with the later second dredge-up. O is
    deliberately *not* asserted: the ON cycle is slow, so surface O barely moves here
    (measured ~0.92x) — asserting its direction would be flaky. Ratios measured at the
    RGB tip: N 3.14x up, C 0.63x down.
    """
    t = provider.track(3.0, 0.0)
    zams = t[0].metals_surf
    tip = max((s for s in t if s.phase == "RGB"), key=lambda s: s.R_rsun).metals_surf
    assert tip["N"] / zams["N"] > 1.5    # measured 3.14x — nitrogen enrichment
    assert tip["C"] / zams["C"] < 0.8    # measured 0.63x — carbon depletion


def test_surface_lithium_depletes(provider):
    """The Phase 4 visible payoff: surface lithium is *destroyed* as the star evolves.

    Lithium burns at a low temperature (~2.5e6 K), so it survives only in the thin,
    cool outer envelope. As an intermediate-mass star ascends the RGB, the deepening
    convective envelope reaches Li-burning depths and mixes surface lithium down to be
    destroyed — the famous lithium-depletion story (and the reason the §5.4 detail
    view has a log scale: at ~1e-10 of mass Li is sub-pixel on a linear axis, but its
    *relative* plunge is dramatic). We check a grid-point mass (3.0 M_sun, raw MIST)
    from ZAMS to the first-ascent RGB tip (max R among RGB rows). Measured: surface Li
    1.0e-8 -> 1.35e-10, a 74x drop. The core, meanwhile, burns Li essentially to zero
    from the start (central T is far above the Li threshold the whole main sequence),
    so core Li is negligible against surface Li at ZAMS (measured ~1e-8 of it).
    """
    t = provider.track(3.0, 0.0)
    zams, tip = t[0], max((s for s in t if s.phase == "RGB"), key=lambda s: s.R_rsun)
    assert tip.metals_surf["Li"] / zams.metals_surf["Li"] < 0.05   # measured 0.0135 (74x down)
    # the core burns Li instantly -> negligible vs the (already tiny) surface store
    assert zams.metals_core["Li"] < 1e-4 * zams.metals_surf["Li"]  # measured ~1.5e-8 ratio


def test_light_elements_deplete_in_burning_temperature_order(provider):
    """The §5.4 *light-element* view payoff: fragility tracks burning temperature.

    The fragile light elements are destroyed by proton capture, each at a higher
    temperature than the last — Li (~2.5 MK), Be (~3.5 MK) — so as the deepening RGB
    convective envelope reaches successively hotter gas it destroys them *in that
    order*: surface Li plunges hardest, Be less, and fluorine (whose destruction needs
    hotter still, and whose enrichment story is on the TPAGB we don't expose) barely
    moves — it's the stable backdrop the light view reads the depletion against (the
    role Fe plays in the per-element view). That Li > Be depletion ordering IS the
    teaching moment. Measured at 3 M_sun (grid point, raw MIST) ZAMS -> first-ascent
    RGB tip (max R among RGB rows): Li ×0.0135, Be ×0.35, F ×0.91.

    Boron is absent on purpose — MIST v2.5's only B isotope is the radioactive b8
    (~1e-83), not stable boron — so the requested "Be/B/F" panel is honestly Li/Be/F.
    """
    t = provider.track(3.0, 0.0)
    zams = t[0].metals_surf
    tip = max((s for s in t if s.phase == "RGB"), key=lambda s: s.R_rsun).metals_surf
    li_r = tip["Li"] / zams["Li"]
    be_r = tip["Be"] / zams["Be"]
    f_r = tip["F"] / zams["F"]
    assert 0.1 < be_r < 0.6      # beryllium depletes, but modestly (measured 0.35)
    assert be_r > li_r           # ...and it's more robust than lithium (burns hotter)
    assert 0.8 < f_r < 1.1       # fluorine ~preserved this side of the AGB (measured 0.91)


def test_core_cno_equilibrium_signature(provider):
    """The Sun's *core* shows CNO-cycle equilibrium: ¹⁴N built up, ¹²C burned away.

    Distinct from the surface dredge-up — this is the core itself running the CNO
    cycle, whose slowest step (¹⁴N + p) makes nitrogen pile up while carbon is
    consumed. So core N greatly exceeds surface N, and core C is far below it. This
    is exactly the contrast the detail view's independent core/surface scales exist
    to show. Measured (Sun core): C~1e-5, N~0.0043 vs surface N~0.0008.
    """
    s = provider.state_at(1.0, 0.0, SUN_AGE_YR)
    assert s.metals_core["N"] > 3.0 * s.metals_surf["N"]   # measured ~5.6x
    assert s.metals_core["C"] < 0.1 * s.metals_surf["C"]   # measured ~0.004x


def test_heavy_tracers_inert_while_cno_processes(provider):
    """The detail-view contrast: the heavy tracers barely move while CNO is rewritten.

    As a 3 M_sun star dredges up CN-cycle-processed material (surface N triples, C
    nearly halves), most heavier α / odd-Z / iron-peak tracers — Fe, Ne, Mg, Al, Si,
    P, S, Ca, Ti — are neither made nor destroyed this side of the AGB, so their
    surface fractions hold to within a few percent. That steady backdrop is exactly
    what makes the CNO motion legible in the §5.4 view. We assert a *relative* bound
    (|Δ| small vs N's 3x), not strict flatness: at 1 M_sun MIST's surface diffusion
    settles metals out and drags Fe down ~10% over the MS (real physics, measured) —
    so we use the diffusion-quiet 3 M_sun grid point, where these tracers all measure
    ~x1.00 (Fe/Al/Si/P/S/Ca/Ti x1.00, Ne x0.99).

    **Na and Li are the deliberate exceptions** and get their own assertions. Na: the
    Ne-Na cycle runs alongside CN burning, so first dredge-up enriches surface sodium
    too — measured ×1.41 at the 3 M_sun RGB tip (the real Na-O / Na-rich-giant
    physics). Li: it burns at a low temperature, so the deepening convective envelope
    *destroys* surface lithium — measured ×0.0135 (a 74x plunge) at the same tip (the
    famous lithium-depletion story). Both are data-only signals far too small to see
    on the §5.4 chart's *linear* per-region scale (Na ~3e-5, Li ~1e-10 vs O's 7e-3) —
    the log scale is what reveals them — but neither may be mislabeled "inert."
    Measured at the first-ascent RGB tip (max R among RGB rows — not the global max,
    which now lands on the early-AGB after the window was widened).
    """
    t = provider.track(3.0, 0.0)
    zams = t[0].metals_surf
    tip = max((s for s in t if s.phase == "RGB"), key=lambda s: s.R_rsun).metals_surf
    assert tip["N"] / zams["N"] > 2.0          # CNO processes hard (measured 3.14x)
    assert tip["Na"] / zams["Na"] > 1.2        # Ne-Na cycle dredge-up (measured 1.41x)
    assert tip["Li"] / zams["Li"] < 0.1        # lithium destroyed (measured 0.0135 — 74x down)
    for el in ("Fe", "Ne", "Mg", "Al", "Si", "P", "S", "Ca", "Ti"):
        assert abs(tip[el] / zams[el] - 1.0) < 0.05   # inert tracer (measured <1%)


def test_out_of_range_raises(provider):
    with pytest.raises(ParameterOutOfRange):
        provider.state_at(1000.0, 0.0, 0.0)   # mass past the grid
    feh_max = provider.parameter_ranges()["feh"]["max"]
    with pytest.raises(ParameterOutOfRange):
        provider.state_at(1.0, feh_max + 1.0, 0.0)   # [Fe/H] past the grid


# --- full grid + the .npz parse cache ----------------------------------------
def test_full_grid_loaded_by_default(provider):
    """The default provider loads the *whole* grid, not the curated subset.

    That's both the density that tames the ~2 M_sun interpolation cliff and the
    widened domain: the mass axis now reaches the grid's true 300 M_sun ceiling
    (the massive-O-star end the §10 ZAMS-spread note wants), and each metallicity
    holds well over a hundred tracks — far more than DEFAULT_MASSES' 27.
    """
    provider._ensure_loaded()
    assert all(len(g.masses) > 100 for g in provider._grids)
    rng = provider.parameter_ranges()["mass_msun"]
    assert rng["min"] == pytest.approx(0.1)
    assert rng["max"] == pytest.approx(300.0)
    # the fine spacing across the He-ignition transition is what tames the cliff
    solar = next(g for g in provider._grids if abs(g.feh) < 1e-6)
    near_2 = [float(m) for m in solar.masses if 1.8 <= m <= 2.2]
    assert max(np.diff(sorted(near_2))) <= 0.1 + 1e-9   # 1.9/2.0/2.1 present, not 1.8->2.5


def test_parsed_track_cache_roundtrip_fidelity(provider):
    """The cache must reproduce a fresh parse *exactly* — every column, bit-for-bit.

    Anchor tests can pass on a subtly-corrupt cache (a wrong offset that still
    lands on plausible numbers); this can't. Force the cache to exist (loading the
    provider writes it), then compare a from-scratch parse of one grid against what
    `_read_cache` reconstructs: array_equal on every per-row column, and the
    scalars round-tripping as exact ints / floats.
    """
    provider._ensure_loaded()   # writes each grid's _parsed_tracks.npz
    eep_dir = _find_eep_dirs(DATA_DIR)[0]

    fresh, fresh_feh, fresh_vvcrit = _parse_all_tracks(eep_dir)
    reconstructed = _read_cache(_cache_path(eep_dir), _grid_fingerprint(eep_dir))
    assert reconstructed is not None, "cache should exist and its fingerprint match"
    cached, cached_feh, cached_vvcrit = reconstructed

    assert cached_feh == fresh_feh
    assert cached_vvcrit == fresh_vvcrit
    assert len(cached) == len(fresh)
    for a, b in zip(fresh, cached):
        assert a.minit == b.minit
        assert a.zams_row == b.zams_row and isinstance(b.zams_row, int)
        assert a.track_end == b.track_end and isinstance(b.track_end, int)
        for col in _TRACK_COLS:
            assert np.array_equal(getattr(a, col), getattr(b, col)), col


def test_cache_fingerprint_rejects_stale_source(provider):
    """A changed source dir must invalidate the cache (no stale arrays served).

    The fingerprint folds in file size + mtime, so any altered fingerprint string
    makes `_read_cache` miss — the guard that forces a reparse after a re-fetch.
    """
    provider._ensure_loaded()
    eep_dir = _find_eep_dirs(DATA_DIR)[0]
    good = _grid_fingerprint(eep_dir)
    assert _read_cache(_cache_path(eep_dir), good) is not None      # matches -> hit
    assert _read_cache(_cache_path(eep_dir), good + "x") is None     # mismatch -> miss


def test_transition_mass_interpolation_reduced_not_eliminated():
    """The honest regression on the ~2 M_sun He-ignition cliff.

    The full grid's payoff here is *density*: a held-out 2.0 M_sun interpolates from
    the tight (1.9, 2.1) neighbors — a ~0.1-M_sun bracket — instead of the old
    curated 0.5-M_sun one. That genuinely helps: the whole-window median L-error
    drops well under 1%, and the hard core-He-burning (CHeB) sliver falls to ~8%
    median (vs ~23% measured on the wide 2.0/2.5 bracket). But it does NOT eliminate
    the cliff — the morphology change at the degenerate->non-degenerate He-ignition
    boundary is intrinsic, so the steepest CHeB rows stay rough (their peak L-error
    is intrinsically large and deliberately left unasserted). This pins the
    measured *improvement* so the docstring's claim can't silently rot, while
    refusing to pretend the sliver is accurate. lies_between (convexity) is the
    separate tight guarantee; this is the accuracy one.
    """
    p = MISTProvider(masses=(1.9, 2.1))     # 2.0 held out, full-density bracket
    real = _real_track("00200")             # ground truth: the real 2.0 M_sun track

    all_err, cheb_err = [], []
    for eep, st in {int(round(s.eep)): s for s in p.track(2.0, 0.0)}.items():
        row = eep - 1
        if row >= real["log_L"].size:
            continue
        L_real = 10 ** real["log_L"][row]
        e = abs(st.L_lsun - L_real) / L_real
        all_err.append(e)
        if 605 <= eep <= 706:               # the CHeB span
            cheb_err.append(e)

    # The bulk of the track stays faithful under tight bracketing (measured ~0.7%)...
    assert float(np.median(all_err)) < 0.03
    # ...and the hard CHeB sliver is bounded well below the wide-bracket ~23%
    # (measured ~8%), but is not claimed to be tight.
    assert len(cheb_err) > 40
    assert float(np.median(cheb_err)) < 0.15


def test_eep_interpolation_lies_between_neighbors(interp_provider):
    """The direct §6/§10 test: interpolate on EEP, not age.

    With the bracket pinned to {1.4, 1.6}, 1.5 M_sun is interpolated from those
    two tracks. At the EEP the interpolated star reports, its HR position must sit
    between those neighbors — and track the *real* 1.5 M_sun run, which an
    age-based (phase-blending) interpolation would not.
    """
    t14 = _real_track("00140")
    t16 = _real_track("00160")
    t15 = _real_track("00150")  # ground truth

    lo, hi = interp_provider.age_range(1.5, 0.0)
    rel_errs = []
    for frac in np.linspace(0.02, 0.98, 25):
        st = interp_provider.state_at(1.5, 0.0, lo + frac * (hi - lo))
        row = int(round(st.eep)) - 1  # EEP n == row n-1, the same phase across masses

        logL, logL14, logL16 = math.log10(st.L_lsun), t14["log_L"][row], t16["log_L"][row]
        logT, logT14, logT16 = math.log10(st.Teff_K), t14["log_Teff"][row], t16["log_Teff"][row]
        # lies between the bracketing tracks at this EEP (small slack for rounding)
        assert min(logL14, logL16) - 0.03 <= logL <= max(logL14, logL16) + 0.03
        assert min(logT14, logT16) - 0.01 <= logT <= max(logT14, logT16) + 0.01

        rel_errs.append(abs(st.L_lsun - 10 ** t15["log_L"][row]) / 10 ** t15["log_L"][row])

    # Tracks the real 1.5 track closely (median ~1%); an age-interp would not.
    assert float(np.median(rel_errs)) < 0.05


def test_cheb_interpolation_sampled_by_eep(interp_provider):
    """The widened CHeB span (EEP 605..706), sampled by *EEP*, not age.

    The lies-between/accuracy tests above sample by age, but core-He burning is a
    ~1% age-sliver at the far end of the window — almost no age sample lands there,
    so the newly-exposed region would otherwise ship untested. track() emits one
    state per EEP row, so we can walk the post-RGB-tip rows directly. 1.5 M_sun is
    interpolated from the pinned 1.4/1.6 neighbors — a *narrow* bracket on purpose:
    the transition-mass cliff (~2.0-2.1 M_sun, where even fine spacing is poor) is a
    documented limitation, not something this test pretends is accurate.
    """
    t14 = _real_track("00140")
    t16 = _real_track("00160")
    t15 = _real_track("00150")  # ground truth

    by_eep = {int(round(s.eep)): s for s in interp_provider.track(1.5, 0.0)}
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


# --- the early-AGB extension (the window now runs ZAMS -> end of EAGB) --------
def test_eagb_extends_window_and_tpagb_is_excluded(provider):
    """The window now reaches the early-AGB (EAGB, phase 4) — the second giant
    ascent — but hard-stops before the thermally-pulsing AGB (phase 5).

    The TPAGB's thermal pulses are the non-monotonic mess §6 defers (and MIST v2.5's
    weak third dredge-up wouldn't even pay off as a carbon star), so they must never
    appear. An intermediate-mass track therefore reaches EAGB, no state is ever
    TPAGB / post-AGB, and the age-window far end is a luminous, low-gravity AGB giant
    (the §7 enormous-granule payoff)."""
    for m in (1.0, 3.0):
        phases = {s.phase for s in provider.track(m, 0.0)}
        assert "EAGB" in phases                          # the newly-exposed phase
        assert not (phases & {"TPAGB", "post-AGB"})      # the deferred thermal-pulse mess
    # the far end of the age window is an EAGB giant: puffed up, cool, low-gravity
    _, hi = provider.age_range(3.0, 0.0)
    end = provider.state_at(3.0, 0.0, hi)
    zams = provider.state_at(3.0, 0.0, 0.0)
    assert end.phase == "EAGB"
    assert end.R_rsun > 10.0 * zams.R_rsun               # swollen second-ascent giant
    assert end.logg < zams.logg                          # low surface gravity


def test_eagb_interpolation_sampled_by_eep(interp_provider):
    """The newly-exposed EAGB span (EEP >= 707), sampled by *EEP*, not age.

    EAGB is, like CHeB, a thin age-sliver at the far end of the window — the
    age-sampled tests barely land on it — so we walk track()'s post-CHeB rows
    directly. 1.5 M_sun is interpolated from the pinned 1.4/1.6 neighbors (both have
    a real AGB). lies-between is structural (the blend is convex at every EEP);
    accuracy tracks the real 1.5 EAGB closely (measured median ~2%)."""
    t14 = _real_track("00140")
    t16 = _real_track("00160")
    t15 = _real_track("00150")  # ground truth

    by_eep = {int(round(s.eep)): s for s in interp_provider.track(1.5, 0.0)}
    eagb_eeps = sorted(e for e in by_eep if e >= 707)
    assert len(eagb_eeps) > 40   # the window genuinely reaches into the EAGB

    rel_errs = []
    for eep in eagb_eeps:
        st = by_eep[eep]
        row = eep - 1  # EEP n == MIST row n-1, the same phase across masses
        logL, logL14, logL16 = math.log10(st.L_lsun), t14["log_L"][row], t16["log_L"][row]
        logT, logT14, logT16 = math.log10(st.Teff_K), t14["log_Teff"][row], t16["log_Teff"][row]
        assert min(logL14, logL16) - 0.03 <= logL <= max(logL14, logL16) + 0.03
        assert min(logT14, logT16) - 0.01 <= logT <= max(logT14, logT16) + 0.01
        rel_errs.append(abs(st.L_lsun - 10 ** t15["log_L"][row]) / 10 ** t15["log_L"][row])

    assert float(np.median(rel_errs)) < 0.06   # measured ~2%


def test_eagb_interpolation_across_tpagb_boundary():
    """The honest cross-mass EAGB check at the 6.5->7 M_sun boundary.

    This is the EAGB analog of test_transition_mass_interpolation: §6 warns about
    interpolating across a phase present on one side of a mass bracket and absent on
    the other. At 6.5->7 M_sun it is the *TPAGB* that disappears (7 M_sun ends at
    TPAGB onset, with no thermal pulses) — but the *early*-AGB exists on both sides
    (7 M_sun does climb the EAGB before its track ends). So a held-out 6.5,
    interpolated from the (6.0, 7.0) neighbors, stays accurate over the EAGB rows
    (measured ~0.6% median L-error), confirming the boundary we chose is
    interpolation-safe — unlike the TPAGB we refuse to interpolate."""
    p = MISTProvider(masses=(6.0, 7.0))     # 6.5 held out, the boundary bracket
    real = _real_track("00650")             # ground truth: the real 6.5 M_sun track

    rel_errs = []
    for eep, st in {int(round(s.eep)): s for s in p.track(6.5, 0.0)}.items():
        if eep < 707:
            continue                        # EAGB rows only (the newly-exposed span)
        row = eep - 1
        if row >= real["log_L"].size:
            continue
        L_real = 10 ** real["log_L"][row]
        rel_errs.append(abs(st.L_lsun - L_real) / L_real)

    assert len(rel_errs) > 40
    assert float(np.median(rel_errs)) < 0.05   # measured ~0.6%


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


@requires_mist_multifeh
def test_iron_validates_the_feh_axis(provider):
    """Fe is the element that *is* [Fe/H]: surface iron at ZAMS must track the axis.

    [Fe/H] is by definition the log iron-to-hydrogen ratio vs solar, so the surface
    Fe mass fraction at ZAMS (before processing/diffusion bite) is the cleanest
    cross-check that the metallicity axis means what it says: it must rise
    monotonically with [Fe/H], and step by ~10^Δ[Fe/H] per grid (here 0.5 dex →
    ~10^0.5≈3.16). The ratio lands a touch *under* 10^Δ because [Fe/H] is a number
    ratio against H while we report mass fractions and X shifts with Z — so the
    tolerance is generous (±20%). Measured: Fe(+0.5)/Fe(0)=2.85, Fe(0)/Fe(-0.5)=3.05.
    """
    provider._ensure_loaded()
    fehs = sorted(float(f) for f in provider._fehs)
    fe = {}
    for feh in fehs:
        lo, _ = provider.age_range(1.0, feh)
        fe[feh] = provider.state_at(1.0, feh, lo).metals_surf["Fe"]
    # surface iron rises monotonically with [Fe/H]
    assert [fe[f] for f in fehs] == sorted(fe[f] for f in fehs)
    # ...and each grid step scales ~10^Δ[Fe/H] (generous: number- vs mass-ratio slack)
    for f_lo, f_hi in zip(fehs, fehs[1:]):
        assert fe[f_hi] / fe[f_lo] == pytest.approx(10.0 ** (f_hi - f_lo), rel=0.20)


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
