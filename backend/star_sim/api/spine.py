"""The spine (spec §3): every route that goes **through** `PROVIDER`.

These are the endpoints whose answer *is* a `StellarState` (or the metadata the UI
needs to ask for one): the ranges that clamp the sliders, the state at an age, the
whole track, the endgame, the three data-derived honesty gates — and `/supernova`,
which is a hybrid (it classifies on the spine, then computes in the `supernova.py`
sibling). Nothing here knows which provider it is; `provider()` resolves the one
swap point at request time.
"""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Query

from ..provider import ProviderDataMissing
from ..supernova import supernova_payload
from ._deps import provider

router = APIRouter()


@router.get("/health")
def health() -> dict:
    """Liveness + whether the provider's data is actually ready to serve state."""
    prov = provider()
    info = {"status": "ok", "provider": getattr(prov, "name", type(prov).__name__)}
    try:
        info["ranges"] = prov.parameter_ranges()
        info["data_ready"] = True
    except ProviderDataMissing as exc:
        info["data_ready"] = False
        info["detail"] = str(exc)
    return info


@router.get("/ranges")
def ranges() -> dict:
    """Valid mass / [Fe/H] ranges so the UI can never request an out-of-grid point."""
    return provider().parameter_ranges()


@router.get("/mass_range")
def mass_range(
    feh: float = Query(..., description="initial [Fe/H]"),
    vvcrit: float = Query(0.0, description="rotation v/vcrit (snaps to a rotation grid)"),
) -> dict:
    """Valid mass span at this [Fe/H] so the UI can clamp the mass slider.

    The (mass, [Fe/H]) domain isn't rectangular — some metallicities lack
    low-mass tracks — so this can be narrower than /ranges' bounding box.
    `vvcrit` snaps to a rotation bucket (default 0.0 = non-rotating).
    """
    lo, hi = provider().mass_range(feh, vvcrit)
    return {"min": lo, "max": hi}


@router.get("/age_range")
def age_range(
    mass: float = Query(..., description="initial mass / M_sun"),
    feh: float = Query(..., description="initial [Fe/H]"),
    vvcrit: float = Query(0.0, description="rotation v/vcrit (snaps to a rotation grid)"),
) -> dict:
    lo, hi = provider().age_range(mass, feh, vvcrit)
    return {"min": lo, "max": hi}


@router.get("/state")
def state(
    mass: float = Query(..., description="initial mass / M_sun"),
    feh: float = Query(..., description="initial [Fe/H]"),
    age: float = Query(..., description="current age / yr"),
    vvcrit: float = Query(0.0, description="rotation v/vcrit (snaps to a rotation grid)"),
) -> dict:
    """(mass, [Fe/H], age) -> StellarState, serialized exactly as the §3 dataclass."""
    st = provider().state_at(mass, feh, age, vvcrit)
    return asdict(st)


@router.get("/track")
def track(
    mass: float = Query(..., description="initial mass / M_sun"),
    feh: float = Query(..., description="initial [Fe/H]"),
    vvcrit: float = Query(0.0, description="rotation v/vcrit (snaps to a rotation grid)"),
) -> list[dict]:
    """(mass, [Fe/H]) -> the full evolutionary track: a list of StellarState dicts
    ordered by EEP. Age-independent, so the HR diagram and composition panel fetch
    it once per (mass, [Fe/H]) and move their marker as age scrubs. Same per-element
    shape as /state — the API still adds no fields of its own (§3, §4). `vvcrit`
    snaps to a rotation bucket (default 0.0 = non-rotating); the rotating track
    carries the same shape with the surface enrichment / HR shift baked in."""
    states = provider().track(mass, feh, vvcrit)
    return [asdict(st) for st in states]


@router.get("/endgame")
def endgame(
    mass: float = Query(..., description="initial mass / M_sun"),
    feh: float = Query(..., description="initial [Fe/H]"),
    vvcrit: float = Query(0.0, description="rotation v/vcrit (snaps to a rotation grid)"),
    meta: bool = Query(
        False,
        description="type-only fast path: drop the heavy `states` list and return just "
        "the routing metadata (fate type + snapped mass + a `has_states` flag). The "
        "gateway BUTTON needs only these — ~120 B vs the full ~1 MB cooling/wind track.",
    ),
) -> dict:
    """(mass, [Fe/H]) -> the stellar endgame past the normal track window: the WR/WD
    gateway (STAR_SIM_SPEC §6+; docs/plans/smoldering-cinder-gateway.md).

    This DOES go through `PROVIDER` — unlike `/polytrope` and `/spectrum`, an endgame
    state *is* a `StellarState` (a white dwarf / Wolf-Rayet has a defined Teff, L, R,
    log g, composition). The route stays provider-agnostic: a provider with no endgame
    data answers `type="none"` (the §3 boundary holds — the route never asks which
    provider it is). The response is the `EndgameResult` dataclass with its `states`
    serialized exactly as the §3 `StellarState` shape (the API adds no fields). The
    gateway reads `type` (WD / WR / SN / none) to pick the renderer; `states` is the
    scrubbable endgame sequence (empty for SN / none).

    `meta=1` serves the *same* `EndgameResult`, minus its bulk: the gateway button only
    needs the fate type, the snapped `mass_init_msun` (for the SN note), and whether a
    renderable sequence exists. So we drop `states` and add an explicit `has_states`
    boolean (mirrors the frontend's `states.length` guard without assuming "type implies
    states"). Still §3-clean — every field is the same routing metadata the dataclass
    already exposes, no provider internals leak; the classifier still builds the full
    track (so cold latency is unchanged), we just don't serialize/ship the 1 MB. The
    full fetch (no `meta=`) still backs the HR preview + the warm gateway-enter cache."""
    result = provider().endgame(mass, feh, vvcrit)
    d = asdict(result)
    if meta:
        d["has_states"] = bool(d["states"])
        d["states"] = []
    return d


@router.get("/rotation_status")
def rotation_status(
    mass: float = Query(..., description="initial mass / M_sun"),
    feh: float = Query(..., description="initial [Fe/H]"),
) -> dict:
    """Whether the rotation control is *meaningful* at (mass, [Fe/H]) — the
    data-derived honesty gate the frontend reads to render the rotation toggle
    (docs/plans/whirling-cohort-atlas.md, Chunk 3).

    Goes through `PROVIDER` (a provider with no rotating grid answers has_grid=False,
    so the route stays §3-clean). Shape:
        {"has_grid": bool,             # a rotating grid covers this [Fe/H]
         "threshold_msun": float|None, # rotation-onset (Kraft-break) mass, data-derived
         "active": bool}               # has_grid AND mass >= threshold

    `active` is False where toggling rotation would change nothing (below the
    magnetic-braking limit the rotating and non-rotating tracks are bit-identical),
    so the UI greys the toggle as an honest no-op there; `has_grid` False hides it
    entirely (no rotating grid fetched at this metallicity)."""
    return provider().rotation_status(mass, feh)


@router.get("/he_ignition_status")
def he_ignition_status(
    mass: float = Query(..., description="initial mass / M_sun"),
    feh: float = Query(..., description="initial [Fe/H]"),
    vvcrit: float = Query(0.0, description="rotation v/vcrit (snaps to a rotation grid)"),
) -> dict:
    """Is the served track blended across the helium-ignition transition? — the
    data-derived honesty gate behind the He-ignition-cliff caption
    (docs/plans/science-hurdles.md §1.3).

    Goes through `PROVIDER` (a provider that doesn't interpolate across mass answers
    has_data=False, so the route stays §3-clean and the caption simply never appears).
    Shape:
        {"has_data": bool,             # this provider can answer at all
         "band_lo_msun": float|None,   # the He-ignition transition band, data-derived
         "band_hi_msun": float|None,
         "in_band": bool,              # the requested mass is inside the band
         "interpolated": bool,         # the window really is a blend, not one real track
         "active": bool}               # in_band AND interpolated

    The frontend fires the caption on `active` AND the marker being in core-He burning
    (the phase check is the consumer's — this route has no age). `interpolated` is the
    load-bearing half: on an exact grid node nothing is smoothed and the confession
    would be false."""
    return provider().he_ignition_status(mass, feh, vvcrit)


@router.get("/fate_boundary_status")
def fate_boundary_status(
    mass: float = Query(..., description="initial mass / M_sun"),
    feh: float = Query(..., description="initial [Fe/H]"),
    vvcrit: float = Query(0.0, description="rotation v/vcrit (snaps to a rotation grid)"),
) -> dict:
    """Is the gateway's white-dwarf-or-supernova verdict inside the genuinely uncertain
    band? — the data-derived honesty gate behind the uncertain-fate caption
    (docs/plans/science-hurdles.md §2, "SN/WD boundary").

    Goes through `PROVIDER` (a provider with no endgame answers has_data=False, so the
    route stays §3-clean and the caption simply never appears). Shape:
        {"has_data": bool,
         "wd_max_msun": float|None,   # heaviest node that still ends a WD (measured)
         "sn_min_msun": float|None,   # lightest node that core-collapses (measured)
         "band_lo_msun": float|None,  # the uncertain band's MEASURED lower edge
         "band_hi_msun": float|None,  # its CITED upper edge (published, not measured)
         "in_band": bool,
         "active": bool}

    The frontend fires the caption on `active` and hedges BOTH sides of the flip there —
    the "Continue: White Dwarf" button and the core-collapse note — because in this band
    the grid's single answer is crisper than the physics. The two edges have different
    provenance and the caption must say so.
    """
    return provider().fate_boundary_status(mass, feh, vvcrit)


@router.get("/supernova")
def supernova(
    mass: float = Query(..., description="initial mass / M_sun"),
    feh: float = Query(..., description="initial [Fe/H]"),
    vvcrit: float = Query(0.0, description="rotation v/vcrit (snaps to a rotation grid)"),
    m_ni: float | None = Query(
        None,
        ge=0.0,
        le=1.0,
        description="⁵⁶Ni mass / M_sun — the Tier-3 free knob (default 0.06; clamped to "
        "the observed 0.001–0.3 range). Drives the radioactive tail/peak height.",
    ),
    e_kin: float = Query(
        1.0e51, gt=0.0, description="explosion kinetic energy / erg (canonical 1e51)"
    ),
) -> dict:
    """(mass, [Fe/H]) -> the computed core-collapse supernova: a ⁵⁶Ni-powered light curve
    + homologous-expansion photosphere states (docs/plans/radioactive-afterglow-requiem.md).

    Like `/polytrope` and `/spectrum`, the *computation* does **not** go through `PROVIDER`
    — a supernova is a semi-analytic model, not a `StellarState` snapped to a track (the
    MIST tracks end at collapse and carry no explosion data). But it is a **hybrid**: the
    route first calls `PROVIDER.endgame()` to *classify* the star and read its progenitor
    scalars (he/CO cores, pre-collapse R₀, surface-H), then hands those to the
    `supernova.py` sibling. The §3 boundary holds: a non-SN progenitor (WD/WR/none, or any
    provider that doesn't model the endgame) comes back `is_supernova=false` with the real
    fate echoed and no curve — the gateway then shows the matching renderer instead.

    The SN payload is the `SupernovaModel` serialized verbatim: the three-tier light curve
    (`light_curve.L_total/L_radio/L_plateau` in erg/s vs `time_days`), the photosphere
    `states` (exactly the §3 StellarState shape, for the 3D/SED/scale consumers), the
    explosion scalars (M_ej, M_Ni default+range, E_K, v_phot, remnant), and the honesty
    `tiers`. `m_ni` is the only free input (Tier-3); the plateau peak carries no M_Ni term."""
    eg = provider().endgame(mass, feh, vvcrit)
    return supernova_payload(          # the shape (incl. the honest non-SN one) is the sibling's
        fate=eg.type,
        mass_init_msun=eg.mass_init_msun,
        feh_init=eg.feh_init,
        final_mass_msun=eg.final_mass_msun,
        he_core_msun=eg.he_core_msun,
        co_core_msun=eg.co_core_msun,
        pre_sn_radius_rsun=eg.pre_sn_radius_rsun,
        h_retained=eg.h_retained,
        m_ni=m_ni,
        e_kin=e_kin,
    )
