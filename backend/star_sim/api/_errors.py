"""The 422 / 503 ladder, written once instead of ~30 times.

Every route used to repeat the same two-arm `try/except`: `ParameterOutOfRange`
-> 422 ("you asked for a point off the grid") and one of eleven `*DataMissing`
classes -> 503 ("that grid isn't fetched yet; here's how"). Both arms are
*uniform* across the whole surface, so they belong on the app, not in the
handlers — a router now returns the sibling's payload and nothing else.

Two rules that are easy to get wrong later:

* **Only these two families are mapped.** A bare `ValueError` handler is
  tempting (`/co_binary_track` wants one) but wrong app-wide: `ParameterOutOfRange`
  *is* a `ValueError`, so a blanket rule would relabel every genuine bug — a bad
  dict key, a numpy conversion — as a client error across 33 routes instead of a
  visible 500. Routes that really do want `ValueError` -> 422 catch it locally.
* **The body shape is load-bearing.** `{"detail": str(exc)}` is exactly what
  `HTTPException(status_code=…, detail=str(exc))` produced before, and what the
  frontend reads to show the actionable "fetch the grid" hint.

`/health` deliberately does *not* use this: it catches `ProviderDataMissing`
itself and answers 200 with `data_ready: false`, because "is the data ready?" is
the question it exists to answer.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from ..errors import DataMissing
from ..provider import ParameterOutOfRange


def install_error_handlers(app: FastAPI) -> None:
    """Map the two provider-agnostic failure families onto HTTP status codes."""

    @app.exception_handler(ParameterOutOfRange)
    async def _out_of_range(request: Request, exc: Exception) -> JSONResponse:
        """Off-grid input. Providers never silently extrapolate (§6); the UI is
        supposed to clamp, so reaching here is a client error, not a server one."""
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(DataMissing)
    async def _data_missing(request: Request, exc: Exception) -> JSONResponse:
        """A grid / cube / MESA run isn't on disk. The app stays up and only the
        features that need that dataset are unavailable — the message says how to
        fetch it. Covers all eleven sibling exceptions plus `ProviderDataMissing`."""
        return JSONResponse(status_code=503, content={"detail": str(exc)})
