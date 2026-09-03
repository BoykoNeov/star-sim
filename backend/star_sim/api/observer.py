"""Axis A — the observer's view: what the star looks like from here.

Apparent brightness is a *view* of the intrinsic `StellarState`, never on the spine.
Both routes compose rather than model: they take the star's served surface spectrum,
scale it by (R/d)², redden it, and convolve it through the committed filter curves
(`photometry.py`). `/photometry_track` reaches `provider()` only to fetch the track's
states — the sibling itself is handed plain arrays, because a magnitude is not a star
and `photometry.py` may not import `StellarState` at all (§3).
"""

from __future__ import annotations

import numpy as np
from fastapi import APIRouter, Query

from ..photometry import band_names, photometry_payload, track_band_mags
from ._deps import provider

router = APIRouter()


@router.get("/photometry")
def photometry(
    teff: float = Query(..., ge=1000.0, le=200000.0, description="effective temperature / K"),
    logg: float = Query(..., ge=-2.0, le=7.0, description="surface gravity, cgs dex"),
    feh: float = Query(0.0, ge=-5.0, le=2.0, description="initial [Fe/H]"),
    radius_rsun: float = Query(..., gt=0.0, le=2000.0, description="stellar radius / R☉"),
    distance_pc: float = Query(10.0, gt=0.0, le=1e9, description="observer distance / pc"),
    av: float = Query(0.0, ge=0.0, le=20.0, description="V-band extinction A_V / mag"),
    rv: float = Query(3.1, ge=1.0, le=7.0, description="extinction R_V (default 3.1)"),
) -> dict:
    """Axis A — the observer's view: (Teff, log g, [Fe/H], R) + a distance and a dust
    column → synthetic Vega magnitudes and an observational colour (B−V, M_V).

    Like `/spectrum` this does **not** go through `PROVIDER`: apparent brightness is a
    *view* of the intrinsic `StellarState`, never on the spine. The route composes —
    it takes the star's served surface spectrum (`spectrum_data`, absolute physical
    F_λ), scales it by (R/d)², reddens it with the Cardelli–Clayton–Mathis law, and
    convolves it through the committed B/V/BP filter curves (`photometry.py`), exactly
    the way `/binary_pair` composes a donor + a PROVIDER companion.

    Returns both the intrinsic ABSOLUTE magnitudes/colour (M_X at 10 pc, no dust — the
    CMD ordinate/abscissa) and the APPARENT ones as seen (m_X at this distance +
    extinction), plus the distance modulus and E(B−V). Only the B/V/BP bands the
    3001–8999 Å cube can cover are computed (Gaia G/RP, 2MASS JHK fall off the red
    edge — out of scope). `teff_requested`/`teff_max` from the spectrum echo whether a
    very hot star's spectrum was clamped to the grid ceiling (its blue colour is then a
    lower bound). 503 if the spectrum cube or filter asset is missing."""
    return photometry_payload(
        teff, logg, feh, radius_rsun, distance_pc=distance_pc, av=av, rv=rv,
    )


@router.get("/photometry_track")
def photometry_track(
    mass: float = Query(..., description="initial mass / M_sun"),
    feh: float = Query(..., description="initial [Fe/H]"),
    vvcrit: float = Query(0.0, description="rotation v/vcrit (snaps to a rotation grid)"),
    n_max: int = Query(120, ge=8, le=606, description="max locus points (uniform decimation)"),
) -> dict:
    """Axis A3 — the observational colour–magnitude locus of the whole evolutionary
    track: the star's (B−V)₀ vs. absolute M_V, the observer's version of the HR diagram.

    Like `/photometry` this is a **view**, not the spine: it goes through `PROVIDER`
    only to fetch the track's `StellarState`s, then composes each one's served surface
    spectrum (`spectrum_data`) into a flux stack and convolves the whole stack through
    the committed B/V/BP filters in ONE vectorized pass (`band_mags_stack`, written for
    exactly this). The result is the INTRINSIC absolute magnitudes (10 pc, no dust) —
    the CMD backdrop; the panel draws distance (a uniform μ shift) and reddening (the
    CMD reddening vector) on top, and the current-age marker's EXACT observed position
    comes from `/photometry`, so nothing approximate is ever plotted as truth.

    Decimated to `n_max` points (uniform stride) — a smooth locus needs far fewer than
    the ~600 EEP rows, and each row costs one spectrum interpolation. 503 if the
    spectrum cube or filter asset is missing; 422 if (mass, [Fe/H]) is out of range."""
    states = provider().track(mass, feh, vvcrit)

    if len(states) > n_max:
        idx = np.linspace(0, len(states) - 1, n_max).round().astype(int)
        idx = np.unique(idx)
        states = [states[i] for i in idx]

    # Plain arrays, not the states themselves: a magnitude is not a star, so
    # `photometry.py` never sees a StellarState (§3).
    mags = track_band_mags(
        [st.Teff_K for st in states],
        [st.logg for st in states],
        [st.feh_init for st in states],
        [st.R_rsun for st in states],
    )

    have_bv = "B" in mags and "V" in mags
    points = []
    for i, st in enumerate(states):
        row = {
            "age_yr": st.age_yr,
            "eep": st.eep,
            "phase": st.phase,
            "teff": st.Teff_K,
            "mv": float(mags["V"][i]),
        }
        if have_bv:
            row["bv0"] = float(mags["B"][i] - mags["V"][i])
        if "BP" in mags:
            row["bp"] = float(mags["BP"][i])
        points.append(row)
    return {"bands": band_names(), "points": points, "has_bv": have_bv}
