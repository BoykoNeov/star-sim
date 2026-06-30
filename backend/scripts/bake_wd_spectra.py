"""Build-time bake of the white-dwarf spectrum cube — endgame Chunk 6 (6a + 6b).

The stellar-endgame gateway's WD branch needs real cooling-DA and hot-central-star
spectra. White dwarfs live at log g 6.5–9.5 — essentially DISJOINT from the main
cube's log g 0–5 — and a DA is pure hydrogen (no [Fe/H] axis), so they cannot
splice onto the main `(Teff, [Fe/H], log g)` cube. This script bakes a **separate**
2-axis `(Teff, log g)` cube that the runtime serves at `/wd_spectrum`, a sibling of
`/spectrum` (Chunk-0 scoping in `backend/docs/msg_spectra_build_recipe.md §7–8`).

Two grids, spliced along the Teff axis (mirrors the main cube's CAP18+OSTAR splice):

  * **Koester DA (6a)** — LTE, hydrostatic, plane-parallel; Teff 5000–80000 K,
    log g 6.5–9.5/0.25 = 82×13 = 1066 models. The cooling white dwarf.
  * **TMAP hot WD / CSPN (6b)** — NLTE H+He (we take the H-rich Hemass=0 slab to
    match the DA); Teff 80000–190000 K, log g 5–9. The ~100–190 kK post-AGB central
    star (central star of a planetary nebula), which is hotter than Koester. We
    splice TMAP's nodes ABOVE Koester's 80000 K ceiling onto the hot end of the
    Teff axis, interpolated onto Koester's 6.5–9.5 log g grid (TMAP's 0.5-step log g
    nodes → the 0.25 grid; the two log g 9.25/9.5 nodes past TMAP's 9.0 ceiling clamp
    to 9.0). Optional: omit `--tmap-dir` and the bake is Koester-only (the 6a cube).

Unlike `bake_spectra.py`, this needs **no pymsg / Fortran / Docker**: both grids are
plain 2-column ASCII (λ Å, F_λ erg/cm²/s/Å), fetched by `python -m
star_sim.fetch_koester` and `python -m star_sim.fetch_tmap`. So it runs on the host
with numpy only.

Two measured gotchas the bake handles (both confirmed this build, see §8 of the recipe):

  * **TMAP λ is vacuum; Koester/main are air.** We convert TMAP vacuum→air (Morton
    2000) so the panel's x-axis and Balmer guides line up when it switches cubes.
    (The ~1.4 Å optical shift is sub-bin — hot CSPN optical spectra are nearly
    featureless continuum — but we convert for correctness anyway.)
  * **TMAP covers only 3200–25000 Å; our window starts at 3000 Å.** That 3000–3200 Å
    gap (~80 bins, ~3% of the panel) sits on the steep blue Rayleigh-Jeans rise
    toward a hot star's UV Wien peak — a flat extrapolation would flatten it into a
    visible shelf. We fill it with a **log-linear (power-law) extrapolation** of the
    model's bluest segment (flux ∝ λ^p, p ≈ −4 on the RJ tail).

  * **No ×π×10⁸ unit conversion** — the SVO ascii path already serves physical
    erg/cm²/s/Å. Measured: the TMAP/Koester optical-continuum ratio at the 80000 K /
    log g 7 overlap node is 0.98–1.08 (the NLTE↔LTE seam is already graceful), so we
    splice with NO rescale and just REPORT the measured agreement (the OSTAR splice
    precedent). The ×π×10⁸ gotcha from the scoping was for the native TheoSSA files.

Run on the host (no container) after the fetches:

    python scripts/bake_wd_spectra.py --tmap-dir data/spectra/grids/tmap
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
# the main cube are read by the same _Spectra class, so they share the version. The
# 6b TMAP splice does NOT bump it: the on-disk schema is unchanged (still a 2-axis
# Teff×log g cube — only the Teff-axis length + grid_name differ), exactly the
# OSTAR/Göttingen splice precedent; bumping would needlessly invalidate the MAIN
# cube on disk and force a Docker re-bake.
BAKE_VERSION = 1

_REPO_ROOT = Path(__file__).resolve().parents[2]
KOESTER_DIR = _REPO_ROOT / "data" / "spectra" / "grids" / "koester"
TMAP_DIR = _REPO_ROOT / "data" / "spectra" / "grids" / "tmap"
OUT_PATH = _REPO_ROOT / "data" / "spectra" / "wd_spectra_grid.npz"

# Koester's ceiling = the Koester↔TMAP splice seam. Koester supplies Teff ≤ this;
# TMAP supplies the nodes strictly above it.
_SEAM_TEFF = 80000.0

_TEFF_RE = re.compile(r"#\s*teff\s*=\s*([\d.]+)")
_LOGG_RE = re.compile(r"#\s*logg\s*=\s*([\d.]+)")


def _read_model(path: Path) -> tuple[float, float, np.ndarray, np.ndarray]:
    """Parse one Koester/TMAP ASCII model -> (teff, logg, lam[Å], flux[erg/cm²/s/Å]).

    The two grids share the same simple header convention (`# teff = …`, `# logg =
    …`) and 2-column body, so one reader serves both. TMAP's extra `# Hemass = …`
    and column-description comment lines are ignored (they match neither regex)."""
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


def _vac_to_air(lam_vac: np.ndarray) -> np.ndarray:
    """Vacuum → air wavelength conversion (Morton 2000, the IAU-standard formula,
    valid above ~2000 Å). TMAP serves vacuum λ; the cube (Koester + main) is air, so
    converting keeps the Balmer guides aligned when the panel switches cubes."""
    s2 = (1e4 / lam_vac) ** 2
    n = (1.0 + 0.0000834254 + 0.02406147 / (130.0 - s2)
         + 0.00015998 / (38.9 - s2))
    return lam_vac / n


def _extend_blue(lam: np.ndarray, flux: np.ndarray, target_min: float,
                 fit_width: float = 300.0, step: float = 20.0
                 ) -> tuple[np.ndarray, np.ndarray]:
    """Extend a model blueward to `target_min` Å with a power-law (log-linear)
    extrapolation, so a grid that starts above the bake window (TMAP, 3200 Å) still
    spans it. Fits flux ∝ λ^p on the bluest `fit_width` Å — on a hot star's optical
    Rayleigh-Jeans tail p ≈ −4, so the blue edge keeps rising instead of flattening
    into a shelf (a flat fill would visibly understate the 3000–3200 Å bins)."""
    if lam[0] <= target_min:
        return lam, flux
    seg = lam <= lam[0] + fit_width
    ll = np.log(lam[seg])
    lf = np.log(np.maximum(flux[seg], 1e-300))
    p = float(np.polyfit(ll, lf, 1)[0])     # d ln F / d ln λ
    new_lam = np.arange(target_min, lam[0], step)
    if new_lam.size == 0:
        new_lam = np.array([target_min])
    new_flux = flux[0] * (new_lam / lam[0]) ** p
    return np.concatenate([new_lam, lam]), np.concatenate([new_flux, flux])


def _bin_average(model_lam: np.ndarray, model_flux: np.ndarray,
                 lam_edges: np.ndarray) -> np.ndarray:
    """Average a high-resolution model onto the coarse bin grid (flux-conserving in
    the sense of a mean sample per bin — both grids' sub-Å sampling puts several
    points in each 2.5 Å bin, so this preserves line depth far better than
    point-sampling at bin centres would). Any bin with no sample falls back to linear
    interpolation so the cube has no gaps."""
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


def _read_grid(files: list[Path], lam_edges: np.ndarray, lam_min: float,
               lam_max: float, *, vac_to_air: bool = False,
               extend_blue_to: float | None = None
               ) -> tuple[dict[tuple[float, float], np.ndarray], list[float], list[float]]:
    """Read a set of ASCII models -> ({(teff,logg): binned_flux}, teff_nodes,
    logg_nodes). `vac_to_air`/`extend_blue_to` are the TMAP-specific preprocessing
    (Koester is already air and spans the window, so it passes neither)."""
    models: dict[tuple[float, float], np.ndarray] = {}
    teffs: set[float] = set()
    loggs: set[float] = set()
    for i, path in enumerate(files):
        teff, logg, ml, mf = _read_model(path)
        if vac_to_air:
            ml = _vac_to_air(ml)
        if extend_blue_to is not None:
            ml, mf = _extend_blue(ml, mf, extend_blue_to)
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
    print()
    return models, sorted(teffs), sorted(loggs)


def _require_rectangular(models: dict[tuple[float, float], np.ndarray],
                         teff_nodes: list[float], logg_nodes: list[float],
                         label: str) -> None:
    present = set(models.keys())
    missing = [(t, g) for t in teff_nodes for g in logg_nodes if (t, g) not in present]
    if missing:
        raise ValueError(
            f"{label} grid not rectangular: {len(present)} models but "
            f"{len(teff_nodes)}×{len(logg_nodes)} nodes; {len(missing)} missing, "
            f"e.g. {missing[:5]}"
        )


def _interp_logg(src_loggs: list[float], src_cube: np.ndarray,
                 target_loggs: np.ndarray) -> np.ndarray:
    """Linearly interpolate a (n_src_logg, n_lam) spectrum stack onto `target_loggs`,
    clamping outside the source range (so Koester's 9.25/9.5 nodes past TMAP's 9.0
    ceiling take the 9.0 spectrum). numpy-only — no scipy in this host bake."""
    src = np.asarray(src_loggs, dtype=float)
    out = np.empty((target_loggs.size, src_cube.shape[1]), dtype=src_cube.dtype)
    for i, g in enumerate(target_loggs):
        if g <= src[0]:
            out[i] = src_cube[0]
        elif g >= src[-1]:
            out[i] = src_cube[-1]
        else:
            j = int(np.searchsorted(src, g) - 1)
            w = (g - src[j]) / (src[j + 1] - src[j])
            out[i] = (1.0 - w) * src_cube[j] + w * src_cube[j + 1]
    return out


def _report_seam(koester: dict, tmap: dict, logg_nodes: np.ndarray,
                 lam: np.ndarray) -> None:
    """Measure + report the NLTE↔LTE seam agreement at the 80000 K overlap node
    (Koester LTE vs TMAP NLTE, optical-continuum mean per shared log g). We splice
    with NO rescale — this is the OSTAR-precedent validation that the seam is
    graceful, not a correction."""
    opt = (lam >= 4000) & (lam <= 7000)
    ratios = []
    for g in logg_nodes:
        kk = koester.get((_SEAM_TEFF, float(g)))
        tt = tmap.get((_SEAM_TEFF, float(g)))
        if kk is None or tt is None:
            continue
        km = float(kk[opt].mean())
        if km > 0:
            ratios.append(float(tt[opt].mean()) / km)
    if ratios:
        r = np.array(ratios)
        print(f"  seam @ {int(_SEAM_TEFF)} K (TMAP/Koester optical mean, {r.size} log g): "
              f"{r.min():.3f}-{r.max():.3f} (mean {r.mean():.3f}) -- spliced as-is, no rescale")


def bake(koester_dir: Path, out_path: Path, *, tmap_dir: Path | None,
         lam_min: float, lam_max: float, lam_step: float) -> None:
    kfiles = sorted(koester_dir.glob("koester_da_*.txt"))
    if not kfiles:
        raise SystemExit(
            f"No Koester models in {koester_dir} — run: python -m star_sim.fetch_koester"
        )

    # The SAME bin grid the main cube uses (3000–9000 Å @ 2.5 Å), so the x-axis and
    # line guides are identical when the panel switches between cubes.
    lam_edges = np.arange(lam_min, lam_max + lam_step, lam_step)
    lam_edges = lam_edges[lam_edges <= lam_max]
    lam = 0.5 * (lam_edges[:-1] + lam_edges[1:])
    n_lam = lam.size

    # --- Koester DA slab (6a): Teff 5000–80000, log g 6.5–9.5, the master log g grid.
    print(f"reading {len(kfiles)} Koester DA models from {koester_dir} ...", flush=True)
    t0 = time.time()
    koester, k_teffs, logg_nodes_list = _read_grid(kfiles, lam_edges, lam_min, lam_max)
    print(f"  ({time.time() - t0:.1f}s)")
    _require_rectangular(koester, k_teffs, logg_nodes_list, "Koester")
    logg_nodes = np.array(logg_nodes_list)
    n_g = logg_nodes.size

    teff_nodes_list = list(k_teffs)
    tmap: dict[tuple[float, float], np.ndarray] = {}
    tmap_hot_teffs: list[float] = []

    # --- TMAP hot slab (6b): Teff > 80000, spliced on (optional).
    if tmap_dir is not None:
        tfiles = sorted(tmap_dir.glob("tmap_h_*.txt"))
        if not tfiles:
            raise SystemExit(
                f"--tmap-dir {tmap_dir} has no tmap_h_*.txt — run: python -m star_sim.fetch_tmap"
            )
        print(f"reading {len(tfiles)} TMAP H-rich models from {tmap_dir} "
              f"(vacuum->air, blue-extend to {lam_min:.0f} A) ...", flush=True)
        t0 = time.time()
        tmap, t_teffs, t_loggs = _read_grid(
            tfiles, lam_edges, lam_min, lam_max,
            vac_to_air=True, extend_blue_to=lam_min)
        print(f"  ({time.time() - t0:.1f}s)")
        _require_rectangular(tmap, t_teffs, t_loggs, "TMAP")
        _report_seam(koester, tmap, logg_nodes, lam)
        # Splice only the nodes strictly ABOVE Koester's ceiling (Koester owns 80000).
        tmap_hot_teffs = [t for t in t_teffs if t > _SEAM_TEFF]
        teff_nodes_list += tmap_hot_teffs
        print(f"  splicing TMAP Teff {int(tmap_hot_teffs[0])}-{int(tmap_hot_teffs[-1])} K "
              f"({len(tmap_hot_teffs)} nodes) onto the hot end, "
              f"interp log g {t_loggs[0]}-{t_loggs[-1]} -> {logg_nodes[0]}-{logg_nodes[-1]}")

    teff_nodes = np.array(teff_nodes_list)
    n_t = teff_nodes.size
    print(f"  cube: {n_t} Teff [{teff_nodes[0]:.0f}..{teff_nodes[-1]:.0f}] x "
          f"{n_g} log g [{logg_nodes[0]}..{logg_nodes[-1]}]")

    # Assemble the cube (teff, logg, lam). Koester rows are native nodes; TMAP hot
    # rows are interpolated onto the master log g grid (clamped past TMAP's 9.0).
    cube = np.zeros((n_t, n_g, n_lam), dtype=np.float32)
    for it, t in enumerate(teff_nodes):
        if t <= _SEAM_TEFF:
            # Koester owns Teff ≤ the seam — native nodes on the master log g grid.
            for ig, g in enumerate(logg_nodes):
                cube[it, ig] = koester[(float(t), float(g))]
        else:
            # TMAP hot node: stack its native log g spectra, interpolate to the grid.
            src_loggs = sorted({g for (tt, g) in tmap if tt == t})
            src_cube = np.stack([tmap[(float(t), float(g))] for g in src_loggs])
            cube[it] = _interp_logg(src_loggs, src_cube, logg_nodes)

    assert np.isfinite(cube).all(), "non-finite flux in baked WD cube"
    n_neg = int((cube < 0).sum())
    if n_neg:
        print(f"  clamped {n_neg} negative flux bins (min was {float(cube.min()):.3g})")
        np.clip(cube, 0.0, None, out=cube)

    grid_name = "koester2-DA+TMAP-CSPN" if tmap_hot_teffs else "koester2-DA"
    keys = ["teff", "logg"]
    axis_log = [True, False]   # interpolate Teff in log10 (cool-end resolution); log g linear
    data: dict[str, np.ndarray] = {
        "bake_version": np.array(BAKE_VERSION),
        "grid_name": np.array(grid_name),
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
          f"grid={grid_name}  lam {lam[0]:.1f}-{lam[-1]:.1f} A @ {lam_step} A")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--koester-dir", default=str(KOESTER_DIR),
                   help="directory of fetched koester_da_*.txt models")
    p.add_argument("--tmap-dir", default=None,
                   help="directory of fetched tmap_h_*.txt models (the 6b hot splice); "
                        "omit for a Koester-only (6a) cube")
    p.add_argument("--out", default=str(OUT_PATH), help="output .npz path")
    p.add_argument("--lam-min", type=float, default=3000.0)
    p.add_argument("--lam-max", type=float, default=9000.0)
    p.add_argument("--lam-step", type=float, default=2.5,
                   help="wavelength bin width in Å (match the main cube)")
    a = p.parse_args(argv)
    tmap_dir = Path(a.tmap_dir) if a.tmap_dir else None
    bake(Path(a.koester_dir), Path(a.out), tmap_dir=tmap_dir,
         lam_min=a.lam_min, lam_max=a.lam_max, lam_step=a.lam_step)
    return 0


if __name__ == "__main__":
    sys.exit(main())
