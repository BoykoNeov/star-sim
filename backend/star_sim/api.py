"""FastAPI surface over the provider (STAR_SIM_SPEC.md §4).

The HTTP payload is *exactly* the `StellarState` shape — the API adds no fields
of its own. It also serves the static frontend so the whole app is one process
on one origin (no CORS needed in practice; the middleware is kept permissive for
localhost so the frontend can also be served standalone during dev).

Swapping providers happens in exactly one place: `PROVIDER` below. Nothing in
this module — and nothing in the frontend — knows or cares which provider it is.
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .lane_emden import polytrope_profile
from .provider import (
    ParameterOutOfRange,
    ProviderDataMissing,
    StellarStateProvider,
)
from .spectra import (
    SpectraDataMissing,
    alpha_spectrum_data,
    spectrum_data,
    wd_spectrum_data,
    wr_spectrum_data,
)
from .structure import StructureDataMissing, interior_structure
from .supernova import Progenitor, supernova_model
from .providers import MISTProvider

# --- the single provider-swap point ------------------------------------------
# v1 ships MISTProvider (real MIST grids). Construction is lazy, so this never
# touches disk at import time; if the grids aren't fetched yet, requests that
# need data surface an actionable 503 (see _provider_unavailable below) rather
# than crashing the app. Swap to StubProvider() here for a data-free run.
PROVIDER: StellarStateProvider = MISTProvider()

# frontend/ lives next to backend/ at the repo root: star_sim/api.py -> parents
#   [0]=star_sim  [1]=backend  [2]=repo root
FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"

app = FastAPI(title="Star Simulator", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # localhost-only app; keep simple
    allow_methods=["GET"],
    allow_headers=["*"],
)


def _provider_unavailable(exc: ProviderDataMissing) -> HTTPException:
    """Translate 'backing data not fetched yet' into an actionable 503."""
    return HTTPException(status_code=503, detail=str(exc))


@app.get("/health")
def health() -> dict:
    """Liveness + whether the provider's data is actually ready to serve state."""
    info = {"status": "ok", "provider": getattr(PROVIDER, "name", type(PROVIDER).__name__)}
    try:
        info["ranges"] = PROVIDER.parameter_ranges()
        info["data_ready"] = True
    except ProviderDataMissing as exc:
        info["data_ready"] = False
        info["detail"] = str(exc)
    return info


@app.get("/ranges")
def ranges() -> dict:
    """Valid mass / [Fe/H] ranges so the UI can never request an out-of-grid point."""
    try:
        return PROVIDER.parameter_ranges()
    except ProviderDataMissing as exc:
        raise _provider_unavailable(exc) from exc


@app.get("/mass_range")
def mass_range(
    feh: float = Query(..., description="initial [Fe/H]"),
    vvcrit: float = Query(0.0, description="rotation v/vcrit (snaps to a rotation grid)"),
) -> dict:
    """Valid mass span at this [Fe/H] so the UI can clamp the mass slider.

    The (mass, [Fe/H]) domain isn't rectangular — some metallicities lack
    low-mass tracks — so this can be narrower than /ranges' bounding box.
    `vvcrit` snaps to a rotation bucket (default 0.0 = non-rotating).
    """
    try:
        lo, hi = PROVIDER.mass_range(feh, vvcrit)
    except ParameterOutOfRange as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ProviderDataMissing as exc:
        raise _provider_unavailable(exc) from exc
    return {"min": lo, "max": hi}


@app.get("/age_range")
def age_range(
    mass: float = Query(..., description="initial mass / M_sun"),
    feh: float = Query(..., description="initial [Fe/H]"),
    vvcrit: float = Query(0.0, description="rotation v/vcrit (snaps to a rotation grid)"),
) -> dict:
    try:
        lo, hi = PROVIDER.age_range(mass, feh, vvcrit)
    except ParameterOutOfRange as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ProviderDataMissing as exc:
        raise _provider_unavailable(exc) from exc
    return {"min": lo, "max": hi}


@app.get("/state")
def state(
    mass: float = Query(..., description="initial mass / M_sun"),
    feh: float = Query(..., description="initial [Fe/H]"),
    age: float = Query(..., description="current age / yr"),
    vvcrit: float = Query(0.0, description="rotation v/vcrit (snaps to a rotation grid)"),
) -> dict:
    """(mass, [Fe/H], age) -> StellarState, serialized exactly as the §3 dataclass."""
    try:
        st = PROVIDER.state_at(mass, feh, age, vvcrit)
    except ParameterOutOfRange as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ProviderDataMissing as exc:
        raise _provider_unavailable(exc) from exc
    return asdict(st)


@app.get("/track")
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
    try:
        states = PROVIDER.track(mass, feh, vvcrit)
    except ParameterOutOfRange as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ProviderDataMissing as exc:
        raise _provider_unavailable(exc) from exc
    return [asdict(st) for st in states]


@app.get("/endgame")
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
    try:
        result = PROVIDER.endgame(mass, feh, vvcrit)
    except ParameterOutOfRange as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ProviderDataMissing as exc:
        raise _provider_unavailable(exc) from exc
    d = asdict(result)
    if meta:
        d["has_states"] = bool(d["states"])
        d["states"] = []
    return d


@app.get("/rotation_status")
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
    try:
        return PROVIDER.rotation_status(mass, feh)
    except ProviderDataMissing as exc:
        raise _provider_unavailable(exc) from exc


@app.get("/supernova")
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
    try:
        eg = PROVIDER.endgame(mass, feh, vvcrit)
    except ParameterOutOfRange as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ProviderDataMissing as exc:
        raise _provider_unavailable(exc) from exc

    # Only the SN branch has a supernova to compute. WD / WR / none -> an honest empty
    # payload echoing the real fate (the §3 boundary: a non-SN progenitor, or a provider
    # with no endgame data, simply has no light curve here).
    if eg.type != "SN" or eg.co_core_msun is None:
        return {
            "type": eg.type,
            "is_supernova": False,
            "mass_init_msun": eg.mass_init_msun,
            "feh_init": eg.feh_init,
            "light_curve": None,
            "states": [],
            "reason": f"{eg.type} progenitor — no core-collapse supernova at this (mass, [Fe/H]).",
        }

    prog = Progenitor(
        mass_init_msun=eg.mass_init_msun,
        final_mass_msun=eg.final_mass_msun,
        he_core_msun=eg.he_core_msun,
        co_core_msun=eg.co_core_msun,
        pre_sn_radius_rsun=eg.pre_sn_radius_rsun,
        h_retained=eg.h_retained,
        feh_init=eg.feh_init,
    )
    model = supernova_model(prog, m_ni=m_ni, e_kin=e_kin)
    d = asdict(model)            # recurses `states` into the §3 StellarState shape
    d["is_supernova"] = True
    return d


@app.get("/polytrope")
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


@app.get("/structure")
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
    try:
        return interior_structure(mass, feh, age)
    except StructureDataMissing as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/spectrum")
def spectrum(
    teff: float = Query(..., ge=1000.0, le=200000.0, description="effective temperature / K"),
    logg: float = Query(..., ge=-2.0, le=7.0, description="surface gravity, cgs dex"),
    feh: float = Query(0.0, ge=-5.0, le=2.0, description="initial [Fe/H]"),
) -> dict:
    """(Teff, log g, [Fe/H]) -> a synthetic spectrum (λ vs flux, with absorption
    lines), STAR_SIM_SPEC §5.

    Like `/polytrope`, this does **not** go through `PROVIDER`: a spectrum is a
    sibling to the StellarState spine, a derived view of the state's
    (Teff, log g, [Fe/H]) — the same numbers `color.js` turns into the star's
    colour. The `Query` bounds are deliberately *wider than any real star* the grid
    can produce (the hottest draggable star — a massive metal-poor O star — reaches
    ~80000 K, above the baked grid's 55000 K ceiling), so dragging the controls
    never trips a 422: `spectrum_data` clamps BOTH ends to the baked grid's real
    coverage (a star below the floor floors to the coolest spectrum, a hot O/B star
    caps at the hottest — symmetric). 422 is reserved for genuinely absurd inputs.
    The response also reports `teff_requested` + the grid's `teff_min`/`teff_max`, so
    the panel can tell a real interpolated spectrum from a clamped-ceiling one: past
    the HOT end (no model atmosphere exists) it shows a "no spectral model for this
    range" notice instead of the misleading boundary spectrum, keyed off the grid's
    real ceiling. The cool end is covered down to 2300 K (the Göttingen/PHOENIX cool
    splice), below every reachable star (~2800 K), so in practice the cool floor never
    clamps a real star — and a cool clamp would be an honest small extrapolation
    anyway (cool models exist), not a model gap, so there is no cool-end notice. If
    the grid hasn't been baked yet, return 503 with an actionable hint (analogue of a
    missing provider grid)."""
    try:
        return spectrum_data(teff, logg, feh)
    except SpectraDataMissing as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/alpha_spectrum")
def alpha_spectrum(
    teff: float = Query(..., ge=1000.0, le=200000.0, description="effective temperature / K"),
    logg: float = Query(..., ge=-2.0, le=7.0, description="surface gravity, cgs dex"),
    feh: float = Query(0.0, ge=-5.0, le=2.0, description="initial [Fe/H]"),
    afe: float = Query(0.0, ge=0.0, le=0.4, description="[alpha/Fe] (0.0 solar-scaled or 0.4 alpha-rich)"),
) -> dict:
    """(Teff, log g, [Fe/H], [alpha/Fe]) -> a Coelho-2014 synthetic spectrum — a
    FOURTH spectrum sibling beside `/spectrum`, `/wd_spectrum`, `/wr_spectrum` (atlas
    Tier B, the thick-disk/halo [alpha/Fe] axis).

    Reads the separate 4-axis Coelho cube (the COOL subset, Teff <= ~10000 K — Gate 1
    measured [alpha/Fe] dead hotter). [alpha/Fe] is a **spectrum-only** axis: at fixed
    [Fe/H] it deepens the O/Mg/Si/Ca/Ti (+ TiO) lines, but MIST evolution is
    solar-scaled so the star's track/composition do NOT follow it — the panel labels it
    a "what-if". Both baselines (afe 0.0 and 0.4) come from THIS cube, so a toggle flips
    two Coelho spectra (never Coelho-alpha vs a CAP18-solar one). The panel decides when
    to call this vs `/spectrum` (cool routes here; the main cube serves hotter stars,
    where alpha is dead). Wide `Query` bounds match `/spectrum` so dragging never trips a
    422 (the cube clamps). 503 if not yet baked."""
    try:
        return alpha_spectrum_data(teff, logg, feh, afe)
    except SpectraDataMissing as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/wd_spectrum")
def wd_spectrum(
    teff: float = Query(..., ge=1000.0, le=500000.0, description="effective temperature / K"),
    logg: float = Query(..., ge=3.0, le=10.0, description="surface gravity, cgs dex"),
) -> dict:
    """(Teff, log g) -> a white-dwarf / central-star synthetic spectrum (endgame Chunk 6).

    A SECOND spectrum sibling, like `/spectrum`: it reads the separate WD cube
    (log g 6.5–9.5, pure hydrogen — no `[Fe/H]` axis), because a white dwarf's
    gravity is disjoint from the main-sequence atmosphere grid (0–5) and can't share
    its cube. Two spliced sources cover the cooling sequence: **Koester DA** (LTE,
    5000–80000 K) for the cooling white dwarf, and **TMAP** (NLTE, 80000–190000 K,
    Chunk 6b) for the hot post-AGB central star (CSPN). The WD endgame's *consumer*
    (the spectrum panel) decides when to call this vs `/spectrum`, by surface gravity
    / temperature: a TPAGB giant still has a real main-cube spectrum; the degenerate
    remnant and the hot central star route here.

    The `Query` bounds are wide (Teff up to 500000 — the most massive progenitors'
    central stars peak ~400 kK) so a re-snapped remnant never trips a 422;
    `wd_spectrum_data` clamps to the cube and handles the honest edges itself — a DC
    blackbody continuum below the ~5000 K Koester floor (the cold cinder has lost its
    Balmer lines), and the `teff_max` no-model path above TMAP's 190000 K ceiling (the
    narrow residual gap for the very hottest central stars). 503 if not yet baked."""
    try:
        return wd_spectrum_data(teff, logg)
    except SpectraDataMissing as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/wr_spectrum")
def wr_spectrum(
    teff: float = Query(..., ge=1000.0, le=500000.0, description="effective temperature / K"),
    lum: float = Query(..., gt=0.0, description="luminosity / L_sun"),
    xsurf: float = Query(..., ge=0.0, le=1.0, description="surface hydrogen mass fraction"),
    ysurf: float = Query(..., ge=0.0, le=1.0, description="surface helium mass fraction"),
    zsurf: float = Query(..., ge=0.0, le=1.0, description="surface metal mass fraction"),
    feh: float = Query(0.0, ge=-4.0, le=1.0, description="initial [Fe/H]"),
) -> dict:
    """Wolf-Rayet wind-emission spectrum (endgame Chunk 7) — a THIRD spectrum sibling.

    Reads the PoWR cube, whose axis is the WR spectroscopic pair (T*, transformed
    radius Rt), NOT (Teff, log g) — so the route takes the star's `(Teff, L, surface
    composition, [Fe/H])` and `wr_spectrum_data` does the placement: subtype (WNE/WNL/
    WC) from the composition, metallicity grid from [Fe/H], T* ≈ Teff, and Rt from L +
    a Nugis-Lamers Ṁ. It then snaps to the nearest real grid node, OR reports
    `regime="none"` when the star is hotter / denser-wind than any PoWR model — the
    stripped-core bulk the Chunk-7a gate measured off-grid, where the panel shows an
    honest 'no model' frame (recipe §7a). The wide Teff `Query` bound (up to 500000)
    keeps a 250+ kK stripped core from tripping a 422; the off-grid path handles it.
    503 if the WR cube isn't baked."""
    try:
        return wr_spectrum_data(teff, lum, xsurf, ysurf, zsurf, feh)
    except SpectraDataMissing as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


# --- static frontend ----------------------------------------------------------
# Mounted last so the API routes above take precedence. html=True serves
# index.html at "/".
if FRONTEND_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
