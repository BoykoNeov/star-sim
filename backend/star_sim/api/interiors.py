"""Interiors: the two radial-structure siblings, neither on the spine.

`/polytrope` is the idealized Lane-Emden teaching piece (spec §8) driven by the
index `n` alone; `/structure` is its honest successor — a real MESA radial
snapshot, snapped to the nearest saved profile. Both bypass `PROVIDER`: an
interior is a sibling to the `StellarState` spine, not a `StellarState`.
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from ..lane_emden import polytrope_profile
from ..structure import interior_structure

router = APIRouter()


@router.get("/polytrope")
def polytrope(
    n: float = Query(
        ...,
        ge=0.0,
        le=5.0,
        description="polytropic index n (P = K ρ^(1+1/n)); 0 ≤ n ≤ 5",
    ),
) -> dict:
    """(n) -> a static Lane-Emden polytrope profile (STAR_SIM_SPEC.md §8).

    This is the one endpoint that does **not** go through `PROVIDER`: Lane-Emden is
    a sibling to the StellarState spine, not a `StellarState`. It's a self-contained
    static-structure teaching piece driven by the index `n` alone — independent of
    whichever star the rest of the UI is showing. The valid domain is 0 ≤ n ≤ 5
    (n ≥ 5 has no finite surface; n > 5 is unbound), enforced by the Query bounds.
    """
    return polytrope_profile(n)


@router.get("/structure")
def structure(
    mass: float = Query(..., gt=0.0, description="initial mass / M_sun"),
    feh: float = Query(0.0, description="initial [Fe/H]"),
    age: float = Query(..., gt=0.0, description="stellar age / yr"),
) -> dict:
    """(mass, [Fe/H], age) -> a REAL MESA radial interior-structure snapshot.

    The honest successor to `/polytrope`: where Lane-Emden gives an *idealized* static
    polytrope from an index `n`, this serves a **real** radial structure — ρ(r), T(r),
    P(r), composition(r), and the true convective/radiative boundaries — read from an
    offline MESA `profile.data` snapshot, plus the two canonical polytrope overlays
    (n=1.5, n=3) so the panel can show how good the idealization is.

    Like `/polytrope` and `/spectrum` this does **not** go through `PROVIDER`: interior
    structure is a sibling to the `StellarState` spine, not a `StellarState`. It snaps
    to the nearest saved snapshot in (mass, [Fe/H], age) and reports the *true* snapped
    values — never an interpolation across snapshots (the panel jumps between the
    handful of saved snapshots, labeled honestly). If no profiles have been generated
    yet, return 503 with an actionable hint (analogue of a missing provider grid)."""
    return interior_structure(mass, feh, age)
