"""MISTProvider — real MESA Isochrones & Stellar Tracks behind the §3 boundary.

This is the first *real* provider (spec §6). It reads MIST `.track.eep` files
with MIST's own parser (`_vendor/read_mist_models.py`) and turns (mass, [Fe/H],
age) into a `StellarState` exactly the way `StubProvider` did — so the swap is
invisible downstream. Everything MIST-specific (columns, file formats, the EEP
machinery) stays sealed inside this module; nothing here leaks into `state.py`
or any consumer.

The one critical gotcha (spec §6): **interpolate on EEP, not age.** MIST resamples
every track so that *row index N is the same evolutionary phase across all masses*
(ZAMS at EEP 202, TAMS at 454, …). So mass-interpolation is done at fixed row
index; age enters only through the (mass-interpolated) age-vs-row relation, which
we invert to locate the requested age. Interpolating raw tracks against age would
blend, say, a main-sequence star with a red giant — physical nonsense.

Scope of this v1 cut (deliberately narrow; widen later):
  * one [Fe/H] (whatever grid is on disk — solar by default). No metallicity
    blend yet, so the [Fe/H] axis is effectively a single point.
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
    "(downloads the current MIST EEP tarball and extracts it; see spec §6)."
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
# Kept small so startup parses ~2 dozen files, not ~130. Widen / add an .npz
# cache later; the §10 ZAMS-spread test needs the 0.1 and 40 endpoints present.
DEFAULT_MASSES = (
    0.1, 0.15, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9,
    1.0, 1.1, 1.2, 1.4, 1.6, 1.8, 2.0, 2.5, 3.0, 4.0,
    5.0, 7.0, 10.0, 15.0, 20.0, 30.0, 40.0,
)


@dataclass
class _Track:
    """One mass track, reduced to just the columns a StellarState needs.

    Arrays are indexed by EEP row (row i == EEP i+1, the same phase across all
    masses). Quantities are stored in the form we interpolate in: log for the
    structure columns (interp-then-exponentiate), linear for mass fractions.
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


def _mass_from_filename(path: str) -> float:
    """`00100M.track.eep` -> 1.0  (MIST encodes mass*100 in 5 zero-padded digits)."""
    m = re.match(r"(\d+)M\.track\.eep$", os.path.basename(path))
    if not m:
        raise ValueError(f"unrecognized MIST track filename: {path}")
    return int(m.group(1)) / 100.0


def _find_eep_dir(data_dir: Path) -> Path | None:
    """The directory holding `*.track.eep` files, searched recursively under data/."""
    hits = glob.glob(str(data_dir / "**" / "*.track.eep"), recursive=True)
    if not hits:
        return None
    return Path(hits[0]).parent


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


class MISTProvider:
    """A `StellarStateProvider` (structurally — see ../provider.py) backed by MIST.

    Construction is cheap and never touches disk: the grid is loaded lazily on
    first use so that importing the API in a fresh, data-less checkout doesn't
    explode (it raises an *actionable* `ProviderDataMissing` only when state is
    actually requested).
    """

    name = "MISTProvider"

    def __init__(
        self,
        data_dir: Path | None = None,
        masses: tuple[float, ...] = DEFAULT_MASSES,
    ) -> None:
        self._data_dir = Path(data_dir) if data_dir is not None else DATA_DIR
        self._want_masses = tuple(masses)
        self._loaded = False
        self._masses: np.ndarray | None = None
        self._tracks: list[_Track] = []
        self._feh: float = 0.0
        self._zams_row: int = 0

    # -- lazy data load --------------------------------------------------------
    def _ensure_loaded(self) -> None:
        if self._loaded:
            return

        eep_dir = _find_eep_dir(self._data_dir)
        if eep_dir is None:
            raise ProviderDataMissing(_FETCH_HINT.format(data_dir=self._data_dir))

        available = {
            round(_mass_from_filename(f), 2): f
            for f in glob.glob(str(eep_dir / "*.track.eep"))
        }
        # Snap each requested mass to the nearest grid point actually on disk.
        chosen: dict[float, str] = {}
        grid = np.array(sorted(available))
        for want in self._want_masses:
            nearest = float(grid[int(np.argmin(np.abs(grid - want)))])
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
            raise ProviderDataMissing(_FETCH_HINT.format(data_dir=self._data_dir))

        # Row-index alignment is the load-bearing assumption (§6): ZAMS must sit
        # at the same row for every mass, or cross-mass interpolation is garbage.
        zams_rows = {t.zams_row for t in tracks}
        if len(zams_rows) != 1:
            raise ProviderDataMissing(
                f"MIST tracks disagree on the ZAMS row ({sorted(zams_rows)}); "
                "EEP alignment is broken — refusing to interpolate across phases."
            )

        self._tracks = tracks
        self._masses = np.array([t.minit for t in tracks])
        self._feh = float(feh) if feh is not None else 0.0
        self._zams_row = tracks[0].zams_row
        self._loaded = True

    # -- UI metadata -----------------------------------------------------------
    def parameter_ranges(self) -> dict:
        self._ensure_loaded()
        assert self._masses is not None
        return {
            "mass_msun": {"min": float(self._masses[0]), "max": float(self._masses[-1])},
            # one [Fe/H] for now: a single point, so the UI's feh slider is pinned.
            "feh": {"min": self._feh, "max": self._feh},
        }

    def age_range(self, mass: float, feh: float) -> tuple[float, float]:
        self._ensure_loaded()
        self._check_mass_feh(mass, feh)
        age_win = self._interp_window(mass)["age"]
        return (float(age_win[0]), float(age_win[-1]))

    # -- the one method that matters ------------------------------------------
    def state_at(self, mass: float, feh: float, age_yr: float) -> StellarState:
        self._ensure_loaded()
        self._check_mass_feh(mass, feh)

        win = self._interp_window(mass)
        age_win = win["age"]
        # age never extrapolates past the exposed window (ZAMS .. RGB tip).
        age = float(min(max(age_yr, age_win[0]), age_win[-1]))

        # Invert the monotonic age(row) relation to a fractional row position,
        # then read every quantity off at that same position. THIS is the §6
        # "convert age to EEP, then interpolate there" step.
        rows = np.arange(age_win.size, dtype=float)
        frac = float(np.interp(age, age_win, rows))

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

    # -- EEP-fixed mass interpolation (the core of §6) -------------------------
    def _interp_window(self, mass: float) -> dict:
        """Mass-interpolated track over the exposed window [ZAMS .. RGB tip].

        Returns per-quantity arrays on a common row grid for the requested mass:
        each quantity is interpolated across the two bracketing mass tracks *at
        the same row index* (fixed EEP), never across age. `age` comes back in
        years; the structure quantities stay in their stored (log) form.
        """
        assert self._masses is not None
        i_lo, i_hi, w = self._bracket(mass)
        lo, hi = self._tracks[i_lo], self._tracks[i_hi]

        r0 = self._zams_row
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

    def _bracket(self, mass: float) -> tuple[int, int, float]:
        """Indices of the two grid masses bracketing `mass`, and the blend weight.

        Exact grid hit -> (i, i, 0.0). Otherwise w in (0,1) is the linear-in-mass
        position from the lower to the upper bracket.
        """
        assert self._masses is not None
        masses = self._masses
        if mass <= masses[0]:
            return 0, 0, 0.0
        if mass >= masses[-1]:
            n = masses.size - 1
            return n, n, 0.0
        i_hi = int(np.searchsorted(masses, mass, side="left"))
        if masses[i_hi] == mass:
            return i_hi, i_hi, 0.0
        i_lo = i_hi - 1
        w = (mass - masses[i_lo]) / (masses[i_hi] - masses[i_lo])
        return i_lo, i_hi, float(w)

    # -- validation ------------------------------------------------------------
    def _check_mass_feh(self, mass: float, feh: float) -> None:
        assert self._masses is not None
        if not (self._masses[0] <= mass <= self._masses[-1]):
            raise ParameterOutOfRange(
                f"mass {mass} M_sun outside MIST grid "
                f"[{self._masses[0]}, {self._masses[-1]}]"
            )
        # Single [Fe/H] grid: only this metallicity is representable (no blend yet).
        if not math.isclose(feh, self._feh, abs_tol=1e-3):
            raise ParameterOutOfRange(
                f"[Fe/H] {feh} not on the single-metallicity grid (only "
                f"{self._feh} available until a 2D [Fe/H] grid lands)"
            )
