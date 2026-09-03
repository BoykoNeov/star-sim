"""How a router reaches the provider without pinning which one it is.

`PROVIDER` is declared in `star_sim/api/__init__.py` — the one swap point (spec
§3, CLAUDE.md). Routers can't `from . import PROVIDER` at module scope: they are
imported *by* that `__init__`, so the name isn't bound yet. They also shouldn't
snapshot it, because a swap (or a test that rebinds `star_sim.api.PROVIDER`)
must be seen by every route.

So the indirection is deliberately late: `provider()` reads the package
attribute at *request* time. One `sys.modules` lookup per call, and the literal
swap point stays where the docs say it is.
"""

from __future__ import annotations

from ..provider import StellarStateProvider


def provider() -> StellarStateProvider:
    """The live provider, resolved now (never captured at import time)."""
    from . import PROVIDER

    return PROVIDER
