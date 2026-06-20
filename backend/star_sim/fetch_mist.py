"""Fetch the MIST EEP track grid at build time (spec §6).

The whole point of §6 is: **don't trust a hard-coded URL.** MIST has already
moved hosts (waps.cfa.harvard.edu -> mist.science) and bumped versions
(v1.2 -> v2.5) since this project began; a pinned deep link would have rotted.
So this script *discovers* the current tarball location by scraping the MIST
"model grids" index page (following whatever redirect it issues) and picking the
highest-versioned EEPS archive matching the requested [Fe/H] / rotation. Only the
index page — the part of the site least likely to move — is named here.

Run once after checkout:

    python -m star_sim.fetch_mist                 # solar, non-rotating (default)
    python -m star_sim.fetch_mist --feh m100      # [Fe/H] = -1.00
    python -m star_sim.fetch_mist --vvcrit 0.4    # rotating grid

It downloads the ~180 MB tarball into data/ and extracts the `.track.eep`
files there, where `MISTProvider` finds them. Idempotent: re-runs skip the
download/extract if the data is already present.
"""

from __future__ import annotations

import argparse
import re
import sys
import tarfile
import urllib.request
from pathlib import Path
from urllib.parse import urljoin

from .providers.mist import DATA_DIR  # single source of truth for where data lives

# The index page only — deliberately *not* a deep link to a tarball. The first
# (Harvard) URL is the long-standing canonical entry point; it currently 302s to
# mist.science, which urllib follows. The mirror is a fallback if it moves again.
INDEX_PAGES = (
    "https://waps.cfa.harvard.edu/MIST/model_grids.html",
    "https://mist.science/model_grids.html",
)

_USER_AGENT = "star-sim/0.1 (+local teaching tool; spec §6 build-time fetch)"


def discover_tarball_url(
    feh: str = "p000", afe: str = "p0", vvcrit: str = "0.0"
) -> tuple[str, str]:
    """Return (absolute_url, filename) for the newest matching EEPS tarball.

    Scrapes the model-grids index page for `.../tarballs_vX.Y/eeps/..._EEPS.txz`
    references, keeps those matching the requested [Fe/H]/[a/Fe]/rotation, and
    picks the highest MIST version. Resolves the (possibly relative) href
    against the page's *final* URL so a host redirect is honored.
    """
    pat = re.compile(
        r"([\w./-]*tarballs_v[\d.]+/eeps/"
        r"MIST_v[\d.]+_feh_" + re.escape(feh) +
        r"_afe_" + re.escape(afe) +
        r"_vvcrit" + re.escape(vvcrit) + r"_EEPS\.txz)"
    )
    ver = re.compile(r"tarballs_v([\d.]+)/")

    last_err: Exception | None = None
    for page in INDEX_PAGES:
        try:
            req = urllib.request.Request(page, headers={"User-Agent": _USER_AGENT})
            with urllib.request.urlopen(req, timeout=60) as resp:
                final_url = resp.geturl()
                html = resp.read().decode("utf-8", "replace")
        except Exception as exc:  # try the next mirror
            last_err = exc
            continue

        matches = pat.findall(html)
        if not matches:
            continue
        # Both v1.2 and v2.5 are listed on the page — take the newest version.
        best = max(matches, key=lambda m: tuple(int(x) for x in ver.search(m).group(1).split(".")))
        return urljoin(final_url, best), best.rsplit("/", 1)[-1]

    raise RuntimeError(
        "Could not discover a MIST EEPS tarball for "
        f"feh={feh} afe={afe} vvcrit={vvcrit} from {INDEX_PAGES}."
        + (f" Last error: {last_err}" if last_err else "")
    )


def download(url: str, dest: Path) -> None:
    """Stream `url` to `dest`, skipping if a complete copy is already present."""
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(req, timeout=120) as resp:
        total = int(resp.headers.get("Content-Length", 0))
        if dest.exists() and total and dest.stat().st_size == total:
            print(f"  already downloaded: {dest.name} ({total} bytes)")
            return
        dest.parent.mkdir(parents=True, exist_ok=True)
        done = 0
        with open(dest, "wb") as fh:
            while chunk := resp.read(1 << 20):  # 1 MiB
                fh.write(chunk)
                done += len(chunk)
                if total:
                    pct = 100 * done / total
                    print(f"\r  downloading {dest.name}: {pct:5.1f}%", end="", flush=True)
        print()


def extract(txz: Path, data_dir: Path) -> Path:
    """Extract `.track.eep` files from the tarball; return their directory."""
    with tarfile.open(txz, "r:xz") as tf:
        members = tf.getnames()
        eeps = [m for m in members if m.endswith(".track.eep")]
        if not eeps:
            raise RuntimeError(f"{txz.name} contains no .track.eep files")
        eep_dir = data_dir / Path(eeps[0]).parent
        if eep_dir.is_dir() and any(eep_dir.glob("*.track.eep")):
            print(f"  already extracted: {eep_dir}")
            return eep_dir
        print(f"  extracting {len(eeps)} tracks -> {data_dir}")
        # filter='data' guards against path-traversal members (Python >=3.12).
        try:
            tf.extractall(data_dir, filter="data")
        except TypeError:  # older Python without the filter kwarg
            tf.extractall(data_dir)
    return eep_dir


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Fetch MIST EEP tracks (spec §6).")
    ap.add_argument("--feh", default="p000", help="MIST [Fe/H] code, e.g. p000, m100")
    ap.add_argument("--afe", default="p0", help="MIST [a/Fe] code (default p0)")
    ap.add_argument("--vvcrit", default="0.0", help="rotation v/vcrit (default 0.0)")
    ap.add_argument("--keep-tarball", action="store_true", help="don't delete the .txz after extract")
    args = ap.parse_args(argv)

    print(f"Discovering MIST tarball (feh={args.feh}, afe={args.afe}, vvcrit={args.vvcrit}) ...")
    url, filename = discover_tarball_url(args.feh, args.afe, args.vvcrit)
    print(f"  -> {url}")

    txz = DATA_DIR / filename
    download(url, txz)
    eep_dir = extract(txz, DATA_DIR)
    if not args.keep_tarball:
        txz.unlink(missing_ok=True)

    n = len(list(eep_dir.glob("*.track.eep")))
    print(f"Done: {n} tracks under {eep_dir}")
    print("Start the app (uvicorn star_sim.api:app --reload) or run: pytest")
    return 0


if __name__ == "__main__":
    sys.exit(main())
