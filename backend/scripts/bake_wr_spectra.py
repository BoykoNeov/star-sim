"""Build-time bake of the Wolf-Rayet spectrum cube — endgame Chunk 7 (narrow-GO).

The WR-endgame scrub needs a real **wind-emission** spectrum for the stripped core.
That lives only in the PoWR grids (fetched by `python -m star_sim.fetch_powr`), which
are plain 2-col ASCII (λ Å, F_λ erg/cm²/s/Å at 10 pc) — so, like the WD cubes, this
bake runs on the **host** with numpy only (no pymsg/Fortran/Docker).

PoWR is unlike every other grid we bake in two ways, both driven by its physics:

  * **The axis is (T*, Rt), not (Teff, log g).** A WR's spectrum is set by its
    stellar temperature T* and the wind density via the "transformed radius"
    Rt = R*·[(v∞/2500)/(Ṁ√D/1e-4)]^(2/3) (Hamann & Gräfener 2004). One grid per
    subtype × metallicity, each a 2-D (T*, Rt) sheet at FIXED log L=5.3, v∞, D=4.
    No parameter file ships, so we derive each model's node coordinates from the
    PoWR dir-name convention: `<T*idx>-<Rtidx>` → log T* = 4.30 + 0.05·T*idx,
    log Rt = 0.10·Rtidx (the Rt floor 0.4 = the paper's degeneracy boundary; the
    T* scale anchored to the known 28–158 kK WNE range — see recipe §7a).

  * **The footprint is a ragged parallelogram, not a rectangle.** The hot+dense-wind
    corner has no models (it is degenerate / was never computed). So we do NOT build
    a rectangular RGI cube + void-fill (which would invent hot dense-wind spectra
    that don't exist). We store each grid as a FLAT list of (log T*, log Rt) nodes +
    their spectra, and the runtime **snaps to the nearest real node** (the endgame
    snap-to-track discipline) — and reports "no model" when the nearest node is far
    (the stripped bulk, hotter/denser than any PoWR model — recipe §7a gate).

The cube is the emission spectra resampled onto the SAME 3000–9000 Å @ 2.5 Å bin
grid as the other cubes, so the panel's x-axis lines up when it switches cubes.

Run on the host after the fetch:

    python -m star_sim.fetch_powr
    python scripts/bake_wr_spectra.py        # -> data/spectra/wr_spectra_grid.npz
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import time
from pathlib import Path

import numpy as np

# Must match star_sim/spectra.py's BAKE_VERSION. The WR cube uses its OWN .npz schema
# (flat per-grid nodes, not the axis-generic _Spectra cube) but shares the version
# discipline so a stale cube is rejected; bump in lockstep with the other bakes.
BAKE_VERSION = 1

_REPO_ROOT = Path(__file__).resolve().parents[2]
POWR_DIR = _REPO_ROOT / "data" / "spectra" / "grids" / "powr"
OUT_PATH = _REPO_ROOT / "data" / "spectra" / "wr_spectra_grid.npz"

# PoWR grid-name convention (recipe §7a). The model dir is `<T*idx>-<Rtidx>`.
_LOGT_A, _LOGT_B = 0.05, 4.30      # log10(T*/K) = _LOGT_A*T*idx + _LOGT_B
_LOGRT_A = 0.10                    # log10(Rt/Rsun) = _LOGRT_A*Rtidx
_MODEL_RE = re.compile(r"^(\d{2})-(\d{2})$")

# The discrete cube selectors live on the fetched dir names; mirror fetch_powr's table
# so the bake is self-contained (subtype, metallicity Z/Zsun, wind v∞ per grid).
_GRID_META: dict[str, dict] = {
    "WNE-gal": dict(subtype="WNE", metal="gal", z=1.0, vinf=1600.0),
    "WNL-gal": dict(subtype="WNL", metal="gal", z=1.0, vinf=1000.0),
    "WC-gal":  dict(subtype="WC", metal="gal", z=1.0, vinf=2000.0),
    "WNE-lmc": dict(subtype="WNE", metal="lmc", z=0.5, vinf=1600.0),
    "WNL-lmc": dict(subtype="WNL", metal="lmc", z=0.5, vinf=1000.0),
    "WC-lmc":  dict(subtype="WC", metal="lmc", z=0.5, vinf=2000.0),
    "WNE-smc": dict(subtype="WNE", metal="smc", z=0.2, vinf=1600.0),
    "WNL-smc": dict(subtype="WNL", metal="smc", z=0.2, vinf=1000.0),
}


def _read_flux_calib(path: Path) -> tuple[np.ndarray, np.ndarray]:
    """Parse one PoWR flux_calib.dat -> (lam[Å], F_λ[erg/cm²/s/Å at 10 pc]).
    Header lines start with '#' (model name, λ unit, flux unit); body is 2 columns."""
    lam: list[float] = []
    flux: list[float] = []
    with open(path, "r") as fh:
        for line in fh:
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            p = s.split()
            if len(p) >= 2:
                lam.append(float(p[0]))
                flux.append(float(p[1]))
    return np.asarray(lam), np.asarray(flux)


def _vac_to_air(lam_vac: np.ndarray) -> np.ndarray:
    """Vacuum → air (Morton 2000). PoWR serves vacuum λ; the cube is air, so the
    panel's line guides (He II 4686, N/C lines) line up across the cube switch. WR
    emission lines are 1000s km/s broad, so the ~1.4 Å shift is sub-resolution — but
    converted for consistency with the other cubes."""
    s2 = (1e4 / lam_vac) ** 2
    n = (1.0 + 0.0000834254 + 0.02406147 / (130.0 - s2)
         + 0.00015998 / (38.9 - s2))
    return lam_vac / n


def _bin_average(model_lam: np.ndarray, model_flux: np.ndarray,
                 lam_edges: np.ndarray) -> np.ndarray:
    """Average a high-resolution model onto the coarse bin grid (mean sample per bin —
    PoWR's sub-Å sampling puts many points in each 2.5 Å bin, preserving line shape).
    Empty bins (never, given PoWR's density) fall back to linear interpolation."""
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


def _read_grid(grid_dir: Path, lam_edges: np.ndarray
               ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Read one PoWR grid dir -> (logT*[n], logRt[n], flux[n, n_lam]). Each model dir
    `<T*idx>-<Rtidx>` gives the node coordinates via the convention; the flux is
    resampled onto the bin grid (vac→air)."""
    lam = 0.5 * (lam_edges[:-1] + lam_edges[1:])
    logT: list[float] = []
    logRt: list[float] = []
    spectra: list[np.ndarray] = []
    model_dirs = sorted(p for p in grid_dir.iterdir() if p.is_dir())
    for md in model_dirs:
        m = _MODEL_RE.match(md.name)
        fcal = md / "flux_calib.dat"
        if not m or not fcal.is_file():
            continue
        t_idx, r_idx = int(m.group(1)), int(m.group(2))
        ml, mf = _read_flux_calib(fcal)
        ml = _vac_to_air(ml)
        if not (ml[0] <= lam_edges[0] and ml[-1] >= lam_edges[-1]):
            raise ValueError(
                f"{md.name}: λ coverage {ml[0]:.0f}–{ml[-1]:.0f} Å does not span the "
                f"{lam_edges[0]:.0f}–{lam_edges[-1]:.0f} Å bake window"
            )
        logT.append(_LOGT_A * t_idx + _LOGT_B)
        logRt.append(_LOGRT_A * r_idx)
        spectra.append(_bin_average(ml, mf, lam_edges).astype(np.float32))
    if not spectra:
        raise ValueError(f"no PoWR models parsed in {grid_dir}")
    return (np.asarray(logT, dtype=np.float64),
            np.asarray(logRt, dtype=np.float64),
            np.stack(spectra))


def bake(powr_dir: Path, out_path: Path, *, lam_min: float, lam_max: float,
         lam_step: float) -> None:
    lam_edges = np.arange(lam_min, lam_max + lam_step, lam_step)
    lam_edges = lam_edges[lam_edges <= lam_max]
    lam = 0.5 * (lam_edges[:-1] + lam_edges[1:])

    present = [tag for tag in _GRID_META if (powr_dir / tag).is_dir()
               and any((powr_dir / tag).glob("*/flux_calib.dat"))]
    if not present:
        raise SystemExit(
            f"No PoWR grids in {powr_dir} — run: python -m star_sim.fetch_powr")

    data: dict[str, np.ndarray] = {
        "bake_version": np.array(BAKE_VERSION),
        "grid_name": np.array("PoWR-WR"),
        "flux_unit": np.array("erg/cm^2/s/Angstrom @ 10pc"),
        "lam": lam.astype(np.float64),
        "grid_tags": np.array(present),
        "grid_subtype": np.array([_GRID_META[t]["subtype"] for t in present]),
        "grid_metal": np.array([_GRID_META[t]["metal"] for t in present]),
        "grid_z": np.array([_GRID_META[t]["z"] for t in present], dtype=np.float64),
        "grid_vinf": np.array([_GRID_META[t]["vinf"] for t in present], dtype=np.float64),
    }
    for tag in present:
        t0 = time.time()
        logT, logRt, flux = _read_grid(powr_dir / tag, lam_edges)
        n_neg = int((flux < 0).sum())
        if n_neg:
            np.clip(flux, 0.0, None, out=flux)
        data[f"nodes_logT_{tag}"] = logT
        data[f"nodes_logRt_{tag}"] = logRt
        data[f"flux_{tag}"] = flux
        print(f"  {tag}: {flux.shape[0]} models  logT* {logT.min():.2f}–{logT.max():.2f} "
              f"({10**logT.min()/1e3:.0f}–{10**logT.max()/1e3:.0f} kK)  "
              f"logRt {logRt.min():.2f}–{logRt.max():.2f}  "
              f"({n_neg} neg clipped)  ({time.time()-t0:.1f}s)")

    out_path = Path(os.path.abspath(out_path))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(".npz.tmp")
    with open(tmp, "wb") as fh:
        np.savez_compressed(fh, **data)
    os.replace(tmp, out_path)
    size_mb = os.path.getsize(out_path) / 1e6
    print(f"wrote {out_path}  ({size_mb:.1f} MB)  {len(present)} grids  "
          f"lam {lam[0]:.1f}-{lam[-1]:.1f} A @ {lam_step} A")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--powr-dir", default=str(POWR_DIR),
                   help="directory of fetched PoWR grids (per-tag subdirs)")
    p.add_argument("--out", default=str(OUT_PATH), help="output .npz path")
    p.add_argument("--lam-min", type=float, default=3000.0)
    p.add_argument("--lam-max", type=float, default=9000.0)
    p.add_argument("--lam-step", type=float, default=2.5,
                   help="wavelength bin width in Å (match the other cubes)")
    a = p.parse_args(argv)
    bake(Path(a.powr_dir), Path(a.out),
         lam_min=a.lam_min, lam_max=a.lam_max, lam_step=a.lam_step)
    return 0


if __name__ == "__main__":
    sys.exit(main())
