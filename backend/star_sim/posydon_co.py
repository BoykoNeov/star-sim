"""POSYDON CO-HMS_RLO compact-object binary tracks — path (b) Phase 1 Chunk 1a
(docs/plans/tempered-lineage-inspiral.md).

The built path (b) (`posydon.py`) covers only the FIRST mass-transfer episode between two
normal, hydrogen-burning stars (the POSYDON HMS-HMS grid). This module covers what happens
AFTER one star has already died: a compact object (NS/BH, occasionally a WD) orbits a
still hydrogen-rich secondary. If the secondary later overflows its Roche lobe onto the
compact object, accretion releases gravitational potential energy — a genuinely new
luminosity mechanism for this sim (not photospheric). This grid (and the cue below) covers
**Roche-lobe-overflow-fed** accretion specifically — the wind-fed configuration (Cygnus
X-1's own real system: a BH accreting from its O-star companion's stellar wind, not RLOF)
is a DIFFERENT accretion channel this grid doesn't model and this module doesn't claim to
cover; don't read the "X-ray binary" language below as covering that case.

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

**Scoped to STABLE RLOF-phase accretion onto a NEUTRON STAR / BLACK HOLE only** — the cue
is `None` whenever `mt_state == "detached"`, OR the track's POSYDON `interpolation_class ==
"unstable_MT"`, OR the companion is a `co_type == "WD"` (see the `active` gate in
`co_binary_track`). Characterized across the WHOLE 8-bucket baked grid (every stable-transfer
NS/BH active row): <=3.46x the CO's own Eddington luminosity (median ~2.3-2.6x), a real
bounded mildly-super-Eddington/ULX-like regime, no cap needed. **That bound (and the cue's
physical validity) holds BECAUSE of the three-part gate, not as an intrinsic property of the
formula:**
  * over DETACHED rows, `lg_mstar_dot_2` reaches values that would push this formula to
    ~10^14 Lsun (a non-transferring-row artifact);
  * over `unstable_MT` tracks (CE/merger — dynamically unstable, not a clean X-ray binary),
    a handful of runaway `lg_mstar_dot_2` spikes push it to ~10^5x Eddington / ~10^13x the
    star's own L (a Chunk-1c finding — solar happened to carry none, but the metal-poor
    grids do; measured across all 8 buckets, all three outliers were `unstable_MT`);
  * over `WD`-companion tracks, `ACCRETION_EFFICIENCY = 0.1` is simply the WRONG regime — it
    is a NS/BH-depth-potential-well efficiency (GM/Rc^2); a white dwarf's surface potential is
    ~2-3 dex shallower (eta ~ 1e-3..1e-4), so eta=0.1 overstates a WD accretor's accretion
    luminosity by 100-1000x (measured Chunk-1c follow-up: 94 WD-companion tracks would surface
    a cue up to ~55,000 Lsun on the placeholder-frozen 1.0-Msun WD channel). The WD channel is
    already a documented placeholder (every WD node is exactly 1.00 Msun, see the recon note
    above), so the honest move is to defer the cue entirely rather than paint a 3-dex-wrong
    number — consistent with the honesty tiering elsewhere in the sim (don't fabricate; defer).
The cue models a STABLE X-ray-binary accretion luminosity onto a NS/BH, which neither an
unstable-MT episode nor a WD accretor physically is — so gating it off there is honest, not a
magic-number cap. Wind-fed
accretion (e.g. Cyg X-1's own configuration, the plan's motivating example) is likewise
NOT captured this pass — a detached CO orbiting a normal star shows no accretion cue here,
even though a real wind-fed X-ray binary would. Broadening the `active` gate (wind
accretion, or re-admitting unstable MT) reopens an unbounded tail and would need its own
cap — don't do it by loosening the filter without re-deriving the bound.

--- Phase 1 Chunk 2a: the CO-HeMS / CO-HeMS_RLO He-star kinds + the DCO classifier ---

This module now serves THREE CO grid kinds (`VALID_KINDS`), selected by the `kind` argument
(default "co-hms-rlo", behavior-compatible with Chunk 1a — the payload only GAINS additive
`kind`/`dco` keys, `dco` being None for this kind). "co-hems" and "co-hems-rlo" are the
double-compact-object channel: the SAME single-real-star schema (schema recon 2026-07-08
confirmed `history2` absent + every column present — a confirmed drop-in), except the
surviving star (S1) is a bare HE STAR orbiting the compact object — the direct progenitor of
a BH-BH / NS-BH / NS-NS gravitational-wave-merger binary.

  * The He-star StellarState history + the accretion cue (on CO-HeMS_RLO, a He/Case-BB/BC
    donor) are Tier-1/2 real, exactly as for CO-HMS_RLO.
  * The DCO endpoint (`CoBinaryTrack.dco`, He kinds only) is the novel honest GW payoff:
    POSYDON's own SN-model prediction of what S1 becomes (`sn_co_type`/`sn_mass`/`sn_type`,
    from the pinned default prescription baked per track) COMBINED with the known existing
    companion S2 -> "BH + BH" / "NS + BH" / "NS + NS", or an honest "no DCO" when either
    ends a white dwarf / is unresolved. It reuses no kick model and computes no merger TIME
    (that needs the post-second-SN orbit, which this grid does not contain — see
    `DcoClassification`). The prescription is labeled BY INDEX (POSYDON ships 24), the
    boron-b8 discipline; the choice is caption-owned.

**The Eddington bound is RE-DERIVED for the He grids, not inherited.** He-star (Case BB/BC)
RLOF can in principle transfer faster than an H-donor grid, so 3.46x was NOT assumed to carry
over. Measured 2026-07-08 across BOTH He SOLAR grids, split by the same three-part `active`
gate: max **3.47x** the CO's own Eddington luminosity — the same physical ULX ceiling as
CO-HMS_RLO (POSYDON caps stable transfer). This is a SOLAR-ONLY characterization; the
metal-poor He buckets carry the same class of `unstable_MT` artifact CO-HMS_RLO's did (Chunk
1c found solar clean but the metal-poor grids at 505,221x), so the bound MUST be re-derived
across all 8 He buckets when Chunk 2c extracts them — do not re-ship the Chunk-1a->1c mistake.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from .binary import track_roche_geometry
from .posydon import mt_state_label, state_from_row
from .state import StellarState

# Must match scripts/bake_posydon.py's BAKE_VERSION_CO — a stale npz (baked by an older
# version of the CO trim/filter logic) is rejected rather than silently misread.
BAKE_VERSION_CO = 1

_REPO_ROOT = Path(__file__).resolve().parents[2]
BAKED_CO_DIR = _REPO_ROOT / "data" / "posydon" / "baked_co"
BAKED_CO_HEMS_DIR = _REPO_ROOT / "data" / "posydon" / "baked_co_hems"
BAKED_CO_HEMS_RLO_DIR = _REPO_ROOT / "data" / "posydon" / "baked_co_hems_rlo"

# The three CO grid types this sibling serves — all share bake_co()'s one-real-star + CO-scalar
# shape, differing only in the surviving star and the payoff (Chunk 2a). Each grid type has its
# OWN baked dir (never mixed in one glob — the "a CO npz misread in the wrong dir" lesson):
#   * "co-hms-rlo" — the original (Chunk 1a): a compact object + a still-H-RICH secondary; the
#     X-ray-binary accretion payoff. NO DCO story (S1 is nowhere near collapse).
#   * "co-hems"     — a compact object + a bare HE-STAR secondary, DETACHED-inspiral-dominated;
#     the double-compact-object (GW-progenitor) CLASSIFICATION payoff.
#   * "co-hems-rlo" — the same He-star secondary but in a Roche-lobe-overflow episode: the
#     He-donor (Case BB/BC) accretion payoff, and a DCO endpoint too (mostly WD/unresolved here).
# NOTE the one-letter "co-hms-rlo" vs "co-hems-rlo" hazard — always validate `kind` against
# VALID_KINDS (the API does), never string-slice it.
_KIND_DIRS = {
    "co-hms-rlo": BAKED_CO_DIR,
    "co-hems": BAKED_CO_HEMS_DIR,
    "co-hems-rlo": BAKED_CO_HEMS_RLO_DIR,
}
VALID_KINDS = tuple(_KIND_DIRS)
DEFAULT_KIND = "co-hms-rlo"
# The kinds whose surviving star is a He star about to collapse — the only ones for which a
# double-compact-object endpoint is physically meaningful (and where `dco` is surfaced).
_HE_KINDS = ("co-hems", "co-hems-rlo")

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
    """No baked grid found for the requested CO grid kind under its baked dir.

    Never committed (multi-GB source, like the HMS-HMS grid) — the API maps this to a 503
    with an actionable hint, exactly like a missing HMS-HMS bake."""


_MISSING_HINT = (
    "No baked POSYDON {kind} grid found under {baked_dir}. Extract + bake a metallicity's "
    "{kind} grid (see scripts/bake_posydon.py's docstring recipe): "
    "python scripts/bake_posydon.py --grid-type {kind} --z-label <label> --feh <feh>."
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
class DcoClassification:
    """The double-compact-object endpoint of a CO-HeMS / CO-HeMS_RLO system (Chunk 2a).

    Combines the KNOWN existing compact object (S2, already in the binary) with POSYDON's own
    prediction of what the surviving He star (S1) becomes when IT collapses — under one pinned
    core-collapse prescription (`sn_model`, labeled by index; POSYDON ships 24). This is the
    honest, kick-free GW-progenitor payoff (see the module docstring's honesty-tier note):
      * both remnants NS/BH  -> a real merger progenitor ("BH + BH" / "NS + BH" / "NS + NS");
      * either a WD          -> no double-compact merger (a WD isn't a GW-merger component here);
      * either unresolved    -> POSYDON's classifier didn't resolve a fate ("None").

    NOT a merger TIME — that needs the post-second-SN orbit (a natal-kick model this grid does
    not serve), so it is two prescriptions deep and deliberately NOT computed (module docstring)."""

    is_dco: bool
    label: str                        # human one-liner ("BH + BH merger progenitor", etc.)
    s1_remnant_type: str              # what the He star becomes: "BH"|"NS"|"WD"|"None"
    s2_co_type: str                   # the existing compact object: "BH"|"NS"|"WD"|"None"
    s1_remnant_mass_msun: float | None   # predicted remnant mass (None if unresolved/nan)
    s2_mass_msun: float               # the CO's FINAL-row (post-accretion) mass, not m_co_init
    sn_type: str                      # S1's SN channel under the prescription (CCSN/ECSN/WD/None)
    sn_model: str                     # the pinned prescription, labeled by index (honesty)


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
    kind: str                        # which CO grid this track came from (VALID_KINDS)
    dco: DcoClassification | None    # the double-compact-object endpoint (He kinds only; None
                                      # for co-hms-rlo, whose H-rich star has no DCO story)


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
    # The pinned SN-model prediction of what the surviving star becomes at collapse (the DCO
    # classifier's per-track inputs — Chunk 2a). ALL None for a bake made before Chunk 2a
    # (the CO-HMS_RLO buckets were not re-baked): read optionally, so an old npz still loads.
    sn_model_default: str | None
    sn_co_type: np.ndarray | None      # {"BH","NS","WD","None"} — the He star's future remnant
    sn_type: np.ndarray | None         # {"CCSN","ECSN","WD","None",...}
    sn_mass: np.ndarray | None         # remnant mass / Msun (nan where unresolved)
    sn_f_fb: np.ndarray | None         # fallback fraction
    sn_spin: np.ndarray | None         # dimensionless remnant spin


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
        # SN-model scalars are read OPTIONALLY (Chunk 2a additive fields) — an old
        # CO-HMS_RLO npz predates them, so all SN fields stay None and `dco` is never
        # surfaced for it (which is correct — a still-H-rich star has no DCO story).
        have_sn = "track_sn_CO_type" in npz.files
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
            sn_model_default=str(npz["sn_model_default"]) if have_sn else None,
            sn_co_type=npz["track_sn_CO_type"] if have_sn else None,
            sn_type=npz["track_sn_SN_type"] if have_sn else None,
            sn_mass=npz["track_sn_mass"] if have_sn else None,
            sn_f_fb=npz["track_sn_f_fb"] if have_sn else None,
            sn_spin=npz["track_sn_spin"] if have_sn else None,
        )
    _CACHE[path] = grid
    return grid


def _resolve_kind(kind: str) -> str:
    """Validate `kind` against the explicit VALID_KINDS set (never string-slice — the
    one-letter co-hms-rlo/co-hems-rlo hazard). Raises ValueError for the API to map to 422."""
    if kind not in _KIND_DIRS:
        raise ValueError(
            f"unknown CO grid kind {kind!r} — expected one of {VALID_KINDS}"
        )
    return kind


def _available_grids(kind: str = DEFAULT_KIND) -> list[_BakedCoGrid]:
    kind = _resolve_kind(kind)
    baked_dir = _KIND_DIRS[kind]
    paths = sorted(baked_dir.glob("*.npz")) if baked_dir.is_dir() else []
    if not paths:
        raise PosydonCoDataMissing(_MISSING_HINT.format(kind=kind, baked_dir=baked_dir))
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


# The three NS/BH double-compact-object endpoints, keyed by the sorted (type, type) pair so
# the label is order-independent (S1-remnant vs S2 doesn't change the merger's name).
_DCO_LABELS = {
    ("BH", "BH"): "BH + BH merger progenitor",
    ("BH", "NS"): "NS + BH merger progenitor",
    ("NS", "NS"): "NS + NS merger progenitor",
}


def dco_classification(
    s1_remnant_type: str,
    s2_co_type: str,
    s1_remnant_mass_msun: float | None,
    s2_mass_msun: float,
    sn_type: str,
    sn_model: str,
) -> DcoClassification:
    """Classify the double-compact-object endpoint from S1's predicted remnant + the known S2.

    Keys off the remnant TYPE (not `sn_type`), which handles every channel uniformly — a
    pair-instability SN (at low Z, reached in Chunk 2c) leaves no remnant, so POSYDON reports
    its CO_type as "None" and this falls through to the honest unresolved branch for free."""
    r1 = s1_remnant_type if s1_remnant_type in ("BH", "NS", "WD") else "None"
    r2 = s2_co_type if s2_co_type in ("BH", "NS", "WD") else "None"
    mass = (s1_remnant_mass_msun
            if s1_remnant_mass_msun is not None and math.isfinite(s1_remnant_mass_msun)
            else None)

    if r1 == "None" or r2 == "None":
        label = "no clean endpoint — POSYDON did not resolve a remnant fate"
        is_dco = False
    elif r1 == "WD" or r2 == "WD":
        # A white dwarf isn't a NS/BH GW-merger component in this channel — honest "no DCO".
        which = "the He star" if r1 == "WD" else "the companion"
        label = f"no double-compact merger — {which} ends as a white dwarf"
        is_dco = False
    else:
        label = _DCO_LABELS[tuple(sorted((r1, r2)))]
        is_dco = True

    return DcoClassification(
        is_dco=is_dco,
        label=label,
        s1_remnant_type=r1,
        s2_co_type=r2,
        s1_remnant_mass_msun=mass,
        s2_mass_msun=s2_mass_msun,
        sn_type=sn_type,
        sn_model=sn_model,
    )


def co_binary_track(m_star: float, m_co: float, p: float, feh: float = 0.0,
                    kind: str = DEFAULT_KIND) -> CoBinaryTrack:
    """(M_star, M_co_init, P_init [days], [Fe/H], kind) -> the snapped POSYDON CO track:
    the surviving star's full StellarState history + the compact object's mass/accretion
    time series + the orbit, exactly as `bake_posydon.py --grid-type <kind>` recorded it
    (decimated for very long tracks, never interpolated across tracks).

    `kind` selects the grid (VALID_KINDS): the default "co-hms-rlo" (an H-rich secondary) is
    behavior-compatible with Chunk 1a (only additive `kind`/`dco` payload keys, `dco` None
    here); "co-hems"/"co-hems-rlo" are the He-star double-compact-object
    grids (Chunk 2a) — for those, the returned track also carries a `dco` classification of the
    binary's eventual double-compact endpoint."""
    kind = _resolve_kind(kind)
    grids = _available_grids(kind)
    grid = _snap_feh(grids, feh)
    idx = _snap_track_index(grid, m_star, m_co, p)

    m_star_node = float(grid.m_star_init[idx])
    m_co_node = float(grid.m_co_init[idx])
    p_node = float(grid.p_init_d[idx])
    co_type = str(grid.co_type[idx])
    interp_class = str(grid.interpolation_class[idx])
    # POSYDON's own dynamical-stability class for the WHOLE track. The accretion-luminosity
    # cue models STABLE Roche-lobe overflow (a clean X-ray binary); on an `unstable_MT`
    # track the transfer runs away into a common envelope / merger, so the parametrized
    # `lg_mstar_dot_2` spikes to physically-meaningless values (measured on the full 8-bucket
    # grid: a handful of unstable_MT rows push the cue to ~10^5x Eddington / ~10^13x the
    # star's own L — pure artifact) and is NOT a real accretion luminosity. Gate the cue off
    # for these tracks (see the `active` mask below). This is why the module docstring's
    # tight bound is stated for stable transfer only.
    is_unstable_mt = interp_class == "unstable_MT"
    # The accretion cue's `ACCRETION_EFFICIENCY = 0.1` is a NS/BH efficiency (deep potential
    # well). A white dwarf's surface potential is ~2-3 dex shallower, so eta=0.1 overstates a
    # WD accretor's luminosity by 100-1000x; the WD channel is a placeholder anyway (frozen
    # 1.0 Msun, see the module docstring's recon note). Gate the cue off for WD companions —
    # deferring beats painting a 3-dex-wrong number (Chunk-1c follow-up).
    is_wd = co_type == "WD"

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
        # The `active` mask is what BOUNDS the cue — it is not just an activity flag. Two
        # load-bearing conditions, each measured against a real artifact tail on the full
        # 8-bucket grid:
        #   * `mt_state != "detached"`: DETACHED rows carry `lg_mstar_dot_2` values that push
        #     `_accretion_luminosity` to ~10^14 Lsun (a non-transferring-row artifact).
        #   * `not is_unstable_mt`: `unstable_MT` tracks (CE/merger, POSYDON's own instability
        #     class) carry runaway `lg_mstar_dot_2` spikes that push the cue to ~10^5x
        #     Eddington / ~10^13x the star's own L (Chunk-1c finding, measured across all 8
        #     buckets — solar happened to have none, the metal-poor grids do). The cue models
        #     a STABLE X-ray-binary accretion luminosity, which an unstable-MT episode is not.
        #   * `not is_wd`: the cue's eta=0.1 is a NS/BH efficiency, ~2-3 dex too deep for a
        #     white dwarf's shallow potential well (and the WD channel is a placeholder), so a
        #     WD-companion cue would be 100-1000x too bright — defer it (Chunk-1c follow-up).
        # WITH all three conditions the cue is bounded to <=3.46x the CO's own Eddington
        # luminosity grid-wide (the mildly-super-Eddington ULX regime) AND is only ever painted
        # for the NS/BH regime it's physically valid in. Widening this gate (e.g. to add
        # wind-fed accretion, or a WD-appropriate eta) re-opens an unbounded/wrong-regime tail —
        # re-derive the bound, don't just relax the `-30 < lg2 < 10` magnitude filter.
        active = (mt_state != "detached" and not is_unstable_mt and not is_wd
                  and -30.0 < lg_mdot2 < 10.0)
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

    # DCO endpoint — only for the He-star kinds (co-hms-rlo's H-rich star has no DCO story)
    # AND only when the bake recorded the SN-model scalars (an old CO-HMS_RLO npz has none,
    # so `dco` stays None — the optional-load degrades to "no DCO", never an error).
    dco = None
    if kind in _HE_KINDS and grid.sn_co_type is not None:
        # S2's mass is the FINAL-row (post-accretion) mass, not m_co_init (advisor); S1's
        # remnant mass is POSYDON's own prediction, read off the snapped track (never blended).
        s2_final_mass = steps[-1].co_mass_msun if steps else float(grid.m_co_init[idx])
        dco = dco_classification(
            s1_remnant_type=str(grid.sn_co_type[idx]),
            s2_co_type=co_type,
            s1_remnant_mass_msun=float(grid.sn_mass[idx]),
            s2_mass_msun=s2_final_mass,
            sn_type=str(grid.sn_type[idx]),
            sn_model=grid.sn_model_default,   # guaranteed set when sn_co_type is not None
        )

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
        kind=kind,
        dco=dco,
    )


def co_binary_track_meta(feh: float = 0.0, kind: str = DEFAULT_KIND) -> dict:
    """The grid bounds at the nearest available [Fe/H] for the requested `kind` — for UI
    gating, mirroring `posydon.py`'s `binary_track_meta` (don't ship a whole track just to
    size a slider)."""
    kind = _resolve_kind(kind)
    grids = _available_grids(kind)
    grid = _snap_feh(grids, feh)
    return {
        "kind": kind,
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


def co_binary_track_payload(m_star: float, m_co: float, p: float, feh: float = 0.0,
                            kind: str = DEFAULT_KIND) -> dict:
    """JSON-friendly `/co_binary_track` payload: each step's one real StellarState (exact
    §3 dict shape) + the compact-object routing scalars + the orbit, plus the track-level
    snap/outcome metadata (and, for the He kinds, a `dco` double-compact-object endpoint
    block) — mirrors `posydon.py`'s `binary_track_payload` shape."""
    track = co_binary_track(m_star, m_co, p, feh, kind)

    # Per-step Roche-lobe geometry (Chunk 1b) — reuse `binary.track_roche_geometry`, the
    # SAME engine the HMS-HMS movie uses (sibling-calls-sibling). It duck-types on
    # `m1_current_msun`/`m2_current_msun`/`separation_rsun`, so adapt each `CoBinaryStep`:
    # the normal star is the DONOR (origin), the compact object is the accretor at (1, 0),
    # giving q = m_co/m_star. The engine draws a lobe outline for the CO side too, but the
    # frontend renders that side as a schematic point-mass marker (a CO has no photosphere),
    # NOT a Teff disc — the lobe is still meaningful (the accretion target), the disc is not.
    adapted = [
        SimpleNamespace(
            m1_current_msun=s.star_current_msun,
            m2_current_msun=s.co_mass_msun,
            separation_rsun=s.separation_rsun,
        )
        for s in track.steps
    ]
    roche = track_roche_geometry(adapted)

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
                "roche": g,
            }
            for s, g in zip(track.steps, roche)
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
        "kind": track.kind,
        "dco": asdict(track.dco) if track.dco is not None else None,
    }
