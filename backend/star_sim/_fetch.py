"""The fetch framework: one downloader, one user-agent policy, one table runner.

Every `fetch_*.py` in this package is a **build-time** entry point — it puts a grid
under `data/` and is never imported by the running app. They come in two families,
and this module is the half both share:

* **Raw fetchers** (`fetch_mist`, `fetch_koester`, `fetch_powr`, `fetch_coelho`,
  `fetch_tmap`, `fetch_mesa`, `fetch_filters`, `fetch_mist_iso`) talk to somebody
  else's server — MIST's site, SVO, Zenodo, CDS. From here they take only
  `user_agent()`: each still says what it is fetching, but the identifying prefix is
  written once. Their download loops stay their own; a streamed 6.7 GB tarball with
  a discovery step and a sha256'd release asset are not the same operation.
* **Baked fetchers** (`fetch_*_baked`) pull this project's own pre-baked GitHub
  Release assets. Those *are* all the same operation — resolve a URL, verify a
  sha256, land the file — so `run()` below is their whole body, and each module is
  reduced to its release tag, its asset table, its destinations and its citation.

Not a CLI entry point itself. It is also a **leaf**: stdlib only, and nothing from
`star_sim` — a fetcher imports its own sibling's `*_DATA_DIR` and hands the paths
down. `tests/test_fetch_framework.py` pins that, and the tables below it.
"""

from __future__ import annotations

import argparse
import hashlib
import urllib.request
from collections.abc import Callable, Mapping
from pathlib import Path

_RELEASES = "https://github.com/BoykoNeov/star-sim/releases/download"


def user_agent(purpose: str) -> str:
    """The one User-Agent this project sends, with the caller's own purpose tag.

    These strings go to third-party servers, so the *format* is shared but the
    information is not flattened away: a maintainer at SVO or MIST reading their
    logs can still tell which fetch is knocking.
    """
    return f"star-sim/0.1 (+local teaching tool; {purpose})"


USER_AGENT = user_agent("pre-baked data fetch")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def asset_base(tag: str) -> str:
    """The download URL prefix for one GitHub Release tag of this repo."""
    return f"{_RELEASES}/{tag}"


def fetch_one(url: str, dest: Path, expected_sha256: str, timeout: float = 300) -> str:
    """Download one release asset to `dest` (skip if already present with a
    matching hash), verifying its content against `expected_sha256`.

    Returns a one-word status for the caller's progress summary: "ok" or "skip".
    Raises RuntimeError on a hash mismatch after download (corrupted/truncated
    transfer) rather than silently leaving a bad file at `dest` — the download
    lands in a `.tmp` sibling first and is only renamed into place on a match.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and sha256(dest) == expected_sha256:
        return "skip"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    tmp = dest.parent / (dest.name + ".tmp")
    with urllib.request.urlopen(req, timeout=timeout) as resp, open(tmp, "wb") as out:
        while chunk := resp.read(1 << 20):
            out.write(chunk)
    got = sha256(tmp)
    if got != expected_sha256:
        tmp.unlink(missing_ok=True)
        raise RuntimeError(
            f"{dest.name}: sha256 mismatch after download (got {got}, expected "
            f"{expected_sha256}) — corrupted or truncated transfer, try again"
        )
    tmp.replace(dest)
    return "ok"


def parse_no_args(description: str, argv: list[str] | None) -> None:
    """`--help` and nothing else — the shape eight of the ten baked fetchers want.

    They still each own this call rather than having `run()` build a parser: a
    module that later grows a real flag (`--feh`, `--asset`) writes its own parser
    in the same place, instead of the runner sprouting an escape hatch.
    """
    argparse.ArgumentParser(description=description).parse_args(argv)


def run(
    tag: str,
    assets: Mapping[str, str],
    *,
    what: str,
    dest_root: Path,
    citation: str,
    dest_of: Callable[[str], Path] | None = None,
    url_of: Callable[[str], str] | None = None,
    label_of: Callable[[str], str] | None = None,
) -> int:
    """Fetch every asset in `assets` (a key -> sha256 table) and report.

    The key is whatever the module's table is keyed on — a filename for the flat
    cubes, a bucket directory for MIST, a unique release asset name for the MESA
    overlay runs. Three different strings come off it and they are deliberately
    kept apart, because collapsing them would change what the user sees:

    * `url_of(key)`   — the release asset name.  Default: `<release>/<key>`.
    * `dest_of(key)`  — where it lands on disk.  Default: `dest_root / key`.
    * `label_of(key)` — what the progress line prints. Default: the key itself.

    Returns a process exit code (0; the callers' own argument validation is what
    returns 1). Never raises for an already-present file — that is a "skip".
    """
    url_of = url_of or (lambda key: f"{asset_base(tag)}/{key}")
    dest_of = dest_of or (lambda key: dest_root / key)
    label_of = label_of or (lambda key: key)

    print(f"Fetching {what} from release '{tag}' -> {dest_root}")
    n_ok = n_skip = 0
    for key, digest in assets.items():
        status = fetch_one(url_of(key), dest_of(key), digest)
        print(f"  {label_of(key)}: {status}")
        n_ok += status == "ok"
        n_skip += status == "skip"

    print(f"Done: {n_ok} downloaded, {n_skip} already present.")
    print(citation)
    return 0
