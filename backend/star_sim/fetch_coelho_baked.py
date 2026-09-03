"""Fetch the pre-baked [alpha/Fe] spectrum cube from a GitHub Release (the fast path).

`fetch_coelho.py`'s recipe downloads Coelho (2014) high-resolution model spectra
from the SVO Theoretical Spectra Server (the matched alpha=0.0/+0.4 pair across
Teff/logg/[Fe/H], ~8-17 GB depending on how much of the [Fe/H] axis you fetch), and
`scripts/bake_alpha_spectra.py` resamples them into one cube,
`data/spectra/alpha_spectra_grid.npz`, backing the `#alpha-toggle` spectrum what-if.

This script instead pulls the **already-baked** cube directly from a GitHub
Release — a plain HTTPS download, no SVO SSAP queries, no bake step. Straight
into `data/spectra/alpha_spectra_grid.npz`, exactly where `spectra.py` looks for it.

This is a **derived artifact** (a compact resampled cube built from Coelho's public
model spectra, not a verbatim copy) hosted under this project's redistribution
call, not an explicit license grant from Coelho (2014) — see
`docs/memory/star-sim-hosted-data-assets.md`. Cite the paper on use (below).

Run once after checkout, instead of the `fetch_coelho.py` recipe:

    python -m star_sim.fetch_coelho_baked
"""

from __future__ import annotations

import sys

from ._fetch import parse_no_args, run
from .spectra import ALPHA_GRID_FILENAME, SPECTRA_DATA_DIR

RELEASE_TAG = "coelho-baked-v1"

_ASSETS: dict[str, str] = {
    ALPHA_GRID_FILENAME: "7a0f5f5f302115e644e1601feb5851e56c52b29380665540c49b2c4bc09614f2",
}


def main(argv: list[str] | None = None) -> int:
    parse_no_args("Fetch the pre-baked Coelho [alpha/Fe] spectrum cube.", argv)
    return run(
        RELEASE_TAG,
        _ASSETS,
        what="pre-baked [alpha/Fe] spectrum cube",
        dest_root=SPECTRA_DATA_DIR,
        citation="Cite Coelho (2014), MNRAS 440, 1027 on use.",
    )


if __name__ == "__main__":
    sys.exit(main())
