"""Build-time bake of a *standalone* MIST parsed-track cache — the release-asset
half of `fetch_mist_baked.py`.

`providers/mist.py` already caches each grid's parsed tracks to a per-grid
`_parsed_tracks.npz` next to the raw `.track.eep` files (43-45 MB vs ~1.2 GB of raw
text per [Fe/H]xvvcrit bucket, a ~27x reduction — the cache keeps every row, just
drops MIST's unused columns; see `providers/mist.py` `_TRACK_COLS`/`_parse_track_file`).
That cache is normally *validated against its raw source* (`_grid_fingerprint` hashes
every `.track.eep` file's name/size/mtime), so shipping it alone wouldn't load: a
fresh checkout with only the `.npz` and no raw files would fail the fingerprint check.

This script produces the one variant that DOES load standalone. `_grid_fingerprint`
already degrades gracefully to a stable, content-free hash — `sha256(f"v{CACHE_VERSION}")`
— when a directory has zero `.track.eep` files (nothing to fold in). So baking the cache
with *that* fingerprint, computed against a directory that genuinely has no raw files,
produces a `.npz` that validates on any machine running the same code version with no
raw source at all. `providers/mist.py`'s grid discovery (`_find_eep_dirs`) already
recognizes such a directory as a valid grid — no runtime code path is unique to this;
it's the same cache-read logic a normal reparse would produce, just fingerprinted for
absence instead of presence.

Requires the raw MIST grids already fetched locally (`fetch_mist.py`), same as any
other bake step — this reads the real `.track.eep` files to get the tracks, it just
writes the cache under a fingerprint meant for a *source-less* copy.

Run once per bucket you want to publish (default: every [Fe/H]xvvcrit grid found
under data/):

    python scripts/bake_mist_standalone.py                    # every grid on disk
    python scripts/bake_mist_standalone.py --feh p000          # just solar (both vvcrit)
    python scripts/bake_mist_standalone.py --feh p000 --vvcrit 0.0

Writes one `<bucket-dir-name>.npz` per grid into `data/mist_standalone/` (e.g.
`feh_p000_afe_p0_vvcrit0.0.npz`) — a staging dir, never the live `data/feh_*/eeps/`
grid dirs `MISTProvider` reads from, so this never touches a dev's normal cache.
`fetch_mist_baked.py` downloads these back into the right `data/feh_*/eeps/
_parsed_tracks.npz` location on a fresh checkout.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from star_sim.providers.mist import (
    DATA_DIR,
    _feh_from_path,
    _find_eep_dirs,
    _grid_fingerprint,
    _parse_all_tracks,
    _vvcrit_from_path,
    _write_cache,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = _REPO_ROOT / "data" / "mist_standalone"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--feh", type=float, default=None, help="only this [Fe/H] (e.g. 0.0)")
    ap.add_argument("--vvcrit", type=float, default=None, help="only this v/vcrit (e.g. 0.0)")
    args = ap.parse_args(argv)

    eep_dirs = _find_eep_dirs(DATA_DIR)
    if args.feh is not None:
        eep_dirs = [d for d in eep_dirs if _feh_from_path(d) == args.feh]
    if args.vvcrit is not None:
        eep_dirs = [d for d in eep_dirs if _vvcrit_from_path(d) == args.vvcrit]
    if not eep_dirs:
        print("No matching MIST grids found under", DATA_DIR)
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for eep_dir in eep_dirs:
        # bucket dir name, e.g. "feh_p000_afe_p0_vvcrit0.0" (the `eeps` parent)
        bucket = eep_dir.parent.name
        print(f"Parsing {bucket} ({eep_dir}) ...")
        tracks, feh, vvcrit = _parse_all_tracks(eep_dir)
        if not tracks:
            print(f"  skipped: no usable tracks in {eep_dir}")
            continue

        # The source-less fingerprint: computed against OUT_DIR itself, which holds
        # no `.track.eep` files, so `_grid_fingerprint` degrades to the stable
        # version-only hash a fresh no-raw-source client will also compute.
        fingerprint = _grid_fingerprint(OUT_DIR)
        out_path = OUT_DIR / f"{bucket}.npz"
        _write_cache(out_path, tracks, feh, vvcrit, fingerprint)
        size_mb = out_path.stat().st_size / 1e6
        print(f"  -> {out_path.name} ({len(tracks)} tracks, {size_mb:.1f} MB)")

    print(f"Done. Standalone caches in {OUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
