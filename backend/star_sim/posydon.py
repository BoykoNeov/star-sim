"""POSYDON co-evolved binary tracks — path (b) Chunk 4a, the on-ramp to a real
binary grid (docs/plans/entwined-consort-inspiral.md).

Chunks 1-3 of the binary-stripped-star arc (`binary.py`) all worked off the Götberg
**snapshot** grid — one representative state per stripped star. This module is the
first **time-series, two-body** sibling: a POSYDON HMS-HMS track is a real MESA-binary
run, giving both stars' full history (L, Teff, R, composition) AND the orbit (period,
separation, Roche-lobe overflow) at every timestep. That is what makes the Algol
mass-ratio reversal (`binary.py`'s `binary_pair_payload`) a *movie* instead of a caption:
both stars move on the HR diagram and the donor visibly crosses below the companion.

Like `binary.py` / `supernova.py` / `structure.py`, this is a **sibling to the
StellarState spine (§3), not a provider**: it imports only `state.StellarState` (which
it emits, one per star per step) and never touches `StellarStateProvider` — a two-star,
orbit-carrying result cannot pass through the single-star interface. `/binary_track`
bypasses `PROVIDER` exactly like `/binary`.

Runtime stays POSYDON-free (the §3 "no POSYDON at runtime" rule is about the *library*,
not about HDF5-in-general): `fetch_posydon.py`'s validator found the raw grid already
organized **per run** (`grid/run<i>/{binary_history,history1,history2}`), not POSYDON's
packed `PSyGrid` format the plan worried about — so `scripts/bake_posydon.py` reads it
directly with plain h5py, host-side, and writes a compact `.npz` this module reads with
NO h5py / POSYDON import at all (numpy + stdlib only), mirroring the WR/WD/stripped
spectra `bake_*.py` -> pure-Python-runtime split.

Two honest gaps vs the plan's original schema guess, pinned against the REAL grid
(measured 2026-07-07):
  * **No eccentricity column.** HMS-HMS binaries are tidally circularized in this grid,
    so `binary_history` carries none — `BinaryStep.ecc` is a documented 0.0, not a
    fabricated field.
  * **Composition is C/N/O only** (`surface_c12/n14/o16`, `center_c12/n14/o16`) — a
    3-key partial `metals_surf`/`metals_core` dict, never the MIST 16-metal breakdown
    (the boron-b8 discipline).
  * **No per-row phase label.** POSYDON's `S1_state`/`S2_state` are FINAL-row-only
    classifications (used for the track-level `outcome`, below) — so per-step `phase` is
    derived locally from the burning-fraction columns that ARE per-row (center H/He),
    the same spirit as MIST's EEP-window phase labels but keyed on composition instead.

Snap-only (§6): a request (M1, q, P, [Fe/H]) snaps to the nearest track — never
interpolated, since two different (M1,q,P) tracks have no row-for-row correspondence to
blend across. The nearest-node metric normalizes the wildly different axis spans (M1
spans x73, P spans x5x10^4, q spans <1) by comparing in **log M1, log P, linear q**
space (advisor-settled), over CONVERGED tracks only (the bake already dropped
`interpolation_class == "not_converged"` and any run with missing/misaligned history).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .state import StellarState

# Must match scripts/bake_posydon.py's BAKE_VERSION — a stale npz (baked by an older
# version of the trim/filter logic) is rejected rather than silently misread.
BAKE_VERSION = 1

_REPO_ROOT = Path(__file__).resolve().parents[2]
BAKED_DIR = _REPO_ROOT / "data" / "posydon" / "baked"

# POSYDON's own solar reference metallicity (matches the Zbase encoded in the grid file
# paths); [Fe/H] = log10(Z / POSYDON_SOLAR_Z), the same convention `binary.py` uses for
# the Götberg grid's GOTBERG_SOLAR_Z.
POSYDON_SOLAR_Z = 0.0142

# cgs constants (matching supernova.py's convention) for the log g this grid doesn't
# carry directly (MESA's own history.data has a log_g column; POSYDON's history1/2 do
# not, so we compute it from mass + radius).
_G_CGS = 6.674e-8
_MSUN_G = 1.989e33
_RSUN_CM = 6.957e10

# Honesty thresholds for the snapped-far flags (heuristic, like binary.py's
# _FEH_FAR_DEX — tightened later against real UI feedback, not derived from anything
# deeper). log-dex for the log-spaced axes, linear for q.
_M1_FAR_DEX = 0.10
_P_FAR_DEX = 0.30
_Q_FAR = 0.10
_FEH_FAR_DEX = 0.25


class PosydonDataMissing(RuntimeError):
    """No baked POSYDON grid found under `BAKED_DIR`.

    Never committed (multi-GB source, like the MIST/MESA grids) — the API maps this to
    a 503 with an actionable hint, exactly like a missing MESA profile or spectrum cube.
    """


_MISSING_HINT = (
    "No baked POSYDON grid found under {baked_dir}. Fetch + extract a metallicity's "
    "HMS-HMS grid (see fetch_posydon.py's recipe), then bake it: "
    "python scripts/bake_posydon.py --z-label <label> --feh <feh>."
)


@dataclass
class BinaryStep:
    """One timestep of a co-evolving binary: two stars + the orbit between them."""

    age_yr: float
    star_1: StellarState
    star_2: StellarState | None       # None after a merger (the row the two states cease
                                       # to be physically distinguishable — see _truncate)
    period_d: float
    separation_rsun: float
    ecc: float                        # always 0.0 on this grid — HMS-HMS circularizes;
                                       # documented, not fabricated (no source column)
    mt_state: str                     # "detached" | "RLOF1" | "RLOF2" | "contact"
    mdot_msun_yr: float | None        # mass-TRANSFER rate (binary-level), when transferring
    m1_current_msun: float            # routing scalars — no home on StellarState (only
    m2_current_msun: float            # mass_init lives there), the m_strip_msun precedent


@dataclass
class BinaryTrack:
    """A snapped grid node's full time series, plus the honesty/routing scalars."""

    steps: list[BinaryStep]
    m1_init_msun: float               # the TRUE snapped grid node (never interpolated, §6)
    q_init: float
    p_init_d: float
    feh: float
    m1_snapped_far: bool
    q_snapped_far: bool
    p_snapped_far: bool
    feh_snapped_far: bool
    outcome: str                      # data-derived: "merger" / "stripped + companion" /
                                       # "stable mass transfer" / "unstable mass transfer" /
                                       # "detached (no interaction)" / "unclassified"
    grid_m1_range: tuple[float, float]
    grid_q_range: tuple[float, float]
    grid_p_range: tuple[float, float]


@dataclass(frozen=True)
class _BakedGrid:
    """One baked metallicity's tracks — flat CSR-style arrays (track_row_start/count
    index into the shared `rows` flat arrays), exactly the shape `bake_posydon.py` writes."""

    feh: float
    m1_init: np.ndarray
    q_init: np.ndarray
    p_init_d: np.ndarray
    row_start: np.ndarray
    row_count: np.ndarray
    s1_state: np.ndarray
    s2_state: np.ndarray
    interpolation_class: np.ndarray
    mt_history: np.ndarray
    rows: dict[str, np.ndarray]        # column name (no "row_" prefix) -> flat array


_CACHE: dict[Path, _BakedGrid] = {}


def _load_baked(path: Path) -> _BakedGrid:
    if path in _CACHE:
        return _CACHE[path]
    with np.load(path) as npz:
        if int(npz["bake_version"]) != BAKE_VERSION:
            raise PosydonDataMissing(
                f"{path} was baked with an old BAKE_VERSION — rebake with "
                f"scripts/bake_posydon.py"
            )
        rows = {k[len("row_"):]: npz[k] for k in npz.files if k.startswith("row_")}
        grid = _BakedGrid(
            feh=float(npz["feh"]),
            m1_init=npz["track_m1_init"],
            q_init=npz["track_q_init"],
            p_init_d=npz["track_p_init_d"],
            row_start=npz["track_row_start"],
            row_count=npz["track_row_count"],
            s1_state=npz["track_s1_state"],
            s2_state=npz["track_s2_state"],
            interpolation_class=npz["track_interpolation_class"],
            mt_history=npz["track_mt_history"],
            rows=rows,
        )
    _CACHE[path] = grid
    return grid


def _available_grids() -> list[_BakedGrid]:
    paths = sorted(BAKED_DIR.glob("*.npz")) if BAKED_DIR.is_dir() else []
    if not paths:
        raise PosydonDataMissing(_MISSING_HINT.format(baked_dir=BAKED_DIR))
    return [_load_baked(p) for p in paths]


def _snap_feh(grids: list[_BakedGrid], feh: float) -> _BakedGrid:
    return min(grids, key=lambda g: abs(g.feh - feh))


# --- per-row phase label (composition-derived, since POSYDON gives no per-row phase) --

def _phase_label(center_h1: float, center_he4: float, surface_h1: float) -> str:
    """A coarse, data-derived phase string from the burning-fraction columns that ARE
    per-row (POSYDON's S1_state/S2_state are FINAL-row-only). Not MIST's EEP-window
    vocabulary — a different provenance, so a deliberately different (honest) label set."""
    if center_h1 > 1e-3:
        return "core-H burning" if surface_h1 > 0.1 else "stripped, core-H burning"
    if center_he4 > 1e-3:
        return "core-He burning" if surface_h1 > 0.1 else "stripped He star"
    return "post-He-burning"


def _logg(mass_msun: float, r_rsun: float) -> float:
    m_g = max(mass_msun, 1e-6) * _MSUN_G
    r_cm = max(r_rsun, 1e-6) * _RSUN_CM
    return math.log10(_G_CGS * m_g / (r_cm * r_cm))


def _state_from_row(rows: dict[str, np.ndarray], r: int, prefix: str,
                     mass_init: float, mass_current: float, feh: float) -> StellarState:
    log_l = float(rows[f"{prefix}_log_L"][r])
    log_teff = float(rows[f"{prefix}_log_Teff"][r])
    log_r = float(rows[f"{prefix}_log_R"][r])
    r_rsun = 10.0 ** log_r

    x_s = float(rows[f"{prefix}_surface_h1"][r])
    y_s = float(rows[f"{prefix}_surface_he4"][r])
    z_s = max(0.0, 1.0 - x_s - y_s)
    x_c = float(rows[f"{prefix}_center_h1"][r])
    y_c = float(rows[f"{prefix}_center_he4"][r])
    z_c = max(0.0, 1.0 - x_c - y_c)

    return StellarState(
        age_yr=float(rows["age"][r]),
        eep=0.0,                        # POSYDON tracks carry no EEP — a documented
                                         # sentinel (age_yr is the real time axis here).
        phase=_phase_label(x_c, y_c, x_s),
        mass_init_msun=mass_init,       # this STAR's own initial mass (constant down the
                                         # track); the changing mass is a BinaryStep scalar
        feh_init=feh,
        L_lsun=10.0 ** log_l,
        Teff_K=10.0 ** log_teff,
        R_rsun=r_rsun,
        logg=_logg(mass_current, r_rsun),
        X_surf=x_s, Y_surf=y_s, Z_surf=z_s,
        X_core=x_c, Y_core=y_c, Z_core=z_c,
        metals_surf={
            "C": float(rows[f"{prefix}_surface_c12"][r]),
            "N": float(rows[f"{prefix}_surface_n14"][r]),
            "O": float(rows[f"{prefix}_surface_o16"][r]),
        },
        metals_core={
            "C": float(rows[f"{prefix}_center_c12"][r]),
            "N": float(rows[f"{prefix}_center_n14"][r]),
            "O": float(rows[f"{prefix}_center_o16"][r]),
        },
        v_rot_kms=None,   # not baked this pass (surf_avg_omega is on the raw grid but
        activity=None,    # unused downstream today — an honest gap, not a fabrication)
        mdot_msun_yr=None,
    )


def _mt_state(rl1: float, rl2: float) -> str:
    if rl1 > 0.0 and rl2 > 0.0:
        return "contact"
    if rl1 > 0.0:
        return "RLOF1"
    if rl2 > 0.0:
        return "RLOF2"
    return "detached"


def _outcome(s1_state: str, s2_state: str, interpolation_class: str) -> str:
    """A data-derived one-line fate label from the track's FINAL-row classification."""
    if s1_state == "None" or s2_state == "None":
        return "merger"
    if "stripped_He" in s1_state or "stripped_He" in s2_state or "accreted" in s2_state:
        return "stripped + companion"
    if interpolation_class == "unstable_MT":
        return "unstable mass transfer"
    if interpolation_class in ("stable_MT", "stable_reverse_MT", "initial_MT"):
        return "stable mass transfer"
    if interpolation_class == "no_MT":
        return "detached (no interaction)"
    return "unclassified"


def _snap_track_index(grid: _BakedGrid, m1: float, q: float, p: float) -> int:
    """Nearest track in (log M1, log P, linear q) — never interpolated (§6): two
    different (M1,q,P) tracks have no row-for-row correspondence to blend across."""
    d_m1 = np.log10(grid.m1_init) - math.log10(max(m1, 1e-3))
    d_p = np.log10(grid.p_init_d) - math.log10(max(p, 1e-3))
    d_q = grid.q_init - q
    dist = d_m1 * d_m1 + d_p * d_p + d_q * d_q
    return int(np.argmin(dist))


def binary_track(m1: float, q: float, p: float, feh: float = 0.0) -> BinaryTrack:
    """(M1, q=M2/M1, P_init [days], [Fe/H]) -> the snapped POSYDON HMS-HMS track: both
    stars' full StellarState history + the orbit, exactly as `bake_posydon.py` recorded
    it (decimated for very long tracks, never interpolated across tracks)."""
    grids = _available_grids()
    grid = _snap_feh(grids, feh)
    idx = _snap_track_index(grid, m1, q, p)

    m1_node = float(grid.m1_init[idx])
    q_node = float(grid.q_init[idx])
    p_node = float(grid.p_init_d[idx])
    m2_node = q_node * m1_node

    start = int(grid.row_start[idx])
    count = int(grid.row_count[idx])
    rows = grid.rows

    steps: list[BinaryStep] = []
    for j in range(count):
        r = start + j
        m1_cur = float(rows["star_1_mass"][r])
        m2_cur = float(rows["star_2_mass"][r])
        # A non-finite / non-positive mass marks a row the MESA-binary run could no longer
        # resolve as two stars — truncate here (the endgame terminal-row-exclusion
        # precedent) rather than emit a broken StellarState. In PRACTICE, on this grid a
        # merger (`outcome == "merger"`) shows up as a short track that simply stops before
        # any such row (no observed row explicitly sets a null star_2 — `star_2` staying
        # Optional is forward-compatible with a grid that DOES encode one, not a claim that
        # this one does).
        if not (np.isfinite(m1_cur) and np.isfinite(m2_cur) and m1_cur > 0 and m2_cur > 0):
            break

        star_1 = _state_from_row(rows, r, "s1", m1_node, m1_cur, grid.feh)
        star_2 = _state_from_row(rows, r, "s2", m2_node, m2_cur, grid.feh)

        rl1 = float(rows["rl_relative_overflow_1"][r])
        rl2 = float(rows["rl_relative_overflow_2"][r])
        mt_state = _mt_state(rl1, rl2)
        lg_mdot = float(rows["lg_mtransfer_rate"][r])
        mdot = 10.0 ** lg_mdot if mt_state != "detached" and -30.0 < lg_mdot < 10.0 else None

        steps.append(BinaryStep(
            age_yr=float(rows["age"][r]),
            star_1=star_1,
            star_2=star_2,
            period_d=float(rows["period_days"][r]),
            separation_rsun=float(rows["binary_separation"][r]),
            ecc=0.0,
            mt_state=mt_state,
            mdot_msun_yr=mdot,
            m1_current_msun=m1_cur,
            m2_current_msun=m2_cur,
        ))

    return BinaryTrack(
        steps=steps,
        m1_init_msun=m1_node,
        q_init=q_node,
        p_init_d=p_node,
        feh=grid.feh,
        m1_snapped_far=abs(math.log10(m1_node) - math.log10(max(m1, 1e-3))) > _M1_FAR_DEX,
        q_snapped_far=abs(q_node - q) > _Q_FAR,
        p_snapped_far=abs(math.log10(p_node) - math.log10(max(p, 1e-3))) > _P_FAR_DEX,
        feh_snapped_far=abs(grid.feh - feh) > _FEH_FAR_DEX,
        outcome=_outcome(str(grid.s1_state[idx]), str(grid.s2_state[idx]),
                          str(grid.interpolation_class[idx])),
        grid_m1_range=(float(grid.m1_init.min()), float(grid.m1_init.max())),
        grid_q_range=(float(grid.q_init.min()), float(grid.q_init.max())),
        grid_p_range=(float(grid.p_init_d.min()), float(grid.p_init_d.max())),
    )


def binary_track_meta(feh: float = 0.0) -> dict:
    """The grid bounds at the nearest available [Fe/H] — for UI gating, mirroring the
    `/endgame?meta=1` fast-path (don't ship a whole track just to size a slider)."""
    grids = _available_grids()
    grid = _snap_feh(grids, feh)
    return {
        "feh": grid.feh,
        "available_feh": sorted({g.feh for g in grids}),
        "m1_min": float(grid.m1_init.min()),
        "m1_max": float(grid.m1_init.max()),
        "q_min": float(grid.q_init.min()),
        "q_max": float(grid.q_init.max()),
        "p_min": float(grid.p_init_d.min()),
        "p_max": float(grid.p_init_d.max()),
        "n_tracks": int(grid.m1_init.size),
    }


def binary_track_payload(m1: float, q: float, p: float, feh: float = 0.0) -> dict:
    """JSON-friendly `/binary_track` payload: each step's two StellarStates (exact §3
    dict shape, `star_2` possibly null after a merger) + the orbital/routing scalars,
    plus the track-level snap/outcome metadata."""
    from dataclasses import asdict

    track = binary_track(m1, q, p, feh)
    return {
        "steps": [
            {
                "age_yr": s.age_yr,
                "star_1": asdict(s.star_1),
                "star_2": asdict(s.star_2) if s.star_2 is not None else None,
                "period_d": s.period_d,
                "separation_rsun": s.separation_rsun,
                "ecc": s.ecc,
                "mt_state": s.mt_state,
                "mdot_msun_yr": s.mdot_msun_yr,
                "m1_current_msun": s.m1_current_msun,
                "m2_current_msun": s.m2_current_msun,
            }
            for s in track.steps
        ],
        "m1_init_msun": track.m1_init_msun,
        "q_init": track.q_init,
        "p_init_d": track.p_init_d,
        "feh": track.feh,
        "m1_snapped_far": track.m1_snapped_far,
        "q_snapped_far": track.q_snapped_far,
        "p_snapped_far": track.p_snapped_far,
        "feh_snapped_far": track.feh_snapped_far,
        "outcome": track.outcome,
        "grid_m1_range": list(track.grid_m1_range),
        "grid_q_range": list(track.grid_q_range),
        "grid_p_range": list(track.grid_p_range),
    }
