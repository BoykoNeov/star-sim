"""The provider boundary (STAR_SIM_SPEC.md §3).

This `Protocol` *is* the "optional path to more science." v1 ships exactly one
implementation, `StubProvider`. Later, `MISTProvider`, `MESAProvider`, and
eventually `LiveSolverProvider` slot in behind this same interface and nothing
downstream changes. Going deeper is a provider swap — if this boundary is
respected from day one. If it is violated, that path quietly dies.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .state import StellarState


class ParameterOutOfRange(ValueError):
    """Raised when (mass, feh, age) falls outside the provider's valid grid.

    Providers must never silently extrapolate (§6). The UI is responsible for
    clamping/disabling out-of-grid values; this exception is the backstop.
    """


@runtime_checkable
class StellarStateProvider(Protocol):
    def parameter_ranges(self) -> dict:
        """Valid mass / [Fe/H] ranges for the UI.

        Shape: {"mass_msun": {"min": .., "max": ..},
                "feh":       {"min": .., "max": ..}}
        """
        ...

    def age_range(self, mass: float, feh: float) -> tuple[float, float]:
        """(min_age_yr, max_age_yr) for the time scrubber at this (mass, feh)."""
        ...

    def state_at(self, mass: float, feh: float, age_yr: float) -> StellarState:
        """The one method that matters: (mass, [Fe/H], age) -> StellarState."""
        ...
