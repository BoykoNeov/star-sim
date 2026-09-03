"""Ensembles and what-if overlays: many stars, or the same star under changed physics.

None of these is one state of one star, so none goes through `PROVIDER`. The coeval
population (`bpass.py`) and the cluster isochrone (`isochrone.py`) are *loci* over many
masses; the initial-helium and α-enhanced overlays (`helium.py`, `alpha.py`) are self-run
MESA pairs, always drawn MESA-vs-MESA so the effect is never conflated with the known
MESA-vs-MIST systematic.

Each also carries a `*_status` route: the grids here are host-baked or self-run and
absent on a fresh clone, so the frontend hides the toggle rather than offering one that
can only 503 (the honesty gate).
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from ..alpha import alpha_available, alpha_overlay
from ..bpass import bpass_available, hrd_available, population_hrd, population_sed
from ..helium import helium_available, helium_overlay
from ..isochrone import isochrone, isochrone_available

router = APIRouter()


@router.get("/population")
def population(
    feh: float = Query(..., ge=-5.0, le=2.0, description="initial [Fe/H]"),
    age_gyr: float = Query(..., gt=0.0, description="population age / Gyr"),
    population: str = Query("both", pattern="^(both|sin|bin)$",
                            description="which curves: both (default), sin, or bin"),
) -> dict:
    """(feh, age_gyr) -> the integrated single & binary COEVAL-POPULATION spectra at the
    nearest ([Fe/H], age) BPASS node — the first ENSEMBLE overlay
    (docs/plans/coeval-ensemble-overlay.md, Chunk 1).

    Like `/spectrum`, `/structure` and `/helium`, this does **not** go through `PROVIDER`:
    a coeval stellar population (a million stars born together, seen at the marker's age)
    is not a single star — it is a sibling, `bpass.py`, over a build-time BPASS SSP-spectrum
    bake. The headline (Gate 0, measured): binaries keep the population UV/ionizing-bright
    far longer than single-star evolution can. Both curves are served by default (draw-both,
    so a frontend single↔binary comparison needs no refetch).

    Snap-always (like `/structure`): ([Fe/H], age) snap to the nearest grid node (nearest
    [Fe/H] linearly, nearest age in log10) and are flagged in-band (`*_snapped_far`), never
    422'd. 422 is reserved for structurally invalid input (age <= 0, absurd [Fe/H]); a
    missing/unbaked cube -> 503."""
    return population_sed(feh, age_gyr, population)


@router.get("/population_hrd")
def population_hrd_route(
    feh: float = Query(..., ge=-5.0, le=2.0, description="initial [Fe/H]"),
    age_gyr: float = Query(..., gt=0.0, description="population age / Gyr"),
    population: str = Query("both", pattern="^(both|sin|bin)$",
                            description="which grids: both (default), sin, or bin"),
) -> dict:
    """Chunk 2 — the coeval population's number density over the HR diagram (star count per
    (logTeff, logL) cell) at the marker's ([Fe/H], age), single-star vs. +binaries. Like
    `/population` this bypasses `PROVIDER` (a population is a sibling, `bpass.py`). The
    HR-panel analogue of `/population`'s SED wedge: the binary grid lights up hot / stripped
    cells the single grid leaves empty (Gate 0, measured). Snap-always; 503 if unbaked."""
    return population_hrd(feh, age_gyr, population)


@router.get("/population_status")
def population_status() -> dict:
    """Whether the coeval-population overlays have data — the honesty gate the frontend reads
    to decide if the toggle appears (mirrors `/helium_status`). The BPASS cubes are
    gitignored/host-baked (like the MESA runs), so a fresh clone has none; hiding the toggle
    then beats showing one that can only 503. `has_grid` is the SED-spectrum cube (Chunk 1);
    `has_hrd` the HR-diagram number-density cube (Chunk 2). Cheap (stats), always 200."""
    return {"has_grid": bpass_available(), "has_hrd": hrd_available()}


@router.get("/isochrone")
def isochrone_route(
    age_yr: float = Query(..., gt=0.0, description="cluster age / yr"),
    feh: float = Query(..., ge=-5.0, le=2.0, description="initial [Fe/H]"),
    vvcrit: float = Query(0.0, ge=0.0, le=1.0, description="rotation v/v_crit"),
) -> dict:
    """(age, [Fe/H], vvcrit) -> the coeval-cluster locus at the nearest published MIST
    isochrone node (docs/plans/outward-quartet-atlas.md, Axis B).

    Like `/structure`, `/spectrum` and `/population`, this does **not** go through
    `PROVIDER`. An isochrone is all masses at one age — a population locus, not a single
    star — so it is a sibling, `isochrone.py`, reading the *published* MIST `.iso` grid
    with its own parser (Tier-1: no interpolation-of-interpolation). The payoff is the
    **main-sequence turnoff**: the bluest MS point, whose luminosity IS the cluster's age.

    Snap-always (like `/structure`): [Fe/H] snaps to the nearest grid file, age to the
    nearest tabulated isochrone in log10, vvcrit to the nearest rotation grid; all snaps
    are flagged in-band (`*_snapped_far`), never 422'd. 422 is reserved for structurally
    invalid input (age <= 0); a missing/unfetched `.iso` grid -> 503."""
    return isochrone(age_yr, feh, vvcrit)


@router.get("/isochrone_status")
def isochrone_status() -> dict:
    """Whether the isochrone grid is present — the honesty gate the frontend reads to
    decide if the cluster-overlay toggle appears (mirrors `/population_status`). The
    `.iso` files are gitignored/fetched-on-demand, so a fresh clone has none; hiding the
    toggle beats showing one that can only 503. Cheap, always 200."""
    return {"has_grid": isochrone_available()}


@router.get("/helium")
def helium(
    mass: float = Query(..., gt=0.0, description="initial mass / M_sun"),
) -> dict:
    """(mass) -> the initial-helium (Y) what-if: a baseline vs. He-enhanced MESA track
    pair at matched mass/[Fe/H] (docs/plans/tempered-lineage-inspiral.md, Phase 2).

    Like `/structure`, `/binary` and `/supernova`, this does **not** go through
    `PROVIDER`. The globular-cluster second-generation what-if (omega Cen / NGC 2808:
    Y ~ 0.40 vs primordial ~0.27 at the *same* [Fe/H]) cannot be an axis on the single-
    star spine — it is a sibling, `helium.py`, that reads two self-run MESA `history.data`
    runs (identical inlist, Y the sole difference) and returns both as §3 `StellarState`
    tracks. The overlay is drawn ONLY against its own MESA baseline, never the live MIST
    spine — comparing self-run MESA to MIST would conflate the He effect with the
    documented MESA-vs-MIST systematic.

    Snap-always (like `/structure`): `mass` snaps to the nearest grid mass (1/2/6 M_sun,
    solar Z) and is flagged in-band (`mass_snapped_far`), never 422'd. 422 is reserved
    for structurally invalid mass <= 0 (the Query bound); a missing MESA run set -> 503."""
    return helium_overlay(mass)


@router.get("/helium_status")
def helium_status() -> dict:
    """Whether the initial-helium overlay has data — the honesty gate the frontend reads
    to decide if the toggle appears at all (mirrors `/rotation_status`). MESA runs are never
    committed/hosted, so a fresh clone has none; hiding the toggle then beats showing one that
    can only 503. Cheap (a glob), always 200."""
    return {"has_grid": helium_available()}


@router.get("/alpha")
def alpha(
    mass: float = Query(..., gt=0.0, description="initial mass / M_sun"),
) -> dict:
    """(mass) -> the α-enhanced what-if: a baseline vs. α-enhanced (equivalent-Z) MESA
    track pair at matched mass/[Fe/H] (docs/plans/tempered-lineage-inspiral.md, Phase 3).

    Like `/helium`, this does **not** go through `PROVIDER`. [α/Fe] raises the true total
    metallicity Z at fixed [Fe/H] (Salaris 1993 equivalent-Z), pushing the track cooler,
    fainter, and longer-lived — the opposite sign from the He effect. The "enhanced" member
    is a scaled-solar MESA run at the equivalent Z (MESA ships no α-enhanced opacity tables;
    the Salaris residual is below what this sim resolves), so the track responds to α only
    through total Z — α's distinctive signature is spectroscopic (the Coelho α-toggle), which
    the frontend caption pairs this with. The overlay is drawn ONLY against its own MESA
    baseline, never the live MIST spine (that would conflate the effect with the MESA-vs-MIST
    systematic).

    Snap-always: an out-of-grid mass snaps to the nearest node (1/2/6 M_sun, solar [Fe/H]) and
    is flagged in-band (`mass_snapped_far`), never 422'd. 422 is reserved for structurally
    invalid mass <= 0 (the Query bound); a missing MESA run set -> 503."""
    return alpha_overlay(mass)


@router.get("/alpha_status")
def alpha_status() -> dict:
    """Whether the α-enhanced overlay has data — the frontend toggle-visibility gate
    (mirrors `/helium_status`). Self-run MESA runs are never committed/hosted; hiding the
    toggle on a fresh clone beats showing one that can only 503. Cheap (a glob), always 200."""
    return {"has_grid": alpha_available()}
