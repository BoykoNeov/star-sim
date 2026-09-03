"""MISTProvider — real MESA Isochrones & Stellar Tracks behind the §3 boundary.

This is the first *real* provider (spec §6). It reads MIST `.track.eep` files
with MIST's own parser (`_vendor/read_mist_models.py`) and turns (mass, [Fe/H],
age) into a `StellarState` exactly the way `StubProvider` did — so the swap is
invisible downstream. Everything MIST-specific (columns, file formats, the EEP
machinery) stays sealed inside this module; nothing here leaks into `state.py`
or any consumer.

The one critical gotcha (spec §6): **interpolate on EEP, not age.** MIST resamples
every track so that *row index N is the same evolutionary phase across all masses
and metallicities* (ZAMS at EEP 202, TAMS at 454, …). So both mass- and
metallicity-interpolation are done at fixed row index; age enters only through the
(interpolated) age-vs-row relation, which we invert to locate the requested age.
Interpolating raw tracks against age would blend, say, a main-sequence star with a
red giant — physical nonsense.

§6's interpolation is 2D (mass × [Fe/H]). We implement it as **blend-then-invert**:
build the fully (mass, [Fe/H])-interpolated track window first, *then* do a single
age→EEP inversion. This is not a deviation from §6's "convert age→EEP, then read
off" ordering — it is the same scheme the mass axis already used (it builds one
mass-blended `age(row)` array and inverts it once). Treating [Fe/H] identically
keeps the two axes symmetric and gives one coherent reported EEP/age, instead of
clamping/inverting each metallicity grid separately.

Scope of this cut (widen later):
  * the [Fe/H] axis spans whatever metallicity grids are on disk. With one grid
    it degenerates to a single point (the pre-[Fe/H]-axis behavior); with two or
    more it interpolates between the bracketing metallicities. Fetch more with
    `python -m star_sim.fetch_mist --feh m050` (etc.).
  * the valid (mass, [Fe/H]) domain is *not* a rectangle. Super-solar low-mass
    M-dwarfs outlive the simulated grid, so the highest metallicities lack evolved
    tracks below ~0.5 M_sun. `parameter_ranges()` exposes the bounding box;
    `mass_range(feh)` tightens it so the UI can clamp out that dead corner (§6:
    clamp/disable out-of-grid points, never extrapolate).
  * the **full** mass grid (every track on disk, 0.1 .. 300 M_sun) is loaded by
    default. Parsing ~170 MIST text tracks per metallicity is slow (~20 s/grid),
    so the parsed-and-windowed tracks are cached to a per-grid `.npz` keyed by a
    fingerprint of the source files (see _load_all_tracks); warm-cache startup is
    sub-second. `DEFAULT_MASSES` survives as an *opt-in* curated subset (pass
    `masses=...`) for fast data-light runs and for tests that need a controlled
    interpolation bracket — it is no longer the default.
  * the exposed track runs ZAMS -> end of the early-AGB (EAGB, phase 4). It
    captures the RGB tip, the post-tip drama (the He flash for low-mass stars and
    the horizontal branch / blue loop), *and* the early-AGB second ascent — a
    luminous, low-gravity red giant swelling to a few hundred R_sun (the §7
    "handful of enormous granulation cells" payoff). It stops short of the
    thermally-pulsing AGB (phase 5), the genuinely non-monotonic mess §6 says to
    defer: measured ~30-100 logL/logR reversals per track on the TPAGB (the thermal
    pulses survive MIST's EEP resampling) vs 2-4 across the whole EAGB, so cross-mass
    interpolation there would blend incoherent pulse phases. (And MIST v2.5's third
    dredge-up is too weak to deliver the carbon-star payoff — surface C/O stays ~0.3,
    never crossing 1 — that might have justified the risk.) The He flash and the EAGB
    both sit *inside* the window but are handled, not interpolated across blindly:
    MIST resamples them into strictly-increasing-age rows, so the age->EEP inversion
    is well-posed. Across the full grid the phase-4 onset is the *same* EEP row
    (~706) for every mass with a real AGB, so EAGB interpolates at fixed EEP exactly
    like CHeB. Two honesty notes: (a) for massive stars (>~8 M_sun) phase 4 is
    *zero-width* — they jump straight to phase >= 5 at one row — so they expose no
    extra EAGB rows and their last exposed row stays on CHeB or earlier; but in the
    ~15-40 M_sun band MIST does tag phase-4 rows that are physically pre-collapse
    supergiant shell burning, not a literal AGB precursor. We report MIST/FSPS's own
    phase code faithfully (the "EAGB" label is *nominal* there) rather than
    second-guessing it with a mass-dependent relabel. (b) at the 6.5->7 M_sun
    boundary the *TPAGB* disappears (7 M_sun ends at TPAGB onset, no thermal pulses)
    but the EAGB survives on both sides, so EAGB interpolation across it stays
    accurate (measured ~0.6% median L-error for a held-out 6.5) — unlike the TPAGB
    we exclude.
      Caveat (documented, not fixed here): right at the degenerate->non-degenerate
    He-ignition transition (~2.0-2.1 M_sun), CHeB morphology changes so sharply
    with mass that cross-mass interpolation is poor even at fine spacing (~12%
    median, >300% peak L-error at 2.1 M_sun on the curated grid; ~2-3% away from
    the transition). `lies_between` still holds (the blend is convex at every
    EEP, so it never loops through nonsense) — it's smoothed, not wrong. The full
    mass grid (now the default) *reduces but does not eliminate* this. At full
    density the bracket around the cliff is ~0.1 M_sun wide (1.9/2.0/2.1) instead
    of 0.5 (1.8/2.0/2.5), which roughly halves the CHeB median L-error (~8% vs ~23%
    on the wide bracket) and drops the whole-window median below 1%. But the
    steepest CHeB rows right at the He-ignition boundary stay rough (peak L-error
    still hundreds of % when 2.1 M_sun is held out): the morphology change there is
    intrinsic, so tighter bracketing smooths it rather than removing it. Denser
    DEFAULT_MASSES alone never helped — it's the bracket *width* at the cliff that
    matters, which only the full grid narrows. Measured by
    test_transition_mass_interpolation_reduced_not_eliminated.

Anchors that must hold (the §10 regression for the stub->MIST swap, with
*empirical* tolerances — see tests/test_mist_provider.py):
  state_at(1.0, 0.0, 4.6e9) ~ Sun: L~1.07, Teff~5835 K, R~1.01, logg~4.42.

The model is close to reality, but it is an approximation — and the Sun is the
clearest example. L_sun and R_sun are *defined* units: the real present-day Sun is
exactly 1.0 by construction. The anchor values above are MIST's *prediction* for a
1 M_sun, [Fe/H]=0 star at 4.6 Gyr, and it lands ~7% bright / ~1% large. Two honest
reasons, neither a bug:
  1. The grid's own solar residual. (1.0 M_sun, [Fe/H]=0) is an EXACT grid node —
     no mass or [Fe/H] interpolation happens at all — so the offset is entirely
     MIST v2.5's published p000 1.00 M_sun track (ZAMS X/Y/Z = 0.7135/0.2702/0.0164):
     it reads L=1.067, Teff=5834 K, R=1.012 at 4.567 Gyr (measured 2026-09-02). The
     same grid puts L=1.00 at [Fe/H]~+0.07 or at M~0.99 M_sun, i.e. the residual is
     a ~0.07-dex composition / ~1% mass offset in the calibration, not a blend error.
  2. Main-sequence brightening. A star's luminosity climbs as it burns H -> He
     (rising mean molecular weight -> the core contracts and heats): the Sun has
     gained ~30% L since ZAMS and still brightens ~1% per ~100 Myr. So the predicted
     L depends sharply on the age you pick. Scrub the age slider back to ~3.9-4.0 Gyr
     and the model reads L~1.0 — but that is using age to paper over the composition
     residual, not a "more correct" age. The real Sun is ~4.57 Gyr *and* L=1.0
     simultaneously; this model cannot put both at once, and we keep it faithful to
     the evolutionary physics rather than retune the age to hit the anchor.
We deliberately do NOT solar-calibrate to force L=R=1 — that would be a fake green
check (the StubProvider returned the Sun by construction; a real physics provider
should not). We report the honest residual and pin it with empirical tolerances. The
independent MESAProvider cross-check lands *its* solar run at L~1.18 at 4.6 Gyr,
equally uncalibrated — so the offset is real cross-code model spread, not a defect.
See tests/test_mist_provider.py::test_sun_anchor.
"""

# The package's importable surface is exactly what `mist.py` exposed before the
# split, so every existing `from star_sim.providers.mist import …` keeps working.
# The `X as X` form is the explicit re-export marker (a plain import of an unused
# name is what the ruff net flags); the leading-underscore names are deliberate
# white-box handles for the tests and `scripts/bake_mist_standalone.py`, not public
# API — hence they stay out of `__all__`.
from .parsing import (
    CACHE_FILENAME as CACHE_FILENAME,
    CACHE_VERSION as CACHE_VERSION,
    DATA_DIR as DATA_DIR,
    DEFAULT_MASSES as DEFAULT_MASSES,
    _TRACK_COLS as _TRACK_COLS,
    _cache_path as _cache_path,
    _feh_from_path as _feh_from_path,
    _find_eep_dir as _find_eep_dir,
    _find_eep_dirs as _find_eep_dirs,
    _grid_fingerprint as _grid_fingerprint,
    _parse_all_tracks as _parse_all_tracks,
    _read_cache as _read_cache,
    _vvcrit_from_path as _vvcrit_from_path,
    _write_cache as _write_cache,
)
from .provider import MISTProvider as MISTProvider

__all__ = ["MISTProvider", "DATA_DIR", "DEFAULT_MASSES", "CACHE_VERSION", "CACHE_FILENAME"]
