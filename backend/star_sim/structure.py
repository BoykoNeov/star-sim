"""The real interior-structure sibling — MESA radial profiles behind the §3 spine.

This is the honest successor to the Lane-Emden panel (`lane_emden.py`). Lane-Emden
gives an *idealized* static polytrope from a single index `n`; this module serves a
**real** radial structure — ρ(r), T(r), P(r), composition(r), and the true
convective/radiative boundaries — read from an offline MESA `profile.data` snapshot,
and hands the frontend both so it can overlay the two and *show how good (or poor)
the idealization is*.

Like `lane_emden.py` and `spectra.py` it is a **sibling** to the `StellarState` spine
(spec §3), NOT a provider and NOT a `StellarState`:

  * It never routes through `StellarStateProvider`, and it must not import any
    provider's internals (importing `providers.mesa` here would be a §3 bug — a
    consumer reaching into a provider). It carries its own tiny MESA-profile reader
    (the format is public and fixed; the reader is ~15 lines, mirroring the parser in
    `providers/mesa.py` without depending on it).
  * `/structure` bypasses `PROVIDER`, exactly like `/polytrope` and `/spectrum`.

Why MESA-only (and offline): MIST ships no radial profiles at all, and a live
structure solve is ruled out by spec §2/§9. So the profiles are generated offline by
running MESA (the solar Docker recipe extended to save profile snapshots — see
`backend/docs/mesa_structure_recipe.md`) and dropped, gitignored, under
`data/mesa_profiles/`. A request snaps to the nearest saved snapshot in
(mass, [Fe/H], age) and reports the *true* snapped values — never a silent
interpolation across snapshots (raw MESA profiles have no EEP alignment; interpolating
radial structure across ages/masses is exactly the machinery the spec rules out). The
panel therefore **jumps** between the handful of saved snapshots as the age slider
moves — honest, and labeled as "nearest saved snapshot".

The overlay uses the **canonical polytropic index**, not a best-fit `n`: n=3/2 (fully
convective / adiabatic) and n=3 (radiative, the Eddington standard model). A best-fit
would hide the very mismatch the panel exists to show; the canonical curves bracket the
real profile and the departure *is* the lesson (e.g. the Sun sits near n=3 in its
radiative core and pulls away in the convective envelope).
"""

from __future__ import annotations

import glob
import math
import os
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .lane_emden import solve_lane_emden

# data/mesa_profiles/ sits at the repo root: star_sim/structure.py -> parents
#   [0]=star_sim [1]=backend [2]=repo root  (same anchor as spectra.py)
_REPO_ROOT = Path(__file__).resolve().parents[2]
PROFILES_DATA_DIR = Path(
    os.environ.get("STAR_SIM_PROFILES_DIR", _REPO_ROOT / "data" / "mesa_profiles")
)

# Solar metal mass fraction for the derived-[Fe/H] label — matches MESAProvider/stub
# so all three report [Fe/H] on the same scale.
Z_SUN = 0.0152

# MESA mixing_type code for ordinary (Schwarzschild/Ledoux) convection. The other
# codes (overshoot, semiconvection, thermohaline, rotation, …) are not "the convective
# envelope/core" the panel shades; we treat only code 1 as convective, and cross-check
# against the Schwarzschild criterion gradr > grada (see `_convective_mask`).
_CONVECTIVE_MIXING = 1

# The two canonical polytropes the overlay draws (never a fitted n — see module docs).
_N_CONVECTIVE = 1.5   # fully convective / adiabatic
_N_RADIATIVE = 3.0    # radiative, Eddington standard model


class StructureDataMissing(RuntimeError):
    """No MESA `profile.data` snapshots are present under `PROFILES_DATA_DIR`.

    The API maps this to a 503 with an actionable hint, exactly like a missing baked
    spectrum grid or MIST grid — the app stays up; only `/structure` is unavailable
    until the profiles are generated (see the recipe)."""


_MISSING_HINT = (
    "No MESA interior-structure profiles found under {data_dir}. Generate them once "
    "by running MESA with profile snapshots enabled (see "
    "backend/docs/mesa_structure_recipe.md), then copy the profile*.data files into "
    "that directory."
)


def _read_mesa_profile(path: str) -> tuple[dict[str, str], dict[str, np.ndarray]]:
    """Parse one MESA `profile.data` into (header, data) dicts.

    The MESA profile format is the same fixed 6-line-header layout as history.data
    (docs.mesastar.org "MESA output"), just with a per-*zone* body instead of a
    per-*model* one:
      line 1: header column numbers
      line 2: header column names   (model_number, num_zones, star_age, …)
      line 3: header column values
      line 4: blank
      line 5: data column numbers
      line 6: data column names     (zone, mass, logR, logRho, …)
      line 7+: one row per zone (zone 1 = surface, increasing inward to the centre)
    Self-contained (no dependency on the MESA provider) to keep this a clean §3 sibling.
    """
    with open(path, "r") as fh:
        lines = fh.readlines()
    if len(lines) < 7:
        raise StructureDataMissing(f"{path}: too short to be a MESA profile.data file")

    h_names = lines[1].split()
    h_vals = lines[2].split()
    header = dict(zip(h_names, h_vals))

    d_names = lines[5].split()
    arr = np.loadtxt(path, skiprows=6, ndmin=2)
    if arr.shape[1] != len(d_names):
        raise StructureDataMissing(
            f"{path}: {arr.shape[1]} data columns but {len(d_names)} column names"
        )
    data = {name: arr[:, i] for i, name in enumerate(d_names)}
    return header, data


@dataclass
class _ProfileMeta:
    """The header scalars we index each saved snapshot by (for the (mass,feh,age) snap).

    `feh` is derived from `initial_z` (the run's metallicity), NOT the surface Z of the
    snapshot — so it is stable across the track (surface Z barely moves on the MS) and
    matches how the request's [Fe/H] is meant. `center_h` is the central hydrogen mass
    fraction, used only for the human-readable phase label of the snapshot."""

    path: str
    mass_init: float
    feh: float
    age_yr: float
    center_h: float


def _profile_meta(path: str) -> _ProfileMeta | None:
    """Read just a snapshot's header + centre H (cheap: header + final data row)."""
    header, data = _read_mesa_profile(path)
    try:
        mass = float(header["initial_mass"])
        z0 = float(header["initial_z"])
        age = float(header["star_age"])
    except (KeyError, ValueError):
        return None
    feh = math.log10(max(z0, 1e-12) / Z_SUN)
    # zone rows run surface -> centre, so the centre H is the LAST row's H fraction.
    xc = float(data["x_mass_fraction_H"][-1]) if "x_mass_fraction_H" in data else 0.0
    return _ProfileMeta(path=path, mass_init=round(mass, 4), feh=feh, age_yr=age, center_h=xc)


def _phase_label(center_h: float, mass_init: float) -> str:
    """A coarse, honest snapshot label from central hydrogen (the profiles here cover
    the MS, ZAMS→TAMS; no post-MS structure is saved for this slice)."""
    if center_h <= 1e-3:
        return "TAMS (core H exhausted)"
    if center_h >= 0.60:
        return "near ZAMS"
    return "main sequence"


class _ProfileIndex:
    """Lazily-built index of every saved profile snapshot under `PROFILES_DATA_DIR`.

    Construction is cheap and never touches disk until first use (so importing the API
    in a data-less checkout doesn't explode — it raises an actionable
    `StructureDataMissing` only when structure is actually requested), mirroring the
    lazy loads in `MESAProvider` / `_Spectra`."""

    def __init__(self, data_dir: Path | None = None):
        self._data_dir = Path(data_dir) if data_dir is not None else PROFILES_DATA_DIR
        self._metas: list[_ProfileMeta] | None = None

    def _ensure_loaded(self) -> list[_ProfileMeta]:
        if self._metas is not None:
            return self._metas
        files = sorted(glob.glob(str(self._data_dir / "**" / "profile*.data"), recursive=True))
        metas = [m for f in files if (m := _profile_meta(f)) is not None]
        if not metas:
            raise StructureDataMissing(_MISSING_HINT.format(data_dir=self._data_dir))
        self._metas = metas
        return metas

    def snap(self, mass: float, feh: float, age_yr: float) -> _ProfileMeta:
        """The saved snapshot nearest `(mass, feh, age)`: snap mass, then [Fe/H]
        within that mass, then age within that (mass,[Fe/H]) track. Honest — reports
        the true saved values downstream, never an interpolation across snapshots."""
        metas = self._ensure_loaded()
        masses = np.array([m.mass_init for m in metas])
        m_snap = float(masses[int(np.argmin(np.abs(masses - mass)))])
        at_mass = [m for m in metas if m.mass_init == m_snap]

        fehs = np.array([m.feh for m in at_mass])
        f_snap = float(fehs[int(np.argmin(np.abs(fehs - feh)))])
        at_feh = [m for m in at_mass if m.feh == f_snap]

        ages = np.array([m.age_yr for m in at_feh])
        return at_feh[int(np.argmin(np.abs(ages - age_yr)))]

    def available(self) -> list[_ProfileMeta]:
        return list(self._ensure_loaded())


# One process-wide index (built on first request), like the module-level spectra grid.
_INDEX = _ProfileIndex()


def _convective_mask(mixing_type: np.ndarray, gradr: np.ndarray, grada: np.ndarray) -> np.ndarray:
    """Per-zone boolean: is this zone convective?

    Primary signal is MESA's `mixing_type == 1` (ordinary convection). We OR in the
    Schwarzschild criterion `gradr > grada` as a robust cross-check — the two agree in
    the bulk of a convection zone; the mixing_type flag is the authority at the
    boundary (it already folds in the mixing-length treatment)."""
    conv = mixing_type == _CONVECTIVE_MIXING
    schwarz = gradr > grada
    return conv | schwarz


def _zones_from_mask(r_over_R: np.ndarray, mask: np.ndarray) -> list[list[float]]:
    """Contiguous convective intervals as [r/R start, r/R end] pairs (centre→surface).

    `r_over_R` and `mask` are ordered centre→surface. Returns the radial extent of each
    maximal run of convective zones, for the frontend to shade."""
    zones: list[list[float]] = []
    n = len(mask)
    i = 0
    while i < n:
        if mask[i]:
            j = i
            while j + 1 < n and mask[j + 1]:
                j += 1
            zones.append([float(r_over_R[i]), float(r_over_R[j])])
            i = j + 1
        else:
            i += 1
    return zones


def _polytrope_overlay(n: float, num_points: int = 160) -> dict:
    """The canonical polytrope as (r/R, ρ/ρ_c) — directly comparable to the real,
    centre-normalized profile. ξ/ξ₁ is the dimensionless radius fraction; ρ/ρ_c = θ^n."""
    s = solve_lane_emden(n)
    if not s.has_finite_surface or s.xi1 is None:
        return {"n": n, "r_over_R": [], "rho_over_rhoc": []}
    xi = np.linspace(0.0, s.xi1, num_points)
    theta = np.clip(s.theta(xi), 0.0, None)
    return {
        "n": n,
        "r_over_R": (xi / s.xi1).tolist(),
        "rho_over_rhoc": (theta**n).tolist(),
    }


def interior_structure(mass: float, feh: float, age_yr: float) -> dict:
    """(mass, [Fe/H], age) -> a real MESA radial-structure snapshot + polytrope overlay.

    Snaps to the nearest saved MESA `profile.data` and returns a JSON-friendly dict
    (pure numbers — a sibling, never a `StellarState`):

      snapped            : the true (mass, feh, age, phase) of the served snapshot
                           (the request is snapped, not interpolated — §3/§6 honesty)
      r_over_R           : dimensionless radius fraction r/R_surface, centre → surface
      rho_over_rhoc      : ρ(r)/ρ_c   (the §8 payoff plot — central concentration)
      T_over_Tc          : T(r)/T_c
      P_over_Pc          : P(r)/P_c
      X, Y, Z            : mass fractions H / He / metals vs r/R
      convective         : per-zone bool (mixing_type==1 ∪ Schwarzschild-unstable)
      convective_zones   : [[r/R, r/R], …] contiguous convective intervals to shade
      central            : absolute central ρ_c [g/cm³], T_c [K], P_c [dyne/cm²],
                           R_surface [R☉], M_total [M☉]  — for panel annotations
      polytropes         : the two canonical Lane-Emden overlays (n=1.5, n=3), each
                           {n, r_over_R, rho_over_rhoc}; NOT a best fit (see module docs)
      expected_n         : which canonical n the *core* structure matches (1.5 if the
                           innermost zone is convective, else 3) — a labeled hint, not a fit
      available_ages_yr  : all saved snapshot ages at this (mass,feh) (for slider ticks)
    """
    meta = _INDEX.snap(mass, feh, age_yr)
    _, d = _read_mesa_profile(meta.path)

    # MESA zones run surface -> centre; reverse everything to centre -> surface so
    # r/R increases monotonically from 0 and index 0 is the centre.
    order = slice(None, None, -1)
    r = 10.0 ** np.asarray(d["logR"], dtype=float)[order]          # R_sun
    m = np.asarray(d["mass"], dtype=float)[order]                   # M_sun coordinate
    rho = 10.0 ** np.asarray(d["logRho"], dtype=float)[order]       # g/cm^3
    P = 10.0 ** np.asarray(d["logP"], dtype=float)[order]           # dyne/cm^2
    T = 10.0 ** np.asarray(d["logT"], dtype=float)[order]           # K
    X = np.asarray(d["x_mass_fraction_H"], dtype=float)[order]
    Y = np.asarray(d["y_mass_fraction_He"], dtype=float)[order]
    Z = np.asarray(d["z_mass_fraction_metals"], dtype=float)[order]
    mixing = np.asarray(d.get("mixing_type", np.zeros_like(r)), dtype=float)[order]
    gradr = np.asarray(d.get("gradr", np.zeros_like(r)), dtype=float)[order]
    grada = np.asarray(d.get("grada", np.zeros_like(r)), dtype=float)[order]

    r_surf = float(r[-1]) if r[-1] > 0 else 1.0
    r_over_R = r / r_surf
    rho_c = float(rho[0])
    T_c = float(T[0])
    P_c = float(P[0])

    conv = _convective_mask(mixing, gradr, grada)
    expected_n = _N_CONVECTIVE if bool(conv[0]) else _N_RADIATIVE

    return {
        "snapped": {
            "mass_msun": meta.mass_init,
            "feh": round(meta.feh, 4),
            "age_yr": meta.age_yr,
            "phase": _phase_label(meta.center_h, meta.mass_init),
            "center_h": round(meta.center_h, 5),
        },
        "r_over_R": r_over_R.tolist(),
        "rho_over_rhoc": (rho / rho_c).tolist(),
        "T_over_Tc": (T / T_c).tolist(),
        "P_over_Pc": (P / P_c).tolist(),
        "X": X.tolist(),
        "Y": Y.tolist(),
        "Z": Z.tolist(),
        "convective": conv.astype(bool).tolist(),
        "convective_zones": _zones_from_mask(r_over_R, conv),
        "central": {
            "rho_c_gcc": rho_c,
            "T_c_K": T_c,
            "P_c_dyne": P_c,
            "R_surface_rsun": r_surf,
            "M_total_msun": float(m[-1]),
        },
        "polytropes": [_polytrope_overlay(_N_CONVECTIVE), _polytrope_overlay(_N_RADIATIVE)],
        "expected_n": expected_n,
        "available_ages_yr": sorted(mt.age_yr for mt in _INDEX.available()
                                    if mt.mass_init == meta.mass_init and mt.feh == meta.feh),
    }
