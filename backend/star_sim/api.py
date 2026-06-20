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

from .provider import ParameterOutOfRange, StellarStateProvider
from .providers import StubProvider

# --- the single provider-swap point ------------------------------------------
PROVIDER: StellarStateProvider = StubProvider()

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


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "provider": getattr(PROVIDER, "name", type(PROVIDER).__name__)}


@app.get("/ranges")
def ranges() -> dict:
    """Valid mass / [Fe/H] ranges so the UI can never request an out-of-grid point."""
    return PROVIDER.parameter_ranges()


@app.get("/age_range")
def age_range(
    mass: float = Query(..., description="initial mass / M_sun"),
    feh: float = Query(..., description="initial [Fe/H]"),
) -> dict:
    try:
        lo, hi = PROVIDER.age_range(mass, feh)
    except ParameterOutOfRange as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
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
    return asdict(st)


# --- static frontend ----------------------------------------------------------
# Mounted last so the API routes above take precedence. html=True serves
# index.html at "/".
if FRONTEND_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
