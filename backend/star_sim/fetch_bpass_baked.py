"""Fetch the pre-baked BPASS coeval-population SSP cube from a GitHub Release
(the fast path — the casual-user shortcut past the ~1 GB Zenodo pair + the bake).

This backs the `#population-toggle` coeval-population overlay (`bpass.py`) on
**both** panels, so there are **two** baked cubes:

- `bpass_ssp.npz` (4.1 MB) — the SED integrated-spectrum cube. `fetch_bpass.py`'s
  recipe pulls the BPASS v2.3 solar-scaled sin+bin SSP-spectra pair (~1 GB, two
  531 MB HDF5 files) from Zenodo, and `scripts/bake_bpass_spectra.py` log-rebins
  them into it. Backs `/population`.
- `bpass_hrd.npz` (1.6 MB) — the HR-diagram number-density cube (Chunk 2).
  `scripts/bake_bpass_hrd.py` range-extracts the 26 `hrs-{sin,bin}.z*.dat` members
  from the BPASS **v2.2.1** starter-kit Zenodo zip and packs them into it. Backs
  `/population_hrd`.

This script instead pulls the **already-baked** cubes directly from a GitHub
Release — a plain HTTPS download, no Zenodo pair, no h5py, no bake step. Straight
into `data/bpass/`, exactly where `bpass.py` looks. Once present, the frontend's
population-overlay toggle lights up (its `/population_status` gate flips to
`has_grid: true` for the SED wedge, `has_hrd: true` for the HR-diagram cloud).

These are **derived artifacts** (compact rebinned/cropped cubes built from BPASS's
public models, not verbatim copies). Both source releases are under **CC-BY 4.0**
(an explicit redistribution grant — BPASS v2.3 *and* the v2.2.1 starter kit, the
same clean footing as POSYDON; see `docs/memory/star-sim-hosted-data-assets.md`).
Cite the papers on use (below).

Run once after checkout, instead of the `fetch_bpass.py` + bake recipe:

    python -m star_sim.fetch_bpass_baked
"""

from __future__ import annotations

import argparse
import sys

from ._baked_release import fetch_one
from .bpass import BPASS_DATA_DIR, GRID_FILENAME, GRID_FILENAME_HRD

RELEASE_TAG = "bpass-baked-v1"
_ASSET_BASE = f"https://github.com/BoykoNeov/star-sim/releases/download/{RELEASE_TAG}"

_ASSETS: dict[str, str] = {
    GRID_FILENAME: "ae9c944b8d564655c7341fe960953e9349cb6e3c864fe88117bf196e5aaf20ec",
    GRID_FILENAME_HRD: "02946920b9f5561602670b62ba9d2bb201e5cb2541bc77136c6c080e0a7c502a",
}


def _fetch_one(filename: str, expected_sha256: str) -> str:
    url = f"{_ASSET_BASE}/{filename}"
    return fetch_one(url, BPASS_DATA_DIR / filename, expected_sha256)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Fetch the pre-baked BPASS coeval-population SSP cube.")
    args = ap.parse_args(argv)
    del args

    print(f"Fetching pre-baked BPASS population cube from release '{RELEASE_TAG}' -> {BPASS_DATA_DIR}")
    n_ok = n_skip = 0
    for filename, digest in _ASSETS.items():
        status = _fetch_one(filename, digest)
        print(f"  {filename}: {status}")
        n_ok += status == "ok"
        n_skip += status == "skip"

    print(f"Done: {n_ok} downloaded, {n_skip} already present.")
    print("Cite Eldridge et al. 2017 (PASA 34, e058) + Stanway & Eldridge 2018 "
          "(MNRAS 479, 75) + the BPASS v2.3 release on use (CC-BY 4.0).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
