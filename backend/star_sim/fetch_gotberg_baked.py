"""Fetch the pre-baked binary-stripped-star spectrum cube from a GitHub Release
(the fast path).

`fetch_gotberg.py` is a **manual handoff, not an automated fetch**: CDS bot-blocks
its VizieR catalog page and the legacy FTP host has an expired TLS cert, so the
~674 MB Götberg (2018) SED/spectra tarball has to be downloaded in a browser and
extracted by hand before `scripts/bake_stripped_spectra.py` can fold it into
`data/spectra/stripped_spectra_grid.npz` (the cube backing `/stripped_spectrum`).

This script instead pulls the **already-baked** cube directly from a GitHub
Release — a plain HTTPS download, no browser, no manual extraction, no bake step.
Straight into `data/spectra/stripped_spectra_grid.npz`, exactly where `spectra.py`
looks for it.

This is a **derived artifact** (a compact continuum-normalized cube built from
Götberg's public model spectra, not a verbatim copy) hosted under this project's
redistribution call, not an explicit license grant from the paper — see
`docs/memory/star-sim-hosted-data-assets.md`. Cite the paper on use (below).

Run once after checkout, instead of the `fetch_gotberg.py` recipe:

    python -m star_sim.fetch_gotberg_baked
"""

from __future__ import annotations

import argparse
import sys

from ._baked_release import fetch_one
from .spectra import SPECTRA_DATA_DIR, STRIPPED_GRID_FILENAME

RELEASE_TAG = "gotberg-baked-v1"
_ASSET_BASE = f"https://github.com/BoykoNeov/star-sim/releases/download/{RELEASE_TAG}"

_ASSETS: dict[str, str] = {
    STRIPPED_GRID_FILENAME: "62f5f57145b9c251d4b3a221365927991c4699ea1ba2f9aa123183bc395851d3",
}


def _fetch_one(filename: str, expected_sha256: str) -> str:
    url = f"{_ASSET_BASE}/{filename}"
    return fetch_one(url, SPECTRA_DATA_DIR / filename, expected_sha256)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Fetch the pre-baked Götberg binary-stripped-star spectrum cube."
    )
    args = ap.parse_args(argv)
    del args

    print(f"Fetching pre-baked stripped-star spectrum cube from release "
          f"'{RELEASE_TAG}' -> {SPECTRA_DATA_DIR}")
    n_ok = n_skip = 0
    for filename, digest in _ASSETS.items():
        status = _fetch_one(filename, digest)
        print(f"  {filename}: {status}")
        n_ok += status == "ok"
        n_skip += status == "skip"

    print(f"Done: {n_ok} downloaded, {n_skip} already present.")
    print("Cite Götberg, Justham, de Mink et al. (2018), A&A 615, A78 on use.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
