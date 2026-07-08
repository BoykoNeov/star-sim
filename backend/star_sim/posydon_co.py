"""POSYDON CO-HMS_RLO compact-object binary tracks — path (b) Phase 1 Chunk 1a
(docs/plans/tempered-lineage-inspiral.md).

The built path (b) (`posydon.py`) covers only the FIRST mass-transfer episode between two
normal, hydrogen-burning stars (the POSYDON HMS-HMS grid). This module covers what happens
AFTER one star has already died: a compact object (NS/BH, occasionally a WD) orbits a
still hydrogen-rich secondary. If the secondary later overflows onto the compact object,
accretion releases gravitational potential energy — an X-ray binary (Cygnus X-1's
configuration), a genuinely new luminosity mechanism for this sim (not photospheric).

Schema recon (2026-07-08, measured against the real extracted solar `CO-HMS_RLO` HDF5, not
assumed against the HMS-HMS bake's schema):
  * **`history2` is absent in every sampled run, unconditionally** — not a stub, not
    NaN-filled, the HDF5 key genuinely doesn't exist. `S1` is always the normal star (a
    real `history1`); `S2` is always the compact object (`final_values.S2_state` in
    {"BH", "NS", "WD", "None"} — never variable). This is why this module is a SEPARATE
    sibling rather than a `posydon.py` branch that emits two `StellarState`s: there is
    only ever one real star here.
  * No `eccentricity` column (same circularization-at-RLO-onset story as HMS-HMS) —
    `CoBinaryStep.ecc` stays a documented 0.0, not a fabricated field.
  * The compact object's mass is a REAL per-row column (`binary_history.star_2_mass`)
    that grows via accretion (measured on one `stable_MT` run: 4.19->4.99 Msun over the
    track) — a genuine, distinguishable accretion phase, not a placeholder.
  * `rl_relative_overflow_2` is always <=0 on this grid (the point-mass CO cannot itself
    overflow a Roche lobe) — `mt_state` here is effectively only "detached"/"RLOF1", never
    "RLOF2"/"contact" (mirrors `posydon.py`'s `mt_state_label`, reused as-is).
  * CO masses are physically sane per type (NS 1.00-2.45 Msun, BH 1.2-307 Msun) EXCEPT
    the WD channel, where all 145 sampled WD-companion runs show exactly 1.00 Msun — this
    looks like an unimplemented/placeholder channel in POSYDON's model, not real data;
    `co_type == "WD"` results should be treated with that caveat if ever surfaced.

Runtime stays POSYDON-free exactly like `posydon.py` (plain numpy + stdlib reading a
compact `.npz` `scripts/bake_posydon.py --grid-type co-hms-rlo` writes host-side). Reuses
`posydon.py`'s public per-row helpers (`state_from_row`/`phase_label`/
`logg_from_mass_radius`/`mt_state_label`) rather than duplicating them — the CO bake's row
columns share the same `s1_*` naming convention on purpose, so `state_from_row` drops in
unchanged (sibling-calls-sibling, mirroring `structure.py` -> `lane_emden.solve_lane_emden`).

Snap-only (§6), same discipline as `posydon.py`: a request (M_star, M_co_init, P, [Fe/H])
snaps to the nearest track in (log M_star, log M_co_init, log P) space — never
interpolated (two different tracks have no row-for-row correspondence to blend across).
Note the axis swap vs `posydon.py`'s (M1, q, P): a compact object's mass is a real
physical value here, not a mass ratio, so M_co_init is its own axis rather than `q`.

The accretion-luminosity cue (`CoBinaryStep.accretion_lum_lsun`) is SCHEMATIC, the same
honesty tier as the corona/wind shaders: a standard `L = eta * Mdot * c^2` formula applied
to the grid's own served accretion rate (`lg_mstar_dot_2`, the CO's own mass-gain rate —
more direct than the donor-side `lg_mtransfer_rate`, which is pre-`xfer_fraction` loss),
with `ACCRETION_EFFICIENCY` a round literature number (~0.1, the GM/Rc^2 order of
magnitude for a NS/BH), NOT fit to this grid or a measured X-ray spectrum.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

from .posydon import mt_state_label, state_from_row
from .state import StellarState

# Must match scripts/bake_posydon.py's BAKE_VERSION_CO — a stale npz (baked by an older
# version of the CO trim/filter logic) is rejected rather than silently misread.
BAKE_VERSION_CO = 1

_REPO_ROOT = Path(__file__).resolve().parents[2]
BAKED_CO_DIR = _REPO_ROOT / "data" / "posydon" / "baked_co"

# Matches posydon.py's POSYDON_SOLAR_Z convention ([Fe/H] = log10(Z / POSYDON_SOLAR_Z)).
POSYDON_SOLAR_Z = 0.0142

# cgs constants for the accretion-luminosity cue (LSUN matches supernova.py's IAU-nominal
# convention; days/year matches binary.py's).
_C_CGS = 2.99792458e10
_MSUN_G = 1.989e33
_SEC_PER_YR = 365.25 * 86400.0
_LSUN_ERG_S = 3.828e33

# Standard round-number accretion efficiency for a compact accretor (order of magnitude of
# GM/Rc^2 for a NS/BH; ~0.1-0.2 in the literature) — a schematic cue, not fit to this grid.
ACCRETION_EFFICIENCY = 0.1

# Honesty thresholds for the snapped-far flags (heuristic, mirrors posydon.py's).
_M_STAR_FAR_DEX = 0.10
_M_CO_FAR_DEX = 0.10
_P_FAR_DEX = 0.30
_FEH_FAR_DEX = 0.25


class PosydonCoDataMissing(RuntimeError):
    """No baked CO-HMS_RLO grid found under `BAKED_CO_DIR`.

    Never committed (multi-GB source, like the HMS-HMS grid) — the API maps this to a 503
    with an actionable hint, exactly like a missing HMS-HMS bake."""


_MISSING_HINT = (
    "No baked POSYDON CO-HMS_RLO grid found under {baked_dir}. Extract + bake a "
    "metallicity's CO-HMS_RLO grid (see scripts/bake_posydon.py's docstring recipe): "
    "python scripts/bake_posydon.py --grid-type co-hms-rlo --z-label <label> --feh <feh>."
)


@dataclass
class CoBinaryStep:
    """One timestep of a normal star orbiting a compact-object companion."""

    age_yr: float
    star: StellarState
    co_mass_msun: float          # the compact object's CURRENT mass (grows via accretion)
    co_type: str                 # "NS" | "BH" | "WD" | "None" (unresolved) — a final-row
                                  # label, repeated on every step for convenience
    period_d: float
    separation_rsun: float
    ecc: float                   # always 0.0 on this grid — documented, not fabricated
    mt_state: str                 # "detached" | "RLOF1" (RLOF2/contact never fire — the
                                   # CO can't itself overflow a Roche lobe)
    mdot_msun_yr: float | None     # the CO's OWN accretion rate, when actively transferring
    accretion_lum_lsun: float | None   # schematic L=eta*Mdot*c^2 cue — see module docstring
    star_current_msun: float      # routing scalar — no home on StellarState


@dataclass
class CoBinaryTrack:
    """A snapped grid node's full time series, plus the honesty/routing scalars."""

    steps: list[CoBinaryStep]
    m_star_init_msun: float        # the TRUE snapped grid node (never interpolated, §6)
    m_co_init_msun: float
    p_init_d: float
    feh: float
    m_star_snapped_far: bool
    m_co_snapped_far: bool
    p_snapped_far: bool
    feh_snapped_far: bool
    co_type: str                    # final-row classification of the companion
    outcome: str                     # data-derived one-line fate label
    grid_m_star_range: tuple[float, float]
    grid_m_co_range: tuple[float, float]
    grid_p_range: tuple[float, float]


@dataclass(frozen=True)
class _BakedCoGrid:
    """One baked metallicity's CO-HMS_RLO tracks — flat CSR-style arrays, exactly the
    shape `bake_posydon.py --grid-type co-hms-rlo` writes."""

    feh: float
    m_star_init: np.ndarray
    m_co_init: np.ndarray
    p_init_d: np.ndarray
    row_start: np.ndarray
    row_count: np.ndarray
    s1_state: np.ndarray
    co_type: np.ndarray
    interpolation_class: np.ndarray
    mt_history: np.ndarray
    rows: dict[str, np.ndarray]        # column name (no "row_" prefix) -> flat array


_CACHE: dict[Path, _BakedCoGrid] = {}


def _load_baked(path: Path) -> _BakedCoGrid:
    if path in _CACHE:
        return _CACHE[path]
    with np.load(path) as npz:
        if int(npz["bake_version_co"]) != BAKE_VERSION_CO:
            raise PosydonCoDataMissing(
                f"{path} was baked with an old BAKE_VERSION_CO — rebake with "
                f"scripts/bake_posydon.py --grid-type co-hms-rlo"
            )
        rows = {k[len("row_"):]: npz[k] for k in npz.files if k.startswith("row_")}
        grid = _BakedCoGrid(
            feh=float(npz["feh"]),
            m_star_init=npz["track_m1_init"],
            m_co_init=npz["track_m2_init"],
            p_init_d=npz["track_p_init_d"],
            row_start=npz["track_row_start"],
            row_count=npz["track_row_count"],
            s1_state=npz["track_s1_state"],
            co_type=npz["track_co_type"],
            interpolation_class=npz["track_interpolation_class"],
            mt_history=npz["track_mt_history"],
            rows=rows,
        )
    _CACHE[path] = grid
    return grid


def _available_grids() -> list[_BakedCoGrid]:
    paths = sorted(BAKED_CO_DIR.glob("*.npz")) if BAKED_CO_DIR.is_dir() else []
    if not paths:
        raise PosydonCoDataMissing(_MISSING_HINT.format(baked_dir=BAKED_CO_DIR))
    return [_load_baked(p) for p in paths]


def _snap_feh(grids: list[_BakedCoGrid], feh: float) -> _BakedCoGrid:
    return min(grids, key=lambda g: abs(g.feh - feh))


def _snap_track_index(grid: _BakedCoGrid, m_star: float, m_co: float, p: float) -> int:
    """Nearest track in (log M_star, log M_co_init, log P) — never interpolated (§6): two
    different (M_star, M_co, P) tracks have no row-for-row correspondence to blend across."""
    d_ms = np.log10(grid.m_star_init) - math.log10(max(m_star, 1e-3))
    d_mc = np.log10(grid.m_co_init) - math.log10(max(m_co, 1e-3))
    d_p = np.log10(grid.p_init_d) - math.log10(max(p, 1e-3))
    dist = d_ms * d_ms + d_mc * d_mc + d_p * d_p
    return int(np.argmin(dist))


def _accretion_luminosity(mdot_msun_yr: float) -> float:
    """Standard L = eta * Mdot * c^2 for the CO's OWN accretion rate — schematic, the same
    honesty tier as the wind-shader/corona: a real formula on a real served rate, not a
    measured X-ray spectrum. See module docstring for `ACCRETION_EFFICIENCY`'s provenance."""
    mdot_g_s = mdot_msun_yr * _MSUN_G / _SEC_PER_YR
    l_erg_s = ACCRETION_EFFICIENCY * mdot_g_s * _C_CGS * _C_CGS
    return l_erg_s / _LSUN_ERG_S


def _outcome(s1_state: str, co_type: str, interpolation_class: str) -> str:
    """A data-derived one-line fate label — the CO-side vocabulary counterpart of
    `posydon.py`'s `_outcome` (S2_state is a remnant TYPE here, never the "no history"
    merger signal HMS-HMS uses "None" for; on this grid "None" means the companion's fate
    is simply unresolved by POSYDON's own classifier)."""
    if co_type == "None":
        return "unresolved companion"
    if "stripped_He" in s1_state:
        return f"stripped + {co_type} companion"
    if interpolation_class == "unstable_MT":
        return f"unstable mass transfer onto {co_type}"
    if interpolation_class in ("stable_MT", "stable_reverse_MT", "initial_MT"):
        return f"X-ray binary (stable transfer onto {co_type})"
    return f"detached {co_type} companion"


def co_binary_track(m_star: float, m_co: float, p: float, feh: float = 0.0) -> CoBinaryTrack:
    """(M_star, M_co_init, P_init [days], [Fe/H]) -> the snapped POSYDON CO-HMS_RLO track:
    the normal star's full StellarState history + the compact object's mass/accretion time
    series + the orbit, exactly as `bake_posydon.py --grid-type co-hms-rlo` recorded it
    (decimated for very long tracks, never interpolated across tracks)."""
    grids = _available_grids()
    grid = _snap_feh(grids, feh)
    idx = _snap_track_index(grid, m_star, m_co, p)

    m_star_node = float(grid.m_star_init[idx])
    m_co_node = float(grid.m_co_init[idx])
    p_node = float(grid.p_init_d[idx])
    co_type = str(grid.co_type[idx])

    start = int(grid.row_start[idx])
    count = int(grid.row_count[idx])
    rows = grid.rows

    steps: list[CoBinaryStep] = []
    for j in range(count):
        r = start + j
        m_star_cur = float(rows["star_1_mass"][r])
        m_co_cur = float(rows["star_2_mass"][r])
        # A non-finite / non-positive mass marks a row the MESA-binary run could no longer
        # resolve — truncate here (the `posydon.py` merger-truncation precedent).
        if not (np.isfinite(m_star_cur) and np.isfinite(m_co_cur) and m_star_cur > 0 and m_co_cur > 0):
            break

        star = state_from_row(rows, r, "s1", m_star_node, m_star_cur, grid.feh)

        rl1 = float(rows["rl_relative_overflow_1"][r])
        rl2 = float(rows["rl_relative_overflow_2"][r])
        mt_state = mt_state_label(rl1, rl2)

        lg_mdot2 = float(rows["lg_mstar_dot_2"][r])
        active = mt_state != "detached" and -30.0 < lg_mdot2 < 10.0
        mdot = 10.0 ** lg_mdot2 if active else None
        acc_lum = _accretion_luminosity(mdot) if mdot is not None else None

        steps.append(CoBinaryStep(
            age_yr=float(rows["age"][r]),
            star=star,
            co_mass_msun=m_co_cur,
            co_type=co_type,
            period_d=float(rows["period_days"][r]),
            separation_rsun=float(rows["binary_separation"][r]),
            ecc=0.0,
            mt_state=mt_state,
            mdot_msun_yr=mdot,
            accretion_lum_lsun=acc_lum,
            star_current_msun=m_star_cur,
        ))

    return CoBinaryTrack(
        steps=steps,
        m_star_init_msun=m_star_node,
        m_co_init_msun=m_co_node,
        p_init_d=p_node,
        feh=grid.feh,
        m_star_snapped_far=abs(math.log10(m_star_node) - math.log10(max(m_star, 1e-3))) > _M_STAR_FAR_DEX,
        m_co_snapped_far=abs(math.log10(m_co_node) - math.log10(max(m_co, 1e-3))) > _M_CO_FAR_DEX,
        p_snapped_far=abs(math.log10(p_node) - math.log10(max(p, 1e-3))) > _P_FAR_DEX,
        feh_snapped_far=abs(grid.feh - feh) > _FEH_FAR_DEX,
        co_type=co_type,
        outcome=_outcome(str(grid.s1_state[idx]), co_type, str(grid.interpolation_class[idx])),
        grid_m_star_range=(float(grid.m_star_init.min()), float(grid.m_star_init.max())),
        grid_m_co_range=(float(grid.m_co_init.min()), float(grid.m_co_init.max())),
        grid_p_range=(float(grid.p_init_d.min()), float(grid.p_init_d.max())),
    )


def co_binary_track_meta(feh: float = 0.0) -> dict:
    """The grid bounds at the nearest available [Fe/H] — for UI gating, mirroring
    `posydon.py`'s `binary_track_meta` (don't ship a whole track just to size a slider)."""
    grids = _available_grids()
    grid = _snap_feh(grids, feh)
    return {
        "feh": grid.feh,
        "available_feh": sorted({g.feh for g in grids}),
        "m_star_min": float(grid.m_star_init.min()),
        "m_star_max": float(grid.m_star_init.max()),
        "m_co_min": float(grid.m_co_init.min()),
        "m_co_max": float(grid.m_co_init.max()),
        "p_min": float(grid.p_init_d.min()),
        "p_max": float(grid.p_init_d.max()),
        "n_tracks": int(grid.m_star_init.size),
    }


def co_binary_track_payload(m_star: float, m_co: float, p: float, feh: float = 0.0) -> dict:
    """JSON-friendly `/co_binary_track` payload: each step's one real StellarState (exact
    §3 dict shape) + the compact-object routing scalars + the orbit, plus the track-level
    snap/outcome metadata — mirrors `posydon.py`'s `binary_track_payload` shape."""
    track = co_binary_track(m_star, m_co, p, feh)
    return {
        "steps": [
            {
                "age_yr": s.age_yr,
                "star": asdict(s.star),
                "co_mass_msun": s.co_mass_msun,
                "co_type": s.co_type,
                "period_d": s.period_d,
                "separation_rsun": s.separation_rsun,
                "ecc": s.ecc,
                "mt_state": s.mt_state,
                "mdot_msun_yr": s.mdot_msun_yr,
                "accretion_lum_lsun": s.accretion_lum_lsun,
                "star_current_msun": s.star_current_msun,
            }
            for s in track.steps
        ],
        "m_star_init_msun": track.m_star_init_msun,
        "m_co_init_msun": track.m_co_init_msun,
        "p_init_d": track.p_init_d,
        "feh": track.feh,
        "m_star_snapped_far": track.m_star_snapped_far,
        "m_co_snapped_far": track.m_co_snapped_far,
        "p_snapped_far": track.p_snapped_far,
        "feh_snapped_far": track.feh_snapped_far,
        "co_type": track.co_type,
        "outcome": track.outcome,
        "grid_m_star_range": list(track.grid_m_star_range),
        "grid_m_co_range": list(track.grid_m_co_range),
        "grid_p_range": list(track.grid_p_range),
    }
