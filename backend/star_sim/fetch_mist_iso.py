"""Fetch the MIST v2.5 isochrone (`.iso`) grid — Axis B of the outward quartet.

A DIFFERENT MIST data product from the EEP tracks (`fetch_mist.py`): the *published*
isochrones. Version-consistent with the live tracks (both v2.5), so the user's star lands
exactly on the cluster's main-sequence locus.

Like `fetch_mist.py` this **discovers** the tarball from MIST's model-grids index rather
than trusting a hard-coded deep link (the site has moved hosts + bumped versions before).
The v2.5 isochrones ship as ONE ~6.7 GB tarball per rotation rate holding *all*
metallicities and [a/Fe] values (there is no per-[Fe/H] download). So we **stream-extract
only the solar-scaled (`afe_p0`) members** — the whole [Fe/H] axis, matching the tracks —
and never unpack the 90% we don't use. The tarball is a regenerable download; by default
it is fetched to a cache dir and deleted after extraction.

Run once after checkout:

    python -m star_sim.fetch_mist_iso                        # vvcrit 0.0 (non-rotating)
    python -m star_sim.fetch_mist_iso --vvcrit 0.4           # the rotating grid
    python -m star_sim.fetch_mist_iso --tarball PATH.txz     # reuse an already-downloaded tarball

Extracted `.iso` files land flat under data/mist_isochrones/ where `isochrone.py`
discovers them by reading each file's own header ([Fe/H], [a/Fe], vvcrit). Idempotent:
members already extracted are skipped.
"""

from __future__ import annotations

import argparse
import re
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path
from urllib.parse import urljoin

import numpy as np

from .isochrone import BAKE_VERSION, ISO_DATA_DIR

# Only the columns the HR overlay consumes are kept (a 170-column, ~550 MB .iso bakes to a
# ~4.5 MB .npz). `mass` is initial_mass; core H/He give the by-construction Z_core.
_KEEP = {
    "eep": "EEP", "mass": "initial_mass", "logT": "log_Teff", "logL": "log_L",
    "logg": "log_g", "logR": "log_R", "phase": "phase",
    "h1": "surface_h1", "he4": "surface_he4", "ch1": "center_h1", "che4": "center_he4",
}
# Bake only the [Fe/H] nodes inside the live-track domain (the marker never leaves it, so
# metal-poor iso nodes down to −4 would be dead weight). This keeps the axis aligned with —
# and, where the iso grid is finer, denser than — the fetched tracks.
_FEH_MIN, _FEH_MAX = -1.05, 0.55

# The model-grids index — the same entry point fetch_mist uses; deliberately not a deep
# link to the tarball. The Harvard URL 302s to mist.science, which urllib follows.
INDEX_PAGES = (
    "https://waps.cfa.harvard.edu/MIST/model_grids.html",
    "https://mist.science/model_grids.html",
)
_USER_AGENT = "star-sim/0.1 (+local teaching tool; outward-quartet Axis B iso fetch)"

# Default cache dir for the big transient tarball (a regenerable download — keep it out of
# the repo tree). Sits beside the extracted grid.
_CACHE_DIR = ISO_DATA_DIR.parent / "_iso_download"


def discover_iso_tarball_url(vvcrit: str = "0.0") -> tuple[str, str]:
    """Return (absolute_url, filename) for the newest matching v2.5 `_full_isos.txz`.

    Scrapes the model-grids index for `.../tarballs_vX.Y/isos/MIST_vX.Y_vvcritZ_full_isos.txz`,
    keeps those matching the requested rotation, and picks the highest MIST version."""
    pat = re.compile(
        r"([\w./-]*tarballs_v[\d.]+/isos/"
        r"MIST_v[\d.]+_vvcrit" + re.escape(vvcrit) + r"_full_isos\.txz)"
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
        best = max(matches, key=lambda m: tuple(int(x) for x in ver.search(m).group(1).split(".")))
        return urljoin(final_url, best), best.rsplit("/", 1)[-1]

    raise RuntimeError(
        f"Could not discover a MIST v2.5 isochrone tarball for vvcrit={vvcrit} "
        f"from {INDEX_PAGES}." + (f" Last error: {last_err}" if last_err else "")
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
                    print(f"\r  downloading {dest.name}: {100 * done / total:5.1f}%", end="", flush=True)
        print()


def bake_iso(text_path: Path, out_npz: Path) -> tuple[float, float]:
    """Parse one `.iso` text file (streamed line-by-line — never loaded whole; 550 MB in
    ~5 s) and write a compact per-(feh, vvcrit) `.npz` holding only `_KEEP`, CSR-flattened
    across all ~107 tabulated ages. Returns (feh, vvcrit)."""
    with open(text_path, "r") as f:
        hdr = [next(f) for _ in range(8)]
        vals = hdr[4].split()                    # "# 0.2560 5.356E-3 -0.50 0.00 0.00"
        feh, vvcrit = float(vals[3]), float(vals[5])
        num_ages = int(hdr[6].split()[-1])

        log_ages: list[float] = []
        offsets: list[int] = [0]
        cols: dict[str, list[float]] = {k: [] for k in _KEEP}
        logage_flat: list[float] = []
        for _ in range(num_ages):
            line = next(f)
            while "number of EEPs" not in line:  # skip any inter-block separators
                line = next(f)
            neep = int(line.split()[-2])
            next(f)                              # the "# 1 2 3 ..." numbers line
            names = next(f).split()[1:]          # the "# EEP ... phase" names line
            idx = {n: i for i, n in enumerate(names)}
            pick = {k: idx[src] for k, src in _KEEP.items()}
            age_i = idx["log10_isochrone_age_yr"]
            block_age: float | None = None
            for _e in range(neep):
                parts = next(f).split()
                if block_age is None:
                    block_age = float(parts[age_i])
                for k, j in pick.items():
                    cols[k].append(float(parts[j]))
                logage_flat.append(float(parts[age_i]))
            log_ages.append(block_age)           # type: ignore[arg-type]
            offsets.append(len(cols["eep"]))

    arrays = {k: np.asarray(v, dtype=np.float32) for k, v in cols.items()}
    np.savez_compressed(
        out_npz,
        bake_version=np.int32(BAKE_VERSION),
        feh=np.float32(feh),
        vvcrit=np.float32(vvcrit),
        log_ages=np.asarray(log_ages, dtype=np.float32),
        offsets=np.asarray(offsets, dtype=np.int32),
        logage=np.asarray(logage_flat, dtype=np.float32),
        **arrays,
    )
    return feh, vvcrit


def extract_and_bake(txz: Path, vvcrit: str, data_dir: Path) -> int:
    """Stream the tarball once (`r|xz`, never a whole-archive member list in memory); for
    each solar-scaled (`afe_p0`) member inside the live-track [Fe/H] domain, extract it to a
    temp file, bake it to a compact `.npz`, and delete the 550 MB text — so peak disk stays
    ~one .iso, not the ~10 GB the whole afe_p0 axis would unpack to."""
    data_dir.mkdir(parents=True, exist_ok=True)
    wanted = re.compile(r"(^|/)feh_[^/]*_afe_p0_vvcrit" + re.escape(vvcrit) + r"_full\.iso$")
    n_new = 0
    with tarfile.open(txz, "r|xz") as tf:
        for member in tf:
            if not member.isfile() or not wanted.search(member.name):
                continue
            src = tf.extractfile(member)
            if src is None:
                continue
            with tempfile.NamedTemporaryFile("wb", suffix=".iso", dir=data_dir, delete=False) as tmp:
                tmp_path = Path(tmp.name)
                while chunk := src.read(1 << 20):
                    tmp.write(chunk)
            try:
                # peek the header for the [Fe/H] gate before the full parse
                with open(tmp_path) as fh:
                    feh_probe = float([next(fh) for _ in range(5)][4].split()[3])
                if not (_FEH_MIN <= feh_probe <= _FEH_MAX):
                    continue
                out = data_dir / f"iso_feh{feh_probe:+.2f}_vvcrit{vvcrit}.npz"
                if out.exists():
                    continue
                feh, _vv = bake_iso(tmp_path, out)
                n_new += 1
                print(f"\r  baked {n_new} isochrone cube(s) (latest [Fe/H]={feh:+.2f}) ...",
                      end="", flush=True)
            finally:
                tmp_path.unlink(missing_ok=True)
    print()
    return len(list(data_dir.glob("*.npz")))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Fetch the MIST v2.5 isochrone grid (Axis B).")
    ap.add_argument("--vvcrit", default="0.0", help="rotation v/vcrit (default 0.0)")
    ap.add_argument("--tarball", default=None,
                    help="path to an already-downloaded _full_isos.txz (skip the download)")
    ap.add_argument("--keep-tarball", action="store_true",
                    help="don't delete the .txz after extraction")
    args = ap.parse_args(argv)

    if args.tarball:
        txz = Path(args.tarball)
        if not txz.is_file():
            print(f"error: --tarball not found: {txz}", file=sys.stderr)
            return 2
        downloaded_here = False
    else:
        print(f"Discovering MIST v2.5 isochrone tarball (vvcrit={args.vvcrit}) ...")
        url, filename = discover_iso_tarball_url(args.vvcrit)
        print(f"  -> {url}")
        txz = _CACHE_DIR / filename
        download(url, txz)
        downloaded_here = True

    print(f"Extracting + baking solar-scaled (afe_p0) isochrones -> {ISO_DATA_DIR}")
    total = extract_and_bake(txz, args.vvcrit, ISO_DATA_DIR)
    print(f"  done: {total} baked .npz cube(s) under {ISO_DATA_DIR}")

    if downloaded_here and not args.keep_tarball:
        txz.unlink(missing_ok=True)
        print(f"  removed the tarball ({txz.name}); pass --keep-tarball to retain it.")

    print("Start the app (uvicorn star_sim.api:app --reload) or run: pytest")
    return 0


if __name__ == "__main__":
    sys.exit(main())
