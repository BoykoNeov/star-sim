"""FastAPI surface over the provider (STAR_SIM_SPEC.md §4).

The HTTP payload is *exactly* the `StellarState` shape — the API adds no fields
of its own. It also serves the static frontend so the whole app is one process
on one origin (no CORS needed in practice; the middleware is kept permissive for
localhost so the frontend can also be served standalone during dev).

Swapping providers happens in exactly one place: `PROVIDER` below. Nothing in
the routers — and nothing in the frontend — knows or cares which provider it is;
they reach it through `_deps.provider()`, which reads this attribute at request
time.

This module is the assembly, not the routes. Each router file is one *reason* a
group of routes exists, which is also the §3 boundary drawn in filenames:

    spine      routes that go THROUGH `PROVIDER` (a StellarState, or the metadata
               needed to ask for one) + the hybrid `/supernova`
    interiors  Lane-Emden + the real MESA radial snapshot
    spectra    the five baked flux cubes
    binaries   stripped stars, the two-star system, the POSYDON grids
    ensembles  populations, isochrones, and the MESA what-if overlays
    observer   Axis A — magnitudes and the observational CMD locus

The 422 / 503 ladder is *not* in the routers: `_errors.install_error_handlers`
maps `ParameterOutOfRange` and the `DataMissing` family app-wide, so a route body
is the sibling call and nothing else.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from ..provider import StellarStateProvider
from ..providers import MISTProvider
from ._errors import install_error_handlers
from . import binaries, ensembles, interiors, observer, spectra, spine

# --- the single provider-swap point ------------------------------------------
# v1 ships MISTProvider (real MIST grids). Construction is lazy, so this never
# touches disk at import time; if the grids aren't fetched yet, requests that
# need data surface an actionable 503 (see api/_errors.py) rather than crashing
# the app. Swap to StubProvider() here for a data-free run.
PROVIDER: StellarStateProvider = MISTProvider()

# frontend/ lives next to backend/ at the repo root:
#   star_sim/api/__init__.py -> parents [0]=api [1]=star_sim [2]=backend [3]=repo root
FRONTEND_DIR = Path(__file__).resolve().parents[3] / "frontend"

app = FastAPI(title="Star Simulator", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # localhost-only app; keep simple
    allow_methods=["GET"],
    allow_headers=["*"],
)
install_error_handlers(app)

for _router in (spine, interiors, spectra, binaries, ensembles, observer):
    app.include_router(_router.router)

# --- static frontend ----------------------------------------------------------
# Mounted last so the API routes above take precedence — keep this below every
# include_router call. html=True serves index.html at "/".
if FRONTEND_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
