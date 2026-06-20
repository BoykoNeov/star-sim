"""Concrete `StellarStateProvider` implementations.

`MISTProvider` is the real v1 provider (reads MIST `.track.eep` grids).
`StubProvider` is kept as a data-free fallback / reference for the §10 anchors —
both satisfy the same §3 interface, so the API swaps between them in one line.
"""

from .mist import MISTProvider
from .stub import StubProvider

__all__ = ["MISTProvider", "StubProvider"]
