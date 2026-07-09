"""Fetch the pre-baked α-enhanced (equivalent-Z) MESA runs from a GitHub Release
(the fast path — the casual-user shortcut past Docker MESA).

`backend/docs/mesa_alpha_recipe.md` is the **from-scratch recipe**: run a 6-run
batch (3 masses × baseline/α-enhanced, the α boost folded in as an equivalent
total Z per Salaris et al. 1993) in Docker MESA yourself, then drop the
`history.data` files under `data/mesa_alpha/`. That is what produced these files.

This script instead pulls those **already-computed** `history.data` files
directly from a GitHub Release — a plain HTTPS download, no Docker, no MESA, no
compute. Straight into `data/mesa_alpha/{baseline,enhanced}/<M>Msun/history.data`,
exactly where `alpha.py` (the `/alpha` overlay sibling) globs for them. Once
present, the frontend's "α-enhanced" HR-overlay toggle lights up (its
`/alpha_status` gate flips to `has_grid: true`).

These are **self-run MESA output** — the project's own computational results, not
a copy of any third-party dataset (the same class of artifact the project's whole
MIST provider spine already is; MIST is itself published MESA output). Distinct
from the bearums MESAProvider validation tracks, which are third-party and stay
unhosted — see `docs/memory/star-sim-hosted-data-assets.md`. Cite MESA (and
Salaris et al. 1993 for the equivalent-Z mapping) on use.

Run once after checkout, instead of the `mesa_alpha_recipe.md` Docker batch:

    python -m star_sim.fetch_alpha_baked
"""

from __future__ import annotations

import argparse
import sys

from ._baked_release import fetch_one
from .alpha import ALPHA_DATA_DIR

RELEASE_TAG = "mesa-alpha-baked-v1"
_ASSET_BASE = f"https://github.com/BoykoNeov/star-sim/releases/download/{RELEASE_TAG}"

# GitHub requires unique asset names per release, but every file is named
# `history.data`, so each is uploaded under a unique asset name that maps back to
# its real destination path under ALPHA_DATA_DIR.  asset_name -> (relpath, sha256)
# (the baseline runs are byte-identical to the helium baselines — same solar
# Z=0.0152, Y=0.2704 run — but each release is kept self-contained on purpose.)
_ASSETS: dict[str, tuple[str, str]] = {
    "alpha_baseline_1Msun.data": (
        "baseline/1Msun/history.data",
        "d721ce0a345169afa515cfe2c1d629886df0c37afba3ca0948cacfe6b8aa7ef5",
    ),
    "alpha_baseline_2Msun.data": (
        "baseline/2Msun/history.data",
        "e2be6e7cd9db0ba5fabb9dfaeb1f81ea56113ab8b3d8d911ae692229d00bf996",
    ),
    "alpha_baseline_6Msun.data": (
        "baseline/6Msun/history.data",
        "d28bf5b41a0acd5217aa687ab7401179f8596f9fb68f6ea56dc7c8cb8e5dde0c",
    ),
    "alpha_enhanced_1Msun.data": (
        "enhanced/1Msun/history.data",
        "f8759a13be5295e0b2c8a3a67ec1949929ed9b16d0e5a16e02e2cfa7646c0061",
    ),
    "alpha_enhanced_2Msun.data": (
        "enhanced/2Msun/history.data",
        "d4731990cd74eabf797994b2987c6a1d0096b3e714459f401d2dae55aa88eb43",
    ),
    "alpha_enhanced_6Msun.data": (
        "enhanced/6Msun/history.data",
        "8b3ee9564becbab321375db47160fb85dd785b3040c5199ee92283b99af1ca0c",
    ),
}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Fetch the pre-baked alpha-enhanced (equivalent-Z) MESA runs."
    )
    args = ap.parse_args(argv)
    del args

    print(f"Fetching pre-baked alpha-enhanced MESA runs from release "
          f"'{RELEASE_TAG}' -> {ALPHA_DATA_DIR}")
    n_ok = n_skip = 0
    for asset_name, (relpath, digest) in _ASSETS.items():
        url = f"{_ASSET_BASE}/{asset_name}"
        dest = ALPHA_DATA_DIR / relpath
        status = fetch_one(url, dest, digest)
        print(f"  {relpath}: {status}")
        n_ok += status == "ok"
        n_skip += status == "skip"

    print(f"Done: {n_ok} downloaded, {n_skip} already present.")
    print("Cite MESA (Paxton et al. 2011/2013/2015/2018/2019; Jermyn et al. 2023) "
          "and Salaris, Chieffi & Straniero (1993) on use - self-run MESA r24.03.1.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
