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
from .spectra import SpectraDataMissing, spectrum_data
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
) -> dict:
    """Valid mass span at this [Fe/H] so the UI can clamp the mass slider.

    The (mass, [Fe/H]) domain isn't rectangular — some metallicities lack
    low-mass tracks — so this can be narrower than /ranges' bounding box.
    """
    try:
        lo, hi = PROVIDER.mass_range(feh)
    except ParameterOutOfRange as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ProviderDataMissing as exc:
        raise _provider_unavailable(exc) from exc
    return {"min": lo, "max": hi}


@app.get("/age_range")
def age_range(
    mass: float = Query(..., description="initial mass / M_sun"),
    feh: float = Query(..., description="initial [Fe/H]"),
) -> dict:
    try:
        lo, hi = PROVIDER.age_range(mass, feh)
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
) -> dict:
    """(mass, [Fe/H], age) -> StellarState, serialized exactly as the §3 dataclass."""
    try:
        st = PROVIDER.state_at(mass, feh, age)
    except ParameterOutOfRange as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ProviderDataMissing as exc:
        raise _provider_unavailable(exc) from exc
    return asdict(st)


@app.get("/track")
def track(
    mass: float = Query(..., description="initial mass / M_sun"),
    feh: float = Query(..., description="initial [Fe/H]"),
) -> list[dict]:
    """(mass, [Fe/H]) -> the full evolutionary track: a list of StellarState dicts
    ordered by EEP. Age-independent, so the HR diagram and composition panel fetch
    it once per (mass, [Fe/H]) and move their marker as age scrubs. Same per-element
    shape as /state — the API still adds no fields of its own (§3, §4)."""
    try:
        states = PROVIDER.track(mass, feh)
    except ParameterOutOfRange as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ProviderDataMissing as exc:
        raise _provider_unavailable(exc) from exc
    return [asdict(st) for st in states]


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
    ~80000 K, far above the CAP18 grid's 30000 K ceiling), so dragging the controls
    never trips a 422: `spectrum_data` clamps BOTH ends to the baked grid's real
    coverage (a cool M-dwarf floors to the coolest spectrum, a hot O/B star caps at
    the hottest — symmetric). 422 is reserved for genuinely absurd inputs. If the
    grid hasn't been baked yet, return 503 with an actionable hint (analogue of a
    missing provider grid)."""
    try:
        return spectrum_data(teff, logg, feh)
    except SpectraDataMissing as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


# --- static frontend ----------------------------------------------------------
# Mounted last so the API routes above take precedence. html=True serves
# index.html at "/".
if FRONTEND_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
