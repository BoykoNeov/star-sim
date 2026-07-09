"""Fetch the pre-baked initial-helium (Y) MESA runs from a GitHub Release (the
fast path — the casual-user shortcut past Docker MESA).

`backend/docs/mesa_helium_recipe.md` is the **from-scratch recipe**: run a 6-run
batch (3 masses × baseline/enhanced Y) in Docker MESA yourself, ~30 min of
compute, then drop the `history.data` files under `data/mesa_helium/`. That is
what produced these files in the first place.

This script instead pulls those **already-computed** `history.data` files
directly from a GitHub Release — a plain HTTPS download, no Docker, no MESA, no
compute. Straight into `data/mesa_helium/{baseline,enhanced}/<M>Msun/history.data`,
exactly where `helium.py` (the `/helium` overlay sibling) globs for them. Once
present, the frontend's "Helium-enhanced" HR-overlay toggle lights up (its
`/helium_status` gate flips to `has_grid: true`).

These are **self-run MESA output** — the project's own computational results
(temperatures/luminosities/abundances over evolutionary time), not a copy of any
third-party dataset. This is the same class of artifact the project's whole MIST
provider spine already is (MIST is itself published MESA output). Distinct from
the bearums MESAProvider validation tracks, which are third-party and stay
unhosted — see `docs/memory/star-sim-hosted-data-assets.md`. Cite MESA on use
(below).

Run once after checkout, instead of the `mesa_helium_recipe.md` Docker batch:

    python -m star_sim.fetch_helium_baked
"""

from __future__ import annotations

import argparse
import sys

from ._baked_release import fetch_one
from .helium import HELIUM_DATA_DIR

RELEASE_TAG = "mesa-helium-baked-v1"
_ASSET_BASE = f"https://github.com/BoykoNeov/star-sim/releases/download/{RELEASE_TAG}"

# GitHub requires unique asset names per release, but every file is named
# `history.data`, so each is uploaded under a unique asset name that maps back to
# its real destination path under HELIUM_DATA_DIR.  asset_name -> (relpath, sha256)
_ASSETS: dict[str, tuple[str, str]] = {
    "helium_baseline_1Msun.data": (
        "baseline/1Msun/history.data",
        "d721ce0a345169afa515cfe2c1d629886df0c37afba3ca0948cacfe6b8aa7ef5",
    ),
    "helium_baseline_2Msun.data": (
        "baseline/2Msun/history.data",
        "e2be6e7cd9db0ba5fabb9dfaeb1f81ea56113ab8b3d8d911ae692229d00bf996",
    ),
    "helium_baseline_6Msun.data": (
        "baseline/6Msun/history.data",
        "d28bf5b41a0acd5217aa687ab7401179f8596f9fb68f6ea56dc7c8cb8e5dde0c",
    ),
    "helium_enhanced_1Msun.data": (
        "enhanced/1Msun/history.data",
        "f2e4582b8dedb3b80f8dcc51ed48bc4f9ab93deb2b61e0ece595d7eca2c69abf",
    ),
    "helium_enhanced_2Msun.data": (
        "enhanced/2Msun/history.data",
        "d8428128528fe42e91403972fb30f6ab5d48f2eb95ad68bdbae32bc42c3ba549",
    ),
    "helium_enhanced_6Msun.data": (
        "enhanced/6Msun/history.data",
        "d0e6bc4a5388ef5acb5e39b289d89b4a76836167720529285eebe96f7e619f9e",
    ),
}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Fetch the pre-baked initial-helium (Y) MESA runs."
    )
    args = ap.parse_args(argv)
    del args

    print(f"Fetching pre-baked He-enhanced MESA runs from release "
          f"'{RELEASE_TAG}' -> {HELIUM_DATA_DIR}")
    n_ok = n_skip = 0
    for asset_name, (relpath, digest) in _ASSETS.items():
        url = f"{_ASSET_BASE}/{asset_name}"
        dest = HELIUM_DATA_DIR / relpath
        status = fetch_one(url, dest, digest)
        print(f"  {relpath}: {status}")
        n_ok += status == "ok"
        n_skip += status == "skip"

    print(f"Done: {n_ok} downloaded, {n_skip} already present.")
    print("Cite MESA (Paxton et al. 2011/2013/2015/2018/2019; Jermyn et al. 2023) "
          "on use - these are self-run MESA r24.03.1 tracks.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
