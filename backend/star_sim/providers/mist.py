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
  * a curated mass subset spanning the grid, for fast load. (A precomputed .npz
    cache, and full-grid loading, are a deferred optimization — see DEFAULT_MASSES.)
  * the exposed track runs ZAMS -> RGB tip (the §11 "sweet spot"). Capping at the
    RGB tip keeps the user away from the He-flash / AGB phases that are
    non-monotonic and messy to interpolate even in MIST.

Anchors that must hold (the §10 regression for the stub->MIST swap, with
*empirical* tolerances — see tests/test_mist_provider.py):
  state_at(1.0, 0.0, 4.6e9) ~ Sun: L~1.07, Teff~5835 K, R~1.01, logg~4.42.
"""

from __future__ import annotations

import glob
import math
import os
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from ..provider import ParameterOutOfRange, ProviderDataMissing
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

# Curated mass sampling (all are exact MIST grid points) spanning 0.1–40 M_sun.
# Kept small so startup parses ~2 dozen files per metallicity, not ~130. Widen /
# add an .npz cache later; the §10 ZAMS-spread test needs the 0.1 and 40 endpoints.
DEFAULT_MASSES = (
    0.1, 0.15, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9,
    1.0, 1.1, 1.2, 1.4, 1.6, 1.8, 2.0, 2.5, 3.0, 4.0,
    5.0, 7.0, 10.0, 15.0, 20.0, 30.0, 40.0,
)

# [Fe/H] exact-hit tolerance: grid values are tenths of a dex, so this only
# collapses a true grid point to a no-blend short-circuit (the Sun must hit the
# solar grid exactly, not blend across it).
_FEH_TOL = 1e-3


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
    Xs: np.ndarray         # surface H mass fraction
    Ys: np.ndarray         # surface He mass fraction (he4 + he3)
    Xc: np.ndarray         # center H mass fraction
    Yc: np.ndarray         # center He mass fraction
    phase: np.ndarray      # FSPS phase code (float)
    zams_row: int          # first row on the MS (phase >= 0)
    rgb_end: int           # last row at or before the RGB tip (phase <= 2)


@dataclass
class _Grid:
    """All mass tracks at one [Fe/H] — the unit the metallicity axis interpolates.

    `masses` is ascending and parallel to `tracks`; `zams_row` is shared by every
    track in the grid (the EEP-alignment invariant, asserted at load).
    """

    feh: float
    masses: np.ndarray
    tracks: list[_Track]
    zams_row: int


def _mass_from_filename(path: str) -> float:
    """`00100M.track.eep` -> 1.0  (MIST encodes mass*100 in 5 zero-padded digits)."""
    m = re.match(r"(\d+)M\.track\.eep$", os.path.basename(path))
    if not m:
        raise ValueError(f"unrecognized MIST track filename: {path}")
    return int(m.group(1)) / 100.0


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
    """(zams_row, rgb_end) for a track's FSPS-coded `phase` column, or None.

    ZAMS = first row on the MS (phase 0). RGB tip = the last row of the
    contiguous MS+SGB+RGB block (phase 0,2) *before* core-He ignition (phase 3).
    We can't just take `phase <= 2`: MIST tags pre-MS with -1 and caps some
    tracks with a -9 sentinel row, both of which are <= 2 but not what we want.
    Low-mass tracks that never ignite He end on the MS/RGB; use their last real
    row (dropping the sentinel).
    """
    ge = np.where(phase >= 0)[0]
    if ge.size == 0:
        return None
    zams = int(ge[0])
    after = phase[zams:]
    cheb = np.where(after >= 3)[0]            # first core-He-burning row
    if cheb.size:
        rgb_end = zams + int(cheb[0]) - 1
    else:
        valid = np.where(after >= 0)[0]       # never ignites He; drop -9 sentinel
        rgb_end = zams + int(valid[-1])
    if rgb_end <= zams:
        return None
    return zams, rgb_end


def _load_grid(eep_dir: Path, want_masses: tuple[float, ...]) -> _Grid | None:
    """Load one metallicity directory into a `_Grid`, or None if it's unusable.

    Snaps each requested mass to the nearest grid point actually on disk, parses
    those tracks, clips each to its [ZAMS .. RGB tip] window, and checks the
    EEP-alignment invariant (one shared ZAMS row).
    """
    available = {
        round(_mass_from_filename(f), 2): f
        for f in glob.glob(str(eep_dir / "*.track.eep"))
    }
    if not available:
        return None
    grid_masses = np.array(sorted(available))

    chosen: dict[float, str] = {}
    for want in want_masses:
        nearest = float(grid_masses[int(np.argmin(np.abs(grid_masses - want)))])
        chosen[nearest] = available[round(nearest, 2)]

    tracks: list[_Track] = []
    feh: float | None = None
    for mass in sorted(chosen):
        eep = rmm.EEP(chosen[mass], verbose=False)
        e = eep.eeps
        if feh is None:
            feh = float(eep.abun["[Fe/H]"])
        phase = np.asarray(e["phase"], dtype=float)
        win = _phase_window(phase)
        if win is None:
            continue  # no usable MS->RGB block; skip defensively
        zams_row, rgb_end = win
        tracks.append(
            _Track(
                minit=float(eep.minit),
                age=np.asarray(e["star_age"], dtype=float),
                logL=np.asarray(e["log_L"], dtype=float),
                logT=np.asarray(e["log_Teff"], dtype=float),
                logR=np.asarray(e["log_R"], dtype=float),
                logg=np.asarray(e["log_g"], dtype=float),
                Xs=np.asarray(e["surface_h1"], dtype=float),
                Ys=np.asarray(e["surface_he4"], dtype=float)
                + np.asarray(e["surface_he3"], dtype=float),
                Xc=np.asarray(e["center_h1"], dtype=float),
                Yc=np.asarray(e["center_he4"], dtype=float)
                + np.asarray(e["center_he3"], dtype=float),
                phase=phase,
                zams_row=zams_row,
                rgb_end=rgb_end,
            )
        )

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
        feh=float(feh) if feh is not None else 0.0,
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
        masses: tuple[float, ...] = DEFAULT_MASSES,
        fehs: tuple[float, ...] | None = None,
    ) -> None:
        self._data_dir = Path(data_dir) if data_dir is not None else DATA_DIR
        self._want_masses = tuple(masses)
        # Optional filter: load only these metallicity grids (nearest dir-name
        # match). None = load every grid on disk. Used by tests to hold one
        # metallicity out as ground truth, and by the API to curate the axis.
        self._want_fehs = tuple(fehs) if fehs is not None else None
        self._loaded = False
        self._grids: list[_Grid] = []
        self._fehs: np.ndarray | None = None
        self._mass_lo: float = 0.0
        self._mass_hi: float = 0.0
        self._zams_row: int = 0

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

        grids.sort(key=lambda g: g.feh)

        # EEP alignment must hold across metallicity too, not just across mass:
        # row N is the same phase for every grid, or the [Fe/H] blend is garbage.
        zams_rows = {g.zams_row for g in grids}
        if len(zams_rows) != 1:
            raise ProviderDataMissing(
                f"MIST metallicity grids disagree on the ZAMS row ({sorted(zams_rows)}); "
                "EEP alignment is broken — refusing to interpolate across [Fe/H]."
            )

        self._grids = grids
        self._fehs = np.array([g.feh for g in grids])
        # Bounding box for the UI's static mass slider (the UNION across grids).
        # The valid span at a *specific* [Fe/H] can be narrower — see mass_range():
        # super-solar low-mass M-dwarfs outlive the simulated grid, so the highest
        # metallicities lack evolved tracks below ~0.5 M_sun. That dead corner is
        # excluded per-[Fe/H], not by shrinking the whole box (which would discard
        # the §10 red dwarf we *do* have at solar/sub-solar [Fe/H]).
        self._mass_min = float(min(g.masses[0] for g in grids))
        self._mass_max = float(max(g.masses[-1] for g in grids))
        self._zams_row = grids[0].zams_row
        self._loaded = True

    # -- UI metadata -----------------------------------------------------------
    def parameter_ranges(self) -> dict:
        self._ensure_loaded()
        assert self._fehs is not None
        return {
            # Bounding box; mass_range(feh) tightens it where the grid is sparse.
            "mass_msun": {"min": self._mass_min, "max": self._mass_max},
            # A single point when only one grid is on disk (slider pinned); a real
            # span once a second metallicity is fetched.
            "feh": {"min": float(self._fehs[0]), "max": float(self._fehs[-1])},
        }

    def mass_range(self, feh: float) -> tuple[float, float]:
        """Valid mass span at this [Fe/H] — the intersection of the bracketing
        grids' mass coverage. Narrower than the bounding box where a metallicity
        lacks evolved low-mass tracks (the dead corner). Raises if [Fe/H] itself
        is off-grid (no extrapolation, §6)."""
        self._ensure_loaded()
        assert self._fehs is not None
        self._check_feh(feh)
        j_lo, j_hi, _ = self._bracket_feh(feh)
        g_lo, g_hi = self._grids[j_lo], self._grids[j_hi]
        lo = max(float(g_lo.masses[0]), float(g_hi.masses[0]))
        hi = min(float(g_lo.masses[-1]), float(g_hi.masses[-1]))
        return lo, hi

    def age_range(self, mass: float, feh: float) -> tuple[float, float]:
        self._ensure_loaded()
        self._check_mass_feh(mass, feh)
        age_win = self._interp_window(mass, feh)["age"]
        return (float(age_win[0]), float(age_win[-1]))

    # -- the one method that matters ------------------------------------------
    def state_at(self, mass: float, feh: float, age_yr: float) -> StellarState:
        self._ensure_loaded()
        self._check_mass_feh(mass, feh)

        win = self._interp_window(mass, feh)
        age_win = win["age"]
        # age never extrapolates past the exposed window (ZAMS .. RGB tip).
        age = float(min(max(age_yr, age_win[0]), age_win[-1]))

        # Invert the monotonic age(row) relation to a fractional row position,
        # then read every quantity off at that same position. THIS is the §6
        # "convert age to EEP, then interpolate there" step.
        rows = np.arange(age_win.size, dtype=float)
        frac = float(np.interp(age, age_win, rows))
        return self._state_from_row(win, frac, mass, feh)

    def track(self, mass: float, feh: float) -> list[StellarState]:
        """Every exposed EEP row at (mass, [Fe/H]) as a StellarState (§3).

        No age inversion here: the window's rows already *are* the EEPs (ZAMS ..
        RGB tip), so we emit one state per integer row. The window is monotonic
        and pre-He-flash over this span, so the list is cleanly ordered for the HR
        track and the composition panel's EEP axis.
        """
        self._ensure_loaded()
        self._check_mass_feh(mass, feh)
        win = self._interp_window(mass, feh)
        n = int(win["age"].size)
        return [self._state_from_row(win, float(i), mass, feh) for i in range(n)]

    def _state_from_row(
        self, win: dict, frac: float, mass: float, feh: float
    ) -> StellarState:
        """Read a StellarState off the interpolated window at fractional row `frac`.

        The single place a window becomes a StellarState — shared by `state_at`
        (frac from the age inversion) and `track` (frac = each integer row) so the
        two can never drift, and so `win`'s provider-internal keys never escape
        past this boundary (§3).
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

        # phase is a discrete label: take the row we're nearest to.
        phase_code = int(round(float(win["phase"][int(round(frac))])))
        phase = _PHASE_NAMES.get(phase_code, f"phase{phase_code}")

        # EEP is the (1-based) row number; row r == EEP r+1 across all masses.
        eep = float(self._zams_row + frac + 1.0)

        # visual proxy (§7), explicitly evocative: cool stars more chromospherically
        # active than hot ones. v/vcrit=0.0 grid -> no modeled rotation.
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
            v_rot_kms=None,
            activity=activity,
        )

    # -- EEP-fixed 2D (mass × [Fe/H]) interpolation (the core of §6) -----------
    def _interp_window(self, mass: float, feh: float) -> dict:
        """Fully (mass, [Fe/H])-interpolated track window over [ZAMS .. RGB tip].

        Outer loop is metallicity (§6 step 1): bracket [Fe/H], mass-interpolate
        each bracketing grid at fixed EEP (step 2), then blend the two grids
        (step 4) — again at fixed row index, never across age. Returns per-quantity
        arrays on a common row grid; `state_at`/`age_range` invert `age` once.
        """
        j_lo, j_hi, wz = self._bracket_feh(feh)
        win_lo = self._grid_window(self._grids[j_lo], mass)
        if j_lo == j_hi or wz == 0.0:
            return win_lo
        win_hi = self._grid_window(self._grids[j_hi], mass)
        return _blend_windows(win_lo, win_hi, wz)

    def _grid_window(self, grid: _Grid, mass: float) -> dict:
        """Mass-interpolated window for one metallicity grid (fixed-EEP, no age)."""
        i_lo, i_hi, w = _bracket(grid.masses, mass)
        lo, hi = grid.tracks[i_lo], grid.tracks[i_hi]

        r0 = grid.zams_row
        # Common window: stop at the earlier of the two RGB tips (and never run
        # off the shorter track). Keeps both endpoints on real, aligned rows.
        r1 = min(lo.rgb_end, hi.rgb_end, lo.age.size - 1, hi.age.size - 1)
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
            # phase is discrete: take it from the nearer of the two tracks.
            "phase": (lo.phase if w < 0.5 else hi.phase)[sl],
        }

    def _bracket_feh(self, feh: float) -> tuple[int, int, float]:
        """Indices of the two grid [Fe/H] values bracketing `feh`, and the weight.

        Mirrors `_bracket` (mass) but uses `isclose` for the exact-hit test:
        grid metallicities are tenths of a dex, and the Sun ([Fe/H]=0) must
        short-circuit to the solar grid with no blend (the §10 anchor).
        """
        assert self._fehs is not None
        fehs = self._fehs
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
    def _check_feh(self, feh: float) -> None:
        assert self._fehs is not None
        feh_lo, feh_hi = float(self._fehs[0]), float(self._fehs[-1])
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

    def _check_mass_feh(self, mass: float, feh: float) -> None:
        # feh first (mass_range needs a valid [Fe/H]); then the per-[Fe/H] span,
        # which excludes the dead low-mass / super-solar corner.
        m_lo, m_hi = self.mass_range(feh)
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
    for k in ("logL", "logT", "logR", "logg", "Xs", "Ys", "Xc", "Yc"):
        out[k] = (1.0 - w) * a[k][:n] + w * b[k][:n]
    return out
