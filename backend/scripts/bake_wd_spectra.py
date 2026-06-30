"""Build-time bake of the white-dwarf (Koester DA) spectrum cube — endgame Chunk 6.

The stellar-endgame gateway's WD branch needs a real cooling-DA spectrum. Koester
DA white dwarfs live at log g 6.5–9.5 — essentially DISJOINT from the main cube's
log g 0–5 — and are pure hydrogen (no [Fe/H] axis), so they cannot splice onto the
main `(Teff, [Fe/H], log g)` cube. This script bakes a **separate** 2-axis
`(Teff, log g)` cube that the runtime serves at `/wd_spectrum`, a sibling of
`/spectrum` (Chunk-0 scoping in `backend/docs/msg_spectra_build_recipe.md §7`).

Unlike `bake_spectra.py`, this needs **no pymsg / Fortran / Docker**: the Koester
models are plain 2-column ASCII (λ in air Å, F_λ in erg/cm²/s/Å), fetched by
`python -m star_sim.fetch_koester`. So this runs on the host with numpy only.

What it does:

  1. Read every `koester_da_*.txt` in `data/spectra/grids/koester/`, parsing Teff
     and log g from each file's header. The Koester grid is rectangular — 82 Teff
     nodes (5000–80000 K) × 13 log g nodes (6.5–9.5) = 1066 models, no voids — so
     the cube assembles directly from the native nodes (no void-fill, unlike the
     MSG grids; no axis resampling — the runtime interpolates in log10(Teff)).
  2. Bin-average each model's high-resolution flux onto the SAME 3000–9000 Å @
     2.5 Å bin grid the main cube uses, so the panel's x-axis and absorption-line
     guides line up exactly when it switches cubes (both grids are AIR wavelengths
     — verified: the DA Balmer minima land within 0.05 Å of the air positions).
  3. Save `wd_spectra_grid.npz` with the SAME axis-generic schema the runtime
     (`star_sim/spectra.py`) already reads for the main cube — `axis_keys`,
     `axis_log`, per-axis node arrays, the flux cube, `lam`, and metadata. The
     runtime reuses its `_Spectra` class verbatim (a 2-axis cube with no [Fe/H],
     exactly like the original solar `sg-demo`).

Run on the host (no container) after `fetch_koester`:

    python scripts/bake_wd_spectra.py
    # writes data/spectra/wd_spectra_grid.npz (gitignored)
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import time
from pathlib import Path

import numpy as np

# Must match star_sim/spectra.py's BAKE_VERSION — the runtime rejects a stale cube
# (the same discipline as the main bake and MIST's CACHE_VERSION). The WD cube and
# the main cube are read by the same _Spectra class, so they share the version.
BAKE_VERSION = 1

_REPO_ROOT = Path(__file__).resolve().parents[2]
KOESTER_DIR = _REPO_ROOT / "data" / "spectra" / "grids" / "koester"
OUT_PATH = _REPO_ROOT / "data" / "spectra" / "wd_spectra_grid.npz"

_TEFF_RE = re.compile(r"#\s*teff\s*=\s*([\d.]+)")
_LOGG_RE = re.compile(r"#\s*logg\s*=\s*([\d.]+)")


def _read_model(path: Path) -> tuple[float, float, np.ndarray, np.ndarray]:
    """Parse one Koester ASCII model -> (teff, logg, lam[Å], flux[erg/cm²/s/Å])."""
    teff = logg = None
    lam: list[float] = []
    flux: list[float] = []
    with open(path, "r") as fh:
        for line in fh:
            s = line.strip()
            if not s:
                continue
            if s.startswith("#"):
                if (m := _TEFF_RE.match(s)):
                    teff = float(m.group(1))
                elif (m := _LOGG_RE.match(s)):
                    logg = float(m.group(1))
                continue
            parts = s.split()
            if len(parts) >= 2:
                lam.append(float(parts[0]))
                flux.append(float(parts[1]))
    if teff is None or logg is None:
        raise ValueError(f"{path.name}: missing teff/logg header")
    return teff, logg, np.asarray(lam), np.asarray(flux)


def _bin_average(model_lam: np.ndarray, model_flux: np.ndarray,
                 lam_edges: np.ndarray) -> np.ndarray:
    """Average a high-resolution model onto the coarse bin grid (flux-conserving in
    the sense of a mean sample per bin — Koester's ~0.74 Å sampling puts ~3 points
    in each 2.5 Å bin, so this preserves line depth far better than point-sampling
    at bin centres would). Any bin with no sample (none, given the resolution) falls
    back to linear interpolation so the cube has no gaps."""
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


def bake(koester_dir: Path, out_path: Path, *, lam_min: float, lam_max: float,
         lam_step: float) -> None:
    files = sorted(koester_dir.glob("koester_da_*.txt"))
    if not files:
        raise SystemExit(
            f"No Koester models in {koester_dir} — run: python -m star_sim.fetch_koester"
        )
    print(f"reading {len(files)} Koester DA models from {koester_dir} ...", flush=True)

    # The SAME bin grid the main cube uses (3000–9000 Å @ 2.5 Å), so the x-axis and
    # line guides are identical when the panel switches between cubes.
    lam_edges = np.arange(lam_min, lam_max + lam_step, lam_step)
    lam_edges = lam_edges[lam_edges <= lam_max]
    lam = 0.5 * (lam_edges[:-1] + lam_edges[1:])
    n_lam = lam.size

    # First pass: read headers + flux, collect the native node sets.
    models: dict[tuple[float, float], np.ndarray] = {}
    teffs: set[float] = set()
    loggs: set[float] = set()
    t0 = time.time()
    for i, path in enumerate(files):
        teff, logg, ml, mf = _read_model(path)
        if not (ml[0] <= lam_edges[0] and ml[-1] >= lam_edges[-1]):
            raise ValueError(
                f"{path.name}: λ coverage {ml[0]:.0f}–{ml[-1]:.0f} Å does not span "
                f"the {lam_min:.0f}–{lam_max:.0f} Å bake window"
            )
        models[(teff, logg)] = _bin_average(ml, mf, lam_edges).astype(np.float32)
        teffs.add(teff)
        loggs.add(logg)
        if (i + 1) % 100 == 0 or i + 1 == len(files):
            print(f"\r  {i + 1}/{len(files)}", end="", flush=True)
    print(f"  ({time.time() - t0:.1f}s)")

    teff_nodes = np.array(sorted(teffs))
    logg_nodes = np.array(sorted(loggs))
    n_t, n_g = teff_nodes.size, logg_nodes.size
    print(f"  grid: {n_t} Teff [{teff_nodes[0]:.0f}..{teff_nodes[-1]:.0f}] x "
          f"{n_g} log g [{logg_nodes[0]}..{logg_nodes[-1]}]  (expect {n_t * n_g} models)")
    if n_t * n_g != len(models):
        # The Koester DA grid is rectangular; a mismatch means a missing/extra node.
        present = set(models.keys())
        missing = [(t, g) for t in teff_nodes for g in logg_nodes
                   if (t, g) not in present]
        raise ValueError(
            f"grid not rectangular: {len(models)} models but {n_t}×{n_g}={n_t * n_g} "
            f"nodes; {len(missing)} missing, e.g. {missing[:5]}"
        )

    # Assemble the cube (teff, logg, lam) from the native nodes — no resampling, no
    # void-fill (the grid is complete), so every cube entry is a real Koester model.
    cube = np.zeros((n_t, n_g, n_lam), dtype=np.float32)
    for it, t in enumerate(teff_nodes):
        for ig, g in enumerate(logg_nodes):
            cube[it, ig] = models[(t, g)]

    assert np.isfinite(cube).all(), "non-finite flux in baked WD cube"
    n_neg = int((cube < 0).sum())
    if n_neg:
        print(f"  clamped {n_neg} negative flux bins (min was {float(cube.min()):.3g})")
        np.clip(cube, 0.0, None, out=cube)

    keys = ["teff", "logg"]
    axis_log = [True, False]   # interpolate Teff in log10 (cool-end resolution); log g linear
    data: dict[str, np.ndarray] = {
        "bake_version": np.array(BAKE_VERSION),
        "grid_name": np.array("koester2-DA"),
        "flux_unit": np.array("erg/cm^2/s/Angstrom"),
        "axis_keys": np.array(keys),
        "axis_labels": np.array(["Teff", "log(g)"]),
        "axis_log": np.array(axis_log, dtype=bool),
        "lam": lam.astype(np.float64),
        "flux": cube,
        "axis_teff": teff_nodes.astype(np.float64),
        "axis_logg": logg_nodes.astype(np.float64),
    }

    out_path = Path(os.path.abspath(out_path))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(".npz.tmp")
    with open(tmp, "wb") as fh:
        np.savez_compressed(fh, **data)
    os.replace(tmp, out_path)
    size_mb = os.path.getsize(out_path) / 1e6
    # ASCII-only print: this bake runs on the host (Windows cp1252 console), unlike
    # bake_spectra.py which runs in the UTF-8 Docker container.
    print(f"wrote {out_path}  ({size_mb:.1f} MB)  cube{cube.shape}  "
          f"lam {lam[0]:.1f}-{lam[-1]:.1f} A @ {lam_step} A")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--koester-dir", default=str(KOESTER_DIR),
                   help="directory of fetched koester_da_*.txt models")
    p.add_argument("--out", default=str(OUT_PATH), help="output .npz path")
    p.add_argument("--lam-min", type=float, default=3000.0)
    p.add_argument("--lam-max", type=float, default=9000.0)
    p.add_argument("--lam-step", type=float, default=2.5,
                   help="wavelength bin width in Å (match the main cube)")
    a = p.parse_args(argv)
    bake(Path(a.koester_dir), Path(a.out), lam_min=a.lam_min, lam_max=a.lam_max,
         lam_step=a.lam_step)
    return 0


if __name__ == "__main__":
    sys.exit(main())
