"""Fetch the pre-baked MIST isochrone cubes from a GitHub Release (the fast path —
the casual-user shortcut past the ~6.7 GB `.iso` tarball + the bake).

This backs the `#isochrone-toggle` cluster-isochrone HR overlay (`isochrone.py`,
Axis B of the outward quartet). `fetch_mist_iso.py`'s recipe streams the published
MIST v2.5 isochrone grid — ONE ~6.7 GB tarball holding *all* metallicities — and
bakes each solar-scaled ([a/Fe]=0) node in the track [Fe/H] domain down to a compact
per-(feh, vvcrit) `.npz` (~2.6 MB each, ~18 MB for the whole 7-node axis).

This script instead pulls the **already-baked** cubes directly from a GitHub Release
— a plain HTTPS download, no 6.7 GB tarball, no streaming parse, no bake step.
Straight into `data/mist_isochrones/`, exactly where `isochrone.py` discovers them
(it globs `*.npz` and reads each file's own `bake_version`/`feh`/`vvcrit`, so the
downloaded cubes are a pure drop-in — no runtime code change). Once present, the
frontend's cluster-overlay toggle lights up (its `/isochrone_status` gate flips to
`has_grid: true`).

These are **derived artifacts** (compact per-metallicity cubes holding only the ~11
columns the HR overlay reads, baked from MIST's public `.iso` grid — not verbatim
copies). Hosted under this project's redistribution call, not an explicit license
grant from MIST (the same footing as the hosted EEP-track cubes; see
`docs/memory/star-sim-hosted-data-assets.md`). Cite the MIST papers on use (below).

Run once after checkout, instead of the `fetch_mist_iso.py` + bake recipe:

    python -m star_sim.fetch_mist_iso_baked
"""

from __future__ import annotations

import argparse
import sys

from ._baked_release import fetch_one
from .isochrone import ISO_DATA_DIR

RELEASE_TAG = "mist-iso-baked-v1"
_ASSET_BASE = f"https://github.com/BoykoNeov/star-sim/releases/download/{RELEASE_TAG}"

# The solar-scaled non-rotating [Fe/H] axis (−1.0 … +0.5, matching the live tracks;
# denser than the tracks' 5 nodes — the iso grid has ±0.25 steps). Each name is unique,
# so a flat {filename: sha256} mapping suffices (unlike the helium/alpha `history.data`
# case). Add the rotating (vvcrit0.4) axis here if/when it is baked + uploaded.
_ASSETS: dict[str, str] = {
    "iso_feh-1.00_vvcrit0.0.npz": "d68beb10aecf50f5adc7f7dc40447c82bfdf0244eafe2e59359912bcb9549cc1",
    "iso_feh-0.75_vvcrit0.0.npz": "1f45f93f39bed0b7c26b7c7352f544c6844c60763996098891f0880eafe96204",
    "iso_feh-0.50_vvcrit0.0.npz": "21710f18e6decdf8d11fe359f94c01519c8c51890d5c4ab918eec64bc733dbb7",
    "iso_feh-0.25_vvcrit0.0.npz": "7ef38c6f5e553b02839adf0ea4a5eb8e458ebe15ee341803d3116036cee33470",
    "iso_feh+0.00_vvcrit0.0.npz": "a3c25b1e779ebaa59c812452bf3d7d62af2d4ab9cb112d17a23b482b1d8ff8bd",
    "iso_feh+0.25_vvcrit0.0.npz": "98c205265c5bfce02aea5bb9160305aec11a9643bdc19d7c996028be618edefa",
    "iso_feh+0.50_vvcrit0.0.npz": "396da185545088788b66b3515b7dac667cc92332c6861e11ec378d90622c1a96",
}


def _fetch_one(filename: str, expected_sha256: str) -> str:
    url = f"{_ASSET_BASE}/{filename}"
    return fetch_one(url, ISO_DATA_DIR / filename, expected_sha256)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Fetch the pre-baked MIST isochrone cubes.")
    args = ap.parse_args(argv)
    del args

    print(f"Fetching pre-baked MIST isochrone cubes from release '{RELEASE_TAG}' -> {ISO_DATA_DIR}")
    n_ok = n_skip = 0
    for filename, digest in _ASSETS.items():
        status = _fetch_one(filename, digest)
        print(f"  {filename}: {status}")
        n_ok += status == "ok"
        n_skip += status == "skip"

    print(f"Done: {n_ok} downloaded, {n_skip} already present.")
    print("Cite Dotter (2016), ApJS 222, 8 + Choi et al. (2016), ApJ 823, 102 "
          "(MIST) on use.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
