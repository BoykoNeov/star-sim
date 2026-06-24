"""Synthetic-spectrum lookup for the Phase 5 spectrum panel (STAR_SIM_SPEC §5).

Like `lane_emden.py`, this is a **sibling to the StellarState spine (§3), not a
provider and not a `StellarState`**. A spectrum is a *derived view* of the state's
`(Teff, log g, [Fe/H])` — the very thing `color.js` already collapses into the
star's one-pixel colour — so `/spectrum` is, like `/polytrope`, the other route
that does **not** go through `PROVIDER`.

It is also pure numpy/scipy with **no pymsg / Fortran / Docker** dependency: the
spectra were baked once in the MSG build container (`scripts/bake_spectra.py`,
see `backend/docs/msg_spectra_build_recipe.md`) into a dense, void-filled flux
cube `data/spectra/spectra_grid.npz`. Here we just interpolate that cube with
`scipy.RegularGridInterpolator` — Windows-clean, no build tools at run time.

The `.npz` is **axis-generic**: it stores `axis_keys` (e.g. `['teff','logg']` for
the solar `sg-demo` grid, or `['teff','logg','feh']` for a 3-D grid like CAP18)
and an `axis_log` flag per axis. We build the interpolator over whatever axes are
present, so a future 3-D re-bake needs zero code change here. When the grid has no
`feh` axis the spectrum is solar-metallicity and the `feh` argument is ignored
(reported as `feh_varies: false` so the panel can label that honestly).
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
from scipy.interpolate import RegularGridInterpolator

# Must match scripts/bake_spectra.py's BAKE_VERSION; a stale cube is rejected.
BAKE_VERSION = 1

# data/spectra/ sits at the repo root: star_sim/spectra.py -> parents
#   [0]=star_sim [1]=backend [2]=repo root
_REPO_ROOT = Path(__file__).resolve().parents[2]
SPECTRA_DATA_DIR = Path(
    os.environ.get("STAR_SIM_SPECTRA_DIR", _REPO_ROOT / "data" / "spectra")
)
GRID_FILENAME = "spectra_grid.npz"

_BAKE_HINT = (
    "Spectrum grid not baked. Build it once in the MSG container and copy it to "
    "{path}:\n"
    "    (in msg_spike) python scripts/bake_spectra.py --out /tmp/spectra_grid.npz\n"
    "    docker cp msg_spike:/tmp/spectra_grid.npz data/spectra/spectra_grid.npz\n"
    "(see backend/docs/msg_spectra_build_recipe.md)."
)


class SpectraDataMissing(RuntimeError):
    """The baked spectrum grid isn't present (analogue of ProviderDataMissing).

    The API maps this to a 503 with an actionable hint, exactly like a missing
    MIST grid — the app stays up; only /spectrum is unavailable until the bake.
    """


class _Spectra:
    """Lazily-loaded baked grid + interpolator. One instance, built on first use
    (so importing the module — and the whole package — never touches disk)."""

    def __init__(self, path: Path):
        self.path = path
        npz = np.load(path, allow_pickle=False)

        ver = int(npz["bake_version"])
        if ver != BAKE_VERSION:
            raise SpectraDataMissing(
                f"baked grid {path} is BAKE_VERSION {ver}, runtime wants "
                f"{BAKE_VERSION}; re-bake with scripts/bake_spectra.py"
            )

        self.grid_name = str(npz["grid_name"])
        self.flux_unit = str(npz["flux_unit"])
        self.axis_keys: list[str] = [str(k) for k in npz["axis_keys"]]
        self.axis_log = np.asarray(npz["axis_log"], dtype=bool)
        self.lam = np.asarray(npz["lam"], dtype=float)
        flux = np.asarray(npz["flux"], dtype=float)

        # Per-axis node arrays (linear, human-readable) + the bounds we clamp to.
        self.axes = [np.asarray(npz[f"axis_{k}"], dtype=float) for k in self.axis_keys]
        self.bounds = [(float(a[0]), float(a[-1])) for a in self.axes]

        # Build the interpolator in the *transformed* space (log10 for flagged
        # axes — Teff — so cool-end resolution interpolates in log). The flux cube
        # is vector-valued over its trailing wavelength axis, so RGI returns the
        # full spectrum per query point.
        grid_axes = [
            np.log10(a) if is_log else a
            for a, is_log in zip(self.axes, self.axis_log)
        ]
        self._rgi = RegularGridInterpolator(
            tuple(grid_axes), flux, bounds_error=False, fill_value=None
        )
        self.feh_varies = "feh" in self.axis_keys

    def evaluate(self, params: dict[str, float]) -> tuple[np.ndarray, dict[str, float]]:
        """Interpolate the spectrum at the given parameters, clamping each to the
        grid bounds first. Returns (flux array, the clamped values actually used)."""
        query = []
        used: dict[str, float] = {}
        for key, (lo, hi), is_log in zip(self.axis_keys, self.bounds, self.axis_log):
            v = float(params.get(key, 0.0))
            v = min(max(v, lo), hi)          # clamp to the real grid coverage
            used[key] = v
            query.append(np.log10(v) if is_log else v)
        flux = self._rgi(np.array([query]))[0]
        flux = np.clip(flux, 0.0, None)      # guard against tiny interp undershoot
        return flux, used


_CACHE: _Spectra | None = None


def _load() -> _Spectra:
    global _CACHE
    if _CACHE is None:
        path = SPECTRA_DATA_DIR / GRID_FILENAME
        if not path.is_file():
            raise SpectraDataMissing(_BAKE_HINT.format(path=path))
        _CACHE = _Spectra(path)
    return _CACHE


def spectrum_data(
    teff: float,
    logg: float,
    feh: float = 0.0,
    *,
    n_display: int | None = None,
) -> dict:
    """The JSON-friendly spectrum the `/spectrum` endpoint serves and the panel
    plots. Pure numbers, no StellarState — a sibling to the §3 spine.

    Parameters are clamped to the baked grid's coverage (a star below the grid floor
    — now 2300 K via the Göttingen/PHOENIX cool splice, below any reachable star —
    shows the floor spectrum; `feh` is ignored for a solar grid). Raises
    `SpectraDataMissing` if the grid hasn't been baked.

    Returns
    -------
    dict with:
      wavelength : λ bin centres (Å)
      flux       : flux per bin (erg/cm²/s/Å), same length as wavelength
      teff,logg,feh : the (clamped) values the spectrum actually represents
      teff_requested : the *raw* requested Teff (pre-clamp) — so a consumer can
                       tell a real in-grid spectrum from a clamped-boundary one
      teff_min,teff_max : the grid's Teff coverage. A star hotter than teff_max
                       has NO model atmosphere (the returned spectrum is the
                       clamped ceiling); the panel uses this to show a "no model
                       for this range" notice instead of a misleading boundary
                       spectrum, keyed off the grid's real ceiling (not a literal).
      feh_varies : bool — false for a solar-only grid (panel labels it honestly)
      flux_unit, grid_name : provenance
    """
    s = _load()
    flux, used = s.evaluate({"teff": teff, "logg": logg, "feh": feh})
    lam = s.lam

    # Expose the Teff coverage so the panel can distinguish "this is a real
    # interpolated spectrum" from "the star is off the hot end of every grid we
    # have, here's the clamped ceiling". The cool end is covered down to the grid
    # floor (2300 K with the cool splice, below any reachable star), so only the hot
    # end is a true model gap; a cool clamp, if ever hit, is an honest extrapolation.
    ti = s.axis_keys.index("teff")
    teff_min, teff_max = s.bounds[ti]

    # Optional uniform downsample for the panel (default: full baked resolution).
    if n_display is not None and n_display < lam.size:
        new_lam = np.linspace(lam[0], lam[-1], n_display)
        flux = np.interp(new_lam, lam, flux)
        lam = new_lam

    return {
        "wavelength": lam.tolist(),
        "flux": flux.tolist(),
        "teff": used["teff"],
        "logg": used["logg"],
        "feh": used.get("feh", float(feh)),
        "teff_requested": float(teff),
        "teff_min": teff_min,
        "teff_max": teff_max,
        "feh_varies": s.feh_varies,
        "flux_unit": s.flux_unit,
        "grid_name": s.grid_name,
    }
