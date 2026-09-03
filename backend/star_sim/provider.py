"""The provider boundary (STAR_SIM_SPEC.md §3).

This `Protocol` *is* the "optional path to more science." v1 ships exactly one
implementation, `StubProvider`. Later, `MISTProvider`, `MESAProvider`, and
eventually `LiveSolverProvider` slot in behind this same interface and nothing
downstream changes. Going deeper is a provider swap — if this boundary is
respected from day one. If it is violated, that path quietly dies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from .errors import DataMissing
from .state import StellarState


@dataclass
class EndgameResult:
    """The post-window stellar endgame at one (mass, [Fe/H]) — the §3-clean payload
    of `endgame()` (the WR/WD gateway; see docs/plans/smoldering-cinder-gateway.md).

    `states` is the only thing a *renderer* consumes, and each element is a plain
    `StellarState` exactly as `track()` returns — so the §3 boundary holds: a
    consumer of the endgame never sees a provider's columns. The scalar fields are
    gateway *routing metadata* (which renderer to show, what to label it), not
    observable structure — they say nothing about where the state came from:

      * `type` — "WD" (degenerate cooling track: thermal pulses -> ~100 kK central
        star -> cold cinder), "WR" (Wolf-Rayet wind sub-track), "SN" (the
        intermediate-mass dead end: core collapse, which we do NOT render — `states`
        is empty), or "none" (this provider/star has no exposed endgame).
      * `mass_init_msun` / `feh_init` — the *true* snapped grid values (the endgame
        snaps to the nearest real track, never interpolates — §6; so these can
        differ from the requested mass/[Fe/H]).
      * `final_mass_msun` — the current mass at the last real row (the WD's final
        mass, or the WR's stripped mass); `final_mass < mass_init` for a mass-losing
        endgame. None when there is no endgame track.
      * `wr_threshold_msun` — the lowest grid mass at this [Fe/H] whose track reaches
        the WR phase (derived by scanning the grid, never hardcoded — the onset
        shifts with metallicity and is even slightly non-monotonic at low Z). None
        if no track at this [Fe/H] becomes a WR.

    The last four are the **core-collapse progenitor scalars** — the inputs the
    supernova sibling (`supernova.py` / `/supernova`) consumes to compute the
    ⁵⁶Ni-powered light curve (docs/plans/radioactive-afterglow-requiem.md, Chunk 1).
    They are §3-clean routing metadata exactly like the fields above (snapped
    pre-collapse numbers, nothing about *where* the data came from), and are populated
    **only for the `type="SN"` branch** — `None` for WD/WR/none and for every provider
    that doesn't model the endgame (the stub, MESA), so a consumer reads "no SN
    progenitor here" off the `None`:

      * `pre_sn_radius_rsun` — the robust pre-collapse stellar radius R₀ (the RSG
        envelope's photospheric scale, the Tier-2 plateau input). Taken as the
        maximum radius over the final-phase rows *excluding the terminal EEP row*
        (a low-gravity artifact that can spuriously inflate or shrink R), which
        avoids both that artifact and the compact pre-RSG CHeB rows a median would
        average in. None outside the SN branch.
      * `he_core_msun` / `co_core_msun` — the helium- and CO-core masses at collapse
        (the ejecta/remnant split + the NS/BH cut). `co_core_msun` is MIST's
        `c_core_mass` used as the CO-core proxy (very-massive φ3-enders carry an
        explicit `o_core_mass` of 0 at window end). None outside the SN branch.
      * `h_retained` — whether the surface still holds a hydrogen envelope at collapse
        (the SN spectral-type proxy: True ⇒ Type II, the only kind this branch
        reaches — the stripped Ib/c progenitors classify as WR). None outside the SN
        branch.
    """

    type: str
    mass_init_msun: float
    feh_init: float
    final_mass_msun: float | None = None
    wr_threshold_msun: float | None = None
    states: list[StellarState] = field(default_factory=list)
    # core-collapse progenitor scalars (SN branch only; None otherwise) — see above
    pre_sn_radius_rsun: float | None = None
    he_core_msun: float | None = None
    co_core_msun: float | None = None
    h_retained: bool | None = None


class ParameterOutOfRange(ValueError):
    """Raised when (mass, feh, age) falls outside the provider's valid grid.

    Providers must never silently extrapolate (§6). The UI is responsible for
    clamping/disabling out-of-grid values; this exception is the backstop.
    """


class ProviderDataMissing(DataMissing):
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

    def mass_range(self, feh: float, vvcrit: float = 0.0) -> tuple[float, float]:
        """(min_mass, max_mass) for the mass slider at this [Fe/H].

        The valid mass span can depend on metallicity (a provider's grid may not
        cover every mass at every [Fe/H]). The UI calls this per [Fe/H] so it can
        clamp the mass slider and never request an out-of-grid point — without
        knowing *why* the span tightens (§3: no provider internals leak out).

        `vvcrit` selects a rotation grid (see `track`); providers without a
        rotating grid accept it for parity and ignore it.
        """
        ...

    def age_range(self, mass: float, feh: float, vvcrit: float = 0.0) -> tuple[float, float]:
        """(min_age_yr, max_age_yr) for the time scrubber at this (mass, feh)."""
        ...

    def rotation_status(self, mass: float, feh: float) -> dict:
        """Whether the rotation control is *meaningful* at (mass, [Fe/H]).

        The data-derived honesty gate for the rotation toggle (see `track`'s
        `vvcrit`). Shape:
            {"has_grid": bool,            # a rotating grid covers this [Fe/H]
             "threshold_msun": float|None,# rotation-onset mass (the Kraft break)
             "active": bool}              # has_grid AND mass >= threshold

        `active` is False where toggling rotation would change nothing — below the
        magnetic-braking limit the rotating and non-rotating tracks are identical, so
        the UI shows the toggle as an honest no-op rather than a dead control. A
        provider with no rotating data returns has_grid=False / active=False.
        """
        ...

    def he_ignition_status(self, mass: float, feh: float, vvcrit: float = 0.0) -> dict:
        """Is the served track BLENDED across the helium-ignition transition?

        The second data-derived honesty gate (sibling of `rotation_status`), behind the
        He-ignition-cliff caption — see docs/plans/science-hurdles.md Sec 1.3. Around
        ~2 M_sun helium ignition switches from a degenerate flash to quiet burning and
        the core-He-burning morphology changes so sharply that blending two neighbouring
        tracks across it visibly smooths the loop. Shape:

            {"has_data": bool,             # this provider can answer at all
             "band_lo_msun": float|None,   # the transition band, data-derived
             "band_hi_msun": float|None,
             "in_band": bool,              # the requested mass is inside the band
             "interpolated": bool,         # the window really is a blend (not a grid node)
             "active": bool}               # in_band AND interpolated

        `active` is what a caption may fire on (the consumer adds "and the star is
        currently in core-He burning" from `StellarState.phase` — this method has no
        age). `interpolated` is load-bearing: on an exact grid node the drawn track is
        one real track and nothing is smoothed, so a caption there would be a false
        confession. A provider that does not interpolate across mass, or has no data,
        returns has_data=False and every flag False.
        """
        ...

    def fate_boundary_status(self, mass: float, feh: float, vvcrit: float = 0.0) -> dict:
        """Is this star's white-dwarf-or-supernova verdict inside the UNCERTAIN band?

        The third data-derived honesty gate (sibling of `rotation_status` and
        `he_ignition_status`), behind the uncertain-fate caption — see
        docs/plans/science-hurdles.md Sec 2, "SN/WD boundary". `endgame()` returns one
        fate per star because a grid holds one track per mass, and just above the
        heaviest white-dwarf node that verdict flips to core collapse in a single step.
        Around there the step is an artefact of the grid, not of the physics: a star
        that ends its life with a degenerate oxygen-neon core may leave a white dwarf or
        explode as a faint electron-capture supernova, and which one is genuinely
        unsettled. This is what lets a consumer say so instead of asserting the flip.

        Shape:
            {"has_data": bool,           # this provider can answer at all
             "wd_max_msun": float|None,  # heaviest node that still ends a WD (measured)
             "sn_min_msun": float|None,  # lightest node that core-collapses (measured)
             "band_lo_msun": float|None, # the uncertain band, measured lower edge
             "band_hi_msun": float|None, # its upper edge — a PUBLISHED figure, not
                                         #   measured: no track grid can be asked how
                                         #   wide the real uncertainty is
             "in_band": bool,            # the requested mass lies inside the band
             "active": bool}             # what a caption may fire on

        A consumer that draws the band must keep the two edges' provenance apart (the
        one thing this project guards hardest — never paint a caption the data cannot
        support). A provider with no endgame data, or one whose grid shows no single
        clean WD -> SN flip, returns has_data=False and every flag False.
        """
        ...

    def state_at(self, mass: float, feh: float, age_yr: float, vvcrit: float = 0.0) -> StellarState:
        """The one method that matters: (mass, [Fe/H], age) -> StellarState."""
        ...

    def track(self, mass: float, feh: float, vvcrit: float = 0.0) -> list[StellarState]:
        """The full evolutionary track at (mass, [Fe/H]) — a list of StellarStates
        ordered by EEP (ZAMS -> the exposed-window end).

        Age-independent: the HR diagram and composition panel fetch this once per
        (mass, [Fe/H]) and move their own marker as the age scrubs. Each element
        is a `StellarState` exactly as `state_at` would return at that point, so
        consumers never see a provider's track columns (§3 — returning the raw
        interpolation window would leak provider internals).

        `vvcrit` selects the stellar **rotation rate** (v/vcrit) — a discrete
        grid-selection axis, not a continuous blend. A provider may publish more
        than one rotation grid (e.g. MIST's non-rotating 0.0 and rotating 0.4):
        the request **snaps** to the nearest available rate (rotation reshapes the
        whole track above the magnetic-braking limit, so there is no third grid to
        interpolate toward). Default 0.0 = non-rotating, so existing callers are
        unaffected; a provider with no rotating data ignores it.
        """
        ...

    def endgame(self, mass: float, feh: float, vvcrit: float = 0.0) -> EndgameResult:
        """The stellar endgame past the normal `track()` window — the WR/WD gateway.

        The exposed `track()`/`state_at()` window stops at the end of the early-AGB
        (or core-He burning for massive stars); this exposes what comes *after* for
        the dedicated endgame renderers: a white dwarf's cooling track or a
        Wolf-Rayet's wind sub-track. A provider that has no such data (e.g. the stub,
        or MESA tutorial runs that stop on the MS) returns `EndgameResult(type="none",
        ...)` — the gateway then shows nothing, and the §3 boundary holds (the route
        stays provider-agnostic; it never sniffs which provider it is).

        Unlike the rest of the spine, the endgame **snaps to the nearest real grid
        track** and never interpolates across mass or [Fe/H] (§6): the genuinely
        non-monotonic thermal-pulse rows can't be coherently blended across mass, but
        the real pulses of *one* snapped star scrub fine. The result reports the true
        snapped (mass, [Fe/H]).
        """
        ...
