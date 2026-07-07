"""Fetch pre-baked POSYDON binary grids from a GitHub Release (the fast path).

`fetch_posydon.py`'s recipe is the *original* path: download a ~10 GB raw grid
tarball per metallicity from Zenodo, extract it (another few GB), then run
`scripts/bake_posydon.py` yourself to produce a compact `.npz`. That's the right
path if you want to bake a *new* metallicity — but for everyone else it's a lot
of manual work just to get a feature working.

This script instead pulls the **already-baked** `.npz` file(s) directly from a
GitHub Release on this repo — a plain HTTPS download, no Zenodo, no h5py, no
`bake_posydon.py` run required. Straight into `data/posydon/baked/`, exactly
where `posydon.py` looks for them (`BAKED_DIR.glob("*.npz")` — no other wiring
needed).

These are **derived artifacts, not the raw POSYDON data**: POSYDON Data Release 2
(Fragos et al. 2023, ApJS 264, 45; Andrews et al. 2024; Zenodo DOI
10.5281/zenodo.15194708) is **CC-BY**, so redistributing a baked derivative with
attribution is within its terms (unlike the other fetch scripts in this project —
MIST/Koester/TMAP/PoWR/Coelho — none of which carry an explicit redistribution
grant, so none of them are mirrored this way).

Run once after checkout, instead of the `fetch_posydon.py` recipe:

    python -m star_sim.fetch_posydon_baked
"""

from __future__ import annotations

import argparse
import sys

from ._baked_release import fetch_one
from .posydon import BAKED_DIR  # single source of truth for where baked grids live

RELEASE_TAG = "posydon-baked-v1"
_ASSET_BASE = f"https://github.com/BoykoNeov/star-sim/releases/download/{RELEASE_TAG}"

# filename -> sha256, checked against `docs/plans/lantern-grid-waystation.md`'s release
# notes at publish time. Add an entry here (and re-upload the asset to the same
# release) whenever another metallicity gets baked and published.
_ASSETS: dict[str, str] = {
    "1Zsun.npz": "5c3c929d2ce93031bab805dbf6fc8a70cccc257bb24a6a7b347fb65576ea785a",
    "0.1Zsun.npz": "bc56dc2a4e9ad60c601da4313300194af8e5796748fcb1137f9e6750fc5aaa85",
    "0.01Zsun.npz": "e2aa9e38fb2ff284fb7b5d5c4da03f2cac18ff8124232a1a4bd26b01f61faa98",
    "0.2Zsun.npz": "ec1a94e2a64dd51b38ee20e3534a03ade170960aafacc2a3a5de2c7f03b619d7",
    "0.45Zsun.npz": "bf327acdfb2f3e35fa4dd63df8fb0845f8565a77643e0f38b8b483ad039d9209",
    "1e-3Zsun.npz": "d32af3bd2ab2354dcec2a994fdde842da8a58cb8f3e1d5448dc6b1c056667565",
    "1e-4Zsun.npz": "6ee3a1b1b8241d33656dc9ffda9ace1f3526e100dc8250264ca273d67eb21f3e",
    "2Zsun.npz": "bc1b4af81764204db41cef94d96c9ef16cb369f1cd0e6050249e87576d81b701",
}


def _fetch_one(filename: str, expected_sha256: str) -> str:
    url = f"{_ASSET_BASE}/{filename}"
    return fetch_one(url, BAKED_DIR / filename, expected_sha256)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Fetch pre-baked POSYDON binary grids from a GitHub Release."
    )
    ap.add_argument(
        "--asset", action="append", dest="assets", default=None,
        help="fetch only this asset filename (repeatable); default: all known assets",
    )
    args = ap.parse_args(argv)

    wanted = args.assets or list(_ASSETS)
    unknown = [a for a in wanted if a not in _ASSETS]
    if unknown:
        print(f"Unknown asset(s): {unknown}. Known: {list(_ASSETS)}")
        return 1

    BAKED_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Fetching {len(wanted)} pre-baked POSYDON grid(s) from release "
          f"'{RELEASE_TAG}' -> {BAKED_DIR}")

    n_ok = n_skip = 0
    for filename in wanted:
        status = _fetch_one(filename, _ASSETS[filename])
        print(f"  {filename}: {status}")
        n_ok += status == "ok"
        n_skip += status == "skip"

    print(f"Done: {n_ok} downloaded, {n_skip} already present.")
    print("Cite Fragos et al. 2023 and Andrews et al. 2024 on use (CC-BY).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
