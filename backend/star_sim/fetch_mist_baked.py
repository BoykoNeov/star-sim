"""Fetch pre-baked MIST parsed-track caches from a GitHub Release (the fast path).

`fetch_mist.py`'s recipe is the *original* path: discover + download the current
MIST EEP tarball per [Fe/H] (~180 MB each, ~1.2 GB once extracted with a warm
parse cache) directly from MIST's own site. That's the right path if you want a
metallicity/rotation bucket this release doesn't carry yet, or you'd rather pull
straight from the source — but it also depends on MIST's site staying where the
discovery step expects it (spec §6), and it's ~27x more data than the app
actually reads off each track (MIST's raw text carries ~80 columns; the app uses
a windowed ~40).

This script instead pulls a pre-baked, **standalone** `_parsed_tracks.npz` per
[Fe/H]xrotation bucket straight from a GitHub Release — a plain HTTPS download, no
site-scraping, no re-parsing MIST's text tracks (~20 s/bucket saved too). "Standalone"
matters here: `providers/mist.py` normally validates its parse cache against the raw
`.track.eep` files it was built from (name/size/mtime fingerprint), so a cache alone
wouldn't normally load. These particular caches are baked with the *source-less*
fingerprint the provider's fingerprint function already falls back to when a grid
directory has zero raw files (see `scripts/bake_mist_standalone.py` and
`providers/mist.py`'s `_find_eep_dirs` docstring) — so they load correctly with
nothing else alongside them. Straight into `data/feh_<code>_afe_p0_vvcrit<v>/eeps/`,
exactly where `MISTProvider` looks for a grid.

These are **derived artifacts** (a re-serialization of MIST's own public tracks into a
compact binary cache, keeping every row and only the columns this app reads) hosted
under this project's redistribution call, not MIST's license terms (MIST doesn't carry
an explicit redistribution grant like POSYDON's CC-BY) — see
`docs/memory/star-sim-hosted-data-assets.md`. Cite the MIST papers on use (below).

Run once after checkout, instead of the `fetch_mist.py` recipe:

    python -m star_sim.fetch_mist_baked                        # every bucket in this release
    python -m star_sim.fetch_mist_baked --feh p000              # solar only (both rotation rates)
    python -m star_sim.fetch_mist_baked --feh p000 --vvcrit 0.0 # solar, non-rotating only
"""

from __future__ import annotations

import argparse
import sys

from ._baked_release import fetch_one
from .providers.mist import CACHE_FILENAME, DATA_DIR

RELEASE_TAG = "mist-baked-v1"
_ASSET_BASE = f"https://github.com/BoykoNeov/star-sim/releases/download/{RELEASE_TAG}"

# bucket dir name -> sha256 of the standalone `.npz` release asset (same base name +
# ".npz"). Checked against the release notes at publish time. Add an entry (and
# upload the asset to the same release) whenever another bucket is baked +
# published via `scripts/bake_mist_standalone.py`.
_ASSETS: dict[str, str] = {
    "feh_m050_afe_p0_vvcrit0.0": "724be2f4f96846b8a741cf196a4c001f995846797cc090916e1fe937aab5fb2a",
    "feh_m050_afe_p0_vvcrit0.4": "c35927099d87e0b22850d3ee7de1fd9d9fc26a72f30bf6d2a613bc7bf7c7d3aa",
    "feh_m075_afe_p0_vvcrit0.0": "7ce4a698ffa3526ea92cf78facefa7afcd3f92ac8d96088c98e7f5d11765e9e6",
    "feh_m075_afe_p0_vvcrit0.4": "c9f75f13ff9d49bcec03f9c538e8a6dc02ee420ba7e40ae9044ddbd677c9f05a",
    "feh_m100_afe_p0_vvcrit0.0": "6620211e702aa7c6bf75e4de8d9b255aaa5e779db7d1c63e956a7ba77533f7fc",
    "feh_m100_afe_p0_vvcrit0.4": "dd06aeae32901d17c8f6d424e680f1f8917e4aa20d8e38c388588f051506d209",
    "feh_p000_afe_p0_vvcrit0.0": "539323a887c048889b1f088d7ae70163d82ba3d70c551410038a314d9b65daf1",
    "feh_p000_afe_p0_vvcrit0.4": "72f37c5bcefdca39105f6d9abbdf1dccff8e4918a3a4015c029f1a2f2856cb37",
    "feh_p050_afe_p0_vvcrit0.0": "01bc970acbaf41e4fedd3075ac500abd05cd4eb3c20ef802993791e9bee9fa19",
    "feh_p050_afe_p0_vvcrit0.4": "a54f3dcf9b86ed20c37eb43b4e0fdab3ad137eebfa4c46eab1936ce6913c629d",
}


def _feh_code_of(bucket: str) -> str | None:
    """"feh_p000_afe_p0_vvcrit0.0" -> "p000" (a cheap filter, mirrors mist.py)."""
    parts = bucket.split("_")
    return parts[1] if len(parts) > 1 and parts[0] == "feh" else None


def _vvcrit_of(bucket: str) -> str | None:
    if "vvcrit" not in bucket:
        return None
    return bucket.rsplit("vvcrit", 1)[1]


def _fetch_one(bucket: str, expected_sha256: str) -> str:
    filename = f"{bucket}.npz"
    url = f"{_ASSET_BASE}/{filename}"
    dest = DATA_DIR / bucket / "eeps" / CACHE_FILENAME
    return fetch_one(url, dest, expected_sha256)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Fetch pre-baked, standalone MIST parsed-track caches from a GitHub Release."
    )
    ap.add_argument("--feh", type=str, default=None, help="only this [Fe/H] code, e.g. p000/m050")
    ap.add_argument("--vvcrit", type=str, default=None, help="only this v/vcrit, e.g. 0.0/0.4")
    ap.add_argument(
        "--asset", action="append", dest="assets", default=None,
        help="fetch only this bucket name (repeatable); default: all matching buckets",
    )
    args = ap.parse_args(argv)

    wanted = args.assets or list(_ASSETS)
    if args.feh is not None:
        wanted = [b for b in wanted if _feh_code_of(b) == args.feh]
    if args.vvcrit is not None:
        wanted = [b for b in wanted if _vvcrit_of(b) == args.vvcrit]
    unknown = [a for a in wanted if a not in _ASSETS]
    if unknown:
        print(f"Unknown asset(s): {unknown}. Known: {list(_ASSETS)}")
        return 1
    if not wanted:
        print("No buckets match the given --feh/--vvcrit filter.")
        return 1

    print(f"Fetching {len(wanted)} pre-baked MIST bucket(s) from release "
          f"'{RELEASE_TAG}' -> {DATA_DIR}")

    n_ok = n_skip = 0
    for bucket in wanted:
        status = _fetch_one(bucket, _ASSETS[bucket])
        print(f"  {bucket}: {status}")
        n_ok += status == "ok"
        n_skip += status == "skip"

    print(f"Done: {n_ok} downloaded, {n_skip} already present.")
    print("Cite Dotter (2016), ApJS 222, 8 and Choi et al. (2016), ApJ 823, 102 on use.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
