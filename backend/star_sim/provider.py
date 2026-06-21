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


class ProviderDataMissing(RuntimeError):
    """Raised when a provider's backing data (e.g. MIST grids) isn't present.

    Kept on the boundary, not inside any one provider, because "the data layer
    isn't ready" is a provider-agnostic condition the API must translate (to a
    503) without knowing *which* grid is missing. The message should be
    actionable — tell the operator how to fetch the data.
    """


@runtime_checkable
class StellarStateProvider(Protocol):
    def parameter_ranges(self) -> dict:
        """Valid mass / [Fe/H] ranges for the UI.

        Shape: {"mass_msun": {"min": .., "max": ..},
                "feh":       {"min": .., "max": ..}}
        """
        ...

    def mass_range(self, feh: float) -> tuple[float, float]:
        """(min_mass, max_mass) for the mass slider at this [Fe/H].

        The valid mass span can depend on metallicity (a provider's grid may not
        cover every mass at every [Fe/H]). The UI calls this per [Fe/H] so it can
        clamp the mass slider and never request an out-of-grid point — without
        knowing *why* the span tightens (§3: no provider internals leak out).
        """
        ...

    def age_range(self, mass: float, feh: float) -> tuple[float, float]:
        """(min_age_yr, max_age_yr) for the time scrubber at this (mass, feh)."""
        ...

    def state_at(self, mass: float, feh: float, age_yr: float) -> StellarState:
        """The one method that matters: (mass, [Fe/H], age) -> StellarState."""
        ...

    def track(self, mass: float, feh: float) -> list[StellarState]:
        """The full evolutionary track at (mass, [Fe/H]) — a list of StellarStates
        ordered by EEP (ZAMS -> the exposed-window end).

        Age-independent: the HR diagram and composition panel fetch this once per
        (mass, [Fe/H]) and move their own marker as the age scrubs. Each element
        is a `StellarState` exactly as `state_at` would return at that point, so
        consumers never see a provider's track columns (§3 — returning the raw
        interpolation window would leak provider internals).
        """
        ...
