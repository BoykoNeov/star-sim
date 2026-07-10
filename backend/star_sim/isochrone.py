"""Isochrone / cluster sibling — Axis B of the outward quartet.

A *track* is one mass over all ages; an **isochrone** is all masses at **one age** — a
coeval cluster frozen in time, a locus on the HR diagram. The **main-sequence turnoff**
(the bluest point still on the MS) *is* the cluster's age: this is how star clusters are
dated, the most famous single result in stellar populations. Distinct from the BPASS
coeval-ensemble overlay (that is integrated light + number density; this is the
individual-star locus you actually fit to a cluster's photometry).

Like `structure.py` / `bpass.py` / `binary.py`, this is a **sibling**, not a provider:
it bypasses `PROVIDER`, reads the *published* MIST `.iso` grid, and returns a locus of
§3-clean `StellarState`s at a snapped (age, [Fe/H], vvcrit).

Reading the *published* isochrone grid is what keeps this **Tier-1**. The tempting
alternative — reconstructing the isochrone from the already-fetched EEP tracks by
inverting age-at-fixed-EEP for the mass — is exactly the interpolation-of-interpolation
/ EEP hazard the `lies-between-neighbors` test exists to guard against.

Data: the published MIST v2.5 `.iso` files are huge (~550 MB of text each, 170 columns).
So `fetch_mist_iso.py` **bakes** each solar-scaled ([a/Fe]=0) metallicity down to a
compact per-(feh, vvcrit) `.npz` under `data/mist_isochrones/` (gitignored; the tracks'
`_parsed_tracks.npz` precedent) holding only the ~11 columns the HR overlay needs, across
all ~107 tabulated ages. Version-consistent with the live tracks, so the user's star
lands exactly on the MS locus.

Snap-always (like `/structure`): [Fe/H] snaps linearly to the nearest baked node, age
**in log10** to the nearest tabulated isochrone (the age grid is log-spaced ~0.05 dex, so
a linear snap would be coarse at young ages), vvcrit to the nearest baked rotation grid.
Snaps are flagged in-band (`*_snapped_far`), never 422'd.
"""

from __future__ import annotations

import math
import os
from dataclasses import asdict
from functools import lru_cache
from pathlib import Path

import numpy as np

from .state import StellarState

_REPO_ROOT = Path(__file__).resolve().parents[2]
ISO_DATA_DIR = Path(
    os.environ.get("STAR_SIM_ISOCHRONE_DIR", _REPO_ROOT / "data" / "mist_isochrones")
)

# Bump when the baked column set / layout changes so stale `.npz` are rejected, not fed
# silently (the tracks' CACHE_VERSION discipline). Must match `fetch_mist_iso.BAKE_VERSION`.
BAKE_VERSION = 1

# FSPS evolutionary-phase codes → human labels. Defined *locally* (a physics concept, not a
# provider's internals) so the sibling never imports from `providers/`. Matches the map the
# MIST track provider uses.
_PHASE_NAMES = {
    -1: "PMS",
    0: "MS",
    2: "RGB",          # MIST lumps subgiant + RGB into phase 2
    3: "CHeB",
    4: "EAGB",
    5: "TPAGB",
    6: "post-AGB",
    9: "WR",
}

# "snapped far" thresholds (honesty flags, not hard limits — the route never 422s on
# these). [Fe/H] in dex; age in log10(yr).
_FEH_SNAP_FAR = 0.15
_LOGAGE_SNAP_FAR = 0.10


class IsochroneDataMissing(RuntimeError):
    """No baked MIST isochrone `.npz` files are present under `ISO_DATA_DIR`.

    The API maps this to a 503 with an actionable hint, exactly like a missing baked
    spectrum grid or MIST track grid — the app stays up; only `/isochrone` (and the
    frontend cluster overlay) is unavailable until the grid is fetched + baked."""


_MISSING_HINT = (
    "No baked MIST isochrone (.npz) files found under {data_dir}. Fetch + bake them once "
    "with `python -m star_sim.fetch_mist_iso` (downloads the published MIST v2.5 .iso grid "
    "and bakes the compact per-metallicity cubes). The frontend hides the cluster-overlay "
    "toggle until then."
)


@lru_cache(maxsize=16)
def _load_iso(path_str: str, _mtime: float) -> dict:
    """Load one baked per-(feh, vvcrit) `.npz` into a plain dict of arrays. Memoized per
    (path, mtime) — the cubes are ~4.5 MB, so keeping the handful of metallicities in
    memory is cheap and makes repeated requests instant."""
    with np.load(path_str) as npz:
        return {k: npz[k] for k in npz.files}


# --- the grid index --------------------------------------------------------------


class _IsochroneIndex:
    """Lazily-built index of every baked isochrone `.npz` under `ISO_DATA_DIR`, keyed by
    (feh, vvcrit).

    Deferred like `structure._ProfileIndex`: importing the module in a data-less checkout
    never explodes — it raises `IsochroneDataMissing` only when an isochrone is actually
    requested. `.npz` written by an older `BAKE_VERSION` are ignored (never fed stale)."""

    def __init__(self, data_dir: Path | None = None) -> None:
        self._data_dir = Path(data_dir) if data_dir is not None else ISO_DATA_DIR
        self._index: dict[tuple[float, float], Path] | None = None

    def _build(self) -> dict[tuple[float, float], Path]:
        if not self._data_dir.is_dir():
            raise IsochroneDataMissing(_MISSING_HINT.format(data_dir=self._data_dir))
        idx: dict[tuple[float, float], Path] = {}
        for path in sorted(self._data_dir.glob("*.npz")):
            try:
                with np.load(path) as npz:
                    if int(npz["bake_version"]) != BAKE_VERSION:
                        continue
                    feh = float(npz["feh"])
                    vvcrit = float(npz["vvcrit"])
            except (KeyError, OSError, ValueError):
                continue
            idx[(round(feh, 3), round(vvcrit, 2))] = path
        if not idx:
            raise IsochroneDataMissing(_MISSING_HINT.format(data_dir=self._data_dir))
        return idx

    def index(self) -> dict[tuple[float, float], Path]:
        if self._index is None:
            self._index = self._build()
        return self._index


_INDEX = _IsochroneIndex()


def _snap_vvcrit(index: dict[tuple[float, float], Path], vvcrit: float) -> float:
    rots = sorted({rot for (_feh, rot) in index})
    return min(rots, key=lambda r: abs(r - vvcrit))


def _snap_feh(index: dict[tuple[float, float], Path], feh: float, vv: float) -> float:
    fehs = [f for (f, rot) in index if rot == vv]
    return min(fehs, key=lambda f: abs(f - feh))


# --- StellarState construction from a baked age block -----------------------------


def _states_from_block(cube: dict, lo: int, hi: int, feh: float) -> list[StellarState]:
    """Turn one age-block's baked rows [lo:hi) into a locus of §3-clean StellarStates.

    Per-element `metals_*` dicts are left empty (state.py explicitly supports a provider
    with no per-element data): the isochrone's only consumer is the HR overlay, which
    reads Teff/L/mass/phase — not the 16-metal breakdown. Bulk X/Y/Z come from the
    surface/center H+He columns the bake kept."""
    eep = cube["eep"][lo:hi]
    mass = cube["mass"][lo:hi]
    logT = cube["logT"][lo:hi]
    logL = cube["logL"][lo:hi]
    logg = cube["logg"][lo:hi]
    logR = cube["logR"][lo:hi]
    phase = cube["phase"][lo:hi]
    logage = cube["logage"][lo:hi]
    h1 = cube["h1"][lo:hi]
    he4 = cube["he4"][lo:hi]
    ch1 = cube["ch1"][lo:hi]
    che4 = cube["che4"][lo:hi]

    states: list[StellarState] = []
    for i in range(hi - lo):
        teff = 10.0 ** float(logT[i])
        L = 10.0 ** float(logL[i])
        r = 10.0 ** float(logR[i])
        x_s = float(h1[i]); y_s = float(he4[i])
        z_s = max(0.0, 1.0 - x_s - y_s)
        x_c = float(ch1[i]); y_c = float(che4[i])
        z_c = max(0.0, 1.0 - x_c - y_c)
        phase_code = int(round(float(phase[i])))
        activity = max(0.0, min(1.0, (6500.0 - teff) / (6500.0 - 3000.0)))
        states.append(
            StellarState(
                age_yr=10.0 ** float(logage[i]),
                eep=float(eep[i]),
                phase=_PHASE_NAMES.get(phase_code, f"phase{phase_code}"),
                mass_init_msun=float(mass[i]),
                feh_init=feh,
                L_lsun=L, Teff_K=teff, R_rsun=r, logg=float(logg[i]),
                X_surf=x_s, Y_surf=y_s, Z_surf=z_s,
                X_core=x_c, Y_core=y_c, Z_core=z_c,
                metals_surf={}, metals_core={},
                v_rot_kms=None, activity=activity, mdot_msun_yr=None,
            )
        )
    return states


def _turnoff(states: list[StellarState]) -> dict | None:
    """The main-sequence turnoff: the **bluest (hottest) row still on the MS** — NOT the
    global hottest point. Old / metal-poor isochrones carry hot post-MS stars (blue HB,
    hot subdwarfs, WDs) far bluer than the MSTO (measured: global max Teff ~10⁵ K vs an
    MSTO ~6000 K at 10 Gyr) that a naive max(Teff) would hijack onto. The turnoff
    luminosity/temperature *is* the cluster's age clock."""
    ms = [(i, s) for i, s in enumerate(states) if s.phase == "MS"]
    if not ms:
        return None
    i, s = max(ms, key=lambda t: t[1].Teff_K)
    return {"index": i, "Teff_K": s.Teff_K, "L_lsun": s.L_lsun, "mass_msun": s.mass_init_msun}


# --- the public entry point -------------------------------------------------------


def isochrone(age_yr: float, feh: float, vvcrit: float = 0.0) -> dict:
    """(age, [Fe/H], vvcrit) → the coeval-cluster locus at the nearest published MIST
    isochrone node.

    Snap-always: [Fe/H] to the nearest baked node, age to the nearest tabulated isochrone
    **in log10**, vvcrit to the nearest baked rotation grid. Returns:

      states            : list[StellarState] (asdict) — the HR locus, MS → giants → WDs
      turnoff           : {index, Teff_K, L_lsun, mass_msun} — the MSTO (age clock)
      age_yr / log_age  : the *snapped* age (true node), and its log10
      feh / vvcrit      : the *snapped* metallicity / rotation
      *_snapped_far     : honesty flags when the request landed far from a node
      available_feh     : the grid's [Fe/H] nodes at this vvcrit (for a picker)
      available_log_ages: the file's tabulated log10 ages (for a slider)
    """
    if age_yr <= 0:
        raise ValueError("age_yr must be > 0")

    index = _INDEX.index()
    vv = _snap_vvcrit(index, vvcrit)
    feh_snap = _snap_feh(index, feh, vv)
    path = index[(round(feh_snap, 3), vv)]

    cube = _load_iso(str(path), path.stat().st_mtime)
    log_ages = cube["log_ages"]
    offsets = cube["offsets"]

    req_log = math.log10(age_yr)
    ai = int(np.argmin(np.abs(log_ages - req_log)))
    log_age_snap = float(log_ages[ai])
    lo, hi = int(offsets[ai]), int(offsets[ai + 1])

    states = _states_from_block(cube, lo, hi, feh_snap)
    turnoff = _turnoff(states)

    return {
        "states": [asdict(s) for s in states],
        "turnoff": turnoff,
        "age_yr": 10.0 ** log_age_snap,
        "log_age": log_age_snap,
        "feh": feh_snap,
        "vvcrit": vv,
        "feh_snapped_far": abs(feh_snap - feh) > _FEH_SNAP_FAR,
        "age_snapped_far": abs(log_age_snap - req_log) > _LOGAGE_SNAP_FAR,
        "vvcrit_snapped_far": abs(vv - vvcrit) > 1e-3,
        "available_feh": sorted(f for (f, rot) in index if rot == vv),
        "available_log_ages": [float(x) for x in log_ages],
    }


def isochrone_available() -> bool:
    """Cheap honesty gate for `/isochrone_status` — is any baked `.npz` grid present?
    Never raises (a data-less checkout returns False so the frontend hides the toggle)."""
    try:
        _INDEX.index()
        return True
    except IsochroneDataMissing:
        return False
