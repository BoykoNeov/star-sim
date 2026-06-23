"""Fetch a small sample MESA `history.data` grid for `MESAProvider` (spec §5/§6).

`MESAProvider` reads offline-generated MESA history files; this script pulls a
small public sample grid so the provider (and its MIST cross-validation tests)
have real data to run against without anyone needing to install and run MESA.

Provenance / licensing (read this):
  The sample runs come from a public teaching repository,
  `bearums/InteractivePlots` (single-star MESA models at 1/2/4/6/10/14/20 M_sun,
  one metallicity ~Z=0.0022, i.e. [Fe/H] ~ -0.84). That repo carries **no
  license**, so the files are all-rights-reserved upstream. We therefore do NOT
  redistribute them in this repo — they are downloaded on demand into the
  gitignored `data/` tree for *local* use only (the same stance as the MIST
  grids). The pinned commit makes the fetch reproducible.

These are tutorial runs, not a science grid: they're metal-poor, log only
H/He (no per-element isotopes -> empty `metals_*`), and use different MESA
physics from MIST v2.5 — so the cross-validation is a *consistency* check within
physics-choice scatter, not a bit-for-bit match. See test_mesa_vs_mist.py.

Run once after checkout:

    python -m star_sim.fetch_mesa

Idempotent: re-runs skip any file already present at full size.
"""

from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

from .providers.mesa import MESA_DATA_DIR, MESAProvider

# Pinned source: bearums/InteractivePlots @ this commit (reproducible). The
# single-star runs live under models/single/<M>/LOGS/history.data.
_REPO = "bearums/InteractivePlots"
_COMMIT = "b7bf225dd9f2ab97b361357d9a8cd08c1e5703b9"
_PATH_TMPL = (
    "multiple-line-plots/interactive-MESA-plotter/models/single/{m}/LOGS/history.data"
)
_RAW = "https://raw.githubusercontent.com/{repo}/{commit}/{path}"

# The masses available in the source grid (M_sun, integer-labeled dirs).
SAMPLE_MASSES = (1, 2, 4, 6, 10, 14, 20)

_USER_AGENT = "star-sim/0.1 (+local teaching tool; MESAProvider sample fetch)"

_PROVENANCE = f"""MESA sample grid — provenance
==============================
Source repo : https://github.com/{_REPO}
Pinned commit: {_COMMIT}
Path        : multiple-line-plots/interactive-MESA-plotter/models/single/<M>/LOGS/history.data
Masses      : {", ".join(f"{m} M_sun" for m in SAMPLE_MASSES)}
Metallicity : single Z ~ 0.0022 ([Fe/H] ~ -0.84), derived from ZAMS surface Z

The upstream repo carries no license (all rights reserved). These files are
fetched here for LOCAL use only and are not committed to this repository
(data/ is gitignored). Re-fetch with: python -m star_sim.fetch_mesa
"""


def _download(url: str, dest: Path) -> None:
    """Stream `url` to `dest`, skipping if a full-size copy is already present."""
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(req, timeout=120) as resp:
        total = int(resp.headers.get("Content-Length", 0))
        if dest.exists() and total and dest.stat().st_size == total:
            print(f"  already present: {dest.relative_to(MESA_DATA_DIR.parent)} ({total} bytes)")
            return
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.parent / (dest.name + ".tmp")
        with open(tmp, "wb") as fh:
            while chunk := resp.read(1 << 20):  # 1 MiB
                fh.write(chunk)
        tmp.replace(dest)  # atomic: a half-download never looks complete
        print(f"  fetched: {dest.relative_to(MESA_DATA_DIR.parent)} ({dest.stat().st_size} bytes)")


def main(argv: list[str] | None = None) -> int:
    MESA_DATA_DIR.mkdir(parents=True, exist_ok=True)
    (MESA_DATA_DIR / "PROVENANCE.txt").write_text(_PROVENANCE)

    print(f"Fetching {len(SAMPLE_MASSES)} MESA history.data runs into {MESA_DATA_DIR} ...")
    for m in SAMPLE_MASSES:
        path = _PATH_TMPL.format(m=m)
        url = _RAW.format(repo=_REPO, commit=_COMMIT, path=path)
        dest = MESA_DATA_DIR / f"{m}Msun" / "history.data"
        try:
            _download(url, dest)
        except Exception as exc:  # noqa: BLE001 — report and continue with the rest
            print(f"  FAILED {m} M_sun: {exc}")

    # Sanity: load through the provider so a bad fetch surfaces now, not on first request.
    print("Verifying the grid loads through MESAProvider ...")
    try:
        ranges = MESAProvider().parameter_ranges()
        print(f"  ok: mass {ranges['mass_msun']}, [Fe/H] {ranges['feh']['min']:.2f}")
    except Exception as exc:  # noqa: BLE001
        print(f"  WARNING: provider did not load cleanly: {exc}")
        return 1

    print("Done. Run: pytest  (or swap MESAProvider into api.py to view it).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
