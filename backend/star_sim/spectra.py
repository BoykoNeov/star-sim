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
# The Wolf-Rayet cube (endgame Chunk 7): PoWR wind-emission grids, keyed on the WR
# spectroscopic axes (T*, transformed-radius Rt) — NOT (Teff, log g) — so it has its
# OWN flat-node .npz schema (a ragged (T*, Rt) parallelogram per subtype × metallicity)
# and the runtime snaps to the nearest real node (`_WRSpectra`, not `_Spectra`). Baked
# on the host by scripts/bake_wr_spectra.py (no pymsg). See recipe §7/§7a.
WR_GRID_FILENAME = "wr_spectra_grid.npz"
# The binary-stripped-star cube (Chunk 3): CMFGEN continuum-normalized spectra for the
# hot He-stars `binary.py` snaps (Götberg 2018). Like the WR cube it has its OWN flat-node
# schema — the grid is 1-D in initial mass per Z (a ragged (Teff, log g) footprint), so it
# snaps to the node `/binary` already resolved (state<->spectrum consistency) rather than
# interpolating a rectangular cube (`_StrippedSpectra`, not `_Spectra`). Baked on the host
# by scripts/bake_stripped_spectra.py (no pymsg). See docs/plans/stripped-consort-unveiling.md.
STRIPPED_GRID_FILENAME = "stripped_spectra_grid.npz"
# The [alpha/Fe] cube (atlas Tier B): a SEPARATE 4-axis (Teff, log g, [Fe/H],
# [alpha/Fe]) Coelho-2014 cube, the COOL subset only (Teff <= ~10000 K — Gate 1
# measured alpha dead hotter, so the panel hands off to the main cube above). Same
# axis-generic .npz schema as the main cube, so the runtime reuses `_Spectra` verbatim
# (a 4-D grid). alpha is a SPECTRUM-ONLY axis (MIST evolution is solar-scaled, so the
# star's track/composition do NOT follow it — the panel labels it a "what-if"). Baked
# on the host by scripts/bake_alpha_spectra.py (no pymsg). See the atlas plan Tier B.
ALPHA_GRID_FILENAME = "alpha_spectra_grid.npz"

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
_ALPHA_CACHE: _Spectra | None = None


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


def _load_alpha() -> _Spectra:
    """The [alpha/Fe] cube, loaded once (separate cache from the main + WD cubes)."""
    global _ALPHA_CACHE
    if _ALPHA_CACHE is None:
        path = SPECTRA_DATA_DIR / ALPHA_GRID_FILENAME
        if not path.is_file():
            raise SpectraDataMissing(
                f"[alpha/Fe] spectrum grid not baked. Fetch + bake it once:\n"
                f"    python -m star_sim.fetch_coelho\n"
                f"    python scripts/bake_alpha_spectra.py   # -> {path}\n"
                f"(see docs/plans/whirling-cohort-atlas.md, atlas Tier B)."
            )
        _ALPHA_CACHE = _Spectra(path)
    return _ALPHA_CACHE


def alpha_spectrum_data(
    teff: float,
    logg: float,
    feh: float = 0.0,
    afe: float = 0.0,
    *,
    n_display: int | None = None,
) -> dict:
    """The [alpha/Fe] spectrum the `/alpha_spectrum` endpoint serves — a sibling of
    `spectrum_data`, reading the SEPARATE 4-axis Coelho cube (Teff, log g, [Fe/H],
    [alpha/Fe]). Same JSON shape as `spectrum_data` plus `afe` (the clamped [alpha/Fe]
    used) and `afe_varies` (always true for this cube — it exists to vary alpha).

    [alpha/Fe] is a **spectrum-only** axis: at fixed [Fe/H] a higher [alpha/Fe] deepens
    the O/Mg/Si/Ca/Ti (+ TiO) lines, but the star's *track* and *composition* are
    solar-scaled MIST and do NOT follow it — so the panel presents alpha as a
    hypothesis ("what a thick-disk/halo alpha-rich star at these parameters would
    show"), never a claim the plotted star's evolution changed.

    Both baselines (alpha=0 and alpha=0.4) come from THIS cube — a toggle flips between
    two Coelho spectra, never Coelho-alpha vs a CAP18-solar one (the atmosphere-code
    seam would masquerade as the alpha signal; advisor-settled, the load-bearing rule).

    The cube is the COOL subset (Teff <= its `teff_max`, ~10000 K); a hotter star clamps
    to `teff_max` here, but the panel routes it to the main `/spectrum` cube instead
    (alpha is dead there — Gate 1), so the clamp is not normally hit.
    """
    s = _load_alpha()
    flux, used = s.evaluate({"teff": teff, "logg": logg, "feh": feh, "afe": afe})
    lam = s.lam
    ti = s.axis_keys.index("teff")
    teff_min, teff_max = s.bounds[ti]

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
        "afe": used.get("afe", float(afe)),
        "teff_requested": float(teff),
        "teff_min": teff_min,
        "teff_max": teff_max,
        "feh_varies": s.feh_varies,
        "afe_varies": "afe" in s.axis_keys,
        "flux_unit": s.flux_unit,
        "grid_name": s.grid_name,
    }


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


# --- Wolf-Rayet (endgame Chunk 7) -------------------------------------------
#
# The WR spectrum is a wind-EMISSION spectrum from the PoWR grids, keyed on the WR
# spectroscopic axes (stellar temperature T*, transformed radius Rt), not (Teff,
# log g). The mapping from a track star onto the grid is unavoidably assumption-laden
# (PoWR's own framing) and was MEASURED before building (recipe §7a — the narrow-GO
# gate): PoWR honestly covers only the cool, hydrogen-rich WNh ENTRY; MIST's stripped
# core is the hot, compact EVOLUTIONARY surface (Teff ≈ T*, 150–260 kK), far hotter and
# more dense-wind than any observed WR, so the stripped bulk maps OFF-grid and the panel
# shows an honest "no model" frame there.

_TSUN_K = 5772.0          # solar Teff, for R* = sqrt(L/Lsun)·(Tsun/Teff)²
_WR_CLUMP_D = 4.0         # clumping density contrast — fixed in every PoWR grid
# Off-grid tolerances (in dex). A star hotter than the grid's hottest node by more than
# _WR_T_TOL, or whose nearest (log T*, log Rt) node is farther than _WR_SNAP_TOL, is
# "no model" — the stripped-bulk regime the gate found off every PoWR atmosphere.
_WR_T_TOL = 0.06
_WR_SNAP_TOL = 0.30


def _nugis_lamers_mdot(l_lsun: float, y_surf: float, z: float) -> float:
    """Wolf-Rayet mass-loss rate (M☉/yr), Nugis & Lamers (2000) — the standard WR
    Ṁ(L, Y, Z): log Ṁ = −11.00 + 1.29 logL + 1.73 logY + 0.47 logZ. Used to place the
    star on PoWR's wind (Rt) axis without needing the track's own Ṁ (kept off
    StellarState, §3/Option B) — MIST's WR mass loss is itself ~this family, so the
    composite Rt is the same to within the assumptions PoWR's Rt already carries."""
    logL = np.log10(max(l_lsun, 1.0))
    y = min(max(y_surf, 1e-3), 1.0)
    return 10.0 ** (-11.00 + 1.29 * logL + 1.73 * np.log10(y) + 0.47 * np.log10(max(z, 1e-3)))


def _wr_subtype(x_surf: float, y_surf: float, z_surf: float) -> str:
    """Pick the PoWR grid subtype from the surface composition (mirrors classify.js'
    WN/WC logic): carbon/oxygen surfaced → WC; else hydrogen still present → WNL
    (hydrogen-rich WN); else → WNE (hydrogen-free WN). WO has no PoWR grid → folds into
    WC (the hottest carbon grid)."""
    if (z_surf or 0.0) >= 0.4:
        return "WC"
    if (x_surf or 0.0) > 0.05:
        return "WNL"
    return "WNE"


class _WRSpectra:
    """Lazily-loaded PoWR WR grids: a flat set of (log T*, log Rt) nodes + emission
    spectra per (subtype, metallicity) grid. The runtime snaps to the nearest node
    (the endgame snap-to-track discipline) rather than interpolating a ragged,
    parallelogram-shaped grid."""

    def __init__(self, path: Path):
        self.path = path
        npz = np.load(path, allow_pickle=False)
        ver = int(npz["bake_version"])
        if ver != BAKE_VERSION:
            raise SpectraDataMissing(
                f"baked WR grid {path} is BAKE_VERSION {ver}, runtime wants "
                f"{BAKE_VERSION}; re-bake with scripts/bake_wr_spectra.py"
            )
        self.grid_name = str(npz["grid_name"])
        self.flux_unit = str(npz["flux_unit"])
        self.lam = np.asarray(npz["lam"], dtype=float)
        self.tags = [str(t) for t in npz["grid_tags"]]
        subt = [str(s) for s in npz["grid_subtype"]]
        metal = [str(m) for m in npz["grid_metal"]]
        z = np.asarray(npz["grid_z"], dtype=float)
        vinf = np.asarray(npz["grid_vinf"], dtype=float)
        self.grids: dict[str, dict] = {}
        for i, tag in enumerate(self.tags):
            logT = np.asarray(npz[f"nodes_logT_{tag}"], dtype=float)
            logRt = np.asarray(npz[f"nodes_logRt_{tag}"], dtype=float)
            self.grids[tag] = {
                "subtype": subt[i], "metal": metal[i],
                "z": float(z[i]), "vinf": float(vinf[i]),
                "logT": logT, "logRt": logRt,
                "flux": np.asarray(npz[f"flux_{tag}"], dtype=float),
                "logT_max": float(logT.max()),
            }

    def select_grid(self, subtype: str, feh: float) -> dict:
        """Choose the grid: the requested subtype, metallicity-snapped to the nearest
        available Z/Z☉ (a star's [Fe/H] → Z/Z☉ = 10**[Fe/H]). Falls back across subtype
        only if the requested one isn't on disk (so a Galactic-only cube still serves)."""
        z_target = 10.0 ** feh
        cands = [g for g in self.grids.values() if g["subtype"] == subtype]
        if not cands:                      # subtype not baked → any subtype, same Z snap
            cands = list(self.grids.values())
        return min(cands, key=lambda g: abs(g["z"] - z_target))


_WR_CACHE: _WRSpectra | None = None


def _load_wr() -> _WRSpectra:
    global _WR_CACHE
    if _WR_CACHE is None:
        path = SPECTRA_DATA_DIR / WR_GRID_FILENAME
        if not path.is_file():
            raise SpectraDataMissing(
                f"Wolf-Rayet spectrum grid not baked. Fetch + bake it once:\n"
                f"    python -m star_sim.fetch_powr\n"
                f"    python scripts/bake_wr_spectra.py   # -> {path}\n"
                f"(see backend/docs/msg_spectra_build_recipe.md §7, endgame Chunk 7)."
            )
        _WR_CACHE = _WRSpectra(path)
    return _WR_CACHE


def _wr_continuum(flux: np.ndarray, n_chunks: int = 24, pct: float = 25.0) -> np.ndarray:
    """A robust continuum for an EMISSION spectrum: a low percentile per wavelength
    chunk, interpolated back to full resolution. Normalizing by this puts the continuum
    near 1 and lets the emission lines stand UP above it — the advisor's gate against a
    single He II 4686 spike squashing the whole panel under per-max normalization."""
    n = flux.size
    edges = np.linspace(0, n, n_chunks + 1).astype(int)
    xs, ys = [], []
    for i in range(n_chunks):
        a, b = int(edges[i]), int(edges[i + 1])
        if b <= a:
            continue
        xs.append(0.5 * (a + b))
        ys.append(float(np.percentile(flux[a:b], pct)))
    cont = np.interp(np.arange(n), xs, ys)
    return np.maximum(cont, 1e-300)


def wr_spectrum_data(
    teff: float, lum: float, x_surf: float, y_surf: float, z_surf: float,
    feh: float = 0.0, *, n_display: int | None = None,
) -> dict:
    """The Wolf-Rayet wind-emission spectrum the `/wr_spectrum` endpoint serves — a
    third spectrum sibling beside `/spectrum` and `/wd_spectrum`, reading the PoWR cube.

    Maps the track star onto PoWR's (T*, Rt) axes (recipe §7a): **T\\* ≈ MIST Teff**
    (the hot evolutionary surface, the well-known evolutionary-vs-spectroscopic Teff
    split), **Rt** from the star's L + a Nugis-Lamers Ṁ with the grid's fixed v∞/D. The
    subtype (WNE/WNL/WC) comes from the surface composition; the metallicity grid from
    [Fe/H]. Then it **snaps to the nearest real grid node** and returns that emission
    spectrum — UNLESS the star is hotter / denser-wind than any PoWR model (the stripped
    bulk), in which case `regime="none"` and the panel shows an honest "no model" frame.

    Returns a dict (continuum-normalized `flux`, so emission lines stand above 1):
      wavelength, flux, continuum (≡ 1.0 reference), display_max (y-cap so one strong
      line doesn't squash the rest), regime ∈ {"WR","none"}, subtype, metal, z_grid,
      teff (the snapped node T*), teff_requested, teff_max (the grid's hottest node, for
      the no-model frame), rt (snapped node Rt), off_grid, off_reason, grid_name.
    """
    s = _load_wr()
    lam = s.lam
    subtype = _wr_subtype(x_surf, y_surf, z_surf)
    g = s.select_grid(subtype, feh)

    # Place on the wind axis: R* from (L, Teff), Ṁ from Nugis-Lamers, Rt with this
    # grid's fixed v∞ and D=4 (so it's consistent with how the grid was computed).
    z_metal = max(z_surf or 0.014, 1e-3)
    mdot = _nugis_lamers_mdot(lum, y_surf or 0.9, z_metal)
    rstar = float(np.sqrt(max(lum, 1.0)) * (_TSUN_K / max(teff, 1.0)) ** 2)
    rt = rstar * ((g["vinf"] / 2500.0) / ((mdot * np.sqrt(_WR_CLUMP_D)) / 1e-4)) ** (2.0 / 3.0)
    log_t = float(np.log10(max(teff, 1.0)))
    log_rt = float(np.log10(max(rt, 1e-6)))

    # Snap to the nearest node in (log T*, log Rt).
    d = np.hypot(g["logT"] - log_t, g["logRt"] - log_rt)
    j = int(np.argmin(d))
    dist = float(d[j])
    node_logT, node_logRt = float(g["logT"][j]), float(g["logRt"][j])
    teff_max = 10.0 ** g["logT_max"]

    # Off-grid (the stripped bulk): hotter than any node, or the nearest node too far.
    off_grid = False
    off_reason = ""
    if log_t > g["logT_max"] + _WR_T_TOL:
        off_grid, off_reason = True, "hotter than any WR atmosphere model"
    elif dist > _WR_SNAP_TOL:
        off_grid, off_reason = True, "denser/hotter wind than any WR model"
    regime = "none" if off_grid else "WR"

    flux = g["flux"][j].astype(float)
    cont = _wr_continuum(flux)
    flux = flux / cont                       # continuum ≈ 1, emission lines stand up
    # y-cap that frames THIS spectrum's lines: a touch above its tallest emission peak
    # (broad WR lines, so the max is representative — not a single-bin spike), floored at
    # 2.5 so a weak-lined entry still reads as emission and capped at 12 so a monster He II
    # line can't squash the continuum + weaker lines (the advisor's per-max gate).
    display_max = float(min(max(flux.max() * 1.05, 2.5), 12.0))

    if n_display is not None and n_display < lam.size:
        new_lam = np.linspace(lam[0], lam[-1], n_display)
        flux = np.interp(new_lam, lam, flux)
        lam = new_lam

    return {
        "wavelength": lam.tolist(),
        "flux": flux.tolist(),
        "continuum": 1.0,
        "display_max": display_max,
        "regime": regime,
        "subtype": subtype,
        "metal": g["metal"],
        "z_grid": g["z"],
        "teff": 10.0 ** node_logT,
        "teff_requested": float(teff),
        "teff_max": float(teff_max),
        "rt": 10.0 ** node_logRt,
        "rt_requested": float(rt),
        "mdot": float(mdot),
        "off_grid": off_grid,
        "off_reason": off_reason,
        "feh_varies": False,
        "flux_unit": s.flux_unit,
        "grid_name": s.grid_name,
    }


# --- Binary-stripped stars (Chunk 3) ----------------------------------------
#
# The stripped-star spectrum is a CMFGEN continuum-normalized spectrum (Fnorm ≈ 1,
# absorption dips below, emission peaks above) for the hot He-star `binary.py` snaps.
# Like the WR cube it is keyed on a FLAT list of grid nodes — here (Z, M_init), the SAME
# snap identity `binary.py` uses — and the runtime snaps to the node `/binary` already
# resolved, so the panel's spectrum is guaranteed to be the SAME star as the marker.
#
# The measured payoff (Götberg 2018's thesis, confirmed on disk): the sequence bridges
# pure ABSORPTION at the low-mass subdwarf end (Fnorm 0.4–1.0, He II 4686 flat) → a hybrid
# mid-mass regime with mixed absorption+emission → strong EMISSION at the high-mass He-star
# end (He II 4686 up to ~7× continuum). Unlike the WR cube we need NO continuum estimation:
# the file is already continuum-normalized, so we serve Fnorm as-is.

_GOTBERG_SOLAR_Z = 0.014   # mirrors binary.GOTBERG_SOLAR_Z (kept local — sibling discipline)

# Optical-peak Fnorm thresholds that name the regime (measured across the solar grid:
# 2–5 M☉ peak ≈ 1.00–1.01; 6.0/6.7 M☉ 1.11/1.20; 7.4 M☉ 1.52; 8–18 M☉ 2.0–7.2). The
# label steers the caption + the emission/absorption framing, never the data.
_STRIP_EMISSION_PEAK = 1.30
_STRIP_ABSORPTION_PEAK = 1.05


class _StrippedSpectra:
    """Lazily-loaded Götberg stripped-star grid: a flat list of (Z, M_init) nodes + their
    continuum-normalized spectra. The runtime snaps to the nearest node in (Z, then M_init)
    — the same snap `binary.py` does — rather than interpolating (the grid is 1-D in mass
    per Z, a ragged (Teff, log g) footprint; §6 snap-not-interpolate)."""

    def __init__(self, path: Path):
        self.path = path
        npz = np.load(path, allow_pickle=False)
        ver = int(npz["bake_version"])
        if ver != BAKE_VERSION:
            raise SpectraDataMissing(
                f"baked stripped grid {path} is BAKE_VERSION {ver}, runtime wants "
                f"{BAKE_VERSION}; re-bake with scripts/bake_stripped_spectra.py"
            )
        self.grid_name = str(npz["grid_name"])
        self.flux_unit = str(npz["flux_unit"])
        self.lam = np.asarray(npz["lam"], dtype=float)
        self.nodes_z = np.asarray(npz["nodes_z"], dtype=float)
        self.nodes_minit = np.asarray(npz["nodes_minit"], dtype=float)
        self.flux = np.asarray(npz["flux"], dtype=float)

    def snap(self, minit: float, feh: float) -> int:
        """Index of the nearest node: nearest Z (compared in [Fe/H] space, like binary.py),
        then nearest M_init within that Z. Returns the flat node index."""
        z_target = _GOTBERG_SOLAR_Z * 10.0 ** feh
        zs = self.nodes_z
        # nearest grid Z in [Fe/H] space
        z_snap = min(
            set(zs.tolist()),
            key=lambda z: abs(np.log10(z / _GOTBERG_SOLAR_Z) - feh),
        )
        at_z = np.where(np.isclose(zs, z_snap))[0]
        j = at_z[int(np.argmin(np.abs(self.nodes_minit[at_z] - minit)))]
        return int(j)


_STRIPPED_CACHE: _StrippedSpectra | None = None


def _load_stripped() -> _StrippedSpectra:
    global _STRIPPED_CACHE
    if _STRIPPED_CACHE is None:
        path = SPECTRA_DATA_DIR / STRIPPED_GRID_FILENAME
        if not path.is_file():
            raise SpectraDataMissing(
                f"Binary-stripped-star spectrum grid not baked. Fetch the Götberg "
                f"spectra tree + bake it once:\n"
                f"    python -m star_sim.fetch_gotberg   # recipe to get data/gotberg_stripped/\n"
                f"    python scripts/bake_stripped_spectra.py   # -> {path}\n"
                f"(see docs/plans/stripped-consort-unveiling.md, Chunk 3)."
            )
        _STRIPPED_CACHE = _StrippedSpectra(path)
    return _STRIPPED_CACHE


def stripped_spectrum_data(
    minit: float, feh: float = 0.0, *, n_display: int | None = None,
) -> dict:
    """The binary-stripped-star spectrum the `/stripped_spectrum` endpoint serves — a
    FOURTH spectrum sibling beside `/spectrum`, `/wd_spectrum`, `/wr_spectrum`, reading the
    Götberg CMFGEN cube. Takes the progenitor initial mass `minit` (and [Fe/H]) — the SAME
    snap key `binary.py` uses — so the frontend passes the node `/binary` already resolved
    (`m_init_msun`, `feh_snapped`) and the spectrum is guaranteed to be the SAME star as
    the marker.

    The flux is CMFGEN's continuum-normalized Fnorm (continuum ≈ 1), served as-is: a
    BIDIRECTIONAL draw where absorption lines dip below 1 (the low-mass subdwarf end) and
    emission lines rise above it (the high-mass He-star end, up to ~7× the continuum). The
    `regime` ∈ {"absorption","hybrid","emission"} names where on that sequence this node
    sits (from the peak optical Fnorm), and `display_max` is a y-cap a touch above this
    node's tallest emission line (floored so an absorption-only node still fills the panel,
    capped so a strong He II 4686 can't squash the continuum — the WR per-max gate).

    `feh_varies` is false (the cube is solar-only, matching binary.py's committed table);
    a non-solar request snaps to solar with that flag, honestly.
    """
    s = _load_stripped()
    j = s.snap(minit, feh)
    lam = s.lam
    flux = s.flux[j].copy()
    node_minit = float(s.nodes_minit[j])
    node_z = float(s.nodes_z[j])

    # Regime from the peak optical (visible-band) Fnorm — how far the lines stand ABOVE the
    # continuum. Absorption-only nodes peak at ~1.0; a strong He-star emission node peaks
    # several ×. Measured thresholds; the label is a caption cue, not a data change.
    opt = (lam >= 3800) & (lam <= 7800)
    peak = float(flux[opt].max()) if opt.any() else float(flux.max())
    if peak >= _STRIP_EMISSION_PEAK:
        regime = "emission"
    elif peak <= _STRIP_ABSORPTION_PEAK:
        regime = "absorption"
    else:
        regime = "hybrid"

    # y-cap that frames THIS node's lines: a touch above its tallest emission peak, floored
    # at 1.2 so a pure-absorption node still fills the panel (dips from the continuum at 1),
    # capped at 8 so a monster He II 4686 line can't squash the continuum + weaker features.
    display_max = float(min(max(peak * 1.08, 1.2), 8.0))

    if n_display is not None and n_display < lam.size:
        new_lam = np.linspace(lam[0], lam[-1], n_display)
        flux = np.interp(new_lam, lam, flux)
        lam = new_lam

    return {
        "wavelength": lam.tolist(),
        "flux": flux.tolist(),
        "continuum": 1.0,
        "display_max": display_max,
        "regime": regime,
        "minit": node_minit,
        "minit_requested": float(minit),
        "z_grid": node_z,
        "feh": float(np.log10(node_z / _GOTBERG_SOLAR_Z)),
        "feh_varies": len(set(s.nodes_z.tolist())) > 1,
        "flux_unit": s.flux_unit,
        "grid_name": s.grid_name,
    }
