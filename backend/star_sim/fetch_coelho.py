"""Fetch Coelho (2014) high-resolution stellar spectra for the [α/Fe] axis (atlas
Tier B — the thick-disk/halo subpopulation).

MIST evolution is solar-scaled (no α axis), so [α/Fe] is a **spectrum-only** axis:
raising [α/Fe] at fixed [Fe/H] deepens the O/Mg/Si/Ca/Ti lines (and molecular TiO)
without moving the star's *track*. The one public grid with a clean matched
**[α/Fe] = 0.0 AND +0.4** pair across a full (Teff, log g, [Fe/H]) grid is **Coelho
2014** (arXiv 1404.3243; MNRAS 440, 1027C), served by the **SVO Theoretical Spectra
Server** as the `coelho_highres` collection.

Like the WD/WR grids (`fetch_koester`/`fetch_tmap`/`fetch_powr`), and UNLIKE the main
cube, this is a plain HTTP fetch of ASCII spectra — **no MSG/pymsg/Fortran/Docker**
(the CAP18-*large* grid that carries α is 73 GB and needs the Docker bake; this path
sidesteps all of it). The companion bake (`scripts/bake_alpha_spectra.py`) is pure
numpy and runs on the host.

Measured (Gate 1, 2026-07-02, through the 2.5 Å runtime binning): α is clearly
visible and **Teff-gated** — it deepens Ca I 4227 / Ca II K / Mg b / Ca II triplet /
TiO in the cool→F window, goes marginal at A (~9000 K), and is **dead ≥~12000 K**.
So we fetch only the **cool subset (Teff ≤ 10000 K by default)**; hotter stars hand
off to the main cube, mirroring the WD-gravity cube switch. The matched-[α/Fe] [Fe/H]
set on disk is {−1.0, −0.5, 0.0, +0.2} (α=0 exists only there; α=0.4 spans more).

Run once after checkout (default = the full matched [Fe/H] axis; narrow it with --feh):

    python -m star_sim.fetch_coelho                       # full: [Fe/H] -1.0,-0.5,0.0,+0.2
    python -m star_sim.fetch_coelho --feh -0.5,0.0        # the cheaper {−0.5, 0.0} subset

It fetches the SSAP index (a VOTable listing every model + params + `fid`), then pulls
each matched (Teff, log g, [Fe/H]) model at BOTH [α/Fe] into `data/spectra/grids/
coelho/`. Each highres model is ~10.7 MB (325001 λ pts at 0.02 Å — the bake keeps only
the 2400-bin 3000–9000 Å window), so the {−0.5,0.0} MVP is ~8 GB, the full 4-[Fe/H]
axis ~17 GB. Idempotent: re-runs skip a model already present and non-trivially sized.
Data is gitignored (like `data/mist` and the baked cubes); cite Coelho 2014 on use.
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

# The collection's SSAP base. The index (no `fid`) returns a VOTable enumerating every
# model; per-model ASCII is the same URL with `&fid=N&format=ascii` (the Koester/TMAP
# bulk path). `coelho_highres` is the line-bearing grid (the `coelho_sed` low-res SED
# grid at R~200 would not resolve the 2.5 Å lines the α effect lives in).
SSAP_BASE = "https://svo2.cab.inta-csic.es/theory/newov2/ssap.php?model=coelho_highres"

COELHO_DIR = SPECTRA_DATA_DIR / "grids" / "coelho"

_USER_AGENT = "star-sim/0.1 (+local teaching tool; [alpha/Fe] axis, Coelho 2014)"

# A real Coelho highres ASCII spectrum is ~10.7 MB; anything much smaller is a
# truncated download or an error page, so we treat it as missing and re-fetch.
_MIN_BYTES = 1_000_000


def _http_get(url: str, timeout: int = 300) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def discover_models() -> list[dict]:
    """Fetch the SSAP index and return [{teff,logg,feh,afe,fid}, …] for every model.

    The VOTable's TABLEDATA rows carry the axis values in the first four <TD> cells
    (teff, logg, meta=[Fe/H], afe=[α/Fe]) and the model's `fid=N` inside the
    Access.Reference cell. We parse per <TR> so the four axis values and the fid stay
    aligned (the title's own `[Fe/H]:` field is blank — the `meta` column is
    authoritative), and assert we found some so a layout change fails loudly."""
    html = _http_get(SSAP_BASE).decode("utf-8", "replace")
    models: list[dict] = []
    for tr in re.findall(r"<TR>(.*?)</TR>", html, re.S):
        cells = [re.sub(r"<[^>]+>", "", c).strip()
                 for c in re.findall(r"<TD>(.*?)</TD>", tr, re.S)]
        fid_m = re.search(r"fid=(\d+)", tr)
        if not fid_m or len(cells) < 4:
            continue
        try:
            models.append(dict(teff=float(cells[0]), logg=float(cells[1]),
                               feh=float(cells[2]), afe=float(cells[3]),
                               fid=int(fid_m.group(1))))
        except ValueError:
            continue
    if not models:
        raise RuntimeError(f"no Coelho models found in the SSAP index at {SSAP_BASE}")
    return models


def _model_path(teff: float, logg: float, feh: float, afe: float) -> Path:
    # Encode the four axis values so the dir sorts naturally and the bake can recover
    # the node from the filename (the ASCII header is authoritative, name is a check).
    return COELHO_DIR / (f"coelho_{int(round(teff)):05d}_g{logg:+.2f}"
                         f"_z{feh:+.2f}_a{afe:.1f}.txt")


def _fetch_one(m: dict, retries: int = 3) -> str:
    dest = _model_path(m["teff"], m["logg"], m["feh"], m["afe"])
    if dest.exists() and dest.stat().st_size >= _MIN_BYTES:
        return "skip"
    url = f"{SSAP_BASE}&fid={m['fid']}&format=ascii"
    last: Exception | None = None
    for attempt in range(retries):
        try:
            data = _http_get(url)
            if len(data) < _MIN_BYTES:
                raise RuntimeError(f"short response ({len(data)} bytes) for fid={m['fid']}")
            tmp = dest.with_suffix(".txt.tmp")
            tmp.write_bytes(data)
            tmp.replace(dest)
            return "ok"
        except Exception as exc:  # noqa: BLE001 — retry transient SVO hiccups
            last = exc
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"failed to fetch fid={m['fid']} ({m}): {last}")


def select(models: list[dict], fehs: list[float], teff_max: float) -> list[dict]:
    """Keep only models at the requested [Fe/H] and Teff ≤ teff_max whose (teff, logg,
    feh) node has BOTH [α/Fe] present (a toggle needs the matched pair — an unmatched
    node would clamp to the other α on flip, which is a lie). Reports dropped-unmatched."""
    want_feh = {round(f, 2) for f in fehs}
    pool = [m for m in models if round(m["feh"], 2) in want_feh and m["teff"] <= teff_max]
    have = {(m["teff"], m["logg"], m["feh"], m["afe"]) for m in pool}
    matched = [m for m in pool
               if ((m["teff"], m["logg"], m["feh"], 0.0) in have
                   and (m["teff"], m["logg"], m["feh"], 0.4) in have)]
    n_drop = len(pool) - len(matched)
    if n_drop:
        print(f"  ({n_drop} unmatched-alpha nodes dropped - a toggle needs both a=0 and a=0.4)")
    return matched


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Fetch Coelho 2014 highres spectra for the [alpha/Fe] axis.")
    ap.add_argument("--feh", default="-1.0,-0.5,0.0,0.2",
                    help="comma [Fe/H] list to fetch (default the full matched axis "
                         "'-1.0,-0.5,0.0,0.2' — ~17 GB; the cheaper MVP is '-0.5,0.0')")
    ap.add_argument("--teff-max", type=float, default=10000.0,
                    help="fetch Teff <= this (default 10000 — α is dead hotter; the "
                         "panel hands off to the main cube above)")
    ap.add_argument("--workers", type=int, default=4,
                    help="concurrent downloads (default 4 — polite to SVO; the files "
                         "are large)")
    args = ap.parse_args(argv)
    fehs = [float(x) for x in args.feh.split(",")]

    COELHO_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Discovering Coelho highres models from {SSAP_BASE} …")
    all_models = discover_models()
    print(f"  {len(all_models)} models in the collection")
    models = select(all_models, fehs, args.teff_max)
    teffs = sorted({m["teff"] for m in models})
    loggs = sorted({m["logg"] for m in models})
    afes = sorted({m["afe"] for m in models})
    print(f"  fetching {len(models)} models: [Fe/H] {fehs}, Teff "
          f"{teffs[0]:.0f}-{teffs[-1]:.0f} K ({len(teffs)} nodes), "
          f"log g {loggs[0]}-{loggs[-1]} ({len(loggs)} nodes), [alpha/Fe] {afes}")
    print(f"  ~{len(models) * 10.7 / 1024:.1f} GB  -> {COELHO_DIR}")

    n_ok = n_skip = n_done = 0
    total = len(models)
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(_fetch_one, m): m for m in models}
        for fut in as_completed(futs):
            status = fut.result()  # raises on a model that failed all retries
            n_ok += status == "ok"
            n_skip += status == "skip"
            n_done += 1
            if n_done % 10 == 0 or n_done == total:
                print(f"\r  {n_done}/{total}  ({n_ok} downloaded, {n_skip} present)",
                      end="", flush=True)
    print()
    print(f"Done: {total} Coelho models in {COELHO_DIR} ({n_ok} fetched, {n_skip} skipped).")
    print("Next: bake the alpha cube - python scripts/bake_alpha_spectra.py (then: pytest)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
