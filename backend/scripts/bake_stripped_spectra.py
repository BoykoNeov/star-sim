"""Build-time bake of the binary-stripped-star spectrum cube — Chunk 3.

The binary-stripped-star what-if (`binary.py`, `/binary`, frontend `stripped-mode`)
shows a hot He-star a close companion bares (Götberg+2018). Chunk 2 drew an honest
PLACEHOLDER in the spectrum panel: the main cube is H-atmosphere models, so feeding a
He-star's (Teff, log g) would paint a FALSE O-star Balmer spectrum. Chunk 3 replaces it
with the star's REAL CMFGEN spectrum, from the same Götberg grid `binary.py` snaps.

Like the WR cube (`bake_wr_spectra.py`), this is a **flat-node** cube, NOT a rectangular
(Teff, log g) grid: the grid is 1-D in initial mass per metallicity (23 masses × 4 Z;
Gate 0a), a ragged footprint in (Teff, log g), so a rectangular RGI cube would have to
void-fill spectra that don't exist. We store a flat list of (Z, M_init) nodes + their
spectra and the runtime **snaps to the node `binary.py` already resolved** — guaranteeing
the panel's spectrum is the SAME star as the marker (state↔spectrum consistency, the
tightest constraint here).

**Solar-first**, matching `binary.py`'s committed solar-only parameter table: bake only
`grid_014` (Z=0.014) by default. The three non-solar Z grids are on disk under
`data/gotberg_stripped/` and can be added with `--grids` when the non-solar *parameter*
tables land (so `/binary` can reach those states) — until then a non-solar spectrum node
would be unreachable dead data, so we don't bake it (the same scope discipline as the
solar-only param table).

The spectrum file is `normalised_spectrum.txt` — CMFGEN's **continuum-normalized** flux
(Fnorm ≈ 1, absorption dips below, emission peaks above), so unlike the WR cube we need
NO continuum estimation: we bin Fnorm directly and the runtime serves it as-is. The
measured payoff (the abstract's thesis): the sequence bridges pure ABSORPTION at the
low-mass subdwarf end (Fnorm 0.4–1.0, He II 4686 flat) → a hybrid mid-mass regime →
strong EMISSION at the high-mass He-star end (He II 4686 up to ~7× continuum).

Two measured gotchas the bake handles (verified on disk 2026-07-02):

  * **Vacuum → air λ.** The Götberg spectra are in vacuum (Balmer minima land at the
    vacuum wavelengths to <0.1 Å, off air by 1.1–1.7 Å). The other cubes + the panel's
    line guides are air, so we convert (Morton 2000) to keep He II 4686 / Balmer guides
    aligned. The shift is sub-bin at 2.5 Å but converted for consistency (TMAP/PoWR
    precedent).
  * **Sort by λ before binning.** CMFGEN concatenates frequency bands, so a spectrum file
    can be non-monotone in λ (the `SED.txt` verifier hit this). The solar
    `normalised_spectrum.txt` files measured monotone, but the empty-bin `np.interp`
    fallback below REQUIRES monotone λ, so we sort defensively — cheap insurance against a
    silently-corrupted bin on a non-solar grid.

Run on the host after the spectra tree is in place (see `fetch_gotberg.py`):

    python -m star_sim.fetch_gotberg          # validate the tree is present
    python scripts/bake_stripped_spectra.py   # -> data/spectra/stripped_spectra_grid.npz
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import time
from pathlib import Path

import numpy as np

# Must match star_sim/spectra.py's BAKE_VERSION. Like the WR cube this uses its OWN .npz
# schema (flat per-node list, not the axis-generic _Spectra cube) but shares the version
# discipline so a stale cube is rejected; bump in lockstep with the other bakes.
BAKE_VERSION = 1

_REPO_ROOT = Path(__file__).resolve().parents[2]
GOTBERG_DIR = _REPO_ROOT / "data" / "gotberg_stripped"
OUT_PATH = _REPO_ROOT / "data" / "spectra" / "stripped_spectra_grid.npz"

# The grid dirs and their metallicity Z. SOLAR-ONLY by default (matches binary.py's
# committed solar param table — a non-solar spectrum node is unreachable until the
# matching param table lands). Add the rest with --grids "grid_014,grid_006,...".
_GRID_Z: dict[str, float] = {
    "grid_0002": 0.0002,
    "grid_002": 0.002,
    "grid_006": 0.006,
    "grid_014": 0.014,
}
_DEFAULT_GRIDS = ["grid_014"]

# Model subdir name: M1_<Minit>q0.8P<P>Z<Z>_vinf1.5 — the same convention binary.py's
# node list comes from (M_init is the first field).
_MODEL_RE = re.compile(r"^M1_([0-9.]+)q")


def _read_norm_spectrum(path: Path) -> tuple[np.ndarray, np.ndarray]:
    """Parse one normalised_spectrum.txt -> (lam[Å, vacuum], Fnorm). The first line is a
    provenance comment, the second a `Wavelength  Fnorm` header; the body is 2 columns."""
    lam: list[float] = []
    fn: list[float] = []
    with open(path, "r") as fh:
        for line in fh:
            p = line.split()
            if len(p) != 2:
                continue
            try:
                a, b = float(p[0]), float(p[1])
            except ValueError:
                continue  # the header row ("Wavelength [Angstrom]  Fnorm")
            lam.append(a)
            fn.append(b)
    return np.asarray(lam), np.asarray(fn)


def _vac_to_air(lam_vac: np.ndarray) -> np.ndarray:
    """Vacuum → air (Morton 2000, IAU standard, valid >~2000 Å). The Götberg spectra are
    vacuum; the cube + panel guides are air, so converting keeps He II 4686 / the Balmer
    series aligned when the panel switches cubes."""
    s2 = (1e4 / lam_vac) ** 2
    n = (1.0 + 0.0000834254 + 0.02406147 / (130.0 - s2)
         + 0.00015998 / (38.9 - s2))
    return lam_vac / n


def _bin_average(model_lam: np.ndarray, model_flux: np.ndarray,
                 lam_edges: np.ndarray) -> np.ndarray:
    """Average a high-resolution model onto the coarse bin grid (mean sample per bin — the
    ~0.05 Å CMFGEN sampling puts many points in each 2.5 Å bin, preserving line depth far
    better than point-sampling at bin centres). Empty bins fall back to linear interp,
    which REQUIRES monotone λ (the caller sorts first)."""
    n_bins = lam_edges.size - 1
    idx = np.searchsorted(lam_edges, model_lam, side="right") - 1
    inside = (model_lam >= lam_edges[0]) & (model_lam < lam_edges[-1])
    idx = idx[inside]
    fl = model_flux[inside]
    sums = np.bincount(idx, weights=fl, minlength=n_bins)
    counts = np.bincount(idx, minlength=n_bins)
    binned = sums / np.maximum(counts, 1)
    empty = counts == 0
    if empty.any():
        centers = 0.5 * (lam_edges[:-1] + lam_edges[1:])
        binned[empty] = np.interp(centers[empty], model_lam, model_flux)
    return binned


def bake(gotberg_dir: Path, out_path: Path, grids: list[str], *,
         lam_min: float, lam_max: float, lam_step: float) -> None:
    lam_edges = np.arange(lam_min, lam_max + lam_step, lam_step)
    lam_edges = lam_edges[lam_edges <= lam_max]
    lam = 0.5 * (lam_edges[:-1] + lam_edges[1:])

    nodes_z: list[float] = []
    nodes_minit: list[float] = []
    spectra: list[np.ndarray] = []

    for grid in grids:
        z = _GRID_Z.get(grid)
        if z is None:
            raise SystemExit(f"unknown grid {grid!r} (known: {sorted(_GRID_Z)})")
        gdir = gotberg_dir / grid
        model_dirs = sorted(
            d for d in gdir.iterdir() if d.is_dir() and _MODEL_RE.match(d.name)
        ) if gdir.is_dir() else []
        if not model_dirs:
            raise SystemExit(
                f"No stripped-star models in {gdir} — fetch the Götberg spectra tree "
                f"(python -m star_sim.fetch_gotberg for the recipe)."
            )
        t0 = time.time()
        for md in model_dirs:
            m = _MODEL_RE.match(md.name)
            spec = md / "normalised_spectrum.txt"
            if not spec.is_file():
                raise SystemExit(f"{md}: missing normalised_spectrum.txt")
            ml, mf = _read_norm_spectrum(spec)
            # Sort by λ BEFORE anything else (CMFGEN band-concatenation can be non-monotone;
            # the empty-bin interp fallback needs monotone λ).
            order = np.argsort(ml)
            ml, mf = ml[order], mf[order]
            ml = _vac_to_air(ml)
            if not (ml[0] <= lam_edges[0] and ml[-1] >= lam_edges[-1]):
                raise SystemExit(
                    f"{md.name}: λ coverage {ml[0]:.0f}–{ml[-1]:.0f} Å does not span the "
                    f"{lam_min:.0f}–{lam_max:.0f} Å bake window"
                )
            nodes_z.append(z)
            nodes_minit.append(float(m.group(1)))
            spectra.append(_bin_average(ml, mf, lam_edges).astype(np.float32))
        minits = [n for zz, n in zip(nodes_z, nodes_minit) if zz == z]
        print(f"  {grid} (Z={z}): {len(model_dirs)} models, "
              f"M_init {min(minits):.2f}–{max(minits):.2f} M_sun  ({time.time()-t0:.1f}s)")

    flux = np.stack(spectra)
    n_neg = int((flux < 0).sum())
    if n_neg:
        np.clip(flux, 0.0, None, out=flux)   # Fnorm is >= 0 physically; guard tiny artifacts

    data: dict[str, np.ndarray] = {
        "bake_version": np.array(BAKE_VERSION),
        "grid_name": np.array("gotberg2018-stripped"),
        "flux_unit": np.array("normalized (F/Fcontinuum)"),
        "lam": lam.astype(np.float64),
        "nodes_z": np.asarray(nodes_z, dtype=np.float64),
        "nodes_minit": np.asarray(nodes_minit, dtype=np.float64),
        "flux": flux,
    }

    out_path = Path(os.path.abspath(out_path))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(".npz.tmp")
    with open(tmp, "wb") as fh:
        np.savez_compressed(fh, **data)
    os.replace(tmp, out_path)
    size_mb = os.path.getsize(out_path) / 1e6
    # ASCII-only print (host Windows cp1252 console), like the other host bakes.
    print(f"wrote {out_path}  ({size_mb:.1f} MB)  {flux.shape[0]} nodes x {lam.size} lam  "
          f"({n_neg} neg clipped)  lam {lam[0]:.1f}-{lam[-1]:.1f} A @ {lam_step} A")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--gotberg-dir", default=str(GOTBERG_DIR),
                   help="the Götberg spectra tree (grid_0002/grid_002/grid_006/grid_014)")
    p.add_argument("--out", default=str(OUT_PATH), help="output .npz path")
    p.add_argument("--grids", default=",".join(_DEFAULT_GRIDS),
                   help="comma-separated grid dirs to bake (default solar-only grid_014; "
                        "add non-solar when the matching binary.py param tables land)")
    p.add_argument("--lam-min", type=float, default=3000.0)
    p.add_argument("--lam-max", type=float, default=9000.0)
    p.add_argument("--lam-step", type=float, default=2.5,
                   help="wavelength bin width in Å (match the other cubes)")
    a = p.parse_args(argv)
    grids = [g.strip() for g in a.grids.split(",") if g.strip()]
    bake(Path(a.gotberg_dir), Path(a.out), grids,
         lam_min=a.lam_min, lam_max=a.lam_max, lam_step=a.lam_step)
    return 0


if __name__ == "__main__":
    sys.exit(main())
