"""Reading MIST's `.track.eep` files: discovery, parsing, and the `.npz` parse cache.

The MIST-specific *file* layer of the provider — everything that knows what a
`.track.eep` looks like, which directory holds which ([Fe/H], v/vcrit) grid, and how
the parsed result is cached. It hands the rest of the package `_Track` objects and
knows nothing about interpolation.

Two things here are load-bearing and easy to break by accident:

  * **`_TRACK_COLS` order and `_grid_fingerprint` are the cache's identity.** The
    `.npz` stores each column concatenated in this exact order and is keyed by the
    fingerprint; change either and every warm cache on disk silently invalidates,
    so every grid re-parses (~20 s each) with the tests still green. `CACHE_VERSION`
    is the *deliberate* way to invalidate.
  * **`DEFAULT_MASSES` is opt-in, not the default** — the provider loads the full
    grid on disk. See the package docstring.
"""

from __future__ import annotations

import glob
import hashlib
import os
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .._vendor import read_mist_models as rmm

# --- where the grids live -----------------------------------------------------
# data/ sits at the repo root: providers/mist/parsing.py -> parents
#   [0]=mist [1]=providers [2]=star_sim [3]=backend [4]=repo root
_REPO_ROOT = Path(__file__).resolve().parents[4]
DATA_DIR = Path(os.environ.get("STAR_SIM_DATA_DIR", _REPO_ROOT / "data"))

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
# v11 (rotation Chunk 3) added the per-row **surface rotation velocity** (`surf_avg_v_rot`,
# km/s) — surfaced as `StellarState.v_rot_kms`, the rotation payoff the chunk promised.
# It is the model's own surface speed: ~0 on the non-rotating grid (honestly "not
# spinning"), and the real, *evolving* equatorial velocity on the rotating grid (high on
# the ZAMS, falling as the star expands / brakes). Unlike Mcur/Mdot (endgame-only, snapped)
# it IS interpolated across mass/[Fe/H] like the other living-state quantities. Old v10
# caches lack the column, so the bump forces one reparse.
# v12 (supernova endgame, Chunk 1) added the per-row **core masses** — `he_core_mass`,
# `c_core_mass`, `o_core_mass` (M_sun) — the progenitor inputs the core-collapse SN sibling
# needs (the ejecta/remnant split, the NS/BH cut, the pre-collapse radius is read off the
# existing `logR`). Carried on every row so the cache holds them once, but — like Mcur/Mdot
# — deliberately NOT mixed in `_grid_window`/`_blend_windows`: the endgame snaps to a single
# real track (§6), so `endgame()` reads the core masses straight off the snapped `_Track`
# and nothing downstream interpolates a *blended* core mass. Old v11 caches lack the three
# columns, so the bump forces one reparse.
CACHE_VERSION = 12
CACHE_FILENAME = "_parsed_tracks.npz"
# The per-EEP-row array columns of `_Track`, in a fixed order. Concatenated into
# one flat array each in the cache (variable-length tracks -> `lengths` index),
# so the format is pure numeric arrays — no pickle.
_TRACK_COLS = (
    "age", "logL", "logT", "logR", "logg", "Mcur", "Mdot", "Vrot",
    "HeCore", "CCore", "OCore",
    "Xs", "Ys", "Xc", "Yc",
    "Lis", "Bes", "Cs", "Ns", "Os", "Fs", "Nes", "Nas", "Mgs", "Als", "Sis", "Ps", "Ss", "Cas", "Tis", "Fes",
    "Lic", "Bec", "Cc", "Nc", "Oc", "Fc", "Nec", "Nac", "Mgc", "Alc", "Sic", "Pc", "Sc", "Cac", "Tic", "Fec",
    "phase",
)


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
    Vrot: np.ndarray       # surface rotation velocity [km/s] (surf_avg_v_rot); ~0 non-rotating
    # Core masses (the core-collapse SN progenitor inputs — see CACHE_VERSION v12). Read
    # straight off the snapped track by `endgame()`; not blended across mass/[Fe/H] (like
    # Mcur/Mdot). `OCore` is 0 at window end for very-massive φ3-enders (no explicit O core
    # built yet), so the SN sibling uses `CCore` as the CO-core proxy.
    HeCore: np.ndarray     # helium-core mass [M_sun] (he_core_mass)
    CCore: np.ndarray      # carbon-core mass [M_sun] (c_core_mass; the CO-core proxy)
    OCore: np.ndarray      # oxygen-core mass [M_sun] (o_core_mass; 0 at window end for some)
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
    """Every usable grid directory: raw `*.track.eep` files, OR a pre-baked
    `_parsed_tracks.npz` with no raw source at all (a standalone bundle fetched via
    `fetch_mist_baked.py` — see its docstring). One entry per metallicity/rotation
    grid either way.

    The two are interchangeable downstream: `_grid_fingerprint` already degrades to
    a stable version-only hash when a dir has zero `.track.eep` files, so a
    source-less cache (baked with that same fingerprint) validates and loads exactly
    like a fresh reparse would — no separate code path needed for reading it. A
    directory with raw files present is unaffected (its fingerprint still includes
    real per-file stats, so cache invalidation on a re-fetch/upgrade works as before).
    """
    hits = glob.glob(str(data_dir / "**" / "*.track.eep"), recursive=True)
    dirs = {Path(h).parent for h in hits}
    baked_hits = glob.glob(str(data_dir / "**" / CACHE_FILENAME), recursive=True)
    dirs |= {Path(h).parent for h in baked_hits}
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
        Vrot=np.asarray(e["surf_avg_v_rot"], dtype=float),
        HeCore=np.asarray(e["he_core_mass"], dtype=float),
        CCore=np.asarray(e["c_core_mass"], dtype=float),
        OCore=np.asarray(e["o_core_mass"], dtype=float),
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
