"""Fetch the pre-baked BPASS coeval-population SSP cube from a GitHub Release
(the fast path — the casual-user shortcut past the ~1 GB Zenodo pair + the bake).

`fetch_bpass.py`'s recipe pulls the BPASS v2.3 solar-scaled sin+bin SSP-spectra
pair (~1 GB, two 531 MB HDF5 files) from Zenodo, and `scripts/bake_bpass_spectra.py`
log-rebins them into one compact cube, `data/bpass/bpass_ssp.npz` (4.1 MB), backing
the `#population-toggle` coeval-population SED overlay (`bpass.py` / `/population`).

This script instead pulls the **already-baked** cube directly from a GitHub
Release — a plain HTTPS download, no Zenodo pair, no h5py, no bake step. Straight
into `data/bpass/bpass_ssp.npz`, exactly where `bpass.py` looks for it. Once
present, the frontend's population-overlay toggle lights up (its
`/population_status` gate flips to `has_grid: true`).

This is a **derived artifact** (a compact log-rebinned cube built from BPASS's
public model spectra, not a verbatim copy). BPASS v2.3 is released under
**CC-BY 4.0** (an explicit redistribution grant — the same clean footing as
POSYDON; see `docs/memory/star-sim-hosted-data-assets.md`). Cite the papers on
use (below).

Run once after checkout, instead of the `fetch_bpass.py` + bake recipe:

    python -m star_sim.fetch_bpass_baked
"""

from __future__ import annotations

import argparse
import sys

from ._baked_release import fetch_one
from .bpass import BPASS_DATA_DIR, GRID_FILENAME

RELEASE_TAG = "bpass-baked-v1"
_ASSET_BASE = f"https://github.com/BoykoNeov/star-sim/releases/download/{RELEASE_TAG}"

_ASSETS: dict[str, str] = {
    GRID_FILENAME: "ae9c944b8d564655c7341fe960953e9349cb6e3c864fe88117bf196e5aaf20ec",
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
