"""Fetch the pre-baked Wolf-Rayet spectrum cube from a GitHub Release (the fast path).

`fetch_powr.py`'s recipe downloads PoWR's per-grid tarballs (Galactic WNE/WNL/WC by
default, more with `--grids all`) and `scripts/bake_wr_spectra.py` folds them into
one flat-node cube, `data/spectra/wr_spectra_grid.npz`, keyed on the WR axes (T*, Rt)
that back the `/wr_spectrum` endgame panel.

This script instead pulls the **already-baked** cube directly from a GitHub
Release — a plain HTTPS download, no PoWR tarball fetch, no bake step. Straight
into `data/spectra/wr_spectra_grid.npz`, exactly where `spectra.py` looks for it.

This is a **derived artifact** (a compact resampled cube built from PoWR's public
model spectra, not a verbatim copy) hosted under this project's redistribution
call, not an explicit license grant from PoWR — see
`docs/memory/star-sim-hosted-data-assets.md`. Cite the PoWR papers on use (below).

Run once after checkout, instead of the `fetch_powr.py` recipe:

    python -m star_sim.fetch_powr_baked
"""

from __future__ import annotations

import sys

from ._fetch import parse_no_args, run
from .spectra import SPECTRA_DATA_DIR, WR_GRID_FILENAME

RELEASE_TAG = "powr-baked-v1"

_ASSETS: dict[str, str] = {
    WR_GRID_FILENAME: "d1b92a413b2c698c786b273b8d2b0d9fdc0064155c49d4ccce85490ffc0ef9c9",
}


def main(argv: list[str] | None = None) -> int:
    parse_no_args("Fetch the pre-baked PoWR Wolf-Rayet spectrum cube.", argv)
    return run(
        RELEASE_TAG,
        _ASSETS,
        what="pre-baked WR spectrum cube",
        dest_root=SPECTRA_DATA_DIR,
        citation="Cite Hamann & Gräfener (2004), A&A 427, 697; Hamann+ (2006), A&A 457, 1015; "
        "Sander+ (2012), A&A 540, A144 (WC); Todt+ (2015), A&A 579, A75 (WN) on use.",
    )


if __name__ == "__main__":
    sys.exit(main())
