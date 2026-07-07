"""Fetch the pre-baked white-dwarf spectrum cube from a GitHub Release (the fast path).

The white-dwarf endgame's `/wd_spectrum` sibling is built from **two** raw grids —
Koester DA (`fetch_koester.py`, the cool/mid cooling track) spliced with TMAP
(`fetch_tmap.py`, the hot post-AGB/CSPN end) — via `scripts/bake_wd_spectra.py`
into one cube, `data/spectra/wd_spectra_grid.npz`. That original recipe means two
separate multi-hundred-MB SVO fetches plus a host-side bake step just to light up
one panel.

This script instead pulls the **already-baked** cube directly from a GitHub
Release — a plain HTTPS download, no SVO SSAP queries, no bake step. Straight
into `data/spectra/wd_spectra_grid.npz`, exactly where `spectra.py` looks for it.

This is a **derived artifact** (a compact resampled cube built from Koester's and
TMAP's public model spectra, not a verbatim copy) hosted under this project's
redistribution call, not an explicit license grant from either source — see
`docs/memory/star-sim-hosted-data-assets.md`. Cite both papers on use (below).

Run once after checkout, instead of the `fetch_koester.py` + `fetch_tmap.py` recipe:

    python -m star_sim.fetch_koester_baked
"""

from __future__ import annotations

import argparse
import sys

from ._baked_release import fetch_one
from .spectra import SPECTRA_DATA_DIR, WD_GRID_FILENAME

RELEASE_TAG = "koester-baked-v1"
_ASSET_BASE = f"https://github.com/BoykoNeov/star-sim/releases/download/{RELEASE_TAG}"

_ASSETS: dict[str, str] = {
    WD_GRID_FILENAME: "f933914077b6e72b82db2c3afba9d936ce1ed7deb3320f96bcd66d1fe854877b",
}


def _fetch_one(filename: str, expected_sha256: str) -> str:
    url = f"{_ASSET_BASE}/{filename}"
    return fetch_one(url, SPECTRA_DATA_DIR / filename, expected_sha256)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Fetch the pre-baked white-dwarf (Koester DA + TMAP) spectrum cube."
    )
    args = ap.parse_args(argv)
    del args

    print(f"Fetching pre-baked WD spectrum cube from release '{RELEASE_TAG}' -> {SPECTRA_DATA_DIR}")
    n_ok = n_skip = 0
    for filename, digest in _ASSETS.items():
        status = _fetch_one(filename, digest)
        print(f"  {filename}: {status}")
        n_ok += status == "ok"
        n_skip += status == "skip"

    print(f"Done: {n_ok} downloaded, {n_skip} already present.")
    print("Cite Koester (2010), Mem.S.A.It. 81, 921 (DA models) and "
          "Werner et al. (2003) / Rauch et al. (2003) (TMAP) on use.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
