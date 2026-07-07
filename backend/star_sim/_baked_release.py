"""Shared plain-HTTPS + sha256-verified downloader for pre-baked GitHub Release
assets — the common half of every `fetch_*_baked.py` module (POSYDON, MIST,
Koester+TMAP, PoWR, Coelho, Gotberg). Each of those modules owns its own release
tag, asset list, destination paths, and citation text; this module owns only the
download-and-verify mechanics so they don't each reimplement it.

Not a CLI entry point itself — imported by the `fetch_*_baked.py` modules.
"""

from __future__ import annotations

import hashlib
import urllib.request
from pathlib import Path

USER_AGENT = "star-sim/0.1 (+local teaching tool; pre-baked data fetch)"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


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
