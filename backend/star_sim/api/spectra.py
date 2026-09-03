"""Spectra: five cubes, five routes, no provider.

A spectrum is a *derived view* of the state's (Teff, log g, [Fe/H]) — the same
numbers `color.js` turns into the star's colour — so every route here bypasses
`PROVIDER`. They differ only in which baked cube answers: the main atmosphere
grid, the Coelho [α/Fe] cube, the WD/CSPN splice, the PoWR wind cube, and the
Götberg stripped-star cube. The *consumer* decides which to call (by log g, by
temperature, by mode); the routes stay dumb.
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from ..spectra import (
    alpha_spectrum_data,
    spectrum_data,
    stripped_spectrum_data,
    wd_spectrum_data,
    wr_spectrum_data,
)

router = APIRouter()


@router.get("/spectrum")
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
    return spectrum_data(teff, logg, feh)


@router.get("/alpha_spectrum")
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
    return alpha_spectrum_data(teff, logg, feh, afe)


@router.get("/wd_spectrum")
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
    return wd_spectrum_data(teff, logg)


@router.get("/wr_spectrum")
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
    return wr_spectrum_data(teff, lum, xsurf, ysurf, zsurf, feh)


@router.get("/stripped_spectrum")
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
    return stripped_spectrum_data(minit, feh)
