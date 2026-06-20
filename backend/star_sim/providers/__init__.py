"""Concrete `StellarStateProvider` implementations.

v1 ships exactly one: `StubProvider`. `MISTProvider` is the next one to land
(behind the same interface — see ../provider.py).
"""

from .stub import StubProvider

__all__ = ["StubProvider"]
