"""`MISTProvider` — the class itself: (mass, [Fe/H], v/vcrit, age) -> `StellarState`.

The physics half of the package. File formats live in `.parsing`, the grid/axis
containers and the blend arithmetic in `.interp`; what is left here is the provider
interface plus the four honesty gates that read the grid to decide what the UI may
claim (rotation, the He-ignition band, the uncertain-fate band, the endgame fate).

The §6 gotcha this class exists to honour: interpolate at fixed EEP, then invert
age once on the blended track. See the package docstring for the full contract.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np

from ...provider import EndgameResult, ParameterOutOfRange, ProviderDataMissing
from ...state import StellarState
from .interp import (
    _FEH_TOL,
    _VVCRIT_TOL,
    _Axis,
    _Grid,
    _blend_windows,
    _bracket,
    _build_axis,
    _load_grid,
    _log_mass_weight,
)
from .parsing import (
    DATA_DIR,
    _TRACK_COLS,
    _Track,
    _feh_from_path,
    _find_eep_dirs,
)

_FETCH_HINT = (
    "MIST grids not found under {data_dir} (or a pre-baked cache there is stale for "
    "the code's current CACHE_VERSION and has no raw source to reparse from). Fetch "
    "them once with:\n"
    "    python -m star_sim.fetch_mist_baked   # fast: pre-baked caches, no raw fetch\n"
    "    python -m star_sim.fetch_mist         # or: discover + fetch raw MIST grids\n"
    "(the latter downloads the current MIST EEP tarball and extracts it; see spec §6).\n"
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

# Surface gravity (cgs dex) above which the endgame's last row counts as a
# degenerate white dwarf. A real WD sits at log g ~7-9; normal/AGB stars never
# exceed ~5, so 7.0 is a wide, unambiguous floor. Used only to classify a track
# whose cooling ran but whose FSPS phase code we don't want to over-trust.
_WD_LOGG = 7.0

# The endgame's SN-vs-none split (see `endgame`). A track that forms neither a WD
# nor a WR, yet ran past core-helium ignition (FSPS phase >= 3 = CHeB) AND ended
# holding more than a white dwarf's worth of *non-degenerate* mass, can't quietly
# become a WD -> it core-collapses (SN). Both guards are needed: the phase alone
# would catch low-mass blue-HB stars whose track truncates at CHeB (they're future
# WDs), so we also require the final mass to clear the Chandrasekhar ceiling. The
# data leaves a wide gap here (the lightest real SN progenitor ends at ~5.8 M_sun,
# the heaviest excluded HB star at ~0.5), so 1.4 is an unambiguous floor.
_CHEB_PHASE = 3          # FSPS phase code: core-helium burning (first post-RGB phase)
_SN_FINAL_MASS_FLOOR = 1.4   # M_sun ~ the Chandrasekhar mass (max white-dwarf mass)

# Surface hydrogen mass fraction above which a core-collapse progenitor still holds
# an H envelope -> Type II (vs a stripped Ib/c). The SN bucket is purely H-rich
# (measured surf-H 0.30-0.75 over the whole grid; the stripped stars classify as WR,
# not SN), so 0.1 is a wide floor that cleanly reads "retains H" for every SN track.
_SN_H_RETAINED = 0.1     # surface_h1 fraction threshold for "still has an H envelope"

# --- the He-ignition transition band (`_he_ignition_band`) --------------------
# How far the He-core mass at ignition must have fallen from its degenerate plateau
# toward its minimum before a mass counts as "into the transition" (the band's lower
# edge; the upper edge is the minimum itself and needs no constant). Measured on the
# ten grids on disk: inside the plateau the node-to-node wiggle is well under 1 % of
# the total fall, so 10 % is far outside the noise while still catching the start of
# the steepening — it puts the solar band at 1.65-2.10 M_sun, straddling the textbook
# M_HeF ~ 2 M_sun. A grid too sparse to show the shape at all yields no band.
_HE_BAND_LEVEL = 0.10
_HE_BAND_MIN_TRACKS = 5
# The "no He-ignition band here" answer (off-grid [Fe/H], or a grid too sparse). Copied
# per call so a consumer can never mutate the shared dict.
_HE_NO_DATA = {
    "has_data": False,
    "band_lo_msun": None,
    "band_hi_msun": None,
    "in_band": False,
    "interpolated": False,
    "active": False,
}

# --- the uncertain-fate band (`_fate_boundary` / `fate_boundary_status`) ------
# The upper edge of the "white dwarf OR supernova?" band, in M_sun. **Cited, not
# measured** — and the caption says which half is which. The grid flips in ONE step
# from its heaviest white-dwarf node to its lightest core-collapse node (measured
# 2026-09-03 over all ten grids: 6.5 -> 7.0 at solar, 6.0 -> 6.2 at [Fe/H] = -1), so
# the lower edge IS a measurement; the width of the real uncertainty is not something
# MIST can be asked about, because it models neither the super-AGB thermal pulses nor
# electron capture. In that regime the star builds a degenerate O-Ne core and its fate
# — an O-Ne white dwarf, or a faint electron-capture supernova — turns on convective
# overshoot, mass loss and the carbon-burning treatment. Published crossover masses
# (M_up) span ~6.5-8 M_sun at solar metallicity, and some prescriptions push the
# electron-capture channel to ~9 (Poelarends et al. 2008, ApJ 675, 614; Doherty et al.
# 2015, MNRAS 446, 2599; Doherty et al. 2017, PASA 34, e56). 8.0 is the NARROW end of
# that spread, so the band never claims more uncertainty than the literature supports.
_FATE_UNCERTAIN_CEIL_MSUN = 8.0

# The "no fate boundary here" answer (off-grid [Fe/H], or a grid with no clean
# WD -> SN flip). Copied per call, like _HE_NO_DATA.
_FATE_NO_DATA = {
    "has_data": False,
    "wd_max_msun": None,
    "sn_min_msun": None,
    "band_lo_msun": None,
    "band_hi_msun": None,
    "in_band": False,
    "active": False,
}


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
        # Lazy per-[Fe/H] cache of the rotation-onset mass (the data-derived Kraft
        # break): the lowest grid mass where the rotating track actually diverges
        # from the non-rotating one. Keyed by the snapped rotating-grid [Fe/H].
        self._rot_threshold_cache: dict[float, float | None] = {}
        # (vvcrit, [Fe/H]) -> the He-ignition transition band, or None (see `_he_ignition_band`)
        self._he_band_cache: dict[tuple[float, float], tuple[float, float] | None] = {}
        # (vvcrit, [Fe/H]) -> (heaviest WD node, lightest SN node), or None (see `_fate_boundary`)
        self._fate_boundary_cache: dict[tuple[float, float], tuple[float, float] | None] = {}

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

        self._axes = {vc: _build_axis(vc, gs) for vc, gs in buckets.items()}
        self._vvcrits = np.array(sorted(self._axes))
        # Default to non-rotating (0.0) if present — so the live provider is
        # unchanged — else the lowest rotation rate on disk.
        self._default_vvcrit = (
            0.0 if any(math.isclose(vc, 0.0, abs_tol=_VVCRIT_TOL) for vc in self._axes)
            else float(self._vvcrits[0])
        )
        self._loaded = True

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

    # -- rotation honesty gate (Chunk 2): where is the toggle meaningful? -------
    def _rotating_axis(self) -> _Axis | None:
        """The most-rotating axis above the default, or None if only one rate is on
        disk. 'Rotation ON' selects this bucket (MIST's vvcrit=0.4)."""
        self._ensure_loaded()
        assert self._vvcrits is not None
        keys = [k for k in self._axes if k > self._default_vvcrit + _VVCRIT_TOL]
        return self._axes[max(keys)] if keys else None

    @staticmethod
    def _track_diverges(rot: _Track, nonrot: _Track, tol: float = 1e-6) -> bool:
        """Does the rotating track measurably differ from the non-rotating one?

        Below the magnetic-braking (Kraft) limit MIST makes the rotating track
        *bit-identical* to the non-rotating one (max|Δ| = 0 exactly), so any positive
        tolerance cleanly separates 'rotation does nothing here' from 'rotation
        reshapes the track'. Compares luminosity and surface helium over the shared
        exposed window — the two quantities rotation moves first."""
        n = min(rot.logL.size, nonrot.logL.size, rot.track_end + 1, nonrot.track_end + 1)
        r0 = max(rot.zams_row, nonrot.zams_row)
        if n <= r0:
            return False
        sl = slice(r0, n)
        dL = float(np.max(np.abs(rot.logL[sl] - nonrot.logL[sl])))
        dY = float(np.max(np.abs(rot.Ys[sl] - nonrot.Ys[sl])))
        return dL > tol or dY > tol

    def _rotation_threshold(self, feh: float) -> float | None:
        """Lowest mass where rotation bites at the rotating-grid [Fe/H] nearest `feh`.

        Data-derived (never a hardcoded 1.2 M_sun): scans the rotating grid against
        its non-rotating twin and returns the first mass whose track diverges — the
        magnetic-braking/Kraft break, which shifts with [Fe/H]. None if there is no
        rotating grid or no non-rotating twin to compare against."""
        rot = self._rotating_axis()
        if rot is None:
            return None
        rot_grid = rot.grids[int(np.argmin(np.abs(rot.fehs - feh)))]
        key = round(float(rot_grid.feh), 3)
        if key in self._rot_threshold_cache:
            return self._rot_threshold_cache[key]

        nonrot = self._axis(self._default_vvcrit)
        nonrot_grid = nonrot.grids[int(np.argmin(np.abs(nonrot.fehs - rot_grid.feh)))]
        threshold: float | None = None
        if math.isclose(float(nonrot_grid.feh), float(rot_grid.feh), abs_tol=_FEH_TOL):
            by_mass = {round(t.minit, 3): t for t in nonrot_grid.tracks}
            for t in rot_grid.tracks:                 # ascending by mass
                nr = by_mass.get(round(t.minit, 3))
                if nr is not None and self._track_diverges(t, nr):
                    threshold = float(t.minit)
                    break
        self._rot_threshold_cache[key] = threshold
        return threshold

    def rotation_status(self, mass: float, feh: float) -> dict:
        """Whether the rotation control is *meaningful* at (mass, [Fe/H]) — the
        data-derived honesty gate the frontend reads to render the toggle:

          * has_grid       — a rotating grid covers this [Fe/H] (so a rotating track
                             can actually be served; False off the rotating axis's
                             [Fe/H] span, e.g. before the matching grid is fetched).
          * threshold_msun — the rotation-onset mass at this [Fe/H] (the Kraft break,
                             derived from the data); None if has_grid is False.
          * active         — has_grid AND mass >= threshold: toggling rotation changes
                             the track. False below the threshold, where the rotating
                             and non-rotating tracks are bit-identical (the toggle is
                             an honest no-op — 'rotation negligible for this star').
        """
        rot = self._rotating_axis()
        if rot is None or not (rot.fehs[0] - _FEH_TOL <= feh <= rot.fehs[-1] + _FEH_TOL):
            return {"has_grid": False, "threshold_msun": None, "active": False}
        thr = self._rotation_threshold(feh)
        active = thr is not None and mass >= thr - 1e-9
        return {"has_grid": True, "threshold_msun": thr, "active": bool(active)}

    # -- He-ignition honesty gate: is this track BLENDED across the He flash? ---
    @staticmethod
    def _he_core_at_ignition(t: _Track) -> float:
        """Helium-core mass at the first core-He-burning row (FSPS phase 3), or NaN.

        The cleanest data signature of *how* helium ignites. Below the transition mass
        the core is electron-degenerate, so it cannot burn until it has grown to a
        near-universal ~0.47 M_sun — a flat plateau across every low mass. Above it the
        core is non-degenerate and ignites as soon as it is hot enough, at a core mass
        that falls steeply with initial mass and then climbs again. `HeCore` and `phase`
        are already parsed columns, so this costs no CACHE_VERSION bump.
        """
        sl = slice(t.zams_row, t.track_end + 1)
        i = np.where(t.phase[sl] == _CHEB_PHASE)[0]
        return float(t.HeCore[sl][i[0]]) if i.size else float("nan")

    def _he_ignition_band(self, axis: _Axis, grid: _Grid) -> tuple[float, float] | None:
        """(m_lo, m_hi) — the mass band over which He ignition changes character, or None.

        Derived by scanning the grid, never hardcoded (the transition mass shifts with
        metallicity and with rotation): read `_he_core_at_ignition` along the mass
        sequence, then

          * `m_hi` = the mass at the MINIMUM ignition core mass — the first fully
            non-degenerate ignition (searched only over the descent, i.e. before the
            core mass climbs back through the plateau, which it does forever above the
            transition);
          * `m_lo` = the last mass still on the degenerate plateau, taken as the node
            before the core mass has fallen `_HE_BAND_LEVEL` of the way from the plateau
            to that minimum.

        It is a BAND, not a mass, because the change is not a step: measured over the
        whole grid (2026-09-03) the fall spans ~0.3-0.5 M_sun, e.g. 1.65-2.10 M_sun at
        solar [Fe/H] non-rotating, 1.80-2.10 at [Fe/H] = -1, 1.70-2.20 rotating at
        [Fe/H] = +0.5 — all straddling the textbook M_HeF ~= 2 M_sun. Interpolating
        across it is what smooths the core-He-burning loop (see the CHeB residual in
        docs/plans/science-hurdles.md Sec 1.3); the band is what the UI confesses.
        """
        key = (round(float(axis.vvcrit), 3), round(float(grid.feh), 3))
        if key in self._he_band_cache:
            return self._he_band_cache[key]

        masses, cores = [], []
        for t in grid.tracks:                       # ascending by mass
            v = self._he_core_at_ignition(t)
            if math.isfinite(v):                    # skip tracks that never ignite He
                masses.append(float(t.minit))
                cores.append(v)

        band: tuple[float, float] | None = None
        if len(masses) >= _HE_BAND_MIN_TRACKS:
            m = np.asarray(masses)
            c = np.asarray(cores)
            plateau = float(c[0])                   # the lowest mass that ignites He at all
            coarse = int(np.argmin(c[: max(2, c.size // 2)]))
            back = np.where(c >= plateau)[0]
            back = back[back > coarse]
            stop = int(back[0]) if back.size else c.size - 1
            i_hi = int(np.argmin(c[: stop + 1]))
            thr = plateau - _HE_BAND_LEVEL * (plateau - float(c[i_hi]))
            below = np.where(c[: i_hi + 1] < thr)[0]
            i_lo = int(below[0]) - 1 if below.size and below[0] > 0 else 0
            if i_lo < i_hi:
                band = (float(m[i_lo]), float(m[i_hi]))

        self._he_band_cache[key] = band
        return band

    def he_ignition_status(self, mass: float, feh: float, vvcrit: float = 0.0) -> dict:
        """Is the drawn track BLENDED across the helium-ignition transition?

        The data-derived honesty gate behind the He-ignition-cliff caption
        (docs/plans/science-hurdles.md Sec 1.3). Two conditions, and the caption needs
        both — plus core-He burning, which the consumer adds from `StellarState.phase`
        (this method has no age):

          * `in_band`      — the requested mass lies inside the transition band, where
                             the core-He-burning morphology changes fastest;
          * `interpolated` — the window really is a blend: the mass falls BETWEEN two
                             grid masses, or the [Fe/H] falls between two grids (whose
                             bands sit at different masses). On an exact node the drawn
                             track is one real MIST track, nothing is smoothed, and the
                             caption would be a false confession — the defect this
                             project guards against hardest.

        `active` is the AND of the two. The band is the union over the bracketing
        [Fe/H] grids (the honest widest statement when the metallicity is itself a
        blend). Never raises: off-grid or data-free answers has_data=False and the UI
        hides the caption.
        """
        ax = self._axis(vvcrit)
        if not (float(ax.fehs[0]) - _FEH_TOL <= feh <= float(ax.fehs[-1]) + _FEH_TOL):
            return _HE_NO_DATA.copy()
        j_lo, j_hi, _ = self._bracket_feh(ax, feh)
        bands = [b for b in (self._he_ignition_band(ax, ax.grids[j]) for j in {j_lo, j_hi}) if b]
        if not bands:
            return _HE_NO_DATA.copy()

        lo = min(b[0] for b in bands)
        hi = max(b[1] for b in bands)
        in_band = lo - 1e-9 <= mass <= hi + 1e-9
        blended = j_lo != j_hi or any(
            _bracket(ax.grids[j].masses, mass)[0] != _bracket(ax.grids[j].masses, mass)[1]
            for j in {j_lo, j_hi}
        )
        return {
            "has_data": True,
            "band_lo_msun": lo,
            "band_hi_msun": hi,
            "in_band": bool(in_band),
            "interpolated": bool(blended),
            "active": bool(in_band and blended),
        }

    # -- the uncertain-fate band (science-hurdles.md Sec 2, SN/WD boundary) ----
    def _fate_boundary(self, axis: _Axis, grid: _Grid) -> tuple[float, float] | None:
        """(wd_max, sn_min) — where this grid flips white dwarf -> core collapse, or None.

        Scanned, never hardcoded: the flip mass moves with metallicity and rotation
        (measured 2026-09-03: 6.5 -> 7.0 M_sun at solar and at [Fe/H] = +0.5, 6.5 -> 7.0
        at -0.5 non-rotating, 6.2 -> 6.5 rotating, 6.0 -> 6.2 at -1.0). `wd_max` is the
        heaviest node whose fate is a white dwarf, `sn_min` the lightest that core-
        collapses; every grid on disk flips exactly once, with no WD node above `sn_min`.

        Returns None if the grid does NOT show one clean flip (too few masses, or WD and
        SN nodes interleaved) — the caption then simply never appears rather than
        pointing at a boundary that isn't there. Classification goes through `_fate_of`,
        the same predicate `endgame()` answers with, so the band always brackets the
        exact mass at which the gateway's own verdict changes.
        """
        key = (round(float(axis.vvcrit), 3), round(float(grid.feh), 3))
        if key in self._fate_boundary_cache:
            return self._fate_boundary_cache[key]

        wd, sn = [], []
        for t in grid.tracks:                       # ascending by mass
            fate, _, _ = self._fate_of(t)
            if fate == "WD":
                wd.append(float(t.minit))
            elif fate == "SN":
                sn.append(float(t.minit))

        band: tuple[float, float] | None = None
        if wd and sn:
            wd_max, sn_min = max(wd), min(sn)
            if wd_max < sn_min:                     # one clean flip, no interleaving
                band = (wd_max, sn_min)

        self._fate_boundary_cache[key] = band
        return band

    def fate_boundary_status(self, mass: float, feh: float, vvcrit: float = 0.0) -> dict:
        """Is this star's WD-or-supernova verdict inside the genuinely uncertain band?

        The third data-derived honesty gate (sibling of `rotation_status` and
        `he_ignition_status`), behind the uncertain-fate caption — see
        docs/plans/science-hurdles.md Sec 2, "SN/WD boundary". The gateway asserts one
        fate per star because the grid holds one; around the boundary that crispness
        overstates what is known, and this is what lets the UI say so.

        The band has one MEASURED edge and one CITED edge, and the caption keeps them
        apart:

          * `band_lo_msun` = `wd_max_msun`, the heaviest grid node that still ends a
            white dwarf here — measured, and it moves with [Fe/H] and rotation;
          * `band_hi_msun` = `_FATE_UNCERTAIN_CEIL_MSUN` (a published figure, see the
            constant), widened to `sn_min_msun` in the impossible case that the grid
            flips above it. MIST models neither super-AGB thermal pulses nor electron
            capture, so there is nothing here to measure the real width from.

        Shape:
            {"has_data": bool,           # this provider can answer at all
             "wd_max_msun": float|None,  # heaviest node that ends a WD (measured)
             "sn_min_msun": float|None,  # lightest node that core-collapses (measured)
             "band_lo_msun": float|None, # the uncertain band (measured lower edge)
             "band_hi_msun": float|None, #                    (cited upper edge)
             "in_band": bool,            # the requested mass lies inside it
             "active": bool}             # what a caption may fire on

        Unlike `he_ignition_status` there is no `interpolated` flag, and being on an
        exact grid node changes nothing: the endgame SNAPS (Sec 6), so the crisp verdict
        is exactly as crisp on a node as between two, and the uncertainty being confessed
        is the physics', not the interpolation's. The [Fe/H] is likewise snapped, not
        bracketed, so the band describes the same grid the gateway's verdict came from.
        Never raises: off-grid or too sparse answers has_data=False and the UI hides the
        caption.
        """
        ax = self._axis(vvcrit)
        try:
            j = self._snap_feh_index(ax, feh)
        except ParameterOutOfRange:
            return _FATE_NO_DATA.copy()
        pair = self._fate_boundary(ax, ax.grids[j])
        if pair is None:
            return _FATE_NO_DATA.copy()

        wd_max, sn_min = pair
        lo = wd_max
        hi = max(sn_min, _FATE_UNCERTAIN_CEIL_MSUN)
        in_band = lo - 1e-9 <= mass <= hi + 1e-9
        return {
            "has_data": True,
            "wd_max_msun": wd_max,
            "sn_min_msun": sn_min,
            "band_lo_msun": lo,
            "band_hi_msun": hi,
            "in_band": bool(in_band),
            "active": bool(in_band),
        }

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
          * SN  — the track forms neither a WD nor a WR, yet ran past core-helium
                  ignition (FSPS phase >= _CHEB_PHASE) and ended holding more than a
                  white dwarf's worth of non-degenerate mass (> _SN_FINAL_MASS_FLOOR):
                  the core-collapse / uncertain-fate dead end we do NOT render
                  (states = []; the last pre-collapse supergiant row is a low-gravity
                  artifact, not a renderable endgame). At solar this is ~7 M_sun and
                  up — just above where MIST stops modeling cooling, in the
                  genuinely-uncertain super-AGB / electron-capture regime. Some of
                  these stars stop at TPAGB onset (an FSPS-5 row past `track_end`);
                  others — notably massive ROTATING tracks and the very massive
                  metal-poor end — simply terminate at CHeB/EAGB with no row past the
                  window. Both are core-collapse-bound, so we classify by the star's
                  evolved, massive end state, not by whether a post-window row happens
                  to exist (that row count was a data artifact, not physics).
          * none — no exposed endgame at all: a star that never reached the SN
                  criterion above — typically a low-mass star still alive at the
                  grid's end (its `track_end` is already its last row), or a low-mass
                  blue-HB star whose track truncates at CHeB but ends well below the
                  Chandrasekhar mass (a future WD, not a core-collapse). states = [].
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

        r0 = track.track_end + 1                    # first row past the normal window
        wr_threshold = self._wr_threshold(grid)
        etype, r_last, final_mass = self._fate_of(track)

        states: list[StellarState] = []
        if etype in ("WR", "WD") and r0 <= r_last:
            win = {col: getattr(track, col)[r0 : r_last + 1] for col in _TRACK_COLS}
            states = [
                self._state_from_row(
                    ax, win, float(i), snapped_mass, snapped_feh, eep_origin=r0
                )
                for i in range(int(win["age"].size))
            ]

        # Core-collapse progenitor scalars — the inputs the SN sibling consumes. Only
        # the SN branch carries them (None elsewhere); they say nothing about where the
        # data came from (§3), exactly like the routing fields above.
        sn_scalars = self._sn_progenitor(track, r_last) if etype == "SN" else {}

        return EndgameResult(
            type=etype,
            mass_init_msun=snapped_mass,
            feh_init=snapped_feh,
            final_mass_msun=final_mass,
            wr_threshold_msun=wr_threshold,
            states=states,
            **sn_scalars,
        )

    @staticmethod
    def _fate_of(track: _Track) -> tuple[str, int, float]:
        """(fate, last real row, final mass) for one track — the ONE fate classifier.

        Both `endgame()` (which fate does this star meet?) and `_fate_boundary()`
        (where does the grid flip from WD to SN?) read it, so the gateway's answer and
        the uncertain-fate band can never drift apart. The four predicates are spelled
        out in `endgame`'s docstring; the constants are `_WD_LOGG`, `_CHEB_PHASE` and
        `_SN_FINAL_MASS_FLOOR`. Cheap: it touches three already-parsed columns and
        builds nothing, so scanning a whole grid costs milliseconds (materialising the
        endgame `states` per node, by contrast, costs seconds per grid).
        """
        phase = track.phase
        r_last = int(np.where(phase >= 0)[0][-1])   # last real row (drop the -9 sentinel)
        final_mass = float(track.Mcur[r_last])
        if bool(np.any(phase == 9)):
            fate = "WR"
        elif bool(np.any(phase == 6)) or float(track.logg[r_last]) > _WD_LOGG:
            fate = "WD"
        elif float(phase[r_last]) >= _CHEB_PHASE and final_mass > _SN_FINAL_MASS_FLOOR:
            fate = "SN"                             # evolved & massive, no remnant modeled
        else:                                       # low-mass / still-alive: nothing to expose
            fate = "none"
        return fate, r_last, final_mass

    @staticmethod
    def _sn_progenitor(track: _Track, r_last: int) -> dict:
        """The core-collapse progenitor scalars off a snapped SN track (see EndgameResult).

        R₀ (the Tier-2 plateau input) = the maximum radius over the final-phase rows
        (CHeB onward) *excluding the terminal EEP row* — a low-gravity artifact that can
        spuriously inflate or shrink the last row's radius (the gate measured R_last/R_prev
        swinging from ⅓ to R_max across tracks). The max (not the median, which the gate
        found underestimates by averaging in the compact pre-RSG CHeB rows) captures the
        RSG envelope's pre-collapse extent; t_p ∝ R₀^(1/6) is weak, so the estimate is
        robust. Falls back to the terminal row only if it is the lone final-phase row.

        He/CO cores + the surface-H flag come straight off the collapse row (`r_last`).
        `co_core_msun` is MIST's `c_core_mass` (the CO-core proxy — see CACHE_VERSION v12)."""
        phase = track.phase
        real = np.where(phase >= 0)[0]
        fp = real[phase[real] >= _CHEB_PHASE]         # final-phase real rows (CHeB onward)
        fp_inner = fp[fp != r_last]                   # drop the terminal artifact row
        rows = fp_inner if fp_inner.size else (fp if fp.size else np.array([r_last]))
        r0_rsun = float(np.max(10.0 ** track.logR[rows]))
        return {
            "pre_sn_radius_rsun": r0_rsun,
            "he_core_msun": float(track.HeCore[r_last]),
            "co_core_msun": float(track.CCore[r_last]),
            "h_retained": bool(track.Xs[r_last] >= _SN_H_RETAINED),
        }

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

        # Surface rotation velocity (km/s) — the rotation payoff (Chunk 3). It is the
        # MODEL's own surface speed for the selected axis: ~0 on the non-rotating grid,
        # and the real evolving equatorial velocity on the rotating one (high near the
        # ZAMS, falling as the star swells / brakes). A genuine StellarState field now,
        # not a stub. None only if the column is somehow absent (degrades gracefully).
        v_rot = float(np.interp(frac, rows, win["Vrot"])) if "Vrot" in win else None

        # Mass-loss rate (M_sun/yr, signed <= 0). Linearly blended across mass/[Fe/H]
        # (see `_grid_window`), surfaced for the SED's hot-wind free-free tail. The
        # frontend takes |Mdot| and gates on hot Teff. None if the column is absent.
        mdot = float(np.interp(frac, rows, win["Mdot"])) if "Mdot" in win else None

        # visual proxy (§7), explicitly evocative: cool stars more chromospherically
        # active than hot ones.
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
            v_rot_kms=v_rot,
            activity=activity,
            mdot_msun_yr=mdot,
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
        """Mass-interpolated window for one metallicity grid (fixed-EEP, no age).

        The blend weight is taken in **log(mass)**, not mass. Stellar quantities are
        near power laws in M (L ~ M^3.5 on the MS, lifetimes ~ M^-2.5), so at fixed
        EEP log L / log Teff / log age are far closer to linear in log M than in M —
        exactly the assumption a two-point blend makes. Measured on the full solar
        grid (2026-09-02; every interior node held out, reconstructed from its two
        neighbours, compared row-by-row against the real track): mean median
        |Δlog L| 0.0033 → 0.0021 dex, better on 126/169 nodes; the coarse ends win
        most (0.2 M☉: 0.036 → 0.0095 dex; 25 M☉: 0.025 → 0.007 dex; 30 M☉:
        0.019 → 0.007). Exact grid hits (w = 0) are untouched, so the Sun anchor and
        every snapped endgame are byte-identical. See
        tests/test_mist_provider.py::test_mass_interpolation_held_out_grid_nodes.
        """
        i_lo, i_hi, w = _bracket(grid.masses, mass)
        if i_lo != i_hi:
            w = _log_mass_weight(float(grid.masses[i_lo]), float(grid.masses[i_hi]), mass)
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
            # Surface rotation velocity is a living-state quantity (unlike Mcur, which
            # the endgame snaps), so it interpolates across mass at fixed EEP like the rest.
            "Vrot": mix(lo.Vrot, hi.Vrot),
            # Mass-loss rate (signed, <= 0). Mixed LINEARLY like Vrot (sign-safe: both
            # ends <= 0 -> blend <= 0; sidesteps a log(0) hack on the MS rows where Mdot
            # is exactly 0). Drives the SED's hot-wind free-free tail; unlike Mcur it now
            # IS interpolated across mass/[Fe/H] (the endgame still snaps a single track).
            "Mdot": mix(lo.Mdot, hi.Mdot),
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
