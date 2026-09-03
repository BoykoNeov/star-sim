"""Binaries: stripped stars, the two-star system, and the POSYDON co-evolution grids.

A two-star result can't pass through the single-star `StellarState` interface (§3),
so the payloads are built by siblings (`binary.py`, `posydon.py`, `posydon_co.py`)
over snap-to-nearest grids. `/binary_pair` is the exception that proves the rule: the
stripped DONOR comes from the sibling, but the COMPANION is an ordinary single star,
so it comes straight from `provider()` — and the two are composed *here*, in the
router, precisely so `binary.py` never learns that a provider exists.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from ..binary import (
    binary_pair_payload,
    companion_init_mass,
    stripped_star,
    stripped_star_payload,
)
from ..posydon import binary_track_meta, binary_track_payload
from ..posydon_co import co_binary_track_meta, co_binary_track_payload
from ._deps import provider

router = APIRouter()


@router.get("/binary")
def binary(
    mass: float = Query(..., gt=0.0, description="progenitor initial mass / M_sun"),
    feh: float = Query(0.0, description="initial [Fe/H]"),
) -> dict:
    """(progenitor mass, [Fe/H]) -> the hot He-star it becomes if stripped in a close
    binary — the ~70% binary WR/subdwarf channel (docs/plans/stripped-consort-unveiling.md).

    Like `/polytrope`, `/structure` and `/supernova`, this does **not** go through
    `PROVIDER`: a binary product cannot pass through the single-star `StellarState`
    interface (§3). It is a sibling — `binary.py` reads the committed Götberg 2018
    stripped-star table, **snaps** to the nearest grid model in (Z, initial mass) — never
    interpolates (§6) — and returns a `StellarState` (exact §3 shape, under `state`, for
    the existing 3D/HR/comp/spectrum consumers) plus routing scalars: the CURRENT stripped
    mass `M_strip` (which has no home on the state), the true snapped `M_init`/Z, and the
    eligible progenitor-mass range + snapped-far flags the frontend gates its stripped-mode
    toggle and caption on.

    Snap-always (like `/structure`): an out-of-grid request snaps to the nearest node and
    is flagged in-band (`mass_snapped_far` / `feh_snapped_far`) rather than 422'd — the
    hide-below-2 / note-above-18.2 UX decision is the frontend's, reading those flags. 422
    is reserved for structurally invalid input (mass ≤ 0, enforced by the Query bound); a
    missing committed table (should never happen) → 503."""
    return stripped_star_payload(mass, feh)


def _donor_ms_lifetime(mass: float, feh: float) -> float:
    """Elapsed system age when the donor fills its Roche lobe and is stripped ≈ the
    donor's single-star main-sequence lifetime = the age at TAMS (the first post-MS row)
    on its own MIST track. The companion, being less massive (q=0.8), is still on the MS
    at this age — so the two-star view never shows a degenerate off-track companion (the
    path (b) measure-first gate confirmed this holds across the whole eligible grid).

    Lives in the router, not in `binary.py`: it needs `provider()`, and a sibling may
    never import the provider layer (§3)."""
    track = provider().track(mass, feh)
    for s in track:
        if s.phase != "MS":
            return s.age_yr
    return track[-1].age_yr


@router.get("/binary_pair")
def binary_pair(
    mass: float = Query(..., gt=0.0, description="progenitor (donor) initial mass / M_sun"),
    feh: float = Query(0.0, description="initial [Fe/H]"),
) -> dict:
    """(donor initial mass, [Fe/H]) -> the two-star Algol system: the stripped He-star
    DONOR (same top-level shape as `/binary`) PLUS its close companion (the accretor).
    Path (b) of docs/plans/stripped-consort-unveiling.md — "the companion drawn."

    The companion is composed HERE, in the route — NOT in `binary.py`, which stays a pure
    §3 sibling. A *binary product* can't go through the single-star interface, but the
    *companion* is an ordinary single star, so it comes straight from `PROVIDER`. Baseline
    (non-conservative): the companion is a single star at its known initial mass
    M2_init = 0.8·M_init (the grid's fixed q), observed at the elapsed system age = the
    donor's MS lifetime (the donor is stripped at ≈TAMS). Because the companion is less
    massive it is still on the MS then; the mass-ratio *reversal* (M_strip < M2_init) is
    the payoff — see `binary.binary_pair_payload`.

    Both stars share the snapped system metallicity (`feh_snapped`): the donor grid is
    coarse in Z (solar-only for now), so the whole system snaps to the donor's grid Z and
    the companion follows — a binary has one metallicity. Snap-always like `/binary`; a
    missing committed table -> 503, and if the MIST grids are absent the companion fetch
    surfaces the usual data-unavailable 503."""
    donor = stripped_star(mass, feh)
    feh_sys = donor.feh_snapped                       # both stars at the snapped system Z
    m2 = companion_init_mass(donor.m_init_msun)       # 0.8 × the snapped donor node
    tau = _donor_ms_lifetime(donor.m_init_msun, feh_sys)
    companion = provider().state_at(m2, feh_sys, tau)
    return binary_pair_payload(mass, feh, companion, tau)


@router.get("/binary_track_meta")
def binary_track_meta_route(
    feh: float = Query(0.0, description="initial [Fe/H] (snaps to the nearest baked grid)"),
) -> dict:
    """[Fe/H] -> the baked POSYDON HMS-HMS grid bounds (M1/q/P ranges + track count) at
    the nearest available metallicity — for UI gating, mirroring the `/endgame?meta=1`
    fast path (don't ship a whole time-series track just to size a slider)."""
    return binary_track_meta(feh)


@router.get("/binary_track")
def binary_track_route(
    m1: float = Query(..., gt=0.0, description="donor (star 1) initial mass / M_sun"),
    q: float = Query(..., gt=0.0, le=1.0, description="mass ratio M2/M1 at t=0"),
    p: float = Query(..., gt=0.0, description="initial orbital period / days"),
    feh: float = Query(0.0, description="initial [Fe/H]"),
) -> dict:
    """(M1, q, P, [Fe/H]) -> a co-evolved POSYDON HMS-HMS binary track: both stars'
    full time history (paired `StellarState`s) + the real orbit — path (b) Chunk 4a
    (docs/plans/entwined-consort-inspiral.md), the on-ramp to the two-star HR *movie*
    that `/binary_pair`'s single snapshot can't give (the Algol reversal as it happens,
    not a caption).

    Unlike `/binary` and `/binary_pair`, this does **not** go through `PROVIDER` for a
    different reason than usual: it's not just that a two-star result can't fit the
    single-star interface (§3) — it's a genuine TIME SERIES, the first of its kind among
    the siblings. Each step is two `StellarState`s (`star_2` is `null` after a merger)
    plus orbital scalars (period, separation, eccentricity — always 0.0 on this
    tidally-circularized grid — and a data-derived `mt_state` that flags RLOF/contact
    episodes as they fire).

    Snap-always (the `/binary` precedent): (M1, q, P) snaps to the nearest real POSYDON
    track in normalized (log M1, log P, linear q) space — never interpolated (§6, no
    row-for-row correspondence between tracks to blend) — and the true snapped node is
    reported alongside in-band `*_snapped_far` honesty flags. 422 is reserved for
    structurally invalid input (the Query bounds); a missing baked grid -> 503."""
    return binary_track_payload(m1, q, p, feh)


@router.get("/co_binary_track_meta")
def co_binary_track_meta_route(
    feh: float = Query(0.0, description="initial [Fe/H] (snaps to the nearest baked grid)"),
    kind: str = Query("co-hms-rlo", description="CO grid: co-hms-rlo (H-rich secondary, "
                       "default) | co-hems | co-hems-rlo (He-star double-compact channel)"),
) -> dict:
    """([Fe/H], kind) -> the baked POSYDON CO grid bounds (M_star/M_co/P ranges + track
    count) at the nearest available metallicity — mirrors `/binary_track_meta`."""
    try:
        return co_binary_track_meta(feh, kind)
    except ValueError as exc:                     # an unknown `kind` (unbounded str Query)
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/co_binary_track")
def co_binary_track_route(
    m_star: float = Query(..., gt=0.0, description="surviving star's initial mass / M_sun"),
    m_co: float = Query(..., gt=0.0, description="compact object's initial mass / M_sun"),
    p: float = Query(..., gt=0.0, description="initial orbital period / days"),
    feh: float = Query(0.0, description="initial [Fe/H]"),
    kind: str = Query("co-hms-rlo", description="CO grid: co-hms-rlo (H-rich secondary, "
                       "default) | co-hems | co-hems-rlo (He-star double-compact channel)"),
) -> dict:
    """(M_star, M_co_init, P, [Fe/H], kind) -> a POSYDON CO-binary track: a compact object
    (NS/BH/WD, left by an earlier primary's collapse) orbiting a secondary — path (b) Phase 1
    (docs/plans/tempered-lineage-inspiral.md), the stage AFTER `/binary_track`'s two-normal-
    star episode. `kind` selects the grid: "co-hms-rlo" (Chunk 1a, an H-rich secondary — the
    X-ray-binary accretion payoff) or "co-hems"/"co-hems-rlo" (Chunk 2a, a bare-He-star
    secondary — the double-compact-object channel, whose payload also carries a `dco`
    endpoint classification).

    Unlike `/binary_track`, each step carries only ONE real `StellarState` (the surviving
    star — `history2`, the compact-object side, is absent on these grids unconditionally,
    per the schema recon in `posydon_co.py`'s docstring) plus the compact object's own
    mass/type/accretion-rate as routing scalars, and a schematic `accretion_lum_lsun` cue
    (a standard L=eta*Mdot*c^2 formula on the grid's real accretion rate — NOT a measured
    X-ray spectrum, see `posydon_co.py`'s `ACCRETION_EFFICIENCY`).

    Snap-always, same discipline as `/binary_track`: (M_star, M_co, P) snaps to the
    nearest real track in (log M_star, log M_co, log P) space — never interpolated (§6).
    422 is reserved for structurally invalid input (incl. an unknown `kind`); a missing
    baked grid -> 503."""
    try:
        return co_binary_track_payload(m_star, m_co, p, feh, kind)
    except ValueError as exc:                     # an unknown `kind` (unbounded str Query)
        raise HTTPException(status_code=422, detail=str(exc)) from exc
