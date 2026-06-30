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
  1. Calibration residual. MIST tunes its mixing length and initial helium to
     reproduce the Sun, but only at the grid's exact protosolar composition and at
     fixed [Fe/H] nodes. An interpolated (mass, [Fe/H], age) request carries a small
     leftover offset in initial Z/Y, so the rendered "Sun" is a few percent off the
     defined point.
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

from __future__ import annotations

import glob
import hashlib
import math
import os
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from ..provider import EndgameResult, ParameterOutOfRange, ProviderDataMissing
from ..state import StellarState
from ._vendor import read_mist_models as rmm

# --- where the grids live -----------------------------------------------------
# data/ sits at the repo root: providers/mist.py -> parents
#   [0]=providers [1]=star_sim [2]=backend [3]=repo root
_REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = Path(os.environ.get("STAR_SIM_DATA_DIR", _REPO_ROOT / "data"))

_FETCH_HINT = (
    "MIST grids not found under {data_dir}. Fetch them once with:\n"
    "    python -m star_sim.fetch_mist\n"
    "(downloads the current MIST EEP tarball and extracts it; see spec §6).\n"
    "Add a second [Fe/H] for the metallicity axis, e.g. --feh m050 / --feh p050."
)

# --- MIST's `phase` column is FSPS-coded; map it to StellarState.phase --------
# PMS:-1  MS:0  SGB+RGB:2  CHeB:3  EAGB:4  TPAGB:5  post-AGB:6  WR:9
_PHASE_NAMES = {
    -1: "PMS",
    0: "MS",
    2: "RGB",          # MIST lumps subgiant + RGB into phase 2
    3: "CHeB",
    4: "EAGB",
    5: "TPAGB",
    6: "post-AGB",
    9: "WR",
}

# Opt-in curated mass sampling (all exact MIST grid points) spanning 0.1–40 M_sun.
# No longer the default — the provider loads the *full* grid now (see the module
# docstring + _load_all_tracks' .npz cache). Pass `masses=DEFAULT_MASSES` for a
# fast data-light run, or a tighter subset (e.g. (1.4, 1.6)) to force a controlled
# interpolation bracket in tests. Keeps the 0.1 and 40 endpoints the §10
# ZAMS-spread test pins.
DEFAULT_MASSES = (
    0.1, 0.15, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9,
    1.0, 1.1, 1.2, 1.4, 1.6, 1.8, 2.0, 2.5, 3.0, 4.0,
    5.0, 7.0, 10.0, 15.0, 20.0, 30.0, 40.0,
)

# --- parsed-track .npz cache --------------------------------------------------
# Parsing the raw MIST text tracks dominates startup (~20 s for one full grid).
# We cache the *windowed* per-track arrays (the only thing downstream reads) to a
# per-grid `.npz`, keyed by a fingerprint of the source files. Bump CACHE_VERSION
# whenever the parse/window logic or stored columns change, so old caches are
# rejected instead of silently feeding stale arrays.
# v2 (Phase 4) added the C/N/O surface+core columns — old v1 caches lack them, so
# the fingerprint bump forces a one-time reparse rather than feeding short arrays.
# v3 widened the element set to Ne/Mg/Fe (same reason: old v2 caches lack the six
# new columns, so the bump forces one reparse instead of serving short arrays).
# v4 widened the exposed window from end-of-CHeB (phase 3) to end-of-EAGB (phase 4),
# the early-AGB second ascent. The arrays are unchanged, but `track_end` (stored in
# the cache) was ~705 (last CHeB row) and is now ~806 (last EAGB row); a stale v3
# cache would serve the narrower window, so the bump forces one reparse that
# recomputes track_end.
# v5 widened the element set again — Si/S/Ca/Ti surface+core (same reason as v2/v3:
# old caches lack the eight new columns, so the bump forces one reparse instead of
# serving short arrays).
# v6 widened the element set once more — Na/Al/P surface+core (the odd-Z light metals
# MIST *does* track; Cr/Mn/Ni were requested too but are NOT in MIST v2.5's network,
# verified against the real track header — so they can't be added). Same reason as
# v2/v3/v5: old caches lack the six new columns, so the bump forces one reparse.
# v7 added lithium (li7) surface+core — the one *visible-story* element left: at
# ~1e-10 of mass it's far below everything else, but its surface fraction depletes
# dramatically (Sun ×0.87 over the MS, then ×~2400 at the RGB tip as the convective
# envelope reaches Li-burning depths — the famous lithium-depletion story). Single
# isotope like Ca/Ti/Fe. Same reason as v2/v3/v5/v6: old caches lack the two new
# columns, so the bump forces one reparse.
# v8 added the rest of the fragile-light-element panel — beryllium (be7+be9+be10) and
# fluorine (f17+f18+f19) surface+core — the §5.4 "light elements" view that pairs them
# with Li. NOTE on the requested set: it was Be/B/F, but **boron was dropped** — MIST
# v2.5's *only* boron isotope is `b8`, which is radioactive (β⁺ decay, t½≈0.77 s — the
# pp-III branch that makes the high-energy solar neutrinos), so `surface_b8` sits at a
# numerical-zero ~1e-83 floor, not stable boron (b10/b11 aren't in the network). A flat
# 1e-83 line is exactly the invisible floor-hugger this panel exists to avoid, so B is
# excluded (subtler than the Cr/Mn/Ni case: the column exists, but its one isotope is
# radioactive). Be and F are real: be9 dominates Be (be7 electron-captures in ~53 d,
# be10 is long-lived) and f19 dominates F (f17/f18 are short-lived) — so summing all
# isotopes (the project convention) equals the stable value. Same cache reason as the
# prior bumps: old caches lack the four new columns.
# v9 (Phase 5, WR/WD endgame) added the per-row **current mass** (`star_mass`) and
# **mass-loss rate** (`star_mdot`) columns — the inputs the stellar-endgame gateway
# needs: a white dwarf's final mass (initial->final mass relation) and a Wolf-Rayet's
# wind strength. They are carried on every row (so the cache holds them once), but
# deliberately NOT mixed in `_grid_window`/`_blend_windows`: the endgame snaps to a
# single real track and never interpolates across mass/[Fe/H] (§6), so nothing reads
# a *blended* current mass. Same cache reason as the prior bumps: old v8 caches lack
# the two new columns, so the bump forces one reparse.
# v10 (rotation axis) stored the grid's authoritative **rotation rate** (`vvcrit`,
# read from each track's header `rot` value — the same hint-vs-authoritative pattern
# the [Fe/H] axis uses) alongside the cached `feh`. No new per-row columns: rotation
# is a *grid-selection* axis (the rotating grid is a different set of tracks), so the
# provider partitions grids into vvcrit buckets and snaps between them (never blends —
# MIST publishes only {0.0, 0.4}, no third grid to interpolate toward). The bump is
# needed because the cache schema gained the scalar `vvcrit`; old v9 caches lack it.
CACHE_VERSION = 10
CACHE_FILENAME = "_parsed_tracks.npz"
# The per-EEP-row array columns of `_Track`, in a fixed order. Concatenated into
# one flat array each in the cache (variable-length tracks -> `lengths` index),
# so the format is pure numeric arrays — no pickle.
_TRACK_COLS = (
    "age", "logL", "logT", "logR", "logg", "Mcur", "Mdot",
    "Xs", "Ys", "Xc", "Yc",
    "Lis", "Bes", "Cs", "Ns", "Os", "Fs", "Nes", "Nas", "Mgs", "Als", "Sis", "Ps", "Ss", "Cas", "Tis", "Fes",
    "Lic", "Bec", "Cc", "Nc", "Oc", "Fc", "Nec", "Nac", "Mgc", "Alc", "Sic", "Pc", "Sc", "Cac", "Tic", "Fec",
    "phase",
)

# [Fe/H] exact-hit tolerance: grid values are tenths of a dex, so this only
# collapses a true grid point to a no-blend short-circuit (the Sun must hit the
# solar grid exactly, not blend across it).
_FEH_TOL = 1e-3

# v/vcrit bucket-match tolerance: MIST publishes only {0.0, 0.4}, far apart, so this
# only identifies which discrete rotation bucket a request snaps to (never a blend).
_VVCRIT_TOL = 0.05

# Surface gravity (cgs dex) above which the endgame's last row counts as a
# degenerate white dwarf. A real WD sits at log g ~7-9; normal/AGB stars never
# exceed ~5, so 7.0 is a wide, unambiguous floor. Used only to classify a track
# whose cooling ran but whose FSPS phase code we don't want to over-trust.
_WD_LOGG = 7.0


@dataclass
class _Track:
    """One mass track, reduced to just the columns a StellarState needs.

    Arrays are indexed by EEP row (row i == EEP i+1, the same phase across all
    masses *and metallicities*). Quantities are stored in the form we interpolate
    in: log for the structure columns (interp-then-exponentiate), linear for mass
    fractions.
    """

    minit: float
    age: np.ndarray        # star_age [yr]
    logL: np.ndarray       # log10(L / L_sun)
    logT: np.ndarray       # log10(Teff / K)
    logR: np.ndarray       # log10(R / R_sun)
    logg: np.ndarray       # log10 surface gravity [cgs dex]
    # Current mass + mass-loss rate (the endgame's inputs — see CACHE_VERSION v9). Not
    # blended across mass/[Fe/H]: the endgame snaps to one real track, never interpolates.
    Mcur: np.ndarray       # current mass [M_sun] (star_mass) — < minit once winds strip
    Mdot: np.ndarray       # mass-loss rate [M_sun/yr] (star_mdot; signed, <= 0)
    Xs: np.ndarray         # surface H mass fraction
    Ys: np.ndarray         # surface He mass fraction (he4 + he3)
    Xc: np.ndarray         # center H mass fraction
    Yc: np.ndarray         # center He mass fraction
    # Per-element metals (a breakdown of Z), each the sum of its isotopes. The fragile
    # *light* elements carry the depletion story (the §5.4 "light elements" view): Li,
    # Be and (the now-excluded) B burn by proton capture at increasing temperatures, so
    # the deepening convective envelope destroys them in that order — surface Li plunges
    # most (Sun ×0.87 on the MS, ×~2400 at the RGB tip), Be less (×~0.3 at 3 M_sun, it
    # burns hotter), while F survives this side of the AGB (×~0.9 — its enrichment story
    # is on the TPAGB we don't expose). (Boron is absent: MIST's only B isotope is the
    # radioactive `b8` at ~1e-83 — see CACHE_VERSION v8.) The CNO trio carries the
    # burning story: the surface ones the first-dredge-up signature (N up, C down), the
    # core ones the CNO-cycle / He-burning products. Ne/Mg/Al/Si/P/S/Ca/Ti are α / odd-Z
    # / iron-peak tracers (mostly along for the ride this side of the AGB — except Na,
    # which the Ne-Na cycle dredges up at the surface of intermediate-mass giants,
    # measured ×1.4 at 3 M_sun); Fe is the inert tracer that just marks the input [Fe/H]
    # (modulo MIST's surface diffusion). All feed the §5.4 detail/light views. Field
    # names carry a trailing `s` (surface) / `c` (core) — so `Sc` is sulfur-core (not
    # scandium), `Pc` is phosphorus-core, and `Fs`/`Fc` are fluorine (vs `Fes`/`Fec` iron).
    Lis: np.ndarray        # surface lithium   (li7)
    Bes: np.ndarray        # surface beryllium (be7 + be9 + be10; be9 dominates)
    Cs: np.ndarray         # surface carbon    (c12 + c13)
    Ns: np.ndarray         # surface nitrogen  (n13 + n14 + n15)
    Os: np.ndarray         # surface oxygen    (o14 + o15 + o16 + o17 + o18)
    Fs: np.ndarray         # surface fluorine  (f17 + f18 + f19; f19 dominates)
    Nes: np.ndarray        # surface neon      (ne18 + ne19 + ne20 + ne21 + ne22)
    Nas: np.ndarray        # surface sodium    (na21 + na22 + na23 + na24)
    Mgs: np.ndarray        # surface magnesium (mg23 + mg24 + mg25 + mg26)
    Als: np.ndarray        # surface aluminium (al25 + al26 + al27)
    Sis: np.ndarray        # surface silicon   (si27 + si28 + si29 + si30)
    Ps: np.ndarray         # surface phosphorus (p30 + p31)
    Ss: np.ndarray         # surface sulfur    (s31 + s32 + s33 + s34)
    Cas: np.ndarray        # surface calcium   (ca40)
    Tis: np.ndarray        # surface titanium  (ti48)
    Fes: np.ndarray        # surface iron      (fe56)
    Lic: np.ndarray        # center lithium    (li7 — ~0; the core burns it instantly)
    Bec: np.ndarray        # center beryllium  (be7 + be9 + be10)
    Cc: np.ndarray         # center carbon
    Nc: np.ndarray         # center nitrogen
    Oc: np.ndarray         # center oxygen
    Fc: np.ndarray         # center fluorine   (`Fc` = fluorine-core, not iron — see `Fec`)
    Nec: np.ndarray        # center neon
    Nac: np.ndarray        # center sodium
    Mgc: np.ndarray        # center magnesium
    Alc: np.ndarray        # center aluminium
    Sic: np.ndarray        # center silicon
    Pc: np.ndarray         # center phosphorus
    Sc: np.ndarray         # center sulfur     (`Sc` = sulfur-core, not scandium)
    Cac: np.ndarray        # center calcium
    Tic: np.ndarray        # center titanium
    Fec: np.ndarray        # center iron
    phase: np.ndarray      # FSPS phase code (float)
    zams_row: int          # first row on the MS (phase >= 0)
    track_end: int         # last exposed row = end of early-AGB (EAGB, phase 4)


@dataclass
class _Grid:
    """All mass tracks at one [Fe/H] — the unit the metallicity axis interpolates.

    `masses` is ascending and parallel to `tracks`; `zams_row` is shared by every
    track in the grid (the EEP-alignment invariant, asserted at load).
    """

    feh: float
    vvcrit: float
    masses: np.ndarray
    tracks: list[_Track]
    zams_row: int


@dataclass
class _Axis:
    """All [Fe/H] grids at one rotation rate — the unit the rotation axis snaps to.

    Rotation (`vvcrit`) is a *grid-selection* axis, not an interpolation axis: MIST
    publishes only {0.0, 0.4}, so the provider partitions its grids into one `_Axis`
    per rotation rate and **snaps** between them (no third grid to interpolate
    toward), while the [Fe/H] axis still interpolates *within* an axis exactly as
    before. Each axis carries its own bracketing state (the `fehs` array, the mass
    bounding box, the shared ZAMS row) so the feh helpers operate on whichever axis
    the request selected — and the default vvcrit=0.0 axis reproduces the
    pre-rotation behavior bit-for-bit.
    """

    vvcrit: float
    grids: list[_Grid]          # ascending by feh
    fehs: np.ndarray
    mass_min: float
    mass_max: float
    zams_row: int


def _feh_from_path(path: str) -> float | None:
    """`.../feh_m050_afe_p0_vvcrit0.0/eeps` -> -0.5  (a cheap filter hint).

    Only used to *select* which metallicity dirs to load; the authoritative
    [Fe/H] each grid reports comes from the track files' `abun` block.
    """
    m = re.search(r"feh_([mp])(\d{3})", str(path))
    if not m:
        return None
    val = int(m.group(2)) / 100.0
    return -val if m.group(1) == "m" else val


def _vvcrit_from_path(path: str) -> float | None:
    """`.../feh_p000_afe_p0_vvcrit0.4/eeps` -> 0.4  (a cheap selection hint).

    Mirrors `_feh_from_path`: only a *hint* for grouping dirs into rotation
    buckets. The authoritative v/vcrit comes from each track's header `rot` value
    (see `_parse_track_file`). Defaults to 0.0 (non-rotating) when the dir name
    carries no vvcrit token, so a pre-rotation data layout still reads as 0.0.
    """
    m = re.search(r"vvcrit([\d.]+)", str(path))
    if not m:
        return None
    return float(m.group(1))


def _find_eep_dirs(data_dir: Path) -> list[Path]:
    """Every directory holding `*.track.eep` files, one per metallicity grid."""
    hits = glob.glob(str(data_dir / "**" / "*.track.eep"), recursive=True)
    dirs = {Path(h).parent for h in hits}
    return sorted(dirs)


def _find_eep_dir(data_dir: Path) -> Path | None:
    """The first directory holding `*.track.eep` files (kept for tests/conftest)."""
    dirs = _find_eep_dirs(data_dir)
    return dirs[0] if dirs else None


def _phase_window(phase: np.ndarray) -> tuple[int, int] | None:
    """(zams_row, track_end) for a track's FSPS-coded `phase` column, or None.

    ZAMS = first row on the MS (phase 0). The exposed window runs to the end of the
    **early-AGB** (EAGB, phase 4) — i.e. the last row *before* the thermally-pulsing
    AGB (phase >= 5). So it spans MS -> subgiant -> RGB -> RGB tip -> (the He flash,
    for low-mass stars) -> horizontal branch / blue loop -> the early-AGB second
    ascent, and stops short of the TPAGB thermal pulses (phase 5), the genuinely
    non-monotonic mess §6 says to defer (measured: ~30-100 logL/logR reversals per
    track on the TPAGB vs 2-4 across the whole EAGB — and MIST v2.5's third
    dredge-up is too weak to even produce the carbon-star payoff that might justify
    the risk; see the module docstring).

    The EAGB is safe to expose where CHeB already was: MIST resamples it (and the He
    flash) into strictly-increasing-age rows, so the age->EEP inversion never folds;
    and across the full grid the phase-4 onset is the *same* EEP row (~706) for every
    mass that has a real AGB, so cross-mass interpolation stays at fixed EEP. Massive
    stars (>~8 M_sun) have a *zero-width* phase 4 — they jump straight to phase >= 5
    at one row — so this >= 5 threshold leaves their window unchanged (their last
    exposed row stays on CHeB or earlier), exactly as the old >= 4 threshold did.

    We can't just take `phase <= 4`: MIST tags pre-MS with -1 and caps some tracks
    with a -9 sentinel row, both of which are <= 4 but not what we want. Low-mass
    tracks that never ignite He end on the MS/RGB; use their last real row (dropping
    the sentinel).
    """
    ge = np.where(phase >= 0)[0]
    if ge.size == 0:
        return None
    zams = int(ge[0])
    after = phase[zams:]
    tpagb = np.where(after >= 5)[0]           # first thermally-pulsing-AGB row (past EAGB)
    if tpagb.size:
        track_end = zams + int(tpagb[0]) - 1
    else:
        valid = np.where(after >= 0)[0]       # never reaches the TPAGB; drop -9 sentinel
        track_end = zams + int(valid[-1])
    if track_end <= zams:
        return None
    return zams, track_end


def _parse_track_file(path: str) -> tuple[_Track, float, float] | None:
    """Parse one `.track.eep` into a windowed `_Track` + its grid ([Fe/H], v/vcrit).

    Returns None if the track has no usable MS->CHeB block (low-mass tracks with
    no post-ZAMS row, or a malformed file). Both [Fe/H] (the `abun` block) and v/vcrit
    (the header `rot` value) are read from the file itself — the authoritative values,
    not the dir-name hints.
    """
    eep = rmm.EEP(path, verbose=False)
    e = eep.eeps
    phase = np.asarray(e["phase"], dtype=float)
    win = _phase_window(phase)
    if win is None:
        return None
    zams_row, track_end = win

    def elem(prefix: str, *isotopes: str) -> np.ndarray:
        """Total element mass fraction = sum of its isotope columns."""
        return sum(np.asarray(e[prefix + iso], dtype=float) for iso in isotopes)

    track = _Track(
        minit=float(eep.minit),
        age=np.asarray(e["star_age"], dtype=float),
        logL=np.asarray(e["log_L"], dtype=float),
        logT=np.asarray(e["log_Teff"], dtype=float),
        logR=np.asarray(e["log_R"], dtype=float),
        logg=np.asarray(e["log_g"], dtype=float),
        Mcur=np.asarray(e["star_mass"], dtype=float),
        Mdot=np.asarray(e["star_mdot"], dtype=float),
        Xs=np.asarray(e["surface_h1"], dtype=float),
        Ys=np.asarray(e["surface_he4"], dtype=float)
        + np.asarray(e["surface_he3"], dtype=float),
        Xc=np.asarray(e["center_h1"], dtype=float),
        Yc=np.asarray(e["center_he4"], dtype=float)
        + np.asarray(e["center_he3"], dtype=float),
        Lis=elem("surface_", "li7"),
        Bes=elem("surface_", "be7", "be9", "be10"),
        Cs=elem("surface_", "c12", "c13"),
        Ns=elem("surface_", "n13", "n14", "n15"),
        Os=elem("surface_", "o14", "o15", "o16", "o17", "o18"),
        Fs=elem("surface_", "f17", "f18", "f19"),
        Nes=elem("surface_", "ne18", "ne19", "ne20", "ne21", "ne22"),
        Nas=elem("surface_", "na21", "na22", "na23", "na24"),
        Mgs=elem("surface_", "mg23", "mg24", "mg25", "mg26"),
        Als=elem("surface_", "al25", "al26", "al27"),
        Sis=elem("surface_", "si27", "si28", "si29", "si30"),
        Ps=elem("surface_", "p30", "p31"),
        Ss=elem("surface_", "s31", "s32", "s33", "s34"),
        Cas=elem("surface_", "ca40"),
        Tis=elem("surface_", "ti48"),
        Fes=elem("surface_", "fe56"),
        Lic=elem("center_", "li7"),
        Bec=elem("center_", "be7", "be9", "be10"),
        Cc=elem("center_", "c12", "c13"),
        Nc=elem("center_", "n13", "n14", "n15"),
        Oc=elem("center_", "o14", "o15", "o16", "o17", "o18"),
        Fc=elem("center_", "f17", "f18", "f19"),
        Nec=elem("center_", "ne18", "ne19", "ne20", "ne21", "ne22"),
        Nac=elem("center_", "na21", "na22", "na23", "na24"),
        Mgc=elem("center_", "mg23", "mg24", "mg25", "mg26"),
        Alc=elem("center_", "al25", "al26", "al27"),
        Sic=elem("center_", "si27", "si28", "si29", "si30"),
        Pc=elem("center_", "p30", "p31"),
        Sc=elem("center_", "s31", "s32", "s33", "s34"),
        Cac=elem("center_", "ca40"),
        Tic=elem("center_", "ti48"),
        Fec=elem("center_", "fe56"),
        phase=phase,
        zams_row=zams_row,
        track_end=track_end,
    )
    return track, float(eep.abun["[Fe/H]"]), float(eep.rot)


def _parse_all_tracks(eep_dir: Path) -> tuple[list[_Track], float, float]:
    """Parse *every* track in one metallicity dir (the full grid). The slow path.

    Returns (tracks sorted ascending by mass, grid [Fe/H], grid v/vcrit). Skips any
    file with no usable window. This is what the `.npz` cache front-ends — call it
    only on a cache miss.
    """
    tracks: list[_Track] = []
    feh: float | None = None
    vvcrit: float | None = None
    for f in sorted(glob.glob(str(eep_dir / "*.track.eep"))):
        res = _parse_track_file(f)
        if res is None:
            continue
        track, fh, vc = res
        if feh is None:
            feh = fh
        if vvcrit is None:
            vvcrit = vc
        tracks.append(track)
    tracks.sort(key=lambda t: t.minit)
    return tracks, (feh if feh is not None else 0.0), (vvcrit if vvcrit is not None else 0.0)


def _grid_fingerprint(eep_dir: Path) -> str:
    """A cheap content fingerprint of a grid dir's source tracks.

    Hashes the sorted (name, size, mtime_ns) of every `*.track.eep`, plus
    CACHE_VERSION. Any re-fetch / re-extract changes mtime+size; any change to the
    parse logic bumps the version — either invalidates the cache. We deliberately
    *don't* read file contents (too slow for ~170 files); size+mtime is the same
    signal build tools trust.
    """
    h = hashlib.sha256()
    h.update(f"v{CACHE_VERSION}".encode())
    for f in sorted(glob.glob(str(eep_dir / "*.track.eep"))):
        st = os.stat(f)
        h.update(os.path.basename(f).encode())
        h.update(f"{st.st_size}:{st.st_mtime_ns}".encode())
    return h.hexdigest()


def _cache_path(eep_dir: Path) -> Path:
    return eep_dir / CACHE_FILENAME


def _write_cache(path: Path, tracks: list[_Track], feh: float, vvcrit: float, fingerprint: str) -> None:
    """Write the parsed grid to a per-grid `.npz` atomically (temp + os.replace).

    Variable-length tracks are stored as one concatenated flat array per column
    plus a `lengths` index — pure numeric arrays, no pickle. The atomic rename
    means an interrupted write (or a concurrent first run) never leaves a
    half-written cache that the fingerprint would wrongly accept.
    """
    data: dict[str, np.ndarray] = {
        "fingerprint": np.array(fingerprint),
        "feh": np.array(float(feh)),
        "vvcrit": np.array(float(vvcrit)),
        "minit": np.array([t.minit for t in tracks], dtype=np.float64),
        "zams_row": np.array([t.zams_row for t in tracks], dtype=np.int64),
        "track_end": np.array([t.track_end for t in tracks], dtype=np.int64),
        "lengths": np.array([t.age.size for t in tracks], dtype=np.int64),
    }
    for col in _TRACK_COLS:
        data[col] = np.concatenate([getattr(t, col) for t in tracks]).astype(np.float64)
    tmp = path.parent / (path.name + ".tmp")
    with open(tmp, "wb") as fh:
        np.savez_compressed(fh, **data)
    os.replace(tmp, path)


def _read_cache(path: Path, fingerprint: str) -> tuple[list[_Track], float, float] | None:
    """Reconstruct the parsed grid from its `.npz`, or None on miss/mismatch.

    Returns None (caller reparses) when the file is absent, the fingerprint
    doesn't match the current source files, or the archive is unreadable/corrupt.
    """
    if not path.is_file():
        return None
    try:
        with np.load(path) as npz:
            if str(npz["fingerprint"]) != fingerprint:
                return None
            feh = float(npz["feh"])
            vvcrit = float(npz["vvcrit"])
            minit = npz["minit"]
            zams = npz["zams_row"]
            tend = npz["track_end"]
            lengths = npz["lengths"]
            cols = {c: npz[c] for c in _TRACK_COLS}  # materialize before the file closes
    except Exception:
        return None

    offsets = np.concatenate([[0], np.cumsum(lengths)]).astype(np.int64)
    tracks: list[_Track] = []
    for i in range(int(minit.size)):
        a, b = int(offsets[i]), int(offsets[i + 1])
        sliced = {c: cols[c][a:b].copy() for c in _TRACK_COLS}  # own contiguous memory
        tracks.append(
            _Track(
                minit=float(minit[i]),
                zams_row=int(zams[i]),
                track_end=int(tend[i]),
                **sliced,
            )
        )
    return tracks, feh, vvcrit


def _load_all_tracks(eep_dir: Path) -> tuple[list[_Track], float, float]:
    """Full grid for one metallicity dir, from the `.npz` cache if it's fresh.

    Cache hit -> sub-second. Miss (no cache, stale fingerprint, or corrupt file)
    -> reparse every track (~20 s) and write the cache back (best-effort: a failed
    write never blocks serving). Returns (tracks, [Fe/H], v/vcrit).
    """
    fingerprint = _grid_fingerprint(eep_dir)
    path = _cache_path(eep_dir)
    cached = _read_cache(path, fingerprint)
    if cached is not None:
        return cached

    tracks, feh, vvcrit = _parse_all_tracks(eep_dir)
    if tracks:
        try:
            _write_cache(path, tracks, feh, vvcrit, fingerprint)
        except Exception:
            pass  # cache is an optimization; never let a write error break a load
    return tracks, feh, vvcrit


def _load_grid(eep_dir: Path, want_masses: tuple[float, ...] | None) -> _Grid | None:
    """Load one metallicity directory into a `_Grid`, or None if it's unusable.

    Loads the full parsed grid (cached), then keeps either *all* masses
    (`want_masses is None`, the default) or the subset nearest each requested mass
    (opt-in, snap-to-grid). Either way it checks the EEP-alignment invariant (one
    shared ZAMS row) before handing the grid downstream.
    """
    all_tracks, feh, vvcrit = _load_all_tracks(eep_dir)
    if not all_tracks:
        return None

    if want_masses is None:
        tracks = list(all_tracks)            # already ascending by mass
    else:
        by_mass = {round(t.minit, 2): t for t in all_tracks}
        grid_masses = np.array(sorted(by_mass))
        chosen: dict[float, _Track] = {}
        for want in want_masses:
            nearest = float(grid_masses[int(np.argmin(np.abs(grid_masses - want)))])
            chosen[round(nearest, 2)] = by_mass[round(nearest, 2)]
        tracks = [chosen[m] for m in sorted(chosen)]

    if len(tracks) < 2:
        return None

    # Row-index alignment is the load-bearing assumption (§6): ZAMS must sit at
    # the same row for every mass, or cross-mass interpolation is garbage.
    zams_rows = {t.zams_row for t in tracks}
    if len(zams_rows) != 1:
        raise ProviderDataMissing(
            f"MIST tracks in {eep_dir} disagree on the ZAMS row ({sorted(zams_rows)}); "
            "EEP alignment is broken — refusing to interpolate across phases."
        )

    return _Grid(
        feh=float(feh),
        vvcrit=float(vvcrit),
        masses=np.array([t.minit for t in tracks]),
        tracks=tracks,
        zams_row=tracks[0].zams_row,
    )


class MISTProvider:
    """A `StellarStateProvider` (structurally — see ../provider.py) backed by MIST.

    Construction is cheap and never touches disk: the grids are loaded lazily on
    first use so that importing the API in a fresh, data-less checkout doesn't
    explode (it raises an *actionable* `ProviderDataMissing` only when state is
    actually requested).
    """

    name = "MISTProvider"

    def __init__(
        self,
        data_dir: Path | None = None,
        masses: tuple[float, ...] | None = None,
        fehs: tuple[float, ...] | None = None,
    ) -> None:
        self._data_dir = Path(data_dir) if data_dir is not None else DATA_DIR
        # None (default) = load the full grid on disk. A tuple opts into a curated
        # subset (snap-to-grid) — DEFAULT_MASSES for a fast data-light run, or a
        # tight bracket like (1.4, 1.6) to force interpolation in a test.
        self._want_masses = tuple(masses) if masses is not None else None
        # Optional filter: load only these metallicity grids (nearest dir-name
        # match). None = load every grid on disk. Used by tests to hold one
        # metallicity out as ground truth, and by the API to curate the axis.
        self._want_fehs = tuple(fehs) if fehs is not None else None
        self._loaded = False
        # One `_Axis` per rotation rate (vvcrit bucket). The default axis (0.0, or
        # the lowest available) is what every existing query uses; a rotating axis
        # is selected only when a request passes vvcrit != 0.0.
        self._axes: dict[float, _Axis] = {}
        self._vvcrits: np.ndarray | None = None
        self._default_vvcrit: float = 0.0

    # -- lazy data load --------------------------------------------------------
    def _ensure_loaded(self) -> None:
        if self._loaded:
            return

        eep_dirs = _find_eep_dirs(self._data_dir)
        if not eep_dirs:
            raise ProviderDataMissing(_FETCH_HINT.format(data_dir=self._data_dir))

        if self._want_fehs is not None:
            eep_dirs = [
                d for d in eep_dirs
                if (fh := _feh_from_path(d)) is not None
                and any(math.isclose(fh, w, abs_tol=_FEH_TOL) for w in self._want_fehs)
            ]

        grids: list[_Grid] = []
        for d in eep_dirs:
            grid = _load_grid(d, self._want_masses)
            if grid is not None:
                grids.append(grid)

        if not grids:
            raise ProviderDataMissing(_FETCH_HINT.format(data_dir=self._data_dir))

        # Partition grids into rotation buckets (snap axis), then build one `_Axis`
        # per bucket. Keying by vvcrit is what un-collides two grids at the same
        # [Fe/H] but different rotation (e.g. the solar vvcrit0.0 and vvcrit0.4 dirs
        # both report [Fe/H]=0.0): without it they'd form a degenerate duplicate
        # point on the metallicity axis and silently contaminate the interpolation.
        buckets: dict[float, list[_Grid]] = {}
        for g in grids:
            buckets.setdefault(round(g.vvcrit, 3), []).append(g)

        self._axes = {vc: self._build_axis(vc, gs) for vc, gs in buckets.items()}
        self._vvcrits = np.array(sorted(self._axes))
        # Default to non-rotating (0.0) if present — so the live provider is
        # unchanged — else the lowest rotation rate on disk.
        self._default_vvcrit = (
            0.0 if any(math.isclose(vc, 0.0, abs_tol=_VVCRIT_TOL) for vc in self._axes)
            else float(self._vvcrits[0])
        )
        self._loaded = True

    @staticmethod
    def _build_axis(vvcrit: float, grids: list[_Grid]) -> _Axis:
        """Assemble one rotation bucket's [Fe/H] grids into an `_Axis`.

        Sorts by [Fe/H] and re-checks the EEP-alignment invariant *within the
        bucket* (row N is the same phase for every grid, or the [Fe/H] blend is
        garbage). The mass bounding box is the union across the bucket's grids; a
        specific [Fe/H] can be narrower — see `mass_range()`.
        """
        grids = sorted(grids, key=lambda g: g.feh)
        zams_rows = {g.zams_row for g in grids}
        if len(zams_rows) != 1:
            raise ProviderDataMissing(
                f"MIST metallicity grids (vvcrit={vvcrit}) disagree on the ZAMS row "
                f"({sorted(zams_rows)}); EEP alignment is broken — refusing to "
                "interpolate across [Fe/H]."
            )
        return _Axis(
            vvcrit=float(vvcrit),
            grids=grids,
            fehs=np.array([g.feh for g in grids]),
            mass_min=float(min(g.masses[0] for g in grids)),
            mass_max=float(max(g.masses[-1] for g in grids)),
            zams_row=grids[0].zams_row,
        )

    def _axis(self, vvcrit: float | None = None) -> _Axis:
        """Snap a requested rotation rate to the nearest available `_Axis`.

        `None` (the default for every existing call site) selects the default axis
        (non-rotating). Rotation is a discrete 2-point grid, so we snap, never
        interpolate (§6): there is no third grid to blend toward.
        """
        self._ensure_loaded()
        assert self._vvcrits is not None
        want = self._default_vvcrit if vvcrit is None else float(vvcrit)
        key = float(self._vvcrits[int(np.argmin(np.abs(self._vvcrits - want)))])
        return self._axes[key]

    @property
    def _grids(self) -> list[_Grid]:
        """The default (non-rotating) axis's [Fe/H] grids.

        Back-compat for white-box callers/tests that introspected `_grids` before
        the rotation axis split the load into per-vvcrit `_Axis` buckets. The live
        spine selects an axis explicitly via `_axis(vvcrit)`; this is just the
        default-axis view.
        """
        return self._axis().grids

    @property
    def _fehs(self) -> np.ndarray:
        """The default (non-rotating) axis's [Fe/H] values (back-compat, see `_grids`)."""
        return self._axis().fehs

    # -- UI metadata -----------------------------------------------------------
    def parameter_ranges(self) -> dict:
        self._ensure_loaded()
        assert self._vvcrits is not None
        ax = self._axis()                        # the default (non-rotating) axis
        return {
            # Bounding box; mass_range(feh) tightens it where the grid is sparse.
            "mass_msun": {"min": ax.mass_min, "max": ax.mass_max},
            # A single point when only one grid is on disk (slider pinned); a real
            # span once a second metallicity is fetched.
            "feh": {"min": float(ax.fehs[0]), "max": float(ax.fehs[-1])},
            # The rotation rates on disk (≥2 ⇒ the frontend can offer the toggle;
            # the per-(mass,feh) honesty gate is Chunk 2). mass/feh ranges are the
            # default axis's — the rotating grid shares the same coverage.
            "vvcrit": {"available": [float(v) for v in self._vvcrits]},
        }

    def mass_range(self, feh: float, vvcrit: float = 0.0) -> tuple[float, float]:
        """Valid mass span at this [Fe/H] — the intersection of the bracketing
        grids' mass coverage. Narrower than the bounding box where a metallicity
        lacks evolved low-mass tracks (the dead corner). Raises if [Fe/H] itself
        is off-grid (no extrapolation, §6). `vvcrit` snaps to a rotation bucket."""
        ax = self._axis(vvcrit)
        self._check_feh(ax, feh)
        j_lo, j_hi, _ = self._bracket_feh(ax, feh)
        g_lo, g_hi = ax.grids[j_lo], ax.grids[j_hi]
        lo = max(float(g_lo.masses[0]), float(g_hi.masses[0]))
        hi = min(float(g_lo.masses[-1]), float(g_hi.masses[-1]))
        return lo, hi

    def age_range(self, mass: float, feh: float, vvcrit: float = 0.0) -> tuple[float, float]:
        ax = self._axis(vvcrit)
        self._check_mass_feh(ax, mass, feh)
        age_win = self._interp_window(ax, mass, feh)["age"]
        return (float(age_win[0]), float(age_win[-1]))

    # -- the one method that matters ------------------------------------------
    def state_at(self, mass: float, feh: float, age_yr: float, vvcrit: float = 0.0) -> StellarState:
        ax = self._axis(vvcrit)
        self._check_mass_feh(ax, mass, feh)

        win = self._interp_window(ax, mass, feh)
        age_win = win["age"]
        # age never extrapolates past the exposed window (ZAMS .. end of CHeB).
        age = float(min(max(age_yr, age_win[0]), age_win[-1]))

        # Invert the monotonic age(row) relation to a fractional row position,
        # then read every quantity off at that same position. THIS is the §6
        # "convert age to EEP, then interpolate there" step.
        rows = np.arange(age_win.size, dtype=float)
        frac = float(np.interp(age, age_win, rows))
        return self._state_from_row(ax, win, frac, mass, feh)

    def track(self, mass: float, feh: float, vvcrit: float = 0.0) -> list[StellarState]:
        """Every exposed EEP row at (mass, [Fe/H]) as a StellarState (§3).

        No age inversion here: the window's rows already *are* the EEPs (ZAMS ..
        end of CHeB), so we emit one state per integer row. Age is strictly
        increasing across this span — including the He flash, which MIST resolves
        into monotonically-aging rows — so the list is cleanly ordered by EEP for
        the HR track and the composition panel's EEP axis. `vvcrit` snaps to a
        rotation bucket (default 0.0 = the non-rotating grid).
        """
        ax = self._axis(vvcrit)
        self._check_mass_feh(ax, mass, feh)
        win = self._interp_window(ax, mass, feh)
        n = int(win["age"].size)
        return [self._state_from_row(ax, win, float(i), mass, feh) for i in range(n)]

    # -- the stellar endgame (WR/WD gateway) — snap-to-track, never interpolate (§6) --
    def endgame(self, mass: float, feh: float, vvcrit: float = 0.0) -> EndgameResult:
        """The post-window endgame at (mass, [Fe/H]) — see the Protocol docstring.

        Snaps to the nearest real grid track (no cross-mass/[Fe/H] interpolation),
        classifies it from its FSPS phase content, and exposes the rows *past* the
        normal `track()` window (everything after `track_end`) as StellarStates:

          * WR  — the track reaches the Wolf-Rayet phase (FSPS 9). states = the WR
                  wind sub-track (the stripped, ~10^5 K rows).
          * WD  — the track reaches post-AGB (FSPS 6) or a degenerate endpoint
                  (final log g > _WD_LOGG). states = thermal pulses (TPAGB, FSPS 5)
                  -> the ~100 kK central star -> cold-cinder cooling (post-AGB,
                  FSPS 6), the full scrubbable sequence (the pulses are coherent
                  because we snapped to one real star, never blended — §6).
          * SN  — the track just ends at TPAGB onset (one FSPS-5 row, no cooling and
                  no WR): the core-collapse / uncertain-fate dead end we do NOT
                  render (states = []; the lone pre-collapse supergiant row is a
                  low-gravity artifact, not a renderable endgame). At solar this is
                  ~7 M_sun and up — just above where MIST stops modeling cooling, in
                  the genuinely-uncertain super-AGB / electron-capture regime.
          * none — no exposed endgame at all (e.g. a low-mass star still alive at the
                  grid's end, whose `track_end` is already its last row). states = [].
        """
        ax = self._axis(vvcrit)
        j = self._snap_feh_index(ax, feh)           # raises if [Fe/H] is off-grid (§6)
        grid = ax.grids[j]
        masses = grid.masses
        if not (masses[0] <= mass <= masses[-1]):
            raise ParameterOutOfRange(
                f"mass {mass} M_sun outside the MIST grid "
                f"[{masses[0]}, {masses[-1]}] at [Fe/H]={grid.feh}"
            )
        track = grid.tracks[int(np.argmin(np.abs(masses - mass)))]
        snapped_mass, snapped_feh = float(track.minit), float(grid.feh)

        phase = track.phase
        r_last = int(np.where(phase >= 0)[0][-1])   # last real row (drop the -9 sentinel)
        r0 = track.track_end + 1                    # first row past the normal window
        final_mass = float(track.Mcur[r_last])
        wr_threshold = self._wr_threshold(grid)

        if bool(np.any(phase == 9)):
            etype = "WR"
        elif bool(np.any(phase == 6)) or float(track.logg[r_last]) > _WD_LOGG:
            etype = "WD"
        elif r0 <= r_last:                          # ends at TPAGB onset, no cooling
            etype = "SN"
        else:                                       # track_end is already the last row
            etype = "none"

        states: list[StellarState] = []
        if etype in ("WR", "WD") and r0 <= r_last:
            win = {col: getattr(track, col)[r0 : r_last + 1] for col in _TRACK_COLS}
            states = [
                self._state_from_row(
                    ax, win, float(i), snapped_mass, snapped_feh, eep_origin=r0
                )
                for i in range(int(win["age"].size))
            ]

        return EndgameResult(
            type=etype,
            mass_init_msun=snapped_mass,
            feh_init=snapped_feh,
            final_mass_msun=final_mass,
            wr_threshold_msun=wr_threshold,
            states=states,
        )

    def _snap_feh_index(self, axis: _Axis, feh: float) -> int:
        """Index of the axis [Fe/H] nearest `feh` (the endgame snaps, never blends).

        Raises if `feh` is outside the axis's [Fe/H] span — no extrapolation (§6) —
        then snaps in-range to the nearest grid metallicity (its true value is what
        the result reports, mirroring the snapped-mass honesty)."""
        self._check_feh(axis, feh)
        return int(np.argmin(np.abs(axis.fehs - feh)))

    @staticmethod
    def _wr_threshold(grid: _Grid) -> float | None:
        """Lowest mass in `grid` whose track reaches the WR phase (FSPS 9), or None.

        Derived by scanning the grid — never a hardcoded mass cut: the WR onset
        shifts with metallicity (more metals -> stronger winds -> strips at lower
        mass) and is even slightly non-monotonic at low Z, so the gateway must read
        it off the data. `grid.tracks` is ascending by mass, so the first hit is the
        threshold."""
        for t in grid.tracks:
            if bool(np.any(t.phase == 9)):
                return float(t.minit)
        return None

    def _state_from_row(
        self,
        axis: _Axis,
        win: dict,
        frac: float,
        mass: float,
        feh: float,
        eep_origin: int | None = None,
    ) -> StellarState:
        """Read a StellarState off the interpolated window at fractional row `frac`.

        The single place a window becomes a StellarState — shared by `state_at`
        (frac from the age inversion), `track` (frac = each integer row), and
        `endgame` (an unblended single-track slice past the window), so they can
        never drift, and so `win`'s provider-internal keys never escape past this
        boundary (§3). `eep_origin` is the absolute MIST row of `win`'s first row:
        the normal window starts at the axis's ZAMS row (the default); the endgame
        passes its own origin (the first post-window row) so its states report their
        true, continuing EEP rather than restarting at ZAMS.
        """
        rows = np.arange(win["age"].size, dtype=float)
        age = float(np.interp(frac, rows, win["age"]))

        L = 10.0 ** np.interp(frac, rows, win["logL"])
        teff = 10.0 ** np.interp(frac, rows, win["logT"])
        r = 10.0 ** np.interp(frac, rows, win["logR"])
        logg = float(np.interp(frac, rows, win["logg"]))

        x_s = float(np.interp(frac, rows, win["Xs"]))
        y_s = float(np.interp(frac, rows, win["Ys"]))
        z_s = max(0.0, 1.0 - x_s - y_s)
        x_c = float(np.interp(frac, rows, win["Xc"]))
        y_c = float(np.interp(frac, rows, win["Yc"]))
        z_c = max(0.0, 1.0 - x_c - y_c)

        # Per-element metals (a breakdown of Z). float() each — raw np.float64 in the
        # dict would survive asdict() but trip JSON serialization at the API edge.
        metals_surf = {
            "Li": float(np.interp(frac, rows, win["Lis"])),
            "Be": float(np.interp(frac, rows, win["Bes"])),
            "C": float(np.interp(frac, rows, win["Cs"])),
            "N": float(np.interp(frac, rows, win["Ns"])),
            "O": float(np.interp(frac, rows, win["Os"])),
            "F": float(np.interp(frac, rows, win["Fs"])),
            "Ne": float(np.interp(frac, rows, win["Nes"])),
            "Na": float(np.interp(frac, rows, win["Nas"])),
            "Mg": float(np.interp(frac, rows, win["Mgs"])),
            "Al": float(np.interp(frac, rows, win["Als"])),
            "Si": float(np.interp(frac, rows, win["Sis"])),
            "P": float(np.interp(frac, rows, win["Ps"])),
            "S": float(np.interp(frac, rows, win["Ss"])),
            "Ca": float(np.interp(frac, rows, win["Cas"])),
            "Ti": float(np.interp(frac, rows, win["Tis"])),
            "Fe": float(np.interp(frac, rows, win["Fes"])),
        }
        metals_core = {
            "Li": float(np.interp(frac, rows, win["Lic"])),
            "Be": float(np.interp(frac, rows, win["Bec"])),
            "C": float(np.interp(frac, rows, win["Cc"])),
            "N": float(np.interp(frac, rows, win["Nc"])),
            "O": float(np.interp(frac, rows, win["Oc"])),
            "F": float(np.interp(frac, rows, win["Fc"])),
            "Ne": float(np.interp(frac, rows, win["Nec"])),
            "Na": float(np.interp(frac, rows, win["Nac"])),
            "Mg": float(np.interp(frac, rows, win["Mgc"])),
            "Al": float(np.interp(frac, rows, win["Alc"])),
            "Si": float(np.interp(frac, rows, win["Sic"])),
            "P": float(np.interp(frac, rows, win["Pc"])),
            "S": float(np.interp(frac, rows, win["Sc"])),
            "Ca": float(np.interp(frac, rows, win["Cac"])),
            "Ti": float(np.interp(frac, rows, win["Tic"])),
            "Fe": float(np.interp(frac, rows, win["Fec"])),
        }

        # phase is a discrete label: take the row we're nearest to.
        phase_code = int(round(float(win["phase"][int(round(frac))])))
        phase = _PHASE_NAMES.get(phase_code, f"phase{phase_code}")

        # EEP is the (1-based) row number; row r == EEP r+1 across all masses. The
        # normal window's origin is the axis's ZAMS row; the endgame passes its own.
        origin = axis.zams_row if eep_origin is None else eep_origin
        eep = float(origin + frac + 1.0)

        # visual proxy (§7), explicitly evocative: cool stars more chromospherically
        # active than hot ones. `v_rot_kms` stays None for now even on a rotating
        # axis — surfacing the selected rotation as a real value is the payoff chunk
        # (Chunk 3); the axis already reshapes the track, which is the science.
        activity = max(0.0, min(1.0, (6500.0 - teff) / (6500.0 - 3000.0)))

        return StellarState(
            age_yr=age,
            eep=eep,
            phase=phase,
            mass_init_msun=mass,
            feh_init=feh,
            L_lsun=float(L),
            Teff_K=float(teff),
            R_rsun=float(r),
            logg=logg,
            X_surf=x_s, Y_surf=y_s, Z_surf=z_s,
            X_core=x_c, Y_core=y_c, Z_core=z_c,
            metals_surf=metals_surf,
            metals_core=metals_core,
            v_rot_kms=None,
            activity=activity,
        )

    # -- EEP-fixed 2D (mass × [Fe/H]) interpolation (the core of §6) -----------
    def _interp_window(self, axis: _Axis, mass: float, feh: float) -> dict:
        """Fully (mass, [Fe/H])-interpolated track window over [ZAMS .. end of CHeB].

        Outer loop is metallicity (§6 step 1): bracket [Fe/H] within the selected
        rotation `axis`, mass-interpolate each bracketing grid at fixed EEP (step 2),
        then blend the two grids (step 4) — again at fixed row index, never across
        age. Rotation never enters here: it picked the axis, and within a vvcrit
        bucket the blend is identical to the pre-rotation behavior. Returns
        per-quantity arrays on a common row grid; `state_at`/`age_range` invert
        `age` once.
        """
        j_lo, j_hi, wz = self._bracket_feh(axis, feh)
        win_lo = self._grid_window(axis.grids[j_lo], mass)
        if j_lo == j_hi or wz == 0.0:
            return win_lo
        win_hi = self._grid_window(axis.grids[j_hi], mass)
        return _blend_windows(win_lo, win_hi, wz)

    def _grid_window(self, grid: _Grid, mass: float) -> dict:
        """Mass-interpolated window for one metallicity grid (fixed-EEP, no age)."""
        i_lo, i_hi, w = _bracket(grid.masses, mass)
        lo, hi = grid.tracks[i_lo], grid.tracks[i_hi]

        r0 = grid.zams_row
        # Common window: stop at the earlier of the two track ends (end of CHeB,
        # and never run off the shorter track). Keeps both endpoints on real,
        # aligned rows.
        r1 = min(lo.track_end, hi.track_end, lo.age.size - 1, hi.age.size - 1)
        sl = slice(r0, r1 + 1)

        def mix(a: np.ndarray, b: np.ndarray) -> np.ndarray:
            return (1.0 - w) * a[sl] + w * b[sl]

        # age interpolated in log space (it spans many decades vs mass).
        age = 10.0 ** ((1.0 - w) * np.log10(lo.age[sl]) + w * np.log10(hi.age[sl]))

        return {
            "age": age,
            "logL": mix(lo.logL, hi.logL),
            "logT": mix(lo.logT, hi.logT),
            "logR": mix(lo.logR, hi.logR),
            "logg": mix(lo.logg, hi.logg),
            "Xs": mix(lo.Xs, hi.Xs),
            "Ys": mix(lo.Ys, hi.Ys),
            "Xc": mix(lo.Xc, hi.Xc),
            "Yc": mix(lo.Yc, hi.Yc),
            "Lis": mix(lo.Lis, hi.Lis),
            "Bes": mix(lo.Bes, hi.Bes),
            "Cs": mix(lo.Cs, hi.Cs),
            "Ns": mix(lo.Ns, hi.Ns),
            "Os": mix(lo.Os, hi.Os),
            "Fs": mix(lo.Fs, hi.Fs),
            "Nes": mix(lo.Nes, hi.Nes),
            "Nas": mix(lo.Nas, hi.Nas),
            "Mgs": mix(lo.Mgs, hi.Mgs),
            "Als": mix(lo.Als, hi.Als),
            "Sis": mix(lo.Sis, hi.Sis),
            "Ps": mix(lo.Ps, hi.Ps),
            "Ss": mix(lo.Ss, hi.Ss),
            "Cas": mix(lo.Cas, hi.Cas),
            "Tis": mix(lo.Tis, hi.Tis),
            "Fes": mix(lo.Fes, hi.Fes),
            "Lic": mix(lo.Lic, hi.Lic),
            "Bec": mix(lo.Bec, hi.Bec),
            "Cc": mix(lo.Cc, hi.Cc),
            "Nc": mix(lo.Nc, hi.Nc),
            "Oc": mix(lo.Oc, hi.Oc),
            "Fc": mix(lo.Fc, hi.Fc),
            "Nec": mix(lo.Nec, hi.Nec),
            "Nac": mix(lo.Nac, hi.Nac),
            "Mgc": mix(lo.Mgc, hi.Mgc),
            "Alc": mix(lo.Alc, hi.Alc),
            "Sic": mix(lo.Sic, hi.Sic),
            "Pc": mix(lo.Pc, hi.Pc),
            "Sc": mix(lo.Sc, hi.Sc),
            "Cac": mix(lo.Cac, hi.Cac),
            "Tic": mix(lo.Tic, hi.Tic),
            "Fec": mix(lo.Fec, hi.Fec),
            # phase is discrete: take it from the nearer of the two tracks.
            "phase": (lo.phase if w < 0.5 else hi.phase)[sl],
        }

    def _bracket_feh(self, axis: _Axis, feh: float) -> tuple[int, int, float]:
        """Indices of the two axis [Fe/H] values bracketing `feh`, and the weight.

        Mirrors `_bracket` (mass) but uses `isclose` for the exact-hit test:
        grid metallicities are tenths of a dex, and the Sun ([Fe/H]=0) must
        short-circuit to the solar grid with no blend (the §10 anchor).
        """
        fehs = axis.fehs
        if fehs.size == 1:
            return 0, 0, 0.0
        if feh <= fehs[0]:
            return 0, 0, 0.0
        if feh >= fehs[-1]:
            n = fehs.size - 1
            return n, n, 0.0
        i_hi = int(np.searchsorted(fehs, feh, side="left"))
        if math.isclose(float(fehs[i_hi]), feh, abs_tol=_FEH_TOL):
            return i_hi, i_hi, 0.0
        i_lo = i_hi - 1
        if math.isclose(float(fehs[i_lo]), feh, abs_tol=_FEH_TOL):
            return i_lo, i_lo, 0.0
        w = (feh - fehs[i_lo]) / (fehs[i_hi] - fehs[i_lo])
        return i_lo, i_hi, float(w)

    # -- validation ------------------------------------------------------------
    def _check_feh(self, axis: _Axis, feh: float) -> None:
        feh_lo, feh_hi = float(axis.fehs[0]), float(axis.fehs[-1])
        if feh_lo - _FEH_TOL <= feh <= feh_hi + _FEH_TOL:
            return
        if feh_lo == feh_hi:
            raise ParameterOutOfRange(
                f"[Fe/H] {feh} not on the single-metallicity grid (only "
                f"{feh_lo} available — fetch another with "
                "`python -m star_sim.fetch_mist --feh m050`)"
            )
        raise ParameterOutOfRange(
            f"[Fe/H] {feh} outside the MIST grid [{feh_lo}, {feh_hi}]"
        )

    def _check_mass_feh(self, axis: _Axis, mass: float, feh: float) -> None:
        # feh first (mass_range needs a valid [Fe/H]); then the per-[Fe/H] span,
        # which excludes the dead low-mass / super-solar corner.
        m_lo, m_hi = self.mass_range(feh, axis.vvcrit)
        if not (m_lo <= mass <= m_hi):
            raise ParameterOutOfRange(
                f"mass {mass} M_sun outside the MIST grid at [Fe/H]={feh} "
                f"[{m_lo}, {m_hi}] (evolved tracks may be absent for low-mass "
                "stars at high metallicity)"
            )


def _bracket(values: np.ndarray, x: float) -> tuple[int, int, float]:
    """Indices of the two `values` entries bracketing `x`, and the blend weight.

    Exact grid hit -> (i, i, 0.0). Otherwise w in (0,1) is the linear position
    from the lower to the upper bracket. `values` must be ascending.
    """
    if x <= values[0]:
        return 0, 0, 0.0
    if x >= values[-1]:
        n = values.size - 1
        return n, n, 0.0
    i_hi = int(np.searchsorted(values, x, side="left"))
    if values[i_hi] == x:
        return i_hi, i_hi, 0.0
    i_lo = i_hi - 1
    w = (x - values[i_lo]) / (values[i_hi] - values[i_lo])
    return i_lo, i_hi, float(w)


def _blend_windows(a: dict, b: dict, w: float) -> dict:
    """Blend two metallicity windows at fixed row index (the §6 outer loop).

    Truncate to the shorter window so both endpoints stay on real, aligned rows
    (row i is the same EEP in both). Structure quantities blend linearly in the
    [Fe/H] weight; `age` blends in log space (like the mass axis); `phase` is
    discrete and taken from the nearer grid. Blending logL etc. linearly makes the
    result a convex combination of the two grids at every EEP — so it *provably*
    lies between them on the HR diagram (the §10 lies-between property).
    """
    n = min(a["age"].size, b["age"].size)
    out: dict = {
        "age": 10.0 ** ((1.0 - w) * np.log10(a["age"][:n]) + w * np.log10(b["age"][:n])),
        "phase": (a["phase"] if w < 0.5 else b["phase"])[:n],
    }
    for k in ("logL", "logT", "logR", "logg",
              "Xs", "Ys", "Xc", "Yc",
              "Lis", "Bes", "Cs", "Ns", "Os", "Fs", "Nes", "Nas", "Mgs", "Als", "Sis", "Ps", "Ss", "Cas", "Tis", "Fes",
              "Lic", "Bec", "Cc", "Nc", "Oc", "Fc", "Nec", "Nac", "Mgc", "Alc", "Sic", "Pc", "Sc", "Cac", "Tic", "Fec"):
        out[k] = (1.0 - w) * a[k][:n] + w * b[k][:n]
    return out
