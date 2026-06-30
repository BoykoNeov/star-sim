"""Fetch the TMAP hot white-dwarf / CSPN model spectra at build time (endgame Chunk 6b).

The WD-endgame cooling scrub passes through a ~100–400 kK **post-AGB central star**
(the hot star at the heart of a planetary nebula). That regime is hotter than the
Koester DA grid (6a, ≤ 80000 K), so until now it showed the honest "no model"
frame. Chunk 6b fills the gap with **TMAP** — the Tübingen NLTE Model-Atmosphere
Package (Werner et al.; Rauch et al.), served by the **SVO Theoretical Spectra
Server** as the `tmap` collection (the Chunk-0 scoping in
`backend/docs/msg_spectra_build_recipe.md §7` chose this — SVO bulk, *not* the
TheoSSA compute-on-demand service).

Like `fetch_koester`, this is a plain HTTP fetch of ASCII spectra (no MSG / Fortran
/ Docker). The TMAP grid axes are **Teff, log g, and Hemass** (the He *mass*
fraction). A DA white dwarf has a hydrogen atmosphere, so we fetch the **H-rich
slab (Hemass = 0)** to match the DA Koester cube it splices onto. We only need the
hot end (Teff ≥ 80000 K, the Koester ceiling) and the white-dwarf/central-star
gravities (log g 6.5–9.0 — TMAP's nodes that overlap Koester's 6.5–9.5 axis); the
bake (`scripts/bake_wd_spectra.py --tmap-dir`) splices these on as the hot Teff
slab of the same separate WD cube.

Run once after checkout (after `fetch_koester`):

    python -m star_sim.fetch_tmap

It downloads the SSAP index (a VOTable enumerating every model with its `fid` and
its teff/logg/Hemass), filters to the H-rich hot slab we need, then pulls each
model's 2-column ASCII spectrum (λ in **vacuum** Å — the bake converts to air to
match the cube — F_λ in erg/cm²/s/Å) into `data/spectra/grids/tmap/`. Idempotent:
re-runs skip a model already present and non-trivially sized. The data is
gitignored (like `data/mist` and the baked cubes); cite Werner et al. 2003 and
Rauch et al. 2003 on use.

**Unit note (measured, contradicts the §7 scoping guess):** the SVO ascii path
already serves physical erg/cm²/s/Å — the ×π×10⁸ "astrophysical-flux" gotcha is for
the native TheoSSA files, not these. Verified: the TMAP/Koester optical-continuum
flux ratio at the 80000 K / log g 7 overlap node is 0.98–1.08, i.e. the NLTE↔LTE
seam is already graceful and needs no rescale. The bake does the seam check.
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
# every model; per-model ASCII is the same URL with `&fid=N&format=ascii`. SVO bulk
# path (Chunk-0), NOT the TheoSSA compute-on-demand service.
SSAP_BASE = "https://svo2.cab.inta-csic.es/theory/newov2/ssap.php?model=tmap"

TMAP_DIR = SPECTRA_DATA_DIR / "grids" / "tmap"

_USER_AGENT = "star-sim/0.1 (+local teaching tool; endgame Chunk 6b hot-WD/CSPN spectra)"

# A real TMAP ascii spectrum is ~1.8 MB; anything much smaller is a truncated
# download or an error page, so we treat it as missing and re-fetch.
_MIN_BYTES = 100_000

# We splice TMAP onto Koester's hot end (≥ 80000 K) at the WD/central-star
# gravities that overlap Koester's 6.5–9.5 axis. TMAP's log g nodes step by 0.5;
# the bake interpolates them onto Koester's 0.25 grid (clamping 9.25/9.5 → 9.0).
# We fetch the 80000 K node too — the cube uses Koester there, but the bake measures
# the NLTE↔LTE seam agreement on it.
_TEFF_MIN = 80000          # Koester's ceiling — the splice seam
_LOGG_MIN, _LOGG_MAX = 6.5, 9.0
_HEMASS_HRICH = 0.0        # the H-rich (DA-matching) slab

# Each index row is a <TR> with ordered <TD>s; the first three are teff/logg/Hemass
# and the Access.Reference TD carries the model's "fid=N". (We parse the TD columns
# rather than the title string — more robust to a title-format change.)
_TR_RE = re.compile(r"<TR>(.*?)</TR>", re.S)
_TD_RE = re.compile(r"<TD>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</TD>", re.S)
_FID_RE = re.compile(r"fid=(\d+)")


def _http_get(url: str, timeout: int = 180) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def discover_models() -> list[tuple[int, int, float]]:
    """Fetch the SSAP index and return [(fid, teff, logg), …] for the H-rich hot
    slab we need (Hemass = 0, Teff ≥ 80000 K, log g 6.5–9.0).

    Parses each <TR>'s ordered <TD>s (teff, logg, Hemass, …, Access.Reference with
    the fid). Raises if the index is empty or no row carries a fid, so a layout
    change can't silently yield an empty fetch.
    """
    html = _http_get(SSAP_BASE).decode("utf-8", "replace")
    rows = _TR_RE.findall(html)
    if not rows:
        raise RuntimeError(f"no TMAP models found in the SSAP index at {SSAP_BASE}")
    out: list[tuple[int, int, float]] = []
    seen_fid = False
    for tr in rows:
        tds = _TD_RE.findall(tr)
        if len(tds) < 10:
            continue
        try:
            teff = int(round(float(tds[0])))
            logg = float(tds[1])
            hemass = float(tds[2])
        except ValueError:
            continue
        m = _FID_RE.search(tds[9])
        if not m:
            continue
        seen_fid = True
        if (
            abs(hemass - _HEMASS_HRICH) < 1e-9
            and teff >= _TEFF_MIN
            and _LOGG_MIN - 1e-9 <= logg <= _LOGG_MAX + 1e-9
        ):
            out.append((int(m.group(1)), teff, logg))
    if not seen_fid:
        raise RuntimeError(
            f"index parse found no fid in any row — the VOTable layout may have "
            f"changed ({SSAP_BASE})"
        )
    if not out:
        raise RuntimeError(
            "index parsed but no H-rich hot-slab models matched "
            f"(Hemass={_HEMASS_HRICH}, Teff≥{_TEFF_MIN}, log g {_LOGG_MIN}–{_LOGG_MAX})"
        )
    return out


def _model_path(teff: int, logg: float) -> Path:
    # Zero-pad Teff to 6 digits (TMAP reaches 190000) and fix log g to 2 dp so the
    # dir sorts naturally; the ASCII header is the authoritative node source, the
    # name a useful cross-check. The whole dir is the H-rich (Hemass=0) slab.
    return TMAP_DIR / f"tmap_h_{int(round(teff)):06d}_{logg:.2f}.txt"


def _fetch_one(fid: int, teff: int, logg: float, retries: int = 3) -> str:
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
    ap = argparse.ArgumentParser(
        description="Fetch TMAP hot-WD/CSPN spectra (endgame Chunk 6b).")
    ap.add_argument("--workers", type=int, default=4,
                    help="concurrent downloads (default 4 — polite + the files are ~1.8 MB each)")
    args = ap.parse_args(argv)

    TMAP_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Discovering TMAP H-rich hot-slab models from {SSAP_BASE} …")
    models = discover_models()
    teffs = sorted({t for _, t, _ in models})
    loggs = sorted({g for _, _, g in models})
    print(f"  {len(models)} models: Teff {teffs[0]}–{teffs[-1]} K "
          f"({len(teffs)} nodes), log g {loggs[0]}–{loggs[-1]} ({len(loggs)} nodes)")
    print(f"  -> {TMAP_DIR}")

    n_ok = n_skip = n_done = 0
    total = len(models)
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(_fetch_one, fid, t, g): (fid, t, g) for fid, t, g in models}
        for fut in as_completed(futs):
            status = fut.result()  # raises on a model that failed all retries
            n_ok += status == "ok"
            n_skip += status == "skip"
            n_done += 1
            print(f"\r  {n_done}/{total}  ({n_ok} downloaded, {n_skip} already present)",
                  end="", flush=True)
    print()
    print(f"Done: {total} TMAP models in {TMAP_DIR} ({n_ok} fetched, {n_skip} skipped).")
    print("Next: re-bake the WD cube with the hot splice — "
          "python scripts/bake_wd_spectra.py --tmap-dir data/spectra/grids/tmap "
          "(then run: pytest)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
