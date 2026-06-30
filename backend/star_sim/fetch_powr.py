"""Fetch the PoWR Wolf-Rayet model spectra at build time (endgame Chunk 7).

The WR-endgame scrub bares a star's stripped, blazing core. Its *real* spectrum is
a **wind-emission** spectrum — broad He II / N / C emission lines, the opposite of
the absorption notches of every other panel — which lives only in the **PoWR**
grids (Potsdam Wolf-Rayet models; Hamann & Gräfener 2004, Sander+ 2012, Todt+ 2015).
Like Koester/TMAP these are plain ASCII (no MSG `.h5`, so no pymsg/Docker), but
unlike them they download as **per-grid tarballs** (one tarball per subtype ×
metallicity), each holding one subdir per model with a `flux_calib.dat`.

**The gate finding (Chunk 7a, see `backend/docs/msg_spectra_build_recipe.md §7`):**
PoWR is a **narrow-GO** — its (T*, Rt) footprint covers only the cool, hydrogen-rich
**WNh entry** of the scrub (~10% of it). MIST's *stripped* WR core is the hot,
compact **evolutionary** surface (Teff 150–262 kK ≈ PoWR's deep T*), far hotter and
more dense-wind than any *observed* WR the grid was tuned to — so the stripped bulk
maps off-grid and the panel shows an honest "no model" frame there. We still fetch
the real grids for the entry, where a genuine emission spectrum is honest.

Grid naming (the tarball dir per model is `<T*idx>-<Rtidx>`; no parameter file ships,
so the bake derives the node coordinates from the PoWR convention): WNE v∞=1600 km/s
(H-free), WNL v∞=1000 km/s (H-rich), D=4 — all fixed; log L=5.3 for every model.

Run once after checkout (Galactic first, the MVP slice; add metallicity grids later):

    python -m star_sim.fetch_powr                 # default: Galactic WNE+WNL+WC
    python -m star_sim.fetch_powr --grids all      # + LMC/SMC/sub-SMC metallicity grids

It downloads each tarball (skip-existing) and extracts it under
`data/spectra/grids/powr/<tag>/`. The data is gitignored (like the MIST grids and the
baked cubes); cite Hamann & Gräfener 2004 (A&A 427, 697), Hamann+ 2006 (A&A 457,
1015), Sander+ 2012 (A&A 540, A144, WC) and Todt+ 2015 (A&A 579, A75, WN) on use.
"""

from __future__ import annotations

import argparse
import sys
import tarfile
import time
import urllib.request
from pathlib import Path

from .spectra import SPECTRA_DATA_DIR  # single source of truth for where spectra live

POWR_DIR = SPECTRA_DATA_DIR / "grids" / "powr"
_BASE = "https://www.astro.physik.uni-potsdam.de/~htodt/powr-sed"
_USER_AGENT = "star-sim/0.1 (+local teaching tool; endgame Chunk 7 WR spectra)"

# A real PoWR grid tarball is 61–129 MB; anything much smaller is a truncated
# download or an error page, so we treat it as missing and re-fetch.
_MIN_BYTES = 20_000_000

# Each entry: tag -> (tarball filename, metallicity tag, subtype, the dir the tarball
# extracts to). `metal`/`subtype` are the discrete cube selectors; `Z_over_Zsun` lets
# the runtime snap the user's [Fe/H] to the nearest grid metallicity. The "H-rich"
# WNL variants carry a representative surface hydrogen fraction in their name; we take
# one per metallicity (the WNh entry the gate covers is hydrogen-rich either way).
_GRIDS: dict[str, dict] = {
    # --- Galactic (Z = 1.0 Z_sun) — the MVP slice ---
    "WNE-gal": dict(file="wnegrid.200-80000_2016.tgz", metal="gal", subtype="WNE",
                    z=1.0, vinf=1600.0, dirname="wnegrid.200-80000"),
    "WNL-gal": dict(file="wnlgrid.200-80000_2016.tgz", metal="gal", subtype="WNL",
                    z=1.0, vinf=1000.0, dirname="wnlgrid.200-80000"),
    "WC-gal":  dict(file="wcgrid.200-80000.tgz", metal="gal", subtype="WC",
                    z=1.0, vinf=2000.0, dirname="wcgrid.200-80000"),
    # --- LMC (Z = 0.5 Z_sun) ---
    "WNE-lmc": dict(file="lmc-wnegrid.200-80000_2017.tgz", metal="lmc", subtype="WNE",
                    z=0.5, vinf=1600.0, dirname="lmc-wnegrid.200-80000"),
    "WNL-lmc": dict(file="lmc-wnlgrid-h40.200-80000.tgz", metal="lmc", subtype="WNL",
                    z=0.5, vinf=1000.0, dirname="lmc-wnlgrid-h40.200-80000"),
    "WC-lmc":  dict(file="lmc-wcgrid.200-80000.tgz", metal="lmc", subtype="WC",
                    z=0.5, vinf=2000.0, dirname="lmc-wcgrid.200-80000"),
    # --- SMC (Z = 0.2 Z_sun) ---
    "WNE-smc": dict(file="smc-wnegrid.200-80000.tgz", metal="smc", subtype="WNE",
                    z=0.2, vinf=1600.0, dirname="smc-wnegrid.200-80000"),
    "WNL-smc": dict(file="smc-wnlgrid-h40.200-80000_2016.tgz", metal="smc", subtype="WNL",
                    z=0.2, vinf=1000.0, dirname="smc-wnlgrid-h40.200-80000"),
}

_TIERS = {
    "galactic": ["WNE-gal", "WNL-gal", "WC-gal"],
    "all": list(_GRIDS),
}


def _http_get(url: str, dest: Path, timeout: int = 600) -> None:
    """Stream a tarball to disk (atomic via .tmp), with a tiny progress tally."""
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        total = int(resp.headers.get("Content-Length", 0))
        got = 0
        with open(tmp, "wb") as fh:
            while True:
                chunk = resp.read(1 << 20)
                if not chunk:
                    break
                fh.write(chunk)
                got += len(chunk)
                if total:
                    print(f"\r    {got/1e6:6.1f} / {total/1e6:6.1f} MB", end="", flush=True)
    print()
    tmp.replace(dest)


def _fetch_one(tag: str, spec: dict, retries: int = 3) -> str:
    """Download + extract one grid tarball (idempotent). Returns a status word."""
    out_dir = POWR_DIR / tag
    # Already extracted (a model subdir is present)? skip.
    if out_dir.is_dir() and any(out_dir.glob("*/flux_calib.dat")):
        return "skip"
    tarball = POWR_DIR / spec["file"]
    if not (tarball.exists() and tarball.stat().st_size >= _MIN_BYTES):
        url = f"{_BASE}/{spec['file']}"
        last: Exception | None = None
        for attempt in range(retries):
            try:
                print(f"  {tag}: downloading {spec['file']} ...")
                _http_get(url, tarball)
                if tarball.stat().st_size < _MIN_BYTES:
                    raise RuntimeError(f"short tarball ({tarball.stat().st_size} bytes)")
                break
            except Exception as exc:  # noqa: BLE001 — retry transient hiccups
                last = exc
                print(f"    retry {attempt + 1}/{retries}: {exc}")
                time.sleep(2.0 * (attempt + 1))
        else:
            raise RuntimeError(f"failed to download {tag} ({spec['file']}): {last}")
    # Extract the model subdirs into out_dir/, stripping the tarball's OWN top dir
    # (computed from the member path, not a hardcoded name — PoWR tarball top dirs don't
    # always match the filename, e.g. the `_2016` suffix) so the bake reliably finds
    # out_dir/<T*idx>-<Rtidx>/flux_calib.dat one level down.
    print(f"  {tag}: extracting -> {out_dir} ...")
    out_dir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(tarball, "r:gz") as tf:
        for m in tf.getmembers():
            if not m.isfile() or not m.name.endswith("flux_calib.dat"):
                continue  # skip flux.pdf and dir entries — we only need the ASCII
            parts = m.name.split("/")
            rel = "/".join(parts[1:]) if len(parts) > 1 else m.name  # drop the top dir
            dest = out_dir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            src = tf.extractfile(m)
            if src is not None:
                dest.write_bytes(src.read())
    return "ok"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Fetch PoWR WR spectra (endgame Chunk 7).")
    ap.add_argument("--grids", default="galactic",
                    help="tier ('galactic' [default] or 'all'), or a comma-separated list "
                         "of tags, e.g. WNE-gal,WNL-gal")
    ap.add_argument("--keep-tarballs", action="store_true",
                    help="keep the downloaded .tgz (default: delete after extract to save disk)")
    args = ap.parse_args(argv)

    if args.grids in _TIERS:
        tags = _TIERS[args.grids]
    else:
        tags = [t.strip() for t in args.grids.split(",") if t.strip()]
    unknown = [t for t in tags if t not in _GRIDS]
    if unknown:
        raise SystemExit(f"unknown grid tag(s): {unknown}; choose from {list(_GRIDS)} "
                         f"or a tier {list(_TIERS)}")

    POWR_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Fetching {len(tags)} PoWR grid(s) -> {POWR_DIR}")
    n_ok = n_skip = n_fail = 0
    for tag in tags:
        spec = _GRIDS[tag]
        try:
            status = _fetch_one(tag, spec)        # a bad URL shouldn't abort the batch
        except Exception as exc:  # noqa: BLE001
            n_fail += 1
            print(f"  {tag}: FAILED ({exc}) - skipping, other grids continue")
            continue
        n_ok += status == "ok"
        n_skip += status == "skip"
        if status == "ok" and not args.keep_tarballs:
            (POWR_DIR / spec["file"]).unlink(missing_ok=True)
        nmod = len(list((POWR_DIR / tag).glob("*/flux_calib.dat")))
        print(f"  {tag}: {status}  ({nmod} models)")
    print(f"Done: {len(tags)} grids ({n_ok} fetched, {n_skip} already present"
          f"{f', {n_fail} failed' if n_fail else ''}).")
    print("Next: bake the WR cube - python scripts/bake_wr_spectra.py  (then: pytest)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
