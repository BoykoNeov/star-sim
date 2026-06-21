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

from .provider import (
    ParameterOutOfRange,
    ProviderDataMissing,
    StellarStateProvider,
)
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


# --- static frontend ----------------------------------------------------------
# Mounted last so the API routes above take precedence. html=True serves
# index.html at "/".
if FRONTEND_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
