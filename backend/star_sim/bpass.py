"""bpass.py — the coeval-population SED overlay sibling (the first ENSEMBLE sibling).

Chunk 1 of docs/plans/coeval-ensemble-overlay.md. Every sibling so far renders ONE thing
(a track, one representative state, or one two-body system through time). This one renders
a *coeval stellar population*: a million stars born together at the marker's metallicity,
seen at the marker's age, as an INTEGRATED spectrum — split single-star vs binary. The
headline (Gate 0, measured): binaries keep the population UV/ionizing-bright far longer
than single-star evolution can.

Like `spectra.py` / `structure.py` this is a **sibling to the StellarState spine (§3),
NOT a provider and NOT a StellarState** — a population is not a star. It imports only
numpy/stdlib (not even `StellarState`: it returns plain arrays/dicts) and **never touches
`PROVIDER`**; `/population` is, like `/spectrum` and `/polytrope`, a route that does not go
through the provider.

It is pure-numpy over a build-time bake (`scripts/bake_bpass_spectra.py` → a compact
`data/bpass/bpass_ssp.npz`), the `spectra.py` precedent: no h5py / HDF5 at run time.

Two measured facts the runtime is built on (recon 2026-07-10):
  * the cube is **f_nu [L_sun/Hz] per 1e6 M_sun** — we convert to **f_lambda** (× c/λ²) at
    serve time so the served flux is the SAME quantity the SED panel plots (F_λ), and the
    sin/bin *ratio* (the Gate-0 payoff) is preserved (both get the identical factor);
  * the metallicity axis is **already [Fe/H] = log10(Z/0.020)** (Zsun=0.020, a ~0.15 dex
    offset vs MIST's ~0.0142) — we snap the marker's [Fe/H] **directly** and let the caption
    own the Zsun systematic (the project's "labeled, not silently converted" stance).

Snapping is honest (§6): nearest [Fe/H] linearly, nearest age **in log10(age)** (the Gyr
grid is geometric over 5 decades), never interpolated; the true snapped node + snapped-far
flags are reported.
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np

# Must match scripts/bake_bpass_spectra.py's BAKE_VERSION; a stale cube is rejected.
BAKE_VERSION_BPASS = 1
# Chunk 2's HR-diagram number-density cube (scripts/bake_bpass_hrd.py). Independent version.
BAKE_VERSION_HRD = 1

# data/bpass/ sits at the repo root: star_sim/bpass.py -> parents
#   [0]=star_sim [1]=backend [2]=repo root  (same anchor as spectra.py/helium.py)
_REPO_ROOT = Path(__file__).resolve().parents[2]
BPASS_DATA_DIR = Path(os.environ.get("STAR_SIM_BPASS_DIR", _REPO_ROOT / "data" / "bpass"))
GRID_FILENAME = "bpass_ssp.npz"
GRID_FILENAME_HRD = "bpass_hrd.npz"   # Chunk 2 — the HR-diagram number-density cube

# c in Angstrom/s — for the f_nu -> f_lambda conversion  f_lambda = f_nu * c / lambda^2.
_C_ANG_S = 2.99792458e18


class BpassDataMissing(RuntimeError):
    """The baked BPASS cube isn't present (analogue of SpectraDataMissing / a missing
    MIST grid). The API maps this to a 503 with an actionable hint; the app stays up and
    only /population is unavailable until the bake lands."""


_MISSING_HINT = (
    "BPASS population cube not baked. Fastest path — fetch the pre-baked cube (4.1 MB):\n"
    "    python -m star_sim.fetch_bpass_baked          (-> data/bpass/bpass_ssp.npz)\n"
    "Or build it from source (the ~1 GB Zenodo pair + bake):\n"
    "    python -m star_sim.fetch_bpass --download     (opt-in ~1 GB, Zenodo)\n"
    "    python scripts/bake_bpass_spectra.py          (-> data/bpass/bpass_ssp.npz)\n"
    "(see backend/star_sim/fetch_bpass_baked.py / fetch_bpass.py)."
)


class _Bpass:
    """Lazily-loaded baked cube (one instance, built on first use — importing the module
    never touches disk, the `spectra.py` `_Spectra` precedent)."""

    def __init__(self, path: Path):
        self.path = path
        npz = np.load(path, allow_pickle=False)
        ver = int(npz["bake_version"])
        if ver != BAKE_VERSION_BPASS:
            raise BpassDataMissing(
                f"baked BPASS cube {path} is bake_version {ver}, runtime wants "
                f"{BAKE_VERSION_BPASS}; re-bake with scripts/bake_bpass_spectra.py"
            )
        self.feh = np.asarray(npz["feh"], dtype=float)                # (13,) already [Fe/H]
        self.age_gyr = np.asarray(npz["age_gyr"], dtype=float)        # (51,) linear Gyr
        self.lam_ang = np.asarray(npz["lam_ang"], dtype=float)        # (Nlam,) bin centres
        self.spectra_sin = np.asarray(npz["spectra_sin"], dtype=float)  # (Z, age, Nlam) f_nu
        self.spectra_bin = np.asarray(npz["spectra_bin"], dtype=float)
        self.flux_unit = str(npz["flux_unit"])
        self.grid_name = str(npz["grid_name"])
        self.zsun_bpass = float(npz["zsun_bpass"])
        self.log_age = np.log10(self.age_gyr)

    def snap(self, feh: float, age_gyr: float) -> tuple[int, int]:
        """Nearest ([Fe/H] linearly, age in log10) grid indices — never interpolate (§6)."""
        zi = int(np.argmin(np.abs(self.feh - feh)))
        ai = int(np.argmin(np.abs(self.log_age - np.log10(max(age_gyr, 1e-12)))))
        return zi, ai


_cube: _Bpass | None = None


def _load() -> _Bpass:
    global _cube
    if _cube is None:
        path = BPASS_DATA_DIR / GRID_FILENAME
        if not path.is_file():
            raise BpassDataMissing(_MISSING_HINT)
        _cube = _Bpass(path)
    return _cube


def bpass_available() -> bool:
    """True if the baked BPASS cube is on disk — the data-derived honesty gate the frontend
    reads (via /population_status) to decide whether to even SHOW the overlay toggle. The
    cube is gitignored/host-baked (like the MESA runs), so a fresh clone has none and a
    control that can only 503 shouldn't appear. Cheap (a stat), never loads the cube."""
    return (BPASS_DATA_DIR / GRID_FILENAME).is_file()


def _fnu_to_flambda(fnu: np.ndarray, lam_ang: np.ndarray) -> np.ndarray:
    """f_lambda = f_nu * c / lambda^2 (per-Angstrom). Both populations get the identical
    factor, so the sin/bin ratio — the Gate-0 payoff — is preserved; the conversion only
    reshapes the spectrum onto the panel's F_λ axis (matching the blackbody curve)."""
    return fnu * _C_ANG_S / (lam_ang * lam_ang)


def population_sed(feh: float, age_gyr: float, population: str = "both") -> dict:
    """(feh, age_gyr) -> the integrated single & binary coeval-population spectra at the
    nearest ([Fe/H], age) BPASS node, as f_lambda vs lambda. Pure numbers, no StellarState.

    `population` ("both"|"sin"|"bin") selects which curves to include (default "both", the
    Gate-0 draw-both presentation — the caller can request one, but both are cheap so the
    default serves the pair in a single call, no refetch on a frontend toggle).

    Snaps (never interpolates, §6): nearest [Fe/H] linearly, nearest age in log10. Reports
    the TRUE snapped node + snapped-far flags. Raises BpassDataMissing if unbaked.

    Returns a dict with wavelength (Angstrom), flambda_sin / flambda_bin (arb. F_λ units,
    per 1e6 Msun — the panel co-scales them to a shared reference), the snapped node, the
    [Fe/H]/age grids for context, and provenance (incl. the BPASS Zsun for the caption)."""
    c = _load()
    zi, ai = c.snap(feh, age_gyr)
    lam = c.lam_ang
    out: dict = {
        "feh_requested": float(feh),
        "age_gyr_requested": float(age_gyr),
        "feh_snapped": float(c.feh[zi]),
        "age_gyr_snapped": float(c.age_gyr[ai]),
        # snapped-far honesty: >0.4 dex off in [Fe/H], or the age off by >0.5 of a log-decade
        # (half the ~0.1-dex grid spacing would be "on-grid"; 0.5 dex means well between nodes).
        "feh_snapped_far": bool(abs(c.feh[zi] - feh) > 0.4),
        "age_snapped_far": bool(abs(c.log_age[ai] - np.log10(max(age_gyr, 1e-12))) > 0.5),
        "wavelength": lam.tolist(),
        "flux_unit": "erg/s/cm2/A-equivalent F_lambda per 1e6 Msun (from BPASS f_nu)",
        "grid_name": c.grid_name,
        "zsun_bpass": c.zsun_bpass,
        "feh_grid": c.feh.tolist(),
        "age_gyr_grid": c.age_gyr.tolist(),
    }
    if population in ("both", "sin"):
        out["flambda_sin"] = _fnu_to_flambda(c.spectra_sin[zi, ai], lam).tolist()
    if population in ("both", "bin"):
        out["flambda_bin"] = _fnu_to_flambda(c.spectra_bin[zi, ai], lam).tolist()
    return out


# ---------------------------------------------------------------------------------------
# Chunk 2 — the HR-diagram NUMBER-DENSITY cube (bake_bpass_hrd.py). Same sibling, a second
# BPASS product on a DIFFERENT panel: where population_sed puts the integrated spectrum on
# the SED panel, this puts the population's star count per (logTeff, logL) cell on the HR
# panel, split single vs +binaries. Gate 0 (measured): the binary population lights up hot /
# stripped-He HRD cells the single-star population leaves EMPTY (blue stragglers at 10–50 Myr
# where single pops have no hot stars at all; ~33x more stripped-He stars overall).
#
# Source note: the HRD "hrs" numbers are the BPASS v2.2.1 fiducial release, NOT the v2.3 SSP
# spectra the /population route uses (that Zenodo record is spectra-only) — a caption-owned
# version systematic (different panel, no byte-consistency requirement).


class _BpassHRD:
    """Lazily-loaded HR-diagram number-density cube (mirror of _Bpass)."""

    def __init__(self, path: Path):
        self.path = path
        npz = np.load(path, allow_pickle=False)
        ver = int(npz["bake_version"])
        if ver != BAKE_VERSION_HRD:
            raise BpassDataMissing(
                f"baked BPASS HRD cube {path} is bake_version {ver}, runtime wants "
                f"{BAKE_VERSION_HRD}; re-bake with scripts/bake_bpass_hrd.py"
            )
        self.feh = np.asarray(npz["feh"], dtype=float)              # (13,) [Fe/H]
        self.age_gyr = np.asarray(npz["age_gyr"], dtype=float)      # (51,) linear Gyr
        self.logt = np.asarray(npz["logt"], dtype=float)            # (nT,) logTeff bin centres
        self.logl = np.asarray(npz["logl"], dtype=float)            # (nL,) logL bin centres
        self.dens_sin = np.asarray(npz["dens_sin"], dtype=float)    # (Z, age, nT, nL) counts
        self.dens_bin = np.asarray(npz["dens_bin"], dtype=float)
        self.stripped_sin = np.asarray(npz["stripped_sin"], dtype=float)  # (Z, age)
        self.stripped_bin = np.asarray(npz["stripped_bin"], dtype=float)
        self.grid_name = str(npz["grid_name"])
        self.zsun_bpass = float(npz["zsun_bpass"])
        self.log_age = np.log10(self.age_gyr)

    def snap(self, feh: float, age_gyr: float) -> tuple[int, int]:
        """Nearest ([Fe/H] linearly, age in log10) — the same idiom as _Bpass.snap."""
        zi = int(np.argmin(np.abs(self.feh - feh)))
        ai = int(np.argmin(np.abs(self.log_age - np.log10(max(age_gyr, 1e-12)))))
        return zi, ai


_hrd_cube: _BpassHRD | None = None


def _load_hrd() -> _BpassHRD:
    global _hrd_cube
    if _hrd_cube is None:
        path = BPASS_DATA_DIR / GRID_FILENAME_HRD
        if not path.is_file():
            raise BpassDataMissing(_MISSING_HINT)
        _hrd_cube = _BpassHRD(path)
    return _hrd_cube


def hrd_available() -> bool:
    """True if the baked HRD number-density cube is on disk — the honesty gate the frontend
    reads (via /population_status) so the HR-panel overlay is only offered when its data is
    present. Cheap (a stat), never loads the cube."""
    return (BPASS_DATA_DIR / GRID_FILENAME_HRD).is_file()


def population_hrd(feh: float, age_gyr: float, population: str = "both") -> dict:
    """(feh, age_gyr) -> the coeval population's star count per (logTeff, logL) HR-diagram
    cell at the nearest ([Fe/H], age) BPASS node, single-star and +binaries. Pure numbers,
    no StellarState. Snaps (never interpolates, §6): nearest [Fe/H] linearly, nearest age in
    log10; reports the TRUE snapped node + snapped-far flags. Raises BpassDataMissing if
    unbaked.

    `population` ("both"|"sin"|"bin") selects which grids to include (default "both" — the
    frontend needs both to highlight where binaries populate cells single stars leave empty).

    Returns logt/logl axes (bin centres), the density grid(s) (nT x nL, stars per 1e6 Msun),
    the snapped node, the stripped-star (low surface-H) totals for both populations (the ~33x
    caption stat), and provenance."""
    c = _load_hrd()
    zi, ai = c.snap(feh, age_gyr)
    out: dict = {
        "feh_requested": float(feh),
        "age_gyr_requested": float(age_gyr),
        "feh_snapped": float(c.feh[zi]),
        "age_gyr_snapped": float(c.age_gyr[ai]),
        "feh_snapped_far": bool(abs(c.feh[zi] - feh) > 0.4),
        "age_snapped_far": bool(abs(c.log_age[ai] - np.log10(max(age_gyr, 1e-12))) > 0.5),
        "logt": c.logt.tolist(),
        "logl": c.logl.tolist(),
        "grid_name": c.grid_name,
        "zsun_bpass": c.zsun_bpass,
        "count_unit": "stars per 1e6 Msun per cell (all surface-H)",
        # the ~33x stripped-star caption stat (low surface-H total at this age)
        "stripped_sin": float(c.stripped_sin[zi, ai]),
        "stripped_bin": float(c.stripped_bin[zi, ai]),
    }
    if population in ("both", "sin"):
        out["dens_sin"] = c.dens_sin[zi, ai].tolist()
    if population in ("both", "bin"):
        out["dens_bin"] = c.dens_bin[zi, ai].tolist()
    return out
