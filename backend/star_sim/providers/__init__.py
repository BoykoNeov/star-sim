"""Concrete `StellarStateProvider` implementations.

`MISTProvider` is the real v1 provider (reads MIST `.track.eep` grids).
`MESAProvider` is the second real provider (reads offline MESA `history.data`
runs — a different on-disk format behind the same boundary; used to validate MIST,
see tests/test_mesa_vs_mist.py). `StubProvider` is kept as a data-free fallback /
reference for the §10 anchors. All satisfy the same §3 interface, so the API
swaps between them in one line.
"""

from .mesa import MESAProvider
from .mist import MISTProvider
from .stub import StubProvider

__all__ = ["MESAProvider", "MISTProvider", "StubProvider"]
