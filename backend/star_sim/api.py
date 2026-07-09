"""FastAPI surface over the provider (STAR_SIM_SPEC.md §4).

The HTTP payload is *exactly* the `StellarState` shape — the API adds no fields
of its own. It also serves the static frontend so the whole app is one process
on one origin (no CORS needed in practice; the middleware is kept permissive for
localhost so the frontend can also be served standalone during dev).

Swapping providers happens in exactly one place: `PROVIDER` below. Nothing in
this module — and nothing in the frontend — knows or cares which provider it is.
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .lane_emden import polytrope_profile
from .provider import (
    ParameterOutOfRange,
    ProviderDataMissing,
    StellarStateProvider,
)
from .spectra import (
    SpectraDataMissing,
    alpha_spectrum_data,
    spectrum_data,
    stripped_spectrum_data,
    wd_spectrum_data,
    wr_spectrum_data,
)
from .binary import (
    BinaryDataMissing,
    binary_pair_payload,
    companion_init_mass,
    stripped_star,
    stripped_star_payload,
)
from .structure import StructureDataMissing, interior_structure
from .bpass import BpassDataMissing, bpass_available, population_sed
from .helium import HeliumDataMissing, helium_available, helium_overlay
from .alpha import AlphaDataMissing, alpha_available, alpha_overlay
from .supernova import Progenitor, supernova_model
from .posydon import PosydonDataMissing, binary_track_meta, binary_track_payload
from .posydon_co import (
    PosydonCoDataMissing,
    co_binary_track_meta,
    co_binary_track_payload,
)
from .providers import MISTProvider

# --- the single provider-swap point ------------------------------------------
# v1 ships MISTProvider (real MIST grids). Construction is lazy, so this never
# touches disk at import time; if the grids aren't fetched yet, requests that
# need data surface an actionable 503 (see _provider_unavailable below) rather
# than crashing the app. Swap to StubProvider() here for a data-free run.
PROVIDER: StellarStateProvider = MISTProvider()

# frontend/ lives next to backend/ at the repo root: star_sim/api.py -> parents
#   [0]=star_sim  [1]=backend  [2]=repo root
FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"

app = FastAPI(title="Star Simulator", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # localhost-only app; keep simple
    allow_methods=["GET"],
    allow_headers=["*"],
)


def _provider_unavailable(exc: ProviderDataMissing) -> HTTPException:
    """Translate 'backing data not fetched yet' into an actionable 503."""
    return HTTPException(status_code=503, detail=str(exc))


@app.get("/health")
def health() -> dict:
    """Liveness + whether the provider's data is actually ready to serve state."""
    info = {"status": "ok", "provider": getattr(PROVIDER, "name", type(PROVIDER).__name__)}
    try:
        info["ranges"] = PROVIDER.parameter_ranges()
        info["data_ready"] = True
    except ProviderDataMissing as exc:
        info["data_ready"] = False
        info["detail"] = str(exc)
    return info


@app.get("/ranges")
def ranges() -> dict:
    """Valid mass / [Fe/H] ranges so the UI can never request an out-of-grid point."""
    try:
        return PROVIDER.parameter_ranges()
    except ProviderDataMissing as exc:
        raise _provider_unavailable(exc) from exc


@app.get("/mass_range")
def mass_range(
    feh: float = Query(..., description="initial [Fe/H]"),
    vvcrit: float = Query(0.0, description="rotation v/vcrit (snaps to a rotation grid)"),
) -> dict:
    """Valid mass span at this [Fe/H] so the UI can clamp the mass slider.

    The (mass, [Fe/H]) domain isn't rectangular — some metallicities lack
    low-mass tracks — so this can be narrower than /ranges' bounding box.
    `vvcrit` snaps to a rotation bucket (default 0.0 = non-rotating).
    """
    try:
        lo, hi = PROVIDER.mass_range(feh, vvcrit)
    except ParameterOutOfRange as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ProviderDataMissing as exc:
        raise _provider_unavailable(exc) from exc
    return {"min": lo, "max": hi}


@app.get("/age_range")
def age_range(
    mass: float = Query(..., description="initial mass / M_sun"),
    feh: float = Query(..., description="initial [Fe/H]"),
    vvcrit: float = Query(0.0, description="rotation v/vcrit (snaps to a rotation grid)"),
) -> dict:
    try:
        lo, hi = PROVIDER.age_range(mass, feh, vvcrit)
    except ParameterOutOfRange as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ProviderDataMissing as exc:
        raise _provider_unavailable(exc) from exc
    return {"min": lo, "max": hi}


@app.get("/state")
def state(
    mass: float = Query(..., description="initial mass / M_sun"),
    feh: float = Query(..., description="initial [Fe/H]"),
    age: float = Query(..., description="current age / yr"),
    vvcrit: float = Query(0.0, description="rotation v/vcrit (snaps to a rotation grid)"),
) -> dict:
    """(mass, [Fe/H], age) -> StellarState, serialized exactly as the §3 dataclass."""
    try:
        st = PROVIDER.state_at(mass, feh, age, vvcrit)
    except ParameterOutOfRange as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ProviderDataMissing as exc:
        raise _provider_unavailable(exc) from exc
    return asdict(st)


@app.get("/track")
def track(
    mass: float = Query(..., description="initial mass / M_sun"),
    feh: float = Query(..., description="initial [Fe/H]"),
    vvcrit: float = Query(0.0, description="rotation v/vcrit (snaps to a rotation grid)"),
) -> list[dict]:
    """(mass, [Fe/H]) -> the full evolutionary track: a list of StellarState dicts
    ordered by EEP. Age-independent, so the HR diagram and composition panel fetch
    it once per (mass, [Fe/H]) and move their marker as age scrubs. Same per-element
    shape as /state — the API still adds no fields of its own (§3, §4). `vvcrit`
    snaps to a rotation bucket (default 0.0 = non-rotating); the rotating track
    carries the same shape with the surface enrichment / HR shift baked in."""
    try:
        states = PROVIDER.track(mass, feh, vvcrit)
    except ParameterOutOfRange as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ProviderDataMissing as exc:
        raise _provider_unavailable(exc) from exc
    return [asdict(st) for st in states]


@app.get("/endgame")
def endgame(
    mass: float = Query(..., description="initial mass / M_sun"),
    feh: float = Query(..., description="initial [Fe/H]"),
    vvcrit: float = Query(0.0, description="rotation v/vcrit (snaps to a rotation grid)"),
    meta: bool = Query(
        False,
        description="type-only fast path: drop the heavy `states` list and return just "
        "the routing metadata (fate type + snapped mass + a `has_states` flag). The "
        "gateway BUTTON needs only these — ~120 B vs the full ~1 MB cooling/wind track.",
    ),
) -> dict:
    """(mass, [Fe/H]) -> the stellar endgame past the normal track window: the WR/WD
    gateway (STAR_SIM_SPEC §6+; docs/plans/smoldering-cinder-gateway.md).

    This DOES go through `PROVIDER` — unlike `/polytrope` and `/spectrum`, an endgame
    state *is* a `StellarState` (a white dwarf / Wolf-Rayet has a defined Teff, L, R,
    log g, composition). The route stays provider-agnostic: a provider with no endgame
    data answers `type="none"` (the §3 boundary holds — the route never asks which
    provider it is). The response is the `EndgameResult` dataclass with its `states`
    serialized exactly as the §3 `StellarState` shape (the API adds no fields). The
    gateway reads `type` (WD / WR / SN / none) to pick the renderer; `states` is the
    scrubbable endgame sequence (empty for SN / none).

    `meta=1` serves the *same* `EndgameResult`, minus its bulk: the gateway button only
    needs the fate type, the snapped `mass_init_msun` (for the SN note), and whether a
    renderable sequence exists. So we drop `states` and add an explicit `has_states`
    boolean (mirrors the frontend's `states.length` guard without assuming "type implies
    states"). Still §3-clean — every field is the same routing metadata the dataclass
    already exposes, no provider internals leak; the classifier still builds the full
    track (so cold latency is unchanged), we just don't serialize/ship the 1 MB. The
    full fetch (no `meta=`) still backs the HR preview + the warm gateway-enter cache."""
    try:
        result = PROVIDER.endgame(mass, feh, vvcrit)
    except ParameterOutOfRange as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ProviderDataMissing as exc:
        raise _provider_unavailable(exc) from exc
    d = asdict(result)
    if meta:
        d["has_states"] = bool(d["states"])
        d["states"] = []
    return d


@app.get("/rotation_status")
def rotation_status(
    mass: float = Query(..., description="initial mass / M_sun"),
    feh: float = Query(..., description="initial [Fe/H]"),
) -> dict:
    """Whether the rotation control is *meaningful* at (mass, [Fe/H]) — the
    data-derived honesty gate the frontend reads to render the rotation toggle
    (docs/plans/whirling-cohort-atlas.md, Chunk 3).

    Goes through `PROVIDER` (a provider with no rotating grid answers has_grid=False,
    so the route stays §3-clean). Shape:
        {"has_grid": bool,             # a rotating grid covers this [Fe/H]
         "threshold_msun": float|None, # rotation-onset (Kraft-break) mass, data-derived
         "active": bool}               # has_grid AND mass >= threshold

    `active` is False where toggling rotation would change nothing (below the
    magnetic-braking limit the rotating and non-rotating tracks are bit-identical),
    so the UI greys the toggle as an honest no-op there; `has_grid` False hides it
    entirely (no rotating grid fetched at this metallicity)."""
    try:
        return PROVIDER.rotation_status(mass, feh)
    except ProviderDataMissing as exc:
        raise _provider_unavailable(exc) from exc


@app.get("/supernova")
def supernova(
    mass: float = Query(..., description="initial mass / M_sun"),
    feh: float = Query(..., description="initial [Fe/H]"),
    vvcrit: float = Query(0.0, description="rotation v/vcrit (snaps to a rotation grid)"),
    m_ni: float | None = Query(
        None,
        ge=0.0,
        le=1.0,
        description="⁵⁶Ni mass / M_sun — the Tier-3 free knob (default 0.06; clamped to "
        "the observed 0.001–0.3 range). Drives the radioactive tail/peak height.",
    ),
    e_kin: float = Query(
        1.0e51, gt=0.0, description="explosion kinetic energy / erg (canonical 1e51)"
    ),
) -> dict:
    """(mass, [Fe/H]) -> the computed core-collapse supernova: a ⁵⁶Ni-powered light curve
    + homologous-expansion photosphere states (docs/plans/radioactive-afterglow-requiem.md).

    Like `/polytrope` and `/spectrum`, the *computation* does **not** go through `PROVIDER`
    — a supernova is a semi-analytic model, not a `StellarState` snapped to a track (the
    MIST tracks end at collapse and carry no explosion data). But it is a **hybrid**: the
    route first calls `PROVIDER.endgame()` to *classify* the star and read its progenitor
    scalars (he/CO cores, pre-collapse R₀, surface-H), then hands those to the
    `supernova.py` sibling. The §3 boundary holds: a non-SN progenitor (WD/WR/none, or any
    provider that doesn't model the endgame) comes back `is_supernova=false` with the real
    fate echoed and no curve — the gateway then shows the matching renderer instead.

    The SN payload is the `SupernovaModel` serialized verbatim: the three-tier light curve
    (`light_curve.L_total/L_radio/L_plateau` in erg/s vs `time_days`), the photosphere
    `states` (exactly the §3 StellarState shape, for the 3D/SED/scale consumers), the
    explosion scalars (M_ej, M_Ni default+range, E_K, v_phot, remnant), and the honesty
    `tiers`. `m_ni` is the only free input (Tier-3); the plateau peak carries no M_Ni term."""
    try:
        eg = PROVIDER.endgame(mass, feh, vvcrit)
    except ParameterOutOfRange as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ProviderDataMissing as exc:
        raise _provider_unavailable(exc) from exc

    # Only the SN branch has a supernova to compute. WD / WR / none -> an honest empty
    # payload echoing the real fate (the §3 boundary: a non-SN progenitor, or a provider
    # with no endgame data, simply has no light curve here).
    if eg.type != "SN" or eg.co_core_msun is None:
        return {
            "type": eg.type,
            "is_supernova": False,
            "mass_init_msun": eg.mass_init_msun,
            "feh_init": eg.feh_init,
            "light_curve": None,
            "states": [],
            "reason": f"{eg.type} progenitor — no core-collapse supernova at this (mass, [Fe/H]).",
        }

    prog = Progenitor(
        mass_init_msun=eg.mass_init_msun,
        final_mass_msun=eg.final_mass_msun,
        he_core_msun=eg.he_core_msun,
        co_core_msun=eg.co_core_msun,
        pre_sn_radius_rsun=eg.pre_sn_radius_rsun,
        h_retained=eg.h_retained,
        feh_init=eg.feh_init,
    )
    model = supernova_model(prog, m_ni=m_ni, e_kin=e_kin)
    d = asdict(model)            # recurses `states` into the §3 StellarState shape
    d["is_supernova"] = True
    return d


@app.get("/polytrope")
def polytrope(
    n: float = Query(
        ...,
        ge=0.0,
        le=5.0,
        description="polytropic index n (P = K ρ^(1+1/n)); 0 ≤ n ≤ 5",
    ),
) -> dict:
    """(n) -> a static Lane-Emden polytrope profile (STAR_SIM_SPEC.md §8).

    This is the one endpoint that does **not** go through `PROVIDER`: Lane-Emden is
    a sibling to the StellarState spine, not a `StellarState`. It's a self-contained
    static-structure teaching piece driven by the index `n` alone — independent of
    whichever star the rest of the UI is showing. The valid domain is 0 ≤ n ≤ 5
    (n ≥ 5 has no finite surface; n > 5 is unbound), enforced by the Query bounds.
    """
    return polytrope_profile(n)


@app.get("/structure")
def structure(
    mass: float = Query(..., gt=0.0, description="initial mass / M_sun"),
    feh: float = Query(0.0, description="initial [Fe/H]"),
    age: float = Query(..., gt=0.0, description="stellar age / yr"),
) -> dict:
    """(mass, [Fe/H], age) -> a REAL MESA radial interior-structure snapshot.

    The honest successor to `/polytrope`: where Lane-Emden gives an *idealized* static
    polytrope from an index `n`, this serves a **real** radial structure — ρ(r), T(r),
    P(r), composition(r), and the true convective/radiative boundaries — read from an
    offline MESA `profile.data` snapshot, plus the two canonical polytrope overlays
    (n=1.5, n=3) so the panel can show how good the idealization is.

    Like `/polytrope` and `/spectrum` this does **not** go through `PROVIDER`: interior
    structure is a sibling to the `StellarState` spine, not a `StellarState`. It snaps
    to the nearest saved snapshot in (mass, [Fe/H], age) and reports the *true* snapped
    values — never an interpolation across snapshots (the panel jumps between the
    handful of saved snapshots, labeled honestly). If no profiles have been generated
    yet, return 503 with an actionable hint (analogue of a missing provider grid)."""
    try:
        return interior_structure(mass, feh, age)
    except StructureDataMissing as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/binary")
def binary(
    mass: float = Query(..., gt=0.0, description="progenitor initial mass / M_sun"),
    feh: float = Query(0.0, description="initial [Fe/H]"),
) -> dict:
    """(progenitor mass, [Fe/H]) -> the hot He-star it becomes if stripped in a close
    binary — the ~70% binary WR/subdwarf channel (docs/plans/stripped-consort-unveiling.md).

    Like `/polytrope`, `/structure` and `/supernova`, this does **not** go through
    `PROVIDER`: a binary product cannot pass through the single-star `StellarState`
    interface (§3). It is a sibling — `binary.py` reads the committed Götberg 2018
    stripped-star table, **snaps** to the nearest grid model in (Z, initial mass) — never
    interpolates (§6) — and returns a `StellarState` (exact §3 shape, under `state`, for
    the existing 3D/HR/comp/spectrum consumers) plus routing scalars: the CURRENT stripped
    mass `M_strip` (which has no home on the state), the true snapped `M_init`/Z, and the
    eligible progenitor-mass range + snapped-far flags the frontend gates its stripped-mode
    toggle and caption on.

    Snap-always (like `/structure`): an out-of-grid request snaps to the nearest node and
    is flagged in-band (`mass_snapped_far` / `feh_snapped_far`) rather than 422'd — the
    hide-below-2 / note-above-18.2 UX decision is the frontend's, reading those flags. 422
    is reserved for structurally invalid input (mass ≤ 0, enforced by the Query bound); a
    missing committed table (should never happen) → 503."""
    try:
        return stripped_star_payload(mass, feh)
    except BinaryDataMissing as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/population")
def population(
    feh: float = Query(..., ge=-5.0, le=2.0, description="initial [Fe/H]"),
    age_gyr: float = Query(..., gt=0.0, description="population age / Gyr"),
    population: str = Query("both", pattern="^(both|sin|bin)$",
                            description="which curves: both (default), sin, or bin"),
) -> dict:
    """(feh, age_gyr) -> the integrated single & binary COEVAL-POPULATION spectra at the
    nearest ([Fe/H], age) BPASS node — the first ENSEMBLE overlay
    (docs/plans/coeval-ensemble-overlay.md, Chunk 1).

    Like `/spectrum`, `/structure` and `/helium`, this does **not** go through `PROVIDER`:
    a coeval stellar population (a million stars born together, seen at the marker's age)
    is not a single star — it is a sibling, `bpass.py`, over a build-time BPASS SSP-spectrum
    bake. The headline (Gate 0, measured): binaries keep the population UV/ionizing-bright
    far longer than single-star evolution can. Both curves are served by default (draw-both,
    so a frontend single↔binary comparison needs no refetch).

    Snap-always (like `/structure`): ([Fe/H], age) snap to the nearest grid node (nearest
    [Fe/H] linearly, nearest age in log10) and are flagged in-band (`*_snapped_far`), never
    422'd. 422 is reserved for structurally invalid input (age <= 0, absurd [Fe/H]); a
    missing/unbaked cube -> 503."""
    try:
        return population_sed(feh, age_gyr, population)
    except BpassDataMissing as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/population_status")
def population_status() -> dict:
    """Whether the coeval-population overlay has data — the honesty gate the frontend reads
    to decide if the toggle appears (mirrors `/helium_status`). The BPASS cube is
    gitignored/host-baked (like the MESA runs), so a fresh clone has none; hiding the toggle
    then beats showing one that can only 503. Cheap (a stat), always 200."""
    return {"has_grid": bpass_available()}


@app.get("/helium")
def helium(
    mass: float = Query(..., gt=0.0, description="initial mass / M_sun"),
) -> dict:
    """(mass) -> the initial-helium (Y) what-if: a baseline vs. He-enhanced MESA track
    pair at matched mass/[Fe/H] (docs/plans/tempered-lineage-inspiral.md, Phase 2).

    Like `/structure`, `/binary` and `/supernova`, this does **not** go through
    `PROVIDER`. The globular-cluster second-generation what-if (omega Cen / NGC 2808:
    Y ~ 0.40 vs primordial ~0.27 at the *same* [Fe/H]) cannot be an axis on the single-
    star spine — it is a sibling, `helium.py`, that reads two self-run MESA `history.data`
    runs (identical inlist, Y the sole difference) and returns both as §3 `StellarState`
    tracks. The overlay is drawn ONLY against its own MESA baseline, never the live MIST
    spine — comparing self-run MESA to MIST would conflate the He effect with the
    documented MESA-vs-MIST systematic.

    Snap-always (like `/structure`): `mass` snaps to the nearest grid mass (1/2/6 M_sun,
    solar Z) and is flagged in-band (`mass_snapped_far`), never 422'd. 422 is reserved
    for structurally invalid mass <= 0 (the Query bound); a missing MESA run set -> 503."""
    try:
        return helium_overlay(mass)
    except HeliumDataMissing as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/helium_status")
def helium_status() -> dict:
    """Whether the initial-helium overlay has data — the honesty gate the frontend reads
    to decide if the toggle appears at all (mirrors `/rotation_status`). MESA runs are never
    committed/hosted, so a fresh clone has none; hiding the toggle then beats showing one that
    can only 503. Cheap (a glob), always 200."""
    return {"has_grid": helium_available()}


@app.get("/alpha")
def alpha(
    mass: float = Query(..., gt=0.0, description="initial mass / M_sun"),
) -> dict:
    """(mass) -> the α-enhanced what-if: a baseline vs. α-enhanced (equivalent-Z) MESA
    track pair at matched mass/[Fe/H] (docs/plans/tempered-lineage-inspiral.md, Phase 3).

    Like `/helium`, this does **not** go through `PROVIDER`. [α/Fe] raises the true total
    metallicity Z at fixed [Fe/H] (Salaris 1993 equivalent-Z), pushing the track cooler,
    fainter, and longer-lived — the opposite sign from the He effect. The "enhanced" member
    is a scaled-solar MESA run at the equivalent Z (MESA ships no α-enhanced opacity tables;
    the Salaris residual is below what this sim resolves), so the track responds to α only
    through total Z — α's distinctive signature is spectroscopic (the Coelho α-toggle), which
    the frontend caption pairs this with. The overlay is drawn ONLY against its own MESA
    baseline, never the live MIST spine (that would conflate the effect with the MESA-vs-MIST
    systematic).

    Snap-always: an out-of-grid mass snaps to the nearest node (1/2/6 M_sun, solar [Fe/H]) and
    is flagged in-band (`mass_snapped_far`), never 422'd. 422 is reserved for structurally
    invalid mass <= 0 (the Query bound); a missing MESA run set -> 503."""
    try:
        return alpha_overlay(mass)
    except AlphaDataMissing as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/alpha_status")
def alpha_status() -> dict:
    """Whether the α-enhanced overlay has data — the frontend toggle-visibility gate
    (mirrors `/helium_status`). Self-run MESA runs are never committed/hosted; hiding the
    toggle on a fresh clone beats showing one that can only 503. Cheap (a glob), always 200."""
    return {"has_grid": alpha_available()}


def _donor_ms_lifetime(mass: float, feh: float) -> float:
    """Elapsed system age when the donor fills its Roche lobe and is stripped ≈ the
    donor's single-star main-sequence lifetime = the age at TAMS (the first post-MS row)
    on its own MIST track. The companion, being less massive (q=0.8), is still on the MS
    at this age — so the two-star view never shows a degenerate off-track companion (the
    path (b) measure-first gate confirmed this holds across the whole eligible grid)."""
    track = PROVIDER.track(mass, feh)
    for s in track:
        if s.phase != "MS":
            return s.age_yr
    return track[-1].age_yr


@app.get("/binary_pair")
def binary_pair(
    mass: float = Query(..., gt=0.0, description="progenitor (donor) initial mass / M_sun"),
    feh: float = Query(0.0, description="initial [Fe/H]"),
) -> dict:
    """(donor initial mass, [Fe/H]) -> the two-star Algol system: the stripped He-star
    DONOR (same top-level shape as `/binary`) PLUS its close companion (the accretor).
    Path (b) of docs/plans/stripped-consort-unveiling.md — "the companion drawn."

    The companion is composed HERE, in the route — NOT in `binary.py`, which stays a pure
    §3 sibling. A *binary product* can't go through the single-star interface, but the
    *companion* is an ordinary single star, so it comes straight from `PROVIDER`. Baseline
    (non-conservative): the companion is a single star at its known initial mass
    M2_init = 0.8·M_init (the grid's fixed q), observed at the elapsed system age = the
    donor's MS lifetime (the donor is stripped at ≈TAMS). Because the companion is less
    massive it is still on the MS then; the mass-ratio *reversal* (M_strip < M2_init) is
    the payoff — see `binary.binary_pair_payload`.

    Both stars share the snapped system metallicity (`feh_snapped`): the donor grid is
    coarse in Z (solar-only for now), so the whole system snaps to the donor's grid Z and
    the companion follows — a binary has one metallicity. Snap-always like `/binary`; a
    missing committed table -> 503, and if the MIST grids are absent the companion fetch
    surfaces the usual data-unavailable 503."""
    try:
        donor = stripped_star(mass, feh)
    except BinaryDataMissing as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    feh_sys = donor.feh_snapped                       # both stars at the snapped system Z
    m2 = companion_init_mass(donor.m_init_msun)       # 0.8 × the snapped donor node
    try:
        tau = _donor_ms_lifetime(donor.m_init_msun, feh_sys)
        companion = PROVIDER.state_at(m2, feh_sys, tau)
    except ParameterOutOfRange as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ProviderDataMissing as exc:
        raise _provider_unavailable(exc) from exc
    return binary_pair_payload(mass, feh, companion, tau)


@app.get("/binary_track_meta")
def binary_track_meta_route(
    feh: float = Query(0.0, description="initial [Fe/H] (snaps to the nearest baked grid)"),
) -> dict:
    """[Fe/H] -> the baked POSYDON HMS-HMS grid bounds (M1/q/P ranges + track count) at
    the nearest available metallicity — for UI gating, mirroring the `/endgame?meta=1`
    fast path (don't ship a whole time-series track just to size a slider)."""
    try:
        return binary_track_meta(feh)
    except PosydonDataMissing as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/binary_track")
def binary_track_route(
    m1: float = Query(..., gt=0.0, description="donor (star 1) initial mass / M_sun"),
    q: float = Query(..., gt=0.0, le=1.0, description="mass ratio M2/M1 at t=0"),
    p: float = Query(..., gt=0.0, description="initial orbital period / days"),
    feh: float = Query(0.0, description="initial [Fe/H]"),
) -> dict:
    """(M1, q, P, [Fe/H]) -> a co-evolved POSYDON HMS-HMS binary track: both stars'
    full time history (paired `StellarState`s) + the real orbit — path (b) Chunk 4a
    (docs/plans/entwined-consort-inspiral.md), the on-ramp to the two-star HR *movie*
    that `/binary_pair`'s single snapshot can't give (the Algol reversal as it happens,
    not a caption).

    Unlike `/binary` and `/binary_pair`, this does **not** go through `PROVIDER` for a
    different reason than usual: it's not just that a two-star result can't fit the
    single-star interface (§3) — it's a genuine TIME SERIES, the first of its kind among
    the siblings. Each step is two `StellarState`s (`star_2` is `null` after a merger)
    plus orbital scalars (period, separation, eccentricity — always 0.0 on this
    tidally-circularized grid — and a data-derived `mt_state` that flags RLOF/contact
    episodes as they fire).

    Snap-always (the `/binary` precedent): (M1, q, P) snaps to the nearest real POSYDON
    track in normalized (log M1, log P, linear q) space — never interpolated (§6, no
    row-for-row correspondence between tracks to blend) — and the true snapped node is
    reported alongside in-band `*_snapped_far` honesty flags. 422 is reserved for
    structurally invalid input (the Query bounds); a missing baked grid -> 503."""
    try:
        return binary_track_payload(m1, q, p, feh)
    except PosydonDataMissing as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/co_binary_track_meta")
def co_binary_track_meta_route(
    feh: float = Query(0.0, description="initial [Fe/H] (snaps to the nearest baked grid)"),
    kind: str = Query("co-hms-rlo", description="CO grid: co-hms-rlo (H-rich secondary, "
                       "default) | co-hems | co-hems-rlo (He-star double-compact channel)"),
) -> dict:
    """([Fe/H], kind) -> the baked POSYDON CO grid bounds (M_star/M_co/P ranges + track
    count) at the nearest available metallicity — mirrors `/binary_track_meta`."""
    try:
        return co_binary_track_meta(feh, kind)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except PosydonCoDataMissing as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/co_binary_track")
def co_binary_track_route(
    m_star: float = Query(..., gt=0.0, description="surviving star's initial mass / M_sun"),
    m_co: float = Query(..., gt=0.0, description="compact object's initial mass / M_sun"),
    p: float = Query(..., gt=0.0, description="initial orbital period / days"),
    feh: float = Query(0.0, description="initial [Fe/H]"),
    kind: str = Query("co-hms-rlo", description="CO grid: co-hms-rlo (H-rich secondary, "
                       "default) | co-hems | co-hems-rlo (He-star double-compact channel)"),
) -> dict:
    """(M_star, M_co_init, P, [Fe/H], kind) -> a POSYDON CO-binary track: a compact object
    (NS/BH/WD, left by an earlier primary's collapse) orbiting a secondary — path (b) Phase 1
    (docs/plans/tempered-lineage-inspiral.md), the stage AFTER `/binary_track`'s two-normal-
    star episode. `kind` selects the grid: "co-hms-rlo" (Chunk 1a, an H-rich secondary — the
    X-ray-binary accretion payoff) or "co-hems"/"co-hems-rlo" (Chunk 2a, a bare-He-star
    secondary — the double-compact-object channel, whose payload also carries a `dco`
    endpoint classification).

    Unlike `/binary_track`, each step carries only ONE real `StellarState` (the surviving
    star — `history2`, the compact-object side, is absent on these grids unconditionally,
    per the schema recon in `posydon_co.py`'s docstring) plus the compact object's own
    mass/type/accretion-rate as routing scalars, and a schematic `accretion_lum_lsun` cue
    (a standard L=eta*Mdot*c^2 formula on the grid's real accretion rate — NOT a measured
    X-ray spectrum, see `posydon_co.py`'s `ACCRETION_EFFICIENCY`).

    Snap-always, same discipline as `/binary_track`: (M_star, M_co, P) snaps to the
    nearest real track in (log M_star, log M_co, log P) space — never interpolated (§6).
    422 is reserved for structurally invalid input (incl. an unknown `kind`); a missing
    baked grid -> 503."""
    try:
        return co_binary_track_payload(m_star, m_co, p, feh, kind)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except PosydonCoDataMissing as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/spectrum")
def spectrum(
    teff: float = Query(..., ge=1000.0, le=200000.0, description="effective temperature / K"),
    logg: float = Query(..., ge=-2.0, le=7.0, description="surface gravity, cgs dex"),
    feh: float = Query(0.0, ge=-5.0, le=2.0, description="initial [Fe/H]"),
) -> dict:
    """(Teff, log g, [Fe/H]) -> a synthetic spectrum (λ vs flux, with absorption
    lines), STAR_SIM_SPEC §5.

    Like `/polytrope`, this does **not** go through `PROVIDER`: a spectrum is a
    sibling to the StellarState spine, a derived view of the state's
    (Teff, log g, [Fe/H]) — the same numbers `color.js` turns into the star's
    colour. The `Query` bounds are deliberately *wider than any real star* the grid
    can produce (the hottest draggable star — a massive metal-poor O star — reaches
    ~80000 K, above the baked grid's 55000 K ceiling), so dragging the controls
    never trips a 422: `spectrum_data` clamps BOTH ends to the baked grid's real
    coverage (a star below the floor floors to the coolest spectrum, a hot O/B star
    caps at the hottest — symmetric). 422 is reserved for genuinely absurd inputs.
    The response also reports `teff_requested` + the grid's `teff_min`/`teff_max`, so
    the panel can tell a real interpolated spectrum from a clamped-ceiling one: past
    the HOT end (no model atmosphere exists) it shows a "no spectral model for this
    range" notice instead of the misleading boundary spectrum, keyed off the grid's
    real ceiling. The cool end is covered down to 2300 K (the Göttingen/PHOENIX cool
    splice), below every reachable star (~2800 K), so in practice the cool floor never
    clamps a real star — and a cool clamp would be an honest small extrapolation
    anyway (cool models exist), not a model gap, so there is no cool-end notice. If
    the grid hasn't been baked yet, return 503 with an actionable hint (analogue of a
    missing provider grid)."""
    try:
        return spectrum_data(teff, logg, feh)
    except SpectraDataMissing as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/alpha_spectrum")
def alpha_spectrum(
    teff: float = Query(..., ge=1000.0, le=200000.0, description="effective temperature / K"),
    logg: float = Query(..., ge=-2.0, le=7.0, description="surface gravity, cgs dex"),
    feh: float = Query(0.0, ge=-5.0, le=2.0, description="initial [Fe/H]"),
    afe: float = Query(0.0, ge=0.0, le=0.4, description="[alpha/Fe] (0.0 solar-scaled or 0.4 alpha-rich)"),
) -> dict:
    """(Teff, log g, [Fe/H], [alpha/Fe]) -> a Coelho-2014 synthetic spectrum — a
    FOURTH spectrum sibling beside `/spectrum`, `/wd_spectrum`, `/wr_spectrum` (atlas
    Tier B, the thick-disk/halo [alpha/Fe] axis).

    Reads the separate 4-axis Coelho cube (the COOL subset, Teff <= ~10000 K — Gate 1
    measured [alpha/Fe] dead hotter). [alpha/Fe] is a **spectrum-only** axis: at fixed
    [Fe/H] it deepens the O/Mg/Si/Ca/Ti (+ TiO) lines, but MIST evolution is
    solar-scaled so the star's track/composition do NOT follow it — the panel labels it
    a "what-if". Both baselines (afe 0.0 and 0.4) come from THIS cube, so a toggle flips
    two Coelho spectra (never Coelho-alpha vs a CAP18-solar one). The panel decides when
    to call this vs `/spectrum` (cool routes here; the main cube serves hotter stars,
    where alpha is dead). Wide `Query` bounds match `/spectrum` so dragging never trips a
    422 (the cube clamps). 503 if not yet baked."""
    try:
        return alpha_spectrum_data(teff, logg, feh, afe)
    except SpectraDataMissing as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/wd_spectrum")
def wd_spectrum(
    teff: float = Query(..., ge=1000.0, le=500000.0, description="effective temperature / K"),
    logg: float = Query(..., ge=3.0, le=10.0, description="surface gravity, cgs dex"),
) -> dict:
    """(Teff, log g) -> a white-dwarf / central-star synthetic spectrum (endgame Chunk 6).

    A SECOND spectrum sibling, like `/spectrum`: it reads the separate WD cube
    (log g 6.5–9.5, pure hydrogen — no `[Fe/H]` axis), because a white dwarf's
    gravity is disjoint from the main-sequence atmosphere grid (0–5) and can't share
    its cube. Two spliced sources cover the cooling sequence: **Koester DA** (LTE,
    5000–80000 K) for the cooling white dwarf, and **TMAP** (NLTE, 80000–190000 K,
    Chunk 6b) for the hot post-AGB central star (CSPN). The WD endgame's *consumer*
    (the spectrum panel) decides when to call this vs `/spectrum`, by surface gravity
    / temperature: a TPAGB giant still has a real main-cube spectrum; the degenerate
    remnant and the hot central star route here.

    The `Query` bounds are wide (Teff up to 500000 — the most massive progenitors'
    central stars peak ~400 kK) so a re-snapped remnant never trips a 422;
    `wd_spectrum_data` clamps to the cube and handles the honest edges itself — a DC
    blackbody continuum below the ~5000 K Koester floor (the cold cinder has lost its
    Balmer lines), and the `teff_max` no-model path above TMAP's 190000 K ceiling (the
    narrow residual gap for the very hottest central stars). 503 if not yet baked."""
    try:
        return wd_spectrum_data(teff, logg)
    except SpectraDataMissing as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/wr_spectrum")
def wr_spectrum(
    teff: float = Query(..., ge=1000.0, le=500000.0, description="effective temperature / K"),
    lum: float = Query(..., gt=0.0, description="luminosity / L_sun"),
    xsurf: float = Query(..., ge=0.0, le=1.0, description="surface hydrogen mass fraction"),
    ysurf: float = Query(..., ge=0.0, le=1.0, description="surface helium mass fraction"),
    zsurf: float = Query(..., ge=0.0, le=1.0, description="surface metal mass fraction"),
    feh: float = Query(0.0, ge=-4.0, le=1.0, description="initial [Fe/H]"),
) -> dict:
    """Wolf-Rayet wind-emission spectrum (endgame Chunk 7) — a THIRD spectrum sibling.

    Reads the PoWR cube, whose axis is the WR spectroscopic pair (T*, transformed
    radius Rt), NOT (Teff, log g) — so the route takes the star's `(Teff, L, surface
    composition, [Fe/H])` and `wr_spectrum_data` does the placement: subtype (WNE/WNL/
    WC) from the composition, metallicity grid from [Fe/H], T* ≈ Teff, and Rt from L +
    a Nugis-Lamers Ṁ. It then snaps to the nearest real grid node, OR reports
    `regime="none"` when the star is hotter / denser-wind than any PoWR model — the
    stripped-core bulk the Chunk-7a gate measured off-grid, where the panel shows an
    honest 'no model' frame (recipe §7a). The wide Teff `Query` bound (up to 500000)
    keeps a 250+ kK stripped core from tripping a 422; the off-grid path handles it.
    503 if the WR cube isn't baked."""
    try:
        return wr_spectrum_data(teff, lum, xsurf, ysurf, zsurf, feh)
    except SpectraDataMissing as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/stripped_spectrum")
def stripped_spectrum(
    minit: float = Query(..., gt=0.0, description="progenitor initial mass / M_sun"),
    feh: float = Query(0.0, ge=-5.0, le=2.0, description="initial [Fe/H]"),
) -> dict:
    """(progenitor initial mass, [Fe/H]) -> the binary-stripped He-star's CMFGEN spectrum
    (Chunk 3) — a FOURTH spectrum sibling beside `/spectrum`, `/wd_spectrum`, `/wr_spectrum`.

    Reads the separate Götberg 2018 stripped-star cube, keyed on the SAME (Z, M_init) grid
    node `/binary` snaps — so the frontend passes the node `/binary` already resolved
    (`m_init_msun`, `feh_snapped`) and the served spectrum is guaranteed to be the SAME star
    as the marker (state<->spectrum consistency). The flux is CMFGEN's continuum-normalized
    Fnorm, a bidirectional draw: absorption lines dip below the continuum at the low-mass
    subdwarf end, emission lines rise above it at the high-mass He-star end (He II 4686 up to
    ~7× — Götberg's subdwarf↔Wolf-Rayet sequence). `regime` ∈ {"absorption","hybrid",
    "emission"} names where the node sits; `feh_varies` is false (solar-only cube, matching
    binary.py's committed table). Snap-always (mirrors `/binary`): the cube snaps to the
    nearest node, so 422 is reserved for structurally invalid input (mass ≤ 0). 503 if not
    yet baked."""
    try:
        return stripped_spectrum_data(minit, feh)
    except SpectraDataMissing as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


# --- static frontend ----------------------------------------------------------
# Mounted last so the API routes above take precedence. html=True serves
# index.html at "/".
if FRONTEND_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
