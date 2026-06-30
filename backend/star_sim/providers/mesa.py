"""MESAProvider — offline MESA `history.data` runs behind the §3 boundary.

The spec's "optional path to more science" names this provider explicitly
(§5 / §6 Phase 4+): read offline-generated MESA history files "to extend or
replace the grid, or **to validate MIST**." That validation is the point of this
cut — see `tests/test_mesa_vs_mist.py`, which diffs this provider against
`MISTProvider` through the public `track()` API (a §3 boundary demonstration in
its own right).

It is the second *real* provider, and it deliberately proves the §3 boundary a
second time: it reads a completely different on-disk format (raw MESA
`history.data`, not MIST `.track.eep`), with its own parser, yet emits the exact
same `StellarState` — so the swap is invisible downstream. Everything
MESA-specific (the column names, the file layout, the windowing) stays sealed in
this module.

It is **multi-metallicity by snapping, not interpolation**: runs are grouped into
[Fe/H] buckets, and a request snaps to the nearest grid [Fe/H] and then the
nearest mass within it. Multiple grids at different Z load side by side as
separate buckets. *Today only the metal-poor bearums tutorial grid is present (one
bucket)* — but the capability is the point: a second-metallicity grid (e.g. a
solar-Z MESA-Web run for a *clean Sun anchor* vs MIST, instead of cross-matching
through the metal-poor grid) drops into `data/mesa/` as another bucket with **no
code change**. (The single-Z case is just the degenerate one-bucket grid; a clean
fetchable native solar grid was sought and none was suitable — see CLAUDE.md.)

What this provider is NOT (honest scope):
  * **No cross-mass / cross-[Fe/H] interpolation.** Raw MESA `history.data` has
    no EEP column — only `model_number` / `star_age`. Identifying EEPs from raw
    history to make tracks row-aligned for interpolation is exactly MIST's `iso`
    machinery, which the spec rules out ("not a MESA reimplementation"). So this
    is a *discrete-grid, single-track* provider: `state_at`/`track` snap to the
    nearest available run (in both [Fe/H] and mass) and report that run's **true**
    initial mass and [Fe/H] in `mass_init_msun`/`feh_init` (never a silently-
    extrapolated value — §6). The only interpolation done here is the along-track
    age->row inversion, which is safe because it stays within one track. The §10
    "lies-between" interpolation test is MIST-specific and does not apply.
  * **No per-element composition** unless the run logged isotopes. The tutorial
    grid `fetch_mesa.py` pulls logs only `center_/surface_h1,he4`, so
    `metals_surf`/`metals_core` come back empty — `StellarState` defaults them
    empty and consumers degrade gracefully (the bulk X/Y/Z view still works).

Honest proxies (all labeled in-code):
  * **ZAMS** is taken as the first row where central hydrogen has dropped ~0.0015
    below its initial value — the usual "arrived on the MS, core burning has
    started" criterion. It cleanly skips the pre-MS Hayashi/Henyey descent MIST
    also hides.
  * **EEP** is a plain monotonic row index within the exposed window. MESA history
    has no EEP, so these numbers are NOT comparable to MIST's (ZAMS=202, …); they
    exist only to give the composition panel a monotonic x-axis (which it derives
    from the track itself, so nothing downstream assumes a particular origin).
  * **[Fe/H]** is derived from the ZAMS surface metal fraction,
    `log10(Z / Z_sun)`, because the tutorial runs' history header carries no
    `initial_z`. (With no `surface_he3` column, `Z = 1 - X - Y` folds he3 into Z,
    biasing the derived [Fe/H] high by a few hundredths dex — the cross-validation
    matches on Z directly to sidestep this.)
  * **phase** is a coarse label from central H/He, since raw history has no
    FSPS phase code: MS (core H burning) -> RGB (post-MS, He core inert/growing)
    -> CHeB (central He being consumed) -> post-CHeB.
"""

from __future__ import annotations

import glob
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from ..provider import EndgameResult, ParameterOutOfRange, ProviderDataMissing
from ..state import StellarState
from .mist import DATA_DIR

# MESA runs live under data/mesa/ (alongside the MIST grids under data/).
MESA_DATA_DIR = DATA_DIR / "mesa"

_FETCH_HINT = (
    "MESA history.data runs not found under {data_dir}. Fetch the sample grid once with:\n"
    "    python -m star_sim.fetch_mesa\n"
    "(downloads a small public MESA history grid; see fetch_mesa.py for provenance)."
)

# Solar metal mass fraction for the derived-[Fe/H] anchor. Matches the stub's
# Z_SUN so the two providers report [Fe/H] on the same scale.
Z_SUN = 0.0152

# ZAMS proxy: central H has burned this far below its initial value (the star has
# arrived on the MS and core burning has started). Skips the pre-MS descent.
_ZAMS_XC_DROP = 0.0015

# Central-hydrogen floor below which the core is "H-exhausted" (post-MS).
_XC_MS_FLOOR = 1e-4

# [Fe/H] exact-hit tolerance (this provider has a single metallicity).
_FEH_TOL = 1e-3


def _read_mesa_history(path: str) -> tuple[dict[str, str], dict[str, np.ndarray]]:
    """Parse one MESA `history.data` into (header, data) dicts.

    The MESA history/profile format is fixed (docs.mesastar.org "MESA output"):
      line 1: header column numbers
      line 2: header column names
      line 3: header column values
      line 4: blank
      line 5: data column numbers
      line 6: data column names
      line 7+: data rows
    The data block is purely numeric (incl. scientific notation), so we read the
    names off line 6 and the rows with `np.loadtxt`. We deliberately do not depend
    on `mesa_reader` — a ~30-line reader keeps parity with the vendored MIST
    parser and avoids a fragile external dep (spec §5: `mesa_reader` is a *later*
    option, not a requirement).
    """
    with open(path, "r") as fh:
        lines = fh.readlines()
    if len(lines) < 7:
        raise ProviderDataMissing(f"{path}: too short to be a MESA history.data file")

    h_names = lines[1].split()
    h_vals = lines[2].split()
    header = dict(zip(h_names, h_vals))

    d_names = lines[5].split()
    arr = np.loadtxt(path, skiprows=6, ndmin=2)
    if arr.shape[1] != len(d_names):
        raise ProviderDataMissing(
            f"{path}: {arr.shape[1]} data columns but {len(d_names)} column names"
        )
    data = {name: arr[:, i] for i, name in enumerate(d_names)}
    return header, data


def _dedup_by_model_number(d: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    """Drop superseded retry/backup rows, keeping the last write per model_number.

    A MESA run that backs up and recomputes can leave stale rows in history.data,
    so `star_age` is not always monotonic as written. The fix (same as
    py_mesa_reader) is to keep, for each `model_number`, only its *last*
    occurrence, then order by model number — which restores a strictly-increasing
    age sequence the age->row inversion needs. Falls back to the raw data if there
    is no `model_number` column.
    """
    if "model_number" not in d:
        return d
    mn = np.asarray(d["model_number"], dtype=float)
    order = np.argsort(mn, kind="stable")          # ascending model #, ties keep file order
    mn_sorted = mn[order]
    keep = np.ones(mn_sorted.size, dtype=bool)
    keep[:-1] = mn_sorted[1:] != mn_sorted[:-1]     # last row of each model-number group
    kept = order[keep]
    return {k: v[kept] for k, v in d.items()}


@dataclass
class _MesaTrack:
    """One MESA run, windowed to ZAMS->end and reduced to StellarState columns.

    Arrays are stored in the form we read off (log for structure, linear for mass
    fractions), already sliced to the exposed [ZAMS .. end-of-run] window — so a
    row index here *is* the EEP coordinate (a monotonic index; see module
    docstring). `phase` is a per-row coarse label string.
    """

    minit: float
    feh: float
    age: np.ndarray
    logL: np.ndarray
    logT: np.ndarray
    logR: np.ndarray
    logg: np.ndarray
    Xs: np.ndarray
    Ys: np.ndarray
    Xc: np.ndarray
    Yc: np.ndarray
    phase: np.ndarray   # dtype=object array of label strings


def _phase_labels(Xc: np.ndarray, Yc: np.ndarray) -> np.ndarray:
    """Coarse per-row phase labels from central H/He (no FSPS code in raw history).

    MS while core H burns; after H exhaustion the central He fraction tells the
    rest: it sits near its post-TAMS peak through the (inert-He-core) subgiant/RGB
    ascent, then falls as core He burns (CHeB) and is exhausted (post-CHeB). The
    thresholds are coarse on purpose — without a burning-luminosity column RGB and
    the very onset of CHeB are not cleanly separable; this is a flavor label, not
    a phase identification.
    """
    labels = np.empty(Xc.size, dtype=object)
    post_ms = Xc <= _XC_MS_FLOOR
    yc_peak = float(Yc[post_ms].max()) if post_ms.any() else 0.0
    for i in range(Xc.size):
        if Xc[i] > _XC_MS_FLOOR:
            labels[i] = "MS"
        elif Yc[i] >= yc_peak - 0.03:
            labels[i] = "RGB"          # post-MS, He core inert/growing (incl. subgiant)
        elif Yc[i] >= 0.10:
            labels[i] = "CHeB"         # central He being consumed
        else:
            labels[i] = "post-CHeB"
    return labels


def _strictly_increasing_mask(x: np.ndarray) -> np.ndarray:
    """Boolean mask selecting a strictly-increasing subsequence of `x` (running max).

    A correct safety net for the age->row inversion if any non-monotone rows
    survive dedup. O(n); keeps the first row and every later row that exceeds the
    last kept value."""
    mask = np.zeros(x.size, dtype=bool)
    last = -np.inf
    for i in range(x.size):
        if x[i] > last:
            mask[i] = True
            last = x[i]
    return mask


def _build_track(path: str) -> _MesaTrack | None:
    """Parse + window one history.data into a `_MesaTrack`, or None if unusable."""
    _, d = _read_mesa_history(path)
    d = _dedup_by_model_number(d)

    age = np.asarray(d["star_age"], dtype=float)
    # luminosity: prefer log_L; else take linear `L`/`luminosity` [L_sun] and log it.
    if "log_L" in d:
        logL = np.asarray(d["log_L"], dtype=float)
    else:
        lin_L = d["L"] if "L" in d else d["luminosity"]
        logL = np.log10(np.asarray(lin_L, dtype=float))
    logT = np.asarray(d["log_Teff"], dtype=float)
    # radius: prefer log_R; else take linear `radius` [R_sun] and log it.
    if "log_R" in d:
        logR = np.asarray(d["log_R"], dtype=float)
    else:
        logR = np.log10(np.asarray(d["radius"], dtype=float))
    logg = np.asarray(d["log_g"], dtype=float)

    Xs = np.asarray(d["surface_h1"], dtype=float)
    Ys = np.asarray(d["surface_he4"], dtype=float)
    if "surface_he3" in d:
        Ys = Ys + np.asarray(d["surface_he3"], dtype=float)
    Xc = np.asarray(d["center_h1"], dtype=float)
    Yc = np.asarray(d["center_he4"], dtype=float)
    if "center_he3" in d:
        Yc = Yc + np.asarray(d["center_he3"], dtype=float)

    # ZAMS = first row where central H has dropped _ZAMS_XC_DROP below initial.
    xc0 = float(Xc[0])
    below = np.where(Xc <= xc0 - _ZAMS_XC_DROP)[0]
    zams = int(below[0]) if below.size else 0
    if age.size - zams < 2:
        return None  # no usable post-ZAMS evolution

    sl = slice(zams, age.size)
    # dedup restores monotone age; this mask is a correct safety net for any
    # residual non-monotone rows (so age->row inversion always has increasing xp).
    keep = _strictly_increasing_mask(age[sl])
    idx = zams + np.where(keep)[0]            # absolute row indices kept
    age_w = age[idx]
    Xc_w, Yc_w = Xc[idx], Yc[idx]
    logL_w, logT_w, logR_w, logg_w = logL[idx], logT[idx], logR[idx], logg[idx]
    Xs_w, Ys_w = Xs[idx], Ys[idx]
    if age_w.size < 2:
        return None

    # Initial mass: the first row's star_mass (header carries no initial_mass here).
    minit = float(np.asarray(d["star_mass"], dtype=float)[0])

    # [Fe/H] from the *initial* (row 0) surface metals — pre-MS, so unprocessed.
    z0 = max(1e-12, 1.0 - float(Xs[0]) - float(Ys[0]))
    feh = math.log10(z0 / Z_SUN)

    return _MesaTrack(
        minit=round(minit, 4),
        feh=feh,
        age=age_w,
        logL=logL_w,
        logT=logT_w,
        logR=logR_w,
        logg=logg_w,
        Xs=Xs_w,
        Ys=Ys_w,
        Xc=Xc_w,
        Yc=Yc_w,
        phase=_phase_labels(Xc_w, Yc_w),
    )


def _find_history_files(mesa_dir: Path) -> list[str]:
    """Every `history.data` under the MESA data dir (one per run), sorted."""
    return sorted(glob.glob(str(mesa_dir / "**" / "history.data"), recursive=True))


class MESAProvider:
    """A `StellarStateProvider` (structurally — see ../provider.py) backed by MESA.

    Construction is cheap and never touches disk: runs are loaded lazily on first
    use, so importing the API in a data-less checkout doesn't explode (it raises
    an actionable `ProviderDataMissing` only when state is actually requested).
    """

    name = "MESAProvider"

    def __init__(self, data_dir: Path | None = None) -> None:
        self._data_dir = Path(data_dir) if data_dir is not None else MESA_DATA_DIR
        self._loaded = False
        # Tracks are grouped into [Fe/H] buckets (snap on feh, then mass within it).
        self._tracks_by_feh: dict[float, list[_MesaTrack]] = {}
        self._masses_by_feh: dict[float, np.ndarray] = {}
        self._fehs: np.ndarray | None = None   # sorted unique grid [Fe/H] values

    # -- lazy data load --------------------------------------------------------
    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        files = _find_history_files(self._data_dir)
        if not files:
            raise ProviderDataMissing(_FETCH_HINT.format(data_dir=self._data_dir))

        tracks = [t for f in files if (t := _build_track(f)) is not None]
        if not tracks:
            raise ProviderDataMissing(_FETCH_HINT.format(data_dir=self._data_dir))

        # Group runs into [Fe/H] buckets keyed by the derived metallicity rounded
        # to 2 dp. Precision beyond that is spurious here (the he3-in-Z bias alone
        # is a few hundredths dex), and a round key lets a caller echo /ranges'
        # [Fe/H] back without a tolerance miss. Each run within a bucket shares one
        # Z, so snap-to-nearest-mass stays within a single metallicity; the snap on
        # [Fe/H] (below) is what makes this provider multi-metallicity. Stamp the
        # rounded key onto every track so its state's feh_init matches /ranges.
        buckets: dict[float, list[_MesaTrack]] = {}
        for t in tracks:
            key = round(t.feh, 2)
            t.feh = key
            buckets.setdefault(key, []).append(t)
        for ts in buckets.values():
            ts.sort(key=lambda t: t.minit)

        self._tracks_by_feh = buckets
        self._masses_by_feh = {k: np.array([t.minit for t in ts]) for k, ts in buckets.items()}
        self._fehs = np.array(sorted(buckets))
        self._loaded = True

    # -- UI metadata -----------------------------------------------------------
    def parameter_ranges(self) -> dict:
        self._ensure_loaded()
        assert self._fehs is not None
        all_masses = np.concatenate(list(self._masses_by_feh.values()))
        return {
            # Global mass span across all metallicities (outer slider domain);
            # mass_range(feh) tightens it per [Fe/H] for the non-rectangular domain.
            "mass_msun": {"min": float(all_masses.min()), "max": float(all_masses.max())},
            # A real range now (was a pinned point) — one entry per grid Z. With a
            # single-Z grid min==max still, so the slider pins as before.
            "feh": {"min": float(self._fehs[0]), "max": float(self._fehs[-1])},
        }

    def mass_range(self, feh: float, vvcrit: float = 0.0) -> tuple[float, float]:
        """Discrete mass span at the [Fe/H] bucket nearest `feh`. The domain is
        **non-rectangular** in general (different masses per Z), so this is per-Z,
        not global. `feh` snaps to the nearest grid value; out of the grid's
        [Fe/H] span it raises (no extrapolation, §6). `vvcrit` is accepted for
        Protocol parity and ignored — the offline MESA runs are non-rotating."""
        self._ensure_loaded()
        key = self._snap_feh(feh)
        m = self._masses_by_feh[key]
        return float(m[0]), float(m[-1])

    def age_range(self, mass: float, feh: float, vvcrit: float = 0.0) -> tuple[float, float]:
        self._ensure_loaded()
        t = self._snap(mass, feh)
        return float(t.age[0]), float(t.age[-1])

    # -- the one method that matters ------------------------------------------
    def state_at(self, mass: float, feh: float, age_yr: float, vvcrit: float = 0.0) -> StellarState:
        self._ensure_loaded()
        t = self._snap(mass, feh)
        age = float(min(max(age_yr, t.age[0]), t.age[-1]))  # never extrapolate in age
        rows = np.arange(t.age.size, dtype=float)
        frac = float(np.interp(age, t.age, rows))           # age -> fractional row
        return self._state_from_track(t, frac)

    def track(self, mass: float, feh: float, vvcrit: float = 0.0) -> list[StellarState]:
        """Every exposed row of the snapped run as a StellarState (§3), ordered by
        EEP. No age inversion: the run's rows already are the EEP sequence.
        `vvcrit` ignored (the offline MESA runs are non-rotating)."""
        self._ensure_loaded()
        t = self._snap(mass, feh)
        return [self._state_from_track(t, float(i)) for i in range(t.age.size)]

    def endgame(self, mass: float, feh: float, vvcrit: float = 0.0) -> EndgameResult:
        """MESA tutorial runs stop on/near the MS, so there is no exposed stellar
        endgame: return type="none" (the §3-agnostic route then shows no gateway).
        The capability lives on the provider boundary; only MISTProvider has data for
        it today. We don't snap or validate here — "no endgame" is the honest answer
        for any input, and the snap would needlessly raise on an out-of-grid mass."""
        return EndgameResult(type="none", mass_init_msun=mass, feh_init=feh)

    # -- internals -------------------------------------------------------------
    def _snap(self, mass: float, feh: float) -> _MesaTrack:
        """The run nearest `(mass, feh)` — snap [Fe/H] to the nearest grid bucket
        first, then snap mass within it. Centralized so age_range/state_at/track
        can never disagree on which run they picked. Reports the run's *true*
        initial mass and [Fe/H] downstream (the snap is honest, never a silent
        extrapolation — §6). Raises if mass is outside the snapped bucket's span
        (the domain is non-rectangular) or [Fe/H] is outside the grid."""
        key = self._snap_feh(feh)
        masses = self._masses_by_feh[key]
        lo, hi = float(masses[0]), float(masses[-1])
        if not (lo <= mass <= hi):
            raise ParameterOutOfRange(
                f"mass {mass} M_sun outside the MESA grid [{lo}, {hi}] at [Fe/H]={key:.2f}"
            )
        i = int(np.argmin(np.abs(masses - mass)))
        return self._tracks_by_feh[key][i]

    def _state_from_track(self, t: _MesaTrack, frac: float) -> StellarState:
        """Read a StellarState off one run's arrays at fractional row `frac`.

        The single place a track row becomes a StellarState — shared by
        `state_at` (frac from the age inversion) and `track` (frac = each integer
        row), so the two can never drift. `mass_init_msun` is the run's *true*
        initial mass (the snap is honest, not a silent extrapolation)."""
        rows = np.arange(t.age.size, dtype=float)
        age = float(np.interp(frac, rows, t.age))
        L = 10.0 ** float(np.interp(frac, rows, t.logL))
        teff = 10.0 ** float(np.interp(frac, rows, t.logT))
        r = 10.0 ** float(np.interp(frac, rows, t.logR))
        logg = float(np.interp(frac, rows, t.logg))

        x_s = float(np.interp(frac, rows, t.Xs))
        y_s = float(np.interp(frac, rows, t.Ys))
        z_s = max(0.0, 1.0 - x_s - y_s)
        x_c = float(np.interp(frac, rows, t.Xc))
        y_c = float(np.interp(frac, rows, t.Yc))
        z_c = max(0.0, 1.0 - x_c - y_c)

        phase = str(t.phase[int(round(frac))])
        eep = frac  # monotonic row index; NOT a MIST EEP number (see module docstring)
        activity = max(0.0, min(1.0, (6500.0 - teff) / (6500.0 - 3000.0)))

        return StellarState(
            age_yr=age,
            eep=eep,
            phase=phase,
            mass_init_msun=t.minit,
            feh_init=t.feh,
            L_lsun=L,
            Teff_K=teff,
            R_rsun=r,
            logg=logg,
            X_surf=x_s, Y_surf=y_s, Z_surf=z_s,
            X_core=x_c, Y_core=y_c, Z_core=z_c,
            metals_surf={},   # tutorial runs log no isotopes -> degrade gracefully (§3)
            metals_core={},
            v_rot_kms=None,
            activity=activity,
        )

    # -- validation ------------------------------------------------------------
    def _snap_feh(self, feh: float) -> float:
        """The grid [Fe/H] bucket nearest `feh`. Snaps in-range (mirroring the
        mass snap — the state reports the *true* grid value, not the request) and
        raises out of the grid's [Fe/H] span (no extrapolation, §6). On a single-Z
        grid min==max, so only that one value (within _FEH_TOL) is accepted — the
        original exact-match behavior is preserved as the degenerate case."""
        assert self._fehs is not None
        lo, hi = float(self._fehs[0]), float(self._fehs[-1])
        if not (lo - _FEH_TOL <= feh <= hi + _FEH_TOL):
            raise ParameterOutOfRange(
                f"[Fe/H] {feh} outside the MESA grid [{lo:.2f}, {hi:.2f}]"
            )
        i = int(np.argmin(np.abs(self._fehs - feh)))
        return float(self._fehs[i])
