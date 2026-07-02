"""Build-time bake of the [alpha/Fe] spectrum cube (atlas Tier B — thick-disk/halo).

MIST evolution is solar-scaled, so [alpha/Fe] is a SPECTRUM-ONLY axis: at fixed
[Fe/H] a higher [alpha/Fe] deepens the O/Mg/Si/Ca/Ti lines (+ molecular TiO) without
moving the star's track. The matched-pair grid ([alpha/Fe] = 0.0 AND +0.4) is Coelho
2014 (SVO `coelho_highres`), fetched by `python -m star_sim.fetch_coelho`.

This bakes a SEPARATE 4-axis `(Teff, log g, [Fe/H], [alpha/Fe])` cube that the runtime
serves at `/alpha_spectrum` — a sibling of `/spectrum` and `/wd_spectrum`. It uses the
same axis-generic `.npz` schema as every other cube, so the runtime reuses the
`_Spectra` class verbatim (a 4-D grid instead of 3-D). Gate 1 (2026-07-02) measured
alpha DEAD >~12000 K, so the cube is the COOL SUBSET only (default Teff <= 10000 from
the fetch); the panel hands off to the main cube for hotter stars (mirroring the
WD-gravity cube switch). Like the WD/WR cubes, this needs NO pymsg/Fortran/Docker —
Coelho is plain 2-col ASCII, so this runs on the host with numpy only.

Build decision (advisor-settled): the alpha toggle flips between TWO Coelho baselines
(a=0 <-> a=0.4), both from THIS cube — never Coelho-alpha vs a CAP18 solar spectrum
(the atmosphere-code seam would masquerade as the alpha signal). So the alpha=0 slab
is the baseline the panel shows when the toggle is OFF for a star routed to this cube.

Run on the host after the fetch:

    python -m star_sim.fetch_coelho
    python scripts/bake_alpha_spectra.py   # -> data/spectra/alpha_spectra_grid.npz
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import time
from pathlib import Path

import numpy as np

# Must match star_sim/spectra.py's BAKE_VERSION. This is a NEW separate cube file, so
# adding it does NOT invalidate the main/WD/WR cubes — but it shares the version
# discipline (read by the same _Spectra class), so keep it in lockstep. Adding this
# cube did not bump the version (a new file, the WD-cube precedent).
BAKE_VERSION = 1

_REPO_ROOT = Path(__file__).resolve().parents[2]
COELHO_DIR = _REPO_ROOT / "data" / "spectra" / "grids" / "coelho"
OUT_PATH = _REPO_ROOT / "data" / "spectra" / "alpha_spectra_grid.npz"

# Coelho headers: "# teff = 5750 K", "# logg = 4.5 log(cm/s2)", "# meta = -0.5 ...",
# "# afe = 0 ...". meta/afe can be negative, so the value regex must allow a sign.
_NUM = r"([-+]?\d+(?:\.\d+)?)"
_TEFF_RE = re.compile(rf"#\s*teff\s*=\s*{_NUM}")
_LOGG_RE = re.compile(rf"#\s*logg\s*=\s*{_NUM}")
_META_RE = re.compile(rf"#\s*meta\s*=\s*{_NUM}")
_AFE_RE = re.compile(rf"#\s*afe\s*=\s*{_NUM}")


def _read_model(path: Path) -> tuple[float, float, float, float, np.ndarray, np.ndarray]:
    """Parse one Coelho ASCII model -> (teff, logg, meta, afe, lam[A], flux)."""
    teff = logg = meta = afe = None
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
                elif (m := _META_RE.match(s)):
                    meta = float(m.group(1))
                elif (m := _AFE_RE.match(s)):
                    afe = float(m.group(1))
                continue
            parts = s.split()
            if len(parts) >= 2:
                lam.append(float(parts[0]))
                flux.append(float(parts[1]))
    if None in (teff, logg, meta, afe):
        raise ValueError(f"{path.name}: missing teff/logg/meta/afe header")
    return teff, logg, meta, afe, np.asarray(lam), np.asarray(flux)


def _bin_average(model_lam: np.ndarray, model_flux: np.ndarray,
                 lam_edges: np.ndarray) -> np.ndarray:
    """Average a high-resolution model onto the coarse bin grid (mean sample per bin —
    the same flux-per-bin content the main/WD cubes store; preserves line depth far
    better than point-sampling at bin centres). Empty bins fall back to interpolation."""
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


def _clamp_fill_logg(present: dict[float, np.ndarray], logg_nodes: list[float]
                     ) -> dict[float, np.ndarray]:
    """Fill a (single teff/feh/afe) log g row onto the full log g grid by clamping to
    the nearest PRESENT log g (Coelho's grid is ragged — cool giants at very low log g,
    or hot dwarfs at very high log g, aren't all computed). Clamp keeps Teff/[Fe/H]/alpha
    exact and only substitutes gravity at the ragged edges — the WD cube's `_interp_logg`
    clamp precedent. `present` maps log g -> binned flux for the ones that exist."""
    have = sorted(present)
    out: dict[float, np.ndarray] = {}
    for g in logg_nodes:
        if g in present:
            out[g] = present[g]
        elif g <= have[0]:
            out[g] = present[have[0]]
        elif g >= have[-1]:
            out[g] = present[have[-1]]
        else:
            # interior gap: linear-interpolate between the bracketing present nodes
            j = int(np.searchsorted(have, g))
            lo, hi = have[j - 1], have[j]
            w = (g - lo) / (hi - lo)
            out[g] = (1.0 - w) * present[lo] + w * present[hi]
    return out


def bake(coelho_dir: Path, out_path: Path, *, lam_min: float, lam_max: float,
         lam_step: float) -> None:
    files = sorted(coelho_dir.glob("coelho_*.txt"))
    if not files:
        raise SystemExit(
            f"No Coelho models in {coelho_dir} - run: python -m star_sim.fetch_coelho")

    lam_edges = np.arange(lam_min, lam_max + lam_step, lam_step)
    lam_edges = lam_edges[lam_edges <= lam_max]
    lam = 0.5 * (lam_edges[:-1] + lam_edges[1:])
    n_lam = lam.size

    print(f"reading {len(files)} Coelho models from {coelho_dir} ...", flush=True)
    t0 = time.time()
    # models[(feh, afe)][teff][logg] = binned flux
    models: dict[tuple[float, float], dict[float, dict[float, np.ndarray]]] = {}
    for i, path in enumerate(files):
        teff, logg, meta, afe, ml, mf = _read_model(path)
        if not (ml[0] <= lam_edges[0] and ml[-1] >= lam_edges[-1]):
            raise ValueError(
                f"{path.name}: lam coverage {ml[0]:.0f}-{ml[-1]:.0f} A does not span "
                f"the {lam_min:.0f}-{lam_max:.0f} A bake window")
        binned = _bin_average(ml, mf, lam_edges).astype(np.float32)
        models.setdefault((meta, afe), {}).setdefault(teff, {})[logg] = binned
        if (i + 1) % 100 == 0 or i + 1 == len(files):
            print(f"\r  {i + 1}/{len(files)}", end="", flush=True)
    print(f"\n  ({time.time() - t0:.1f}s)")

    afe_nodes = sorted({a for (_, a) in models})
    feh_nodes = sorted({f for (f, _) in models})
    if afe_nodes != [0.0, 0.4]:
        print(f"  WARNING: expected [alpha/Fe] {{0.0, 0.4}}, got {afe_nodes}")
    # Teff/log g nodes = the INTERSECTION present across every (feh, afe) slab, so the
    # cube is rectangular before the log g clamp-fill runs (a toggle/[Fe/H] move must
    # land on a real matched node, never invent one).
    teff_sets = [set(models[k]) for k in models]
    teff_nodes = sorted(set.intersection(*teff_sets))
    logg_set: set[float] = set()
    for k in models:
        for t in models[k]:
            logg_set |= set(models[k][t])
    logg_nodes = sorted(logg_set)
    n_t, n_g, n_f, n_a = len(teff_nodes), len(logg_nodes), len(feh_nodes), len(afe_nodes)
    print(f"  cube: {n_t} Teff [{teff_nodes[0]:.0f}..{teff_nodes[-1]:.0f}] x "
          f"{n_g} log g [{logg_nodes[0]}..{logg_nodes[-1]}] x "
          f"{n_f} [Fe/H] {feh_nodes} x {n_a} [alpha/Fe] {afe_nodes}")

    # Assemble (teff, logg, feh, afe, lam), clamp-filling ragged log g per slab.
    cube = np.zeros((n_t, n_g, n_f, n_a, n_lam), dtype=np.float32)
    n_fill = 0
    for ifeh, feh in enumerate(feh_nodes):
        for iafe, afe in enumerate(afe_nodes):
            slab = models.get((feh, afe), {})
            for it, t in enumerate(teff_nodes):
                present = slab.get(t, {})
                if not present:
                    raise ValueError(f"no models at Teff {t}, [Fe/H] {feh}, [a/Fe] {afe}")
                n_fill += n_g - len(present)
                filled = _clamp_fill_logg(present, logg_nodes)
                for ig, g in enumerate(logg_nodes):
                    cube[it, ig, ifeh, iafe] = filled[g]
    print(f"  clamp-filled {n_fill} ragged (Teff,log g) cells "
          f"(of {n_t * n_g * n_f * n_a})")

    assert np.isfinite(cube).all(), "non-finite flux in baked alpha cube"
    n_neg = int((cube < 0).sum())
    if n_neg:
        print(f"  clamped {n_neg} negative flux bins (min was {float(cube.min()):.3g})")
        np.clip(cube, 0.0, None, out=cube)

    grid_name = "Coelho2014-highres-alpha"
    data: dict[str, np.ndarray] = {
        "bake_version": np.array(BAKE_VERSION),
        "grid_name": np.array(grid_name),
        "flux_unit": np.array("erg/cm^2/s/Angstrom"),
        "axis_keys": np.array(["teff", "logg", "feh", "afe"]),
        "axis_labels": np.array(["Teff", "log(g)", "[Fe/H]", "[alpha/Fe]"]),
        "axis_log": np.array([True, False, False, False], dtype=bool),
        "lam": lam.astype(np.float64),
        "flux": cube,
        "axis_teff": np.asarray(teff_nodes, dtype=np.float64),
        "axis_logg": np.asarray(logg_nodes, dtype=np.float64),
        "axis_feh": np.asarray(feh_nodes, dtype=np.float64),
        "axis_afe": np.asarray(afe_nodes, dtype=np.float64),
    }
    out_path = Path(os.path.abspath(out_path))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(".npz.tmp")
    with open(tmp, "wb") as fh:
        np.savez_compressed(fh, **data)
    os.replace(tmp, out_path)
    size_mb = os.path.getsize(out_path) / 1e6
    print(f"wrote {out_path}  ({size_mb:.1f} MB)  cube{cube.shape}  grid={grid_name}  "
          f"lam {lam[0]:.1f}-{lam[-1]:.1f} A @ {lam_step} A")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--coelho-dir", default=str(COELHO_DIR))
    p.add_argument("--out", default=str(OUT_PATH))
    p.add_argument("--lam-min", type=float, default=3000.0)
    p.add_argument("--lam-max", type=float, default=9000.0)
    p.add_argument("--lam-step", type=float, default=2.5,
                   help="wavelength bin width in A (match the main cube)")
    a = p.parse_args(argv)
    bake(Path(a.coelho_dir), Path(a.out),
         lam_min=a.lam_min, lam_max=a.lam_max, lam_step=a.lam_step)
    return 0


if __name__ == "__main__":
    sys.exit(main())
