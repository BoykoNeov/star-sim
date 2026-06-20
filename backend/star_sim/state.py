"""The StellarState spine (STAR_SIM_SPEC.md §3) — NON-NEGOTIABLE.

This dataclass is the *entire* contract between the data layer and everything
downstream (HR diagram, 3D star, composition panel). It is deliberately a plain
dataclass with no web-framework or data-source concepts in it: a consumer that
imports a provider's internals (MIST columns, file formats, interpolation guts)
is a bug, not a shortcut.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class StellarState:
    # --- identity / where we are -------------------------------------------
    age_yr: float            # current age in years
    eep: float               # equivalent evolutionary point (see §6)
    phase: str               # human-readable: "MS", "subgiant", "RGB", ...

    # --- input parameters (constant for a given star) ----------------------
    mass_init_msun: float    # initial mass
    feh_init: float          # initial [Fe/H]

    # --- observable structure ----------------------------------------------
    L_lsun: float            # luminosity / L_sun
    Teff_K: float            # effective temperature
    R_rsun: float            # radius / R_sun
    logg: float              # surface gravity, cgs dex

    # --- composition (mass fractions) --------------------------------------
    X_surf: float
    Y_surf: float
    Z_surf: float
    X_core: float
    Y_core: float
    Z_core: float

    # --- optional / for visuals (may be derived, may be None early on) ------
    v_rot_kms: float | None = None   # surface rotation, if modeled
    activity: float | None = None    # 0..1 proxy driving corona brightness (§7)
