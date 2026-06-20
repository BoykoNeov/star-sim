"""Star Simulator backend.

The whole architecture hinges on one rule (STAR_SIM_SPEC.md §3): everything the
user sees is a function of a single `StellarState`, and no consumer is ever
allowed to know where that state came from. State is produced *only* through the
`StellarStateProvider` interface. Swapping the data source (Stub -> MIST -> live
solver) must never require a change downstream.
"""

__version__ = "0.1.0"
