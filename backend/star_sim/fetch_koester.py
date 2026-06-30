"""Fetch the Koester DA white-dwarf model spectra at build time (endgame Chunk 6).

The stellar-endgame gateway's white-dwarf branch wants a *real* spectrum for the
cooling DA — pressure-broadened Balmer lines — which is the one piece NOT already
on disk (the WD/WR atmospheres are not in the MIST tracks, and not MSG `.h5` either,
so `pymsg` can't read them). The tractable WD grid is **Koester DA** (Koester 2010;
Stark profiles from Tremblay & Bergeron 2009), served by the **SVO Theoretical
Spectra Server** as the `koester2` collection.

Unlike the main spectrum cube (which is baked from an MSG grid inside a Docker
container, see `backend/docs/msg_spectra_build_recipe.md`), this is a plain HTTP
fetch of ASCII spectra — no MSG/Fortran/Docker. The companion bake
(`scripts/bake_wd_spectra.py`) is likewise pure numpy/scipy and runs on the host.

Run once after checkout:

    python -m star_sim.fetch_koester

It downloads the SSAP index (a VOTable listing every model + its `fid`), then pulls
each model's 2-column ASCII spectrum (λ in air Å, F_λ in erg/cm²/s/Å) into
`data/spectra/grids/koester/`. The grid is rectangular — 82 Teff nodes (5000–80000 K)
× 13 log g nodes (6.5–9.5) = 1066 models, ~150 MB total. Idempotent: re-runs skip a
model whose file is already present and non-trivially sized, so an interrupted fetch
resumes. The data is gitignored (like `data/mist` and the baked cubes); cite Koester
2010, Mem.S.A.It. 81, 921 on use.
"""

from __future__ import annotations

import argparse
import re
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from .spectra import SPECTRA_DATA_DIR  # single source of truth for where spectra live

# The collection's SSAP base. The index (no `fid`) returns a VOTable enumerating
# every model; per-model ASCII is the same URL with `&fid=N&format=ascii`. This is
# the SVO bulk path the Chunk-0 scoping confirmed — NOT TheoSSA on-demand.
SSAP_BASE = "https://svo2.cab.inta-csic.es/theory/newov2/ssap.php?model=koester2"

KOESTER_DIR = SPECTRA_DATA_DIR / "grids" / "koester"

_USER_AGENT = "star-sim/0.1 (+local teaching tool; endgame Chunk 6 WD spectra)"

# A real Koester ASCII spectrum is ~140 KB; anything much smaller is a truncated
# download or an error page, so we treat it as missing and re-fetch.
_MIN_BYTES = 10_000

# Parse the index's TABLEDATA: each <TR> carries a title TD "teff:T, logg:G" and an
# Access.Reference TD with the model's "fid=N". Both appear once per row, in order.
_TITLE_RE = re.compile(r"teff:(\d+(?:\.\d+)?),\s*logg:(\d+(?:\.\d+)?)")
_FID_RE = re.compile(r"fid=(\d+)")


def _http_get(url: str, timeout: int = 120) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def discover_models() -> list[tuple[int, float, float]]:
    """Fetch the SSAP index and return [(fid, teff, logg), …] for every model.

    The title TDs (teff/logg) and the Access.Reference TDs (fid) each appear once
    per row in document order, so zipping the two ordered lists reconstructs the
    rows without a full namespaced-XML parse. We assert equal counts so a layout
    change can't silently drop or misalign models.
    """
    html = _http_get(SSAP_BASE).decode("utf-8", "replace")
    titles = _TITLE_RE.findall(html)
    fids = _FID_RE.findall(html)
    if not titles:
        raise RuntimeError(f"no Koester models found in the SSAP index at {SSAP_BASE}")
    if len(titles) != len(fids):
        raise RuntimeError(
            f"index parse mismatch: {len(titles)} (teff,logg) titles vs {len(fids)} "
            "fids — the VOTable layout may have changed"
        )
    return [
        (int(fid), float(t), float(g))
        for (t, g), fid in zip(titles, fids)
    ]


def _model_path(teff: float, logg: float) -> Path:
    # Zero-pad Teff to 5 digits and fix log g to 2 dp so the dir sorts naturally and
    # the bake can recover the node from the filename (the ASCII header is the
    # authoritative source, but the name is a useful cross-check).
    return KOESTER_DIR / f"koester_da_{int(round(teff)):05d}_{logg:.2f}.txt"


def _fetch_one(fid: int, teff: float, logg: float, retries: int = 3) -> str:
    """Download one model's ASCII spectrum (skip if already present). Returns a
    one-word status for the progress tally."""
    dest = _model_path(teff, logg)
    if dest.exists() and dest.stat().st_size >= _MIN_BYTES:
        return "skip"
    url = f"{SSAP_BASE}&fid={fid}&format=ascii"
    last: Exception | None = None
    for attempt in range(retries):
        try:
            data = _http_get(url)
            if len(data) < _MIN_BYTES:
                raise RuntimeError(f"short response ({len(data)} bytes) for fid={fid}")
            tmp = dest.with_suffix(".txt.tmp")
            tmp.write_bytes(data)
            tmp.replace(dest)
            return "ok"
        except Exception as exc:  # noqa: BLE001 — retry transient SVO hiccups
            last = exc
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"failed to fetch fid={fid} (teff={teff}, logg={logg}): {last}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Fetch Koester DA white-dwarf spectra (endgame Chunk 6).")
    ap.add_argument("--workers", type=int, default=6,
                    help="concurrent downloads (default 6 — polite to the SVO server)")
    args = ap.parse_args(argv)

    KOESTER_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Discovering Koester DA models from {SSAP_BASE} …")
    models = discover_models()
    teffs = sorted({t for _, t, _ in models})
    loggs = sorted({g for _, _, g in models})
    print(f"  {len(models)} models: Teff {teffs[0]:.0f}–{teffs[-1]:.0f} K "
          f"({len(teffs)} nodes), log g {loggs[0]}–{loggs[-1]} ({len(loggs)} nodes)")
    print(f"  -> {KOESTER_DIR}")

    n_ok = n_skip = n_done = 0
    total = len(models)
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(_fetch_one, fid, t, g): (fid, t, g) for fid, t, g in models}
        for fut in as_completed(futs):
            status = fut.result()  # raises on a model that failed all retries
            n_ok += status == "ok"
            n_skip += status == "skip"
            n_done += 1
            if n_done % 25 == 0 or n_done == total:
                print(f"\r  {n_done}/{total}  ({n_ok} downloaded, {n_skip} already present)",
                      end="", flush=True)
    print()
    print(f"Done: {total} Koester DA models in {KOESTER_DIR} "
          f"({n_ok} fetched, {n_skip} skipped).")
    print("Next: bake the WD cube — python scripts/bake_wd_spectra.py "
          "(then run: pytest)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
