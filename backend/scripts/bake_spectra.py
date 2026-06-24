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

An optional **hot-grid splice** (``--hot-grid``) extends the Teff axis past the
primary grid's ceiling. CAP18 stops at 30000 K; splicing OSTAR2002 (a TLUSTY
O-star grid, 27500–55000 K) appends log-spaced Teff nodes up to 55000 K and
samples OSTAR for those hot nodes. The TLUSTY grids carry metallicity as the
*linear* ratio ``Z/Zo`` rather than CAP18's logarithmic ``[Fe/H]``, so we sample
them via ``Z/Zo = 10**[Fe/H]`` (clamped to the hot grid's range) and clamp log g
to the hot grid's narrower span. The cube stays one regular ``(teff, feh, logg,
lam)`` block — the runtime is unchanged (only the Teff axis is longer).

Run inside the container (env per the recipe), e.g.:

    python bake_spectra.py --grid /tmp/sg-CAP18-coarse.h5 \
                           --hot-grid /tmp/sg-OSTAR2002-low.h5 \
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


def _append_hot_teff(cool: np.ndarray, hi_hot: float) -> np.ndarray:
    """Extend a log-spaced Teff axis up to `hi_hot` by APPENDING nodes that
    continue the cool axis' own log-step — never re-spreading the cool nodes.

    The cool axis (e.g. CAP18's 96 log-spaced nodes over 3500–30000 K) is tuned
    for cool-end line resolution; bumping its `hi` to 55000 K would re-`geomspace`
    those 96 nodes over the wider range and coarsen the cool end. Instead we keep
    `cool` exactly and append `n_hot` nodes at the same log-spacing, snapping the
    last to `hi_hot` so the grid ceiling is a real node.
    """
    if hi_hot <= cool[-1]:
        return cool
    logstep = (np.log(cool[-1]) - np.log(cool[0])) / (cool.size - 1)
    n_hot = int(np.ceil((np.log(hi_hot) - np.log(cool[-1])) / logstep))
    hot = np.exp(np.log(cool[-1]) + logstep * np.arange(1, n_hot + 1))
    hot[-1] = hi_hot
    return np.concatenate([cool, hot])


def _fill_voids_along(cube: np.ndarray, valid: np.ndarray, logg_axis: int,
                      teff_axis: int | None = None) -> tuple[int, int, int]:
    """Fill void spectra in-place, preserving the dominant Teff axis as far as
    possible. Three passes, each strictly more permissive than the last:

      1. **along log g** at fixed other params — the voids are a contiguous
         high-log g block, so this preserves *both* Teff and metallicity exactly.
      2. **same-Teff** nearest valid (only if `teff_axis` is given) — for a whole
         log g line that was *entirely* void (e.g. an extreme metal-poor hot O
         star, where OSTAR has no model at any sampled gravity), fill from the
         nearest valid point *at the same Teff*. This clamps metallicity but keeps
         the temperature exact — a 40000 K spectrum stays a 40000 K spectrum, never
         the 30000 K cool-grid neighbour a Teff-crossing nearest-neighbour would
         pull (the spliced hot block makes this case real; the single-grid cool
         block never hits it).
      3. **global fallback** nearest valid over the full param space — a last
         resort that *can* cross Teff; should be 0 in practice (every Teff slice
         has some valid model). Logged so any silent Teff-crossing is visible.

    Returns (n_filled_along_logg, n_filled_same_teff, n_filled_fallback).
    """
    param_shape = valid.shape
    n_logg = param_shape[logg_axis]
    scale = np.array(param_shape, dtype=float)
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

    # Pass 2: same-Teff fill (preserve the dominant Teff axis exactly).
    filled_same_teff = 0
    if teff_axis is not None:
        valid_idx = np.argwhere(valid)               # snapshot after pass 1
        for vi in np.argwhere(~valid):
            same_t = valid_idx[valid_idx[:, teff_axis] == vi[teff_axis]]
            if same_t.size == 0:
                continue                              # no model at this Teff at all
            d = ((same_t - vi) / scale) ** 2
            cube[tuple(vi)] = cube[tuple(same_t[d.sum(axis=1).argmin()])]
            valid[tuple(vi)] = True
            filled_same_teff += 1

    # Pass 3: global fallback (can cross Teff — a last resort; expected to be 0).
    filled_fallback = 0
    remaining = np.argwhere(~valid)
    if remaining.size:
        valid_idx = np.argwhere(valid)
        for vi in remaining:
            d = ((valid_idx - vi) / scale) ** 2
            cube[tuple(vi)] = cube[tuple(valid_idx[d.sum(axis=1).argmin()])]
            valid[tuple(vi)] = True
            filled_fallback += 1

    return filled_logg, filled_same_teff, filled_fallback


def _hot_grid_info(hg, hot_grid_path: str) -> dict:
    """Locate a hot grid's (Teff, metallicity, log g) axis labels + bounds.

    The TLUSTY hot grids (OSTAR2002 / BSTAR2006) label metallicity as the LINEAR
    ratio ``Z/Zo`` (0…2), not CAP18's logarithmic ``[Fe/H]``. We sample them by
    converting ``[Fe/H] -> Z/Zo = 10**[Fe/H]`` (clamped to the grid's range) and
    clamping log g to the grid's narrower range (hot models live at high gravity);
    Teff is shared. The flat clamp below the grid's log g floor at hot Teff is the
    honest edge (a hot supergiant is off-grid), same spirit as void-fill-along-logg.

    The ``Z/Zo`` floor is the grid's smallest *positive* node (OSTAR: 0.001 =
    [Fe/H]=−3), NOT its 0.0 (metal-free) node: a query between 0.0 and 0.001 needs
    the metal-free bracket, which is masked at hot/high-gravity points, so MSG
    raises a `ValueError('invalid argument')` (a partial-cell void) rather than the
    clean `LookupError` we fill. Flooring at the smallest metal node avoids that
    cliff — and [Fe/H]<−3 is below any real star, where metals barely touch a hot
    O-star's optical spectrum anyway.
    """
    import h5py

    labels = list(hg.axis_labels)
    teff_l = next(l for l in labels if _canon(l) == "teff")
    logg_l = next(l for l in labels if _canon(l) == "logg")
    z_l = next(l for l in labels if _canon(l) not in ("teff", "logg"))  # Z/Zo

    # Smallest positive metallicity node (read from the grid's own axis values).
    z_floor = float(hg.axis_x_min[z_l])
    with h5py.File(hot_grid_path, "r") as f:
        vg = f["vgrid"]
        for ax in vg:
            grp = vg[ax]
            if hasattr(grp, "attrs") and grp.attrs.get("label", b"").decode() == z_l:
                nodes = np.asarray(grp["x"])
                pos = nodes[nodes > 0]
                if pos.size:
                    z_floor = float(pos.min())
                break

    return {
        "teff_l": teff_l, "logg_l": logg_l, "z_l": z_l,
        "teff_max": float(hg.axis_x_max[teff_l]),
        "z_min": z_floor, "z_max": float(hg.axis_x_max[z_l]),
        "g_min": float(hg.axis_x_min[logg_l]), "g_max": float(hg.axis_x_max[logg_l]),
    }


def bake(grid_path: str, out_path: str, *, lam_min: float, lam_max: float,
         lam_step: float, n_teff: int | None, hot_grid_path: str | None = None) -> None:
    import pymsg  # imported here so `--help` works outside the container

    sg = pymsg.SpecGrid(grid_path)
    labels = list(sg.axis_labels)
    keys = [_canon(l) for l in labels]
    print(f"grid: {os.path.basename(grid_path)}  axes={labels} -> {keys}", flush=True)

    if n_teff is not None and "teff" in keys:
        _AXIS_PLAN["teff"]["n"] = n_teff

    # Optional hot-grid splice: OSTAR2002 extends Teff past the primary grid's
    # ceiling (CAP18 stops at 30000 K; the spliced axis reaches OSTAR's 55000 K).
    hg = None
    hot = None
    cool_teff_max = float(sg.axis_x_max[next(l for l in labels if _canon(l) == "teff")]) \
        if "teff" in keys else None
    if hot_grid_path is not None:
        hg = pymsg.SpecGrid(hot_grid_path)
        hot = _hot_grid_info(hg, hot_grid_path)
        print(f"hot grid: {os.path.basename(hot_grid_path)}  axes={list(hg.axis_labels)} "
              f"(Teff -> {hot['teff_max']:.0f} K, {hot['z_l']} {hot['z_min']}..{hot['z_max']}, "
              f"log g {hot['g_min']}..{hot['g_max']})", flush=True)

    # Build our regular axes over the grid's own bounds; extend Teff if splicing.
    axes: list[np.ndarray] = []
    axis_log: list[bool] = []
    for label, key in zip(labels, keys):
        lo = float(sg.axis_x_min[label])
        hi = float(sg.axis_x_max[label])
        nodes = _build_axis(key, lo, hi)
        if key == "teff" and hot is not None:
            nodes = _append_hot_teff(nodes, hot["teff_max"])
        axes.append(nodes)
        axis_log.append(_AXIS_PLAN.get(key, _AXIS_PLAN_DEFAULT)["log"])
        print(f"  axis {key}: {nodes.size} nodes [{nodes[0]:.4g} .. {nodes[-1]:.4g}]"
              f"{' (log-spaced)' if axis_log[-1] else ''}", flush=True)

    teff_i = keys.index("teff") if "teff" in keys else None
    feh_i = keys.index("feh") if "feh" in keys else None
    logg_i = keys.index("logg") if "logg" in keys else None

    # Wavelength bins: clamp to BOTH grids' coverage; store bin CENTRES.
    grid_lam_min = max(float(np.ceil(sg.lam_min)),
                       float(np.ceil(hg.lam_min)) if hg is not None else -np.inf)
    grid_lam_max = min(float(np.floor(sg.lam_max)),
                       float(np.floor(hg.lam_max)) if hg is not None else np.inf)
    lo = max(lam_min, grid_lam_min)
    hi = min(lam_max, grid_lam_max)
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
    n_hot_nodes = 0
    for idx in np.ndindex(param_shape):
        teff_val = float(axes[teff_i][idx[teff_i]]) if teff_i is not None else None
        if hot is not None and teff_val is not None and teff_val > cool_teff_max + 1e-6:
            # Sample the hot grid: translate [Fe/H] -> Z/Zo, clamp log g.
            feh_val = float(axes[feh_i][idx[feh_i]]) if feh_i is not None else 0.0
            logg_val = float(axes[logg_i][idx[logg_i]]) if logg_i is not None else 4.0
            x = {
                hot["teff_l"]: teff_val,
                hot["z_l"]: min(max(10.0 ** feh_val, hot["z_min"]), hot["z_max"]),
                hot["logg_l"]: min(max(logg_val, hot["g_min"]), hot["g_max"]),
            }
            grid = hg
            n_hot_nodes += 1
        else:
            x = {label: float(axes[i][idx[i]]) for i, label in enumerate(labels)}
            grid = sg
        try:
            f = grid.flux(x=x, z=0.0, lam=lam_edges)
            cube[idx] = np.asarray(f, dtype=np.float32)
            valid[idx] = True
        except LookupError:
            n_void += 1  # a grid void; filled below
    print(f"    done in {time.time() - t0:.1f}s; {n_void} voids ({100*n_void/n_nodes:.1f}%)"
          f"{f'; {n_hot_nodes} nodes from hot grid' if hot is not None else ''}",
          flush=True)

    logg_axis = keys.index("logg") if "logg" in keys else None
    if n_void:
        if logg_axis is None:
            raise RuntimeError("grid has voids but no log g axis to fill along")
        fl, ft, ff = _fill_voids_along(cube, valid, logg_axis, teff_axis=teff_i)
        print(f"    void-fill: {fl} along log g, {ft} same-Teff, "
              f"{ff} fallback nearest-neighbour", flush=True)
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
    grid_name = os.path.basename(grid_path)
    if hot_grid_path is not None:
        grid_name = f"{grid_name}+{os.path.basename(hot_grid_path)}"
    data: dict[str, np.ndarray] = {
        "bake_version": np.array(BAKE_VERSION),
        "grid_name": np.array(grid_name),
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
    p.add_argument("--hot-grid", default=None,
                   help="optional hot grid (e.g. sg-OSTAR2002-low.h5) spliced onto "
                        "the Teff axis above the primary grid's ceiling, extending "
                        ">30000 K coverage. Its linear Z/Zo axis is sampled via "
                        "Z/Zo=10**[Fe/H]; log g is clamped to the hot grid's range.")
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
         lam_step=a.lam_step, n_teff=a.n_teff, hot_grid_path=a.hot_grid)
    return 0


if __name__ == "__main__":
    sys.exit(main())
