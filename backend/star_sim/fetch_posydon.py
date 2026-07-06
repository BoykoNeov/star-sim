"""Recon + fetch recipe for the POSYDON co-evolved binary grids — the on-ramp to a
REAL binary grid (path (b) Chunk 4). RECIPE + VALIDATOR ONLY, not a provider yet.

WHY THIS IS THE TARGET (measured recon, 2026-07-06 — advisor-steered discriminator).
The next step of path (b) is "both stars co-evolving on the HR *through time*" — a real
inspiral, not the single snapshot the Götberg grid gives. Two candidate datasets, and
they are NOT two flavours of one thing:

  * POSYDON (Fragos+2023; v2 Andrews+2024) ships individual **co-evolved binary tracks**:
    detailed MESA-binary runs, each an HDF5 with the FULL time history of BOTH stars and
    the orbit. That is exactly what path (b) wants. -> THIS is the on-ramp target.
  * BPASS (Eldridge+2017) is **population synthesis**: integrated SEDs / spectra / number
    counts / SN rates vs age & metallicity for whole co-eval populations — NOT individual
    binary tracks. That is a *different feature* (a population-spectrum sibling), a
    separate future thread, not the two-stars-on-the-HR on-ramp. Do not conflate them.

WHAT POSYDON SHIPS (Zenodo Data Release 2, DOI 10.5281/zenodo.15194708, for code v2.0.0;
open CC-BY):
  * Eight metallicities (Z = 1e-4 .. 2 Zsun), one tarball each `POSYDON_data_v2_grids_*`
    (~10 GB apiece) + a `POSYDON_data_auxiliary.tar.gz`. Multi-GB — gitignored, like the
    MIST/MESA grids; NEVER committed.
  * Per metallicity: TWO single-star grids + FIVE binary grids. The relevant one for
    "two MS stars strip each other" is the **HMS-HMS** grid (Hydrogen-MS + Hydrogen-MS).
    Others: CO-HMS_RLO, CO-HeMS, CO-HeMS_RLO, HMS-HMS (compact-object channels).
  * Grid axes (the initial parameters, per binary track): M1, mass ratio q = M2/M1,
    orbital period P, at the grid's metallicity. A 2D-in-(q, P) fan per M1 — RICHER than
    the Götberg 1D-in-Minit fixed-q=0.8 snapshot (a real design decision, see the plan).
  * Per-track HDF5 keys (POSYDON `PSyRunView`): `binary_history` (orbit vs time — period,
    separation, eccentricity, RLOF flags), `history1` / `history2` (each star's MESA
    history vs time — mass, log_L, log_Teff, log_R, surface X/Y, center abundances, …),
    `final_profile1` / `final_profile2`, `initial_values` / `final_values`. Columns are
    read off `dtype.names`. So a track maps cleanly to a *list of paired StellarStates*
    across time — but the state carries a companion + an orbit, which a single-star
    `StellarState` cannot hold (§3). See the architecture note in the plan.

ARCHITECTURE CONSEQUENCE (the scope the user must weigh — surfaced, NOT decided here).
Unlike every sibling so far (all snap to ONE representative state), a POSYDON track is a
TIME SERIES of a two-body system. That introduces a real time axis + a paired-state shape
the current snapshot siblings don't have — a materially bigger build than `binary.py`. It
also needs its own HDF5 parser (h5py) and MUST NOT import the POSYDON package or a
provider (the §3 sibling discipline). The smallest useful slice is ONE metallicity
(solar) + the ONE HMS-HMS grid; even that is a ~10 GB fetch to extract a fraction from.

=> The concrete decision (which grid + how big a slice + build-now vs defer) is the
USER's, taken once this recon shows the cost. This module is the fetch handoff + a
validator; the parser/provider is the next chunk, gated on that decision.

RECIPE (run once, on the host — a USER handoff, like fetch_gotberg; the data is multi-GB
and Zenodo may rate-limit / need a browser, so this is a documented recipe, not an
automated headless pull):

  1. Open the Zenodo record:  https://doi.org/10.5281/zenodo.15194708  (POSYDON Data
     Release 2). Note the exact file list + per-file sizes there (they supersede any
     name quoted here).
  2. Download ONE metallicity tarball to start — solar is `...v2_grids_1e+00_Zsun...`
     (confirm the exact name on the record). ~10 GB. Optionally the auxiliary tarball.
  3. Extract into  data/posydon/<Zlabel>/  (gitignored). Keep at least the HMS-HMS grid
     HDF5(s); the CO-* grids are for the compact-object channels (later, if ever).
  4. Validate:   python -m star_sim.fetch_posydon
     The validator locates the extracted HDF5 grid(s), opens the first track with h5py,
     and prints the available keys + the `history1`/`history2`/`binary_history` column
     names + the track count — so we design the parser against the REAL schema, never a
     summary (the boron-b8 / VO-7400 / Gotberg-transcription discipline).

Cite Fragos et al. 2023 (ApJS) and the POSYDON v2 release (Andrews et al. 2024) on use.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Repo-root  data/posydon/  (gitignored, like data/mist / data/mesa / data/gotberg_stripped).
_DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "posydon"

_ZENODO_DOI = "10.5281/zenodo.15194708"


def _find_h5(root: Path) -> list[Path]:
    return sorted(root.rglob("*.h5")) + sorted(root.rglob("*.hdf5"))


def validate() -> int:
    """Inspect an extracted POSYDON grid: print the HDF5 keys + column schema of the first
    track so the future parser is designed against the real format. Non-zero if nothing is
    found (so it doubles as a "did the manual fetch land" gate). Defensive about the exact
    layout — POSYDON's grid HDF5s have evolved across versions, so we report what we see
    rather than assert a schema."""
    if not _DATA_DIR.is_dir():
        print(f"No POSYDON data under {_DATA_DIR}.")
        print(f"Fetch one metallicity tarball from https://doi.org/{_ZENODO_DOI} and extract")
        print("it there (see the recipe in this module's docstring), then re-run.")
        return 1

    files = _find_h5(_DATA_DIR)
    if not files:
        print(f"{_DATA_DIR} exists but holds no .h5/.hdf5 grid files — extract the tarball there.")
        return 1

    try:
        import h5py  # optional dep — only needed for this validator / the future parser
    except ImportError:
        print(f"Found {len(files)} HDF5 file(s) under {_DATA_DIR}:")
        for f in files[:10]:
            print(f"  {f.relative_to(_DATA_DIR)}  ({f.stat().st_size / 1e9:.2f} GB)")
        print("\nInstall h5py to inspect the schema:  pip install h5py")
        return 0

    f0 = files[0]
    print(f"Inspecting {f0.relative_to(_DATA_DIR)}  ({f0.stat().st_size / 1e9:.2f} GB) of "
          f"{len(files)} grid file(s):\n")
    with h5py.File(f0, "r") as h5:
        top = list(h5.keys())
        print(f"  top-level keys ({len(top)}): {top[:12]}{' …' if len(top) > 12 else ''}")
        # Peek at the first track group and report its history column schema.
        for key in top:
            node = h5[key]
            if isinstance(node, h5py.Group):
                sub = list(node.keys())
                print(f"  '{key}' is a group with {len(sub)} members, e.g. {sub[:6]}")
                for want in ("binary_history", "history1", "history2"):
                    if want in node:
                        ds = node[want]
                        names = getattr(ds.dtype, "names", None)
                        print(f"    {want}: {ds.shape} rows, columns = "
                              f"{list(names)[:20] if names else ds.dtype}")
                break
            else:
                names = getattr(node.dtype, "names", None)
                if names:
                    print(f"  '{key}': {node.shape} rows, columns = {list(names)[:20]}")
    print("\nSchema captured — design the path (b) Chunk-4 parser against THIS, per the plan.")
    return 0


if __name__ == "__main__":
    sys.exit(validate())
