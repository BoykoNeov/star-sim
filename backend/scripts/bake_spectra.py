"""Build-time bake of a synthetic-spectrum grid for the Phase 5 spectrum panel.

This script is **deliberately NOT part of the `star_sim` package** — it is the one
place that imports `pymsg`, and it runs only inside the MSG build container (see
`backend/docs/msg_spectra_build_recipe.md`). Importing the runtime package must
never pull in pymsg/Fortran; the runtime (`star_sim/spectra.py`) reads only the
`.npz` this script produces, with pure numpy/scipy.

What it does (the "dense, void-filled bake"):

  1. Open a `pymsg.SpecGrid` (default the bundled solar `sg-demo.h5`).
  2. Read the grid's own axis labels/bounds (`sg.axis_labels`, `sg.axis_x_min/max`)
     and build our **own regular** axes over them — Teff log-spaced (lines change
     fast at the cool end), the rest linear at a teaching step. This is
     **axis-generic**: a 2-D solar grid bakes to a 2-D cube; a 3-D `[Fe/H]` grid
     (e.g. CAP18) bakes to a 3-D cube with *zero code change* — the runtime reads
     the axis list back out of the `.npz`.
  3. Evaluate `sg.flux` at every regular node. MSG grids have **voids** (no model
     at hot + low-gravity corners → `LookupError`); we fill each void from the
     nearest valid point **along the log g axis at fixed other params** (the voids
     are a contiguous high-log g block, so this preserves the dominant Teff
     variation exactly — a generic nearest-neighbour in raw coords would be
     swamped by the Teff scale and pull a wrong-Teff spectrum). The stored cube is
     therefore fully regular, as `scipy.RegularGridInterpolator` requires.
  4. Save `spectra_grid.npz` atomically (temp + os.replace), pure numeric arrays:
     the per-axis node arrays, an `axis_log` flag per axis (Teff → log), the flux
     cube `(n_axis0, …, n_lam)`, the wavelength bin centres `lam`, and metadata
     (grid name, flux unit, `BAKE_VERSION`).

Run inside the container (env per the recipe), e.g.:

    python bake_spectra.py --grid /tmp/msg-2.2/data/grids/sg-demo.h5 \
                           --out /tmp/spectra_grid.npz

then `docker cp` the `.npz` out to the host `data/spectra/`.
"""

from __future__ import annotations

import argparse
import os
import sys
import time

import numpy as np

# Bump when the on-disk schema or axis/flux semantics change, so the runtime can
# reject a stale cube (mirrors MIST's CACHE_VERSION discipline).
BAKE_VERSION = 1

# MSG axis label -> our canonical lowercased key (what the runtime/state speak).
# Anything not in this map is passed through lowercased with non-alnum stripped,
# so an unknown future axis still bakes (axis-generic).
_LABEL_TO_KEY = {
    "Teff": "teff",
    "log(g)": "logg",
    "[Fe/H]": "feh",
}

# Per-axis node strategy over the grid's [x_min, x_max].  (n_default, log_spaced,
# step) — step (when not None) sets a fixed spacing; otherwise n_default nodes.
# Teff is log-spaced for cool-end resolution; log g / [Fe/H] get a teaching step.
_AXIS_PLAN = {
    "teff": dict(n=96, log=True, step=None),
    "logg": dict(n=None, log=False, step=0.5),
    "feh": dict(n=None, log=False, step=0.5),
}
_AXIS_PLAN_DEFAULT = dict(n=8, log=False, step=None)


def _canon(label: str) -> str:
    if label in _LABEL_TO_KEY:
        return _LABEL_TO_KEY[label]
    return "".join(c for c in label.lower() if c.isalnum())


def _build_axis(key: str, lo: float, hi: float) -> np.ndarray:
    """Regular node array over [lo, hi] for one parameter axis."""
    plan = _AXIS_PLAN.get(key, _AXIS_PLAN_DEFAULT)
    if plan["step"] is not None:
        # Inclusive of hi (within a hair), fixed step.
        n = int(round((hi - lo) / plan["step"])) + 1
        nodes = lo + plan["step"] * np.arange(n)
        nodes[-1] = min(nodes[-1], hi)
        return nodes
    if plan["log"]:
        return np.geomspace(lo, hi, plan["n"])
    return np.linspace(lo, hi, plan["n"])


def _fill_voids_along(cube: np.ndarray, valid: np.ndarray, logg_axis: int) -> tuple[int, int]:
    """Fill void spectra in-place. Primary pass walks the log g axis at fixed
    other params (the voids are a contiguous high-log g block); a fallback pass
    handles any whole-line void via nearest valid over the full param space.

    Returns (n_filled_along_logg, n_filled_fallback).
    """
    param_shape = valid.shape
    n_logg = param_shape[logg_axis]
    filled_logg = 0

    for idx in np.ndindex(param_shape):
        if valid[idx]:
            continue
        # Search outward along the log g axis for the nearest valid neighbour.
        base = list(idx)
        best = None
        for dist in range(1, n_logg):
            for step in (dist, -dist):
                j = idx[logg_axis] + step
                if 0 <= j < n_logg:
                    probe = tuple(base[:logg_axis] + [j] + base[logg_axis + 1 :])
                    if valid[probe]:
                        best = probe
                        break
            if best is not None:
                break
        if best is not None:
            cube[idx] = cube[best]
            valid[idx] = True
            filled_logg += 1

    # Fallback: any param line that was entirely void (no valid log g anywhere).
    remaining = np.argwhere(~valid)
    filled_fallback = 0
    if remaining.size:
        valid_idx = np.argwhere(valid)
        # Normalise param coords so no single axis (e.g. the wide Teff index span)
        # dominates the nearest-neighbour distance.
        scale = np.array(param_shape, dtype=float)
        for vi in remaining:
            d = ((valid_idx - vi) / scale) ** 2
            nearest = tuple(valid_idx[d.sum(axis=1).argmin()])
            cube[tuple(vi)] = cube[nearest]
            valid[tuple(vi)] = True
            filled_fallback += 1

    return filled_logg, filled_fallback


def bake(grid_path: str, out_path: str, *, lam_min: float, lam_max: float,
         lam_step: float, n_teff: int | None) -> None:
    import pymsg  # imported here so `--help` works outside the container

    sg = pymsg.SpecGrid(grid_path)
    labels = list(sg.axis_labels)
    keys = [_canon(l) for l in labels]
    print(f"grid: {os.path.basename(grid_path)}  axes={labels} -> {keys}", flush=True)

    if n_teff is not None and "teff" in keys:
        _AXIS_PLAN["teff"]["n"] = n_teff

    # Build our regular axes over the grid's own bounds.
    axes: list[np.ndarray] = []
    axis_log: list[bool] = []
    for label, key in zip(labels, keys):
        lo = float(sg.axis_x_min[label])
        hi = float(sg.axis_x_max[label])
        nodes = _build_axis(key, lo, hi)
        axes.append(nodes)
        axis_log.append(_AXIS_PLAN.get(key, _AXIS_PLAN_DEFAULT)["log"])
        print(f"  axis {key}: {nodes.size} nodes [{nodes[0]:.4g} .. {nodes[-1]:.4g}]"
              f"{' (log-spaced)' if axis_log[-1] else ''}", flush=True)

    # Wavelength bins: clamp to the grid's coverage; store bin CENTRES.
    lo = max(lam_min, float(np.ceil(sg.lam_min)))
    hi = min(lam_max, float(np.floor(sg.lam_max)))
    lam_edges = np.arange(lo, hi + lam_step, lam_step)
    lam_edges = lam_edges[lam_edges <= hi]
    lam = 0.5 * (lam_edges[:-1] + lam_edges[1:])
    n_lam = lam.size
    print(f"  lam: {n_lam} bins [{lam[0]:.1f} .. {lam[-1]:.1f}] Å @ {lam_step} Å", flush=True)

    param_shape = tuple(a.size for a in axes)
    cube = np.zeros(param_shape + (n_lam,), dtype=np.float32)
    valid = np.zeros(param_shape, dtype=bool)

    n_nodes = int(np.prod(param_shape))
    print(f"  evaluating {n_nodes} nodes × {n_lam} bins …", flush=True)
    t0 = time.time()
    n_void = 0
    for idx in np.ndindex(param_shape):
        x = {label: float(axes[i][idx[i]]) for i, label in enumerate(labels)}
        try:
            f = sg.flux(x=x, z=0.0, lam=lam_edges)
            cube[idx] = np.asarray(f, dtype=np.float32)
            valid[idx] = True
        except LookupError:
            n_void += 1  # a grid void; filled below
    print(f"    done in {time.time() - t0:.1f}s; {n_void} voids ({100*n_void/n_nodes:.1f}%)",
          flush=True)

    logg_axis = keys.index("logg") if "logg" in keys else None
    if n_void:
        if logg_axis is None:
            raise RuntimeError("grid has voids but no log g axis to fill along")
        fl, ff = _fill_voids_along(cube, valid, logg_axis)
        print(f"    void-fill: {fl} along log g, {ff} fallback nearest-neighbour", flush=True)
    assert valid.all(), "cube still has voids after fill"
    assert np.isfinite(cube).all(), "non-finite flux in baked cube"
    # MSG's cubic interpolation can undershoot slightly below zero in deep
    # absorption-line cores (a spline artifact); flux is physically ≥ 0, so clamp.
    n_neg = int((cube < 0).sum())
    if n_neg:
        print(f"    clamped {n_neg} negative flux bins (min was {float(cube.min()):.3g})",
              flush=True)
        np.clip(cube, 0.0, None, out=cube)

    # Save atomically. Axis arrays under axis_<key>; the runtime reads axis_keys
    # to know the cube layout, axis_log to know which to interpolate in log space.
    data: dict[str, np.ndarray] = {
        "bake_version": np.array(BAKE_VERSION),
        "grid_name": np.array(os.path.basename(grid_path)),
        "flux_unit": np.array("erg/cm^2/s/Angstrom"),
        "axis_keys": np.array(keys),
        "axis_labels": np.array(labels),
        "axis_log": np.array(axis_log, dtype=bool),
        "lam": lam.astype(np.float64),
        "flux": cube,
    }
    for key, nodes in zip(keys, axes):
        data[f"axis_{key}"] = nodes.astype(np.float64)

    out_path = os.path.abspath(out_path)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    tmp = out_path + ".tmp"
    with open(tmp, "wb") as fh:
        np.savez_compressed(fh, **data)
    os.replace(tmp, out_path)
    size_mb = os.path.getsize(out_path) / 1e6
    print(f"wrote {out_path}  ({size_mb:.1f} MB)  cube{cube.shape}", flush=True)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--grid", default="/tmp/msg-2.2/data/grids/sg-demo.h5",
                   help="path to the pymsg SpecGrid .h5 (default: bundled sg-demo)")
    p.add_argument("--out", default="/tmp/spectra_grid.npz",
                   help="output .npz path (copy to host data/spectra/ after)")
    p.add_argument("--lam-min", type=float, default=3000.0)
    p.add_argument("--lam-max", type=float, default=9000.0)
    p.add_argument("--lam-step", type=float, default=2.5,
                   help="wavelength bin width in Å (teaching resolution)")
    p.add_argument("--n-teff", type=int, default=None,
                   help="override the number of (log-spaced) Teff nodes")
    a = p.parse_args(argv)
    bake(a.grid, a.out, lam_min=a.lam_min, lam_max=a.lam_max,
         lam_step=a.lam_step, n_teff=a.n_teff)
    return 0


if __name__ == "__main__":
    sys.exit(main())
