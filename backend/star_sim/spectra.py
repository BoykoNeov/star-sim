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

# The WD cube's Koester(LTE)↔TMAP(NLTE) splice seam (endgame Chunk 6b). Koester DA
# supplies Teff ≤ this; the TMAP hot-WD/CSPN slab supplies the post-AGB central star
# above it. Used only to LABEL the regime ("hot central star / CSPN" vs "cooling DA")
# in the served spectrum — the cube itself is one continuous (Teff, log g) grid.
_CSPN_TEFF = 80000.0
# The MAIN spectrum cube's hottest model (OSTAR2002, the hottest grid in MSG). Above
# it ONLY the WD cube can serve a spectrum, so the panel routes a wd-mode row here
# past it — including the brief post-AGB rise (~55–80 kK at log g ≲ 6) on the way up
# to the central-star spike. Such a row is a *contracting central star*, not a cooling
# white dwarf, so it gets the CSPN label too (below the WD-gravity floor).
_MAIN_TEFF_CEIL = 55000.0
# The WD cube's log g floor — below it a hot star is a low-gravity central star, not a
# degenerate remnant. Separates the rise (low g → CSPN) from a cooling hot DA (high g).
_WD_LOGG_FLOOR = 6.5

# data/spectra/ sits at the repo root: star_sim/spectra.py -> parents
#   [0]=star_sim [1]=backend [2]=repo root
_REPO_ROOT = Path(__file__).resolve().parents[2]
SPECTRA_DATA_DIR = Path(
    os.environ.get("STAR_SIM_SPECTRA_DIR", _REPO_ROOT / "data" / "spectra")
)
GRID_FILENAME = "spectra_grid.npz"
# The white-dwarf cube (endgame Chunk 6): a SEPARATE Koester DA cube at log g
# 6.5–9.5 — disjoint from the main cube's 0–5, pure hydrogen (no [Fe/H] axis) — so
# it cannot splice onto the main grid. Same axis-generic .npz schema though, so the
# runtime reuses `_Spectra` verbatim (a 2-axis Teff×log g cube, like the original
# solar `sg-demo`). Baked on the host by scripts/bake_wd_spectra.py (no pymsg).
WD_GRID_FILENAME = "wd_spectra_grid.npz"

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
_WD_CACHE: _Spectra | None = None


def _load() -> _Spectra:
    global _CACHE
    if _CACHE is None:
        path = SPECTRA_DATA_DIR / GRID_FILENAME
        if not path.is_file():
            raise SpectraDataMissing(_BAKE_HINT.format(path=path))
        _CACHE = _Spectra(path)
    return _CACHE


def _load_wd() -> _Spectra:
    """The white-dwarf cube, loaded once (separate cache from the main cube)."""
    global _WD_CACHE
    if _WD_CACHE is None:
        path = SPECTRA_DATA_DIR / WD_GRID_FILENAME
        if not path.is_file():
            raise SpectraDataMissing(
                f"White-dwarf spectrum grid not baked. Fetch + bake it once:\n"
                f"    python -m star_sim.fetch_koester\n"
                f"    python scripts/bake_wd_spectra.py   # -> {path}\n"
                f"(see backend/docs/msg_spectra_build_recipe.md §7, endgame Chunk 6)."
            )
        _WD_CACHE = _Spectra(path)
    return _WD_CACHE


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


def _planck_lambda(lam_ang: np.ndarray, teff: float) -> np.ndarray:
    """Planck B_λ(λ, T) SHAPE (relative — the panel normalises to its own peak), λ
    in Å. B_λ ∝ λ⁻⁵ / (exp(c₂/λT) − 1), c₂ = hc/k = 1.438777e8 Å·K."""
    c2 = 1.438777e8
    x = c2 / (np.maximum(lam_ang, 1.0) * max(teff, 1.0))
    return lam_ang ** -5.0 / np.expm1(x)


def wd_spectrum_data(teff: float, logg: float, *, n_display: int | None = None) -> dict:
    """The white-dwarf spectrum the `/wd_spectrum` endpoint serves — a sibling of
    `spectrum_data`, reading the SEPARATE Koester DA cube (log g 6.5–9.5, pure H).

    Two honest edges, both grounded in the data (measured through this path):

    - **Cold cinder (Teff below the Koester floor, ~5000 K) → DC continuum.** A real
      cooling DA loses its Balmer lines and becomes a featureless DC white dwarf
      (Hα is only ~9% deep at the 5000 K floor, vs ~61% at 13 kK). Clamping the
      5000 K Koester spectrum onto a 2393 K cinder would paint H lines it no longer
      has *and* give the wrong (too-blue) continuum slope, so below the floor we
      return an honest Planck blackbody continuum at the requested Teff, tagged
      `regime="DC"`. This is the same "don't label a non-feature" discipline as the
      VO-7400 / invisible-Na decisions elsewhere.
    - **Hot central star (CSPN), Teff above the Koester ceiling (80000 K).** The
      ~100–190 kK post-AGB central star is past Koester, so the TMAP NLTE H slab
      (Chunk 6b) covers it — `regime="CSPN"`, a real spectrum. Only above TMAP's own
      190000 K ceiling (the most massive progenitors' central stars peak hotter) does
      `teff_requested > teff_max` trip the panel's `teffAboveGrid()` no-model frame —
      a genuine, much narrower residual gap. No special-casing needed here: the cube
      clamps in `evaluate()` and the panel keys off `teff_max` either way.

    Returns the same JSON shape as `spectrum_data` (so the panel can largely share a
    draw path) plus `regime` ∈ {"DA", "DC", "CSPN"}. `feh_varies` is always false (a
    DA / hot H-atmosphere is pure hydrogen — [Fe/H] is meaningless, not merely "solar").
    """
    s = _load_wd()
    ti = s.axis_keys.index("teff")
    gi = s.axis_keys.index("logg")
    teff_min, teff_max = s.bounds[ti]
    glo, ghi = s.bounds[gi]
    lam = s.lam

    if teff < teff_min:
        # DA → DC: honest blackbody continuum, not a clamped (line-bearing) spectrum.
        flux = _planck_lambda(lam, teff)
        peak = float(flux.max())
        if peak > 0:
            flux = flux / peak
        used_teff = float(teff)
        used_logg = float(min(max(logg, glo), ghi))
        regime = "DC"
    else:
        flux, used = s.evaluate({"teff": teff, "logg": logg})
        used_teff = used["teff"]
        used_logg = used["logg"]
        # CSPN = a hot post-AGB central star: unambiguously so above the Koester
        # ceiling (TMAP slab), OR on the contracting rise (hotter than the MAIN cube
        # can model AND still below WD gravity — measured logg ~5–6 on the way up).
        # A hot but already-degenerate remnant (high logg) stays a (hot) DA. We test
        # the RAW requested logg, not the cube-clamped one, to read the true gravity.
        regime = ("CSPN"
                  if used_teff > _CSPN_TEFF
                  or (used_teff > _MAIN_TEFF_CEIL and logg < _WD_LOGG_FLOOR)
                  else "DA")

    if n_display is not None and n_display < lam.size:
        new_lam = np.linspace(lam[0], lam[-1], n_display)
        flux = np.interp(new_lam, lam, flux)
        lam = new_lam

    return {
        "wavelength": lam.tolist(),
        "flux": flux.tolist(),
        "teff": used_teff,
        "logg": used_logg,
        "feh": 0.0,
        "teff_requested": float(teff),
        "teff_min": teff_min,
        "teff_max": teff_max,
        "feh_varies": False,
        "regime": regime,
        "flux_unit": s.flux_unit,
        "grid_name": s.grid_name,
    }
