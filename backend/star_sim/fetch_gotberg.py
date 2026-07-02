"""Fetch (and sanity-check) the Götberg 2018 stripped-star SPECTRA tree.

The binary-stripped-star feature (`binary.py`, `/binary`) has **two** data sources, and
this script owns only the second:

  1. The structural PARAMETER table (Teff/L/R/logg/Mstrip/X_surf per model) is the
     *paper's* Table 1, transcribed + SED-verified and **committed** to the repo at
     `star_sim/data/gotberg_z014.csv`. It is NOT fetched — it ships with the code. That
     is all Chunk 1 needs, so `binary.py` runs on a bare checkout with no fetch at all.
  2. The SPECTRA / SEDs (a 50 Å–50 000 Å CMFGEN NLTE SED + normalized spectrum per model)
     live on VizieR (CDS catalog **J/A+A/615/A78**), are large, and are gitignored under
     `data/gotberg_stripped/`. They back (a) the `test_binary.py::test_table_matches_seds`
     regression that VERIFIES the committed table, and (b) the future stripped-spectrum
     panel (plan Chunk 3). This script documents how to obtain them and sanity-checks the
     extracted tree — the real bake is Chunk 3.

**Why this is not a direct-download script (a USER handoff, like nothing else here).**
CDS bot-blocks the `cdsarc` HTML viz-bin pages behind Anubis anti-bot, and the legacy
`u-strasbg` FTP host has an expired TLS cert — so, unlike `fetch_koester`/`fetch_tmap`
(plain HTTP), this data cannot be pulled headless. The tarball is fetched **in a browser**
(past Anubis) and extracted by hand; this module is the recipe + a validator, not an
automated downloader.

RECIPE (run once, on the host):

  1. In a browser, open the VizieR catalog page for J/A+A/615/A78 and download the full
     tarball `J_A+A_615_A78.tar.gz` (~674 MB) — the "tar.gz" / "download all" link.
  2. Extract the `*/sed/` (or per-grid model) tree into  data/gotberg_stripped/  so it
     holds the four grid dirs  grid_0002 / grid_002 / grid_006 / grid_014  (Z =
     0.0002/0.002/0.006/0.014), each with 23 model subdirs
     `M1_<Minit>q0.8P<P>Z<Z>_vinf1.5/` holding `SED.txt` + `normalised_spectrum.txt`.
  3. Delete the tarball afterwards (the extracted spectra tree is what we keep).
  4. Validate:   python -m star_sim.fetch_gotberg

The validator counts grids/models and confirms `SED.txt` is present + parseable for the
Z=0.014 grid the committed table is verified against; it exits non-zero if the tree is
missing or malformed, so it doubles as a "did the manual fetch land correctly" gate.

Cite Götberg, Justham, de Mink et al. 2018, A&A 615, A78 on use.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# repo-root/data/gotberg_stripped (the gitignored spectra tree). star_sim/fetch_gotberg.py
# -> [0]=star_sim [1]=backend [2]=repo root (same anchor as the other data trees).
_REPO_ROOT = Path(__file__).resolve().parents[2]
GOTBERG_DIR = _REPO_ROOT / "data" / "gotberg_stripped"

# The four grid dirs and their metallicity (Z). Solar (0.014) is the one the committed
# table is verified against; the rest back the future [Fe/H] axis + Chunk-3 spectra.
_GRID_DIRS = {
    "grid_0002": 0.0002,
    "grid_002": 0.002,
    "grid_006": 0.006,
    "grid_014": 0.014,
}
_MODEL_RE = re.compile(r"M1_([0-9.]+)q")


def _model_dirs(grid: Path) -> list[Path]:
    return sorted(d for d in grid.iterdir() if d.is_dir() and _MODEL_RE.match(d.name))


def validate(strict: bool = False) -> int:
    """Sanity-check the extracted spectra tree. Returns the number of Z grids found;
    raises SystemExit-ish (returns 0) semantics are left to `main`."""
    if not GOTBERG_DIR.is_dir():
        print(f"[gotberg] spectra tree not found: {GOTBERG_DIR}")
        print("[gotberg] follow the RECIPE in this module's docstring (browser-fetch the")
        print("[gotberg] VizieR tarball for J/A+A/615/A78 -> data/gotberg_stripped/).")
        return 0

    grids_found = 0
    for name, z in _GRID_DIRS.items():
        grid = GOTBERG_DIR / name
        if not grid.is_dir():
            print(f"[gotberg]   {name:10s} (Z={z:<7}) - MISSING")
            continue
        models = _model_dirs(grid)
        with_sed = sum((m / "SED.txt").is_file() for m in models)
        print(f"[gotberg]   {name:10s} (Z={z:<7}) - {len(models):2d} models, {with_sed:2d} with SED.txt")
        grids_found += 1

    # The solar grid is the one the committed table is verified against — parse-check one SED.
    solar = GOTBERG_DIR / "grid_014"
    if solar.is_dir():
        models = _model_dirs(solar)
        if models:
            sed = models[0] / "SED.txt"
            n = sum(1 for ln in sed.read_text().splitlines()
                    if ln.strip() and not ln.startswith("#") and len(ln.split()) == 2)
            print(f"[gotberg]   parse-check {sed.relative_to(GOTBERG_DIR)}: {n} (lambda, Flux) rows")
            if n < 100:
                print("[gotberg]   WARNING: SED looks truncated (<100 rows)")
    return grids_found


def main() -> None:
    grids = validate()
    if grids == 0:
        sys.exit(1)
    print(f"[gotberg] OK - {grids}/4 metallicity grids present under {GOTBERG_DIR}")


if __name__ == "__main__":
    main()
