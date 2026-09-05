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

import contextlib
import os
import threading
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

# --- startup pre-warm ---------------------------------------------------------
# Every grid is lazy (nothing touches disk at import), which is right for tests and
# for a data-free clone — but it means the FIRST request that needs a grid pays the
# whole cold read, and on a cold OS file cache that is the slow part: measured on
# the dev box, the ten MIST `.npz` caches (450 MB) took 155 s on the first /track and
# the 98 MB spectrum cube 11 s on the first /photometry, while the page sat on its
# first-load shimmer. The server, though, is idle for the seconds it takes the user
# to open the browser, so we start the same two loads in a daemon thread the moment
# the app is up. A request that arrives mid-load blocks on the provider's load lock
# and gets the warmed grid; nothing is duplicated. Anything missing (a fresh clone)
# is swallowed — the pre-warm is an optimization, never a gate: the 503 ladder on
# the real request still says what to fetch.
#
# Only a *served* app pre-warms: FastAPI runs the lifespan when uvicorn starts it,
# not when a test builds `TestClient(app)` without a context manager, so the
# data-free CI run and the unit tests never spawn the thread. `STAR_SIM_NO_PREWARM=1`
# opts out explicitly (profiling, or a laptop on battery).
def _prewarm() -> None:
    with contextlib.suppress(Exception):
        PROVIDER.parameter_ranges()          # every MIST grid (the provider's whole load)
    with contextlib.suppress(Exception):
        from ..photometry import photometry_payload
        photometry_payload(5772.0, 4.44, 0.0, 1.0)   # the spectrum cube + the filter curves


@contextlib.asynccontextmanager
async def _lifespan(_app: FastAPI):
    if not os.environ.get("STAR_SIM_NO_PREWARM"):
        threading.Thread(target=_prewarm, name="star-sim-prewarm", daemon=True).start()
    yield


app = FastAPI(title="Star Simulator", version="0.1.0", lifespan=_lifespan)
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
