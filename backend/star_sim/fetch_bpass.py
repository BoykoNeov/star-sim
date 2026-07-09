"""Recon + fetch recipe for the BPASS coeval-population spectra — the on-ramp to the
first ENSEMBLE sibling (the population overlay). RECIPE + VALIDATOR ONLY, not a provider yet.

WHY THIS IS A SEPARATE THING FROM POSYDON (do not conflate — see fetch_posydon.py):
  * POSYDON ships co-evolved binary *tracks* (both stars + orbit vs time) — that fed the
    two-stars-on-the-HR movie (`posydon.py`, `/binary_track`). A single SYSTEM through time.
  * BPASS (Eldridge+2017; Stanway & Eldridge 2018) is **population synthesis**: the
    integrated spectrum / number census / SN-rate of a whole COEVAL POPULATION (a million
    stars born together) vs age & metallicity, split single-star vs binary. An ENSEMBLE, not
    a track. That is what the population overlay wants. -> THIS is that on-ramp.

WHAT BPASS v2.3 SHIPS (measured recon 2026-07-10; the SSP-spectra record):
  * Zenodo record 10.5281/zenodo.6383329, CC-BY 4.0. Ten HDF5 files, ~531 MB each:
        SSP_Spectra_BPASSv2.3_{sin,bin}-imf135_300-alpha{-02,+00,+02,+04,+06}.hdf5
    `sin` = single-star populations; `bin` = includes binaries. `alpha+00` = solar-scaled
    (matches this sim's non-alpha evolution axis). Each file holds ALL 13 metallicities x the
    age grid x the wavelength grid for one (IMF, alpha). ~531 MB is IN-SESSION fetchable
    (Zenodo direct URLs), unlike POSYDON's ~10 GB/Z — so this validator can optionally pull
    the sin+bin alpha+00 pair itself (opt-in), not just hand off a recipe.
  * 13 metallicities (mass fraction Z): 1e-4, 0.001, 0.002, 0.003, 0.004, 0.006, 0.008,
    0.010, 0.014, 0.017, 0.020, 0.030, 0.040. Map to [Fe/H]=log10(Z/Zsun) at bake time
    (confirm BPASS's solar-Z convention against the release before pinning the label).
  * Population born with 1e6 Msun; the classic age axis is 51 log-age bins (log(age/yr)
    6.0..11.0 by 0.1 dex). VALIDATE the exact axes against the real HDF5 (this module prints
    them) — the boron-b8 / Gotberg-transcription discipline: never hardcode a schema unseen.
  * The HRD "numbers"/stellar-census product is a DIFFERENT release (classic plain-text .dat
    on the Warwick/gSTAR distribution), NOT this Zenodo spectra record. The HR-density overlay
    (plan Chunk 2) needs its own recon; do not infer its schema from the spectra file here.

ARCHITECTURE CONSEQUENCE (the scope, surfaced not decided here):
  A BPASS SSP is a FLUX ARRAY f_lambda(lambda) per (Z, age, single|binary) — not a
  StellarState, not a pair, not a track of pairs. The first ensemble sibling. Runtime
  `bpass.py` will import only numpy/stdlib (a population is not a star), never a provider
  (SS3); `/population` bypasses PROVIDER. Extraction may use h5py / BPASS's HOKI reader
  host-side (the MESA-structure precedent) to bake a compact void-free .npz; the runtime
  reads that flat, HDF5-free. This validator reveals the real internal schema so the bake +
  parser are designed against it. Full design: docs/plans/coeval-ensemble-overlay.md.

RECIPE:
  1. (Optional auto-fetch) `python -m star_sim.fetch_bpass --download` pulls the sin+bin
     alpha+00 pair (~1 GB) from Zenodo into data/bpass/ (gitignored). Or download by hand
     from https://doi.org/10.5281/zenodo.6383329 into that folder.
  2. Validate: `python -m star_sim.fetch_bpass`
     Opens the first HDF5 and prints its datasets/shapes + the wavelength & age axes + how
     metallicity is keyed — so the plan Chunk-1 bake/parser is designed against the REAL
     schema, never a summary.

Cite Eldridge et al. 2017 (PASA) + Stanway & Eldridge 2018 (MNRAS) + the BPASS v2.3 release
paper on use.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Repo-root  data/bpass/  (gitignored, like data/posydon / data/mist).
_DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "bpass"

_ZENODO_DOI = "10.5281/zenodo.6383329"
_ZENODO_RECORD = "6383329"
# The solar-scaled (alpha+00) single + binary SSP-spectra pair — the first slice (~1 GB).
_WANTED = (
    "SSP_Spectra_BPASSv2.3_sin-imf135_300-alpha+00.hdf5",
    "SSP_Spectra_BPASSv2.3_bin-imf135_300-alpha+00.hdf5",
)


def _find_h5(root: Path) -> list[Path]:
    return sorted(root.rglob("*.h5")) + sorted(root.rglob("*.hdf5"))


def download() -> int:
    """Opt-in: pull the alpha+00 sin+bin pair from Zenodo into _DATA_DIR. ~1 GB total.
    Kept behind a flag (never automatic) — a 531 MB x2 network pull is a deliberate act."""
    try:
        import urllib.request
    except ImportError:  # pragma: no cover - stdlib always present
        print("urllib unavailable; download by hand from https://doi.org/%s" % _ZENODO_DOI)
        return 1
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    for name in _WANTED:
        dest = _DATA_DIR / name
        if dest.exists():
            print(f"  have {name} ({dest.stat().st_size / 1e6:.0f} MB) — skipping")
            continue
        url = f"https://zenodo.org/records/{_ZENODO_RECORD}/files/{name}?download=1"
        print(f"  fetching {name} (~531 MB) from Zenodo …")
        try:
            urllib.request.urlretrieve(url, dest)  # noqa: S310 - trusted Zenodo host
        except Exception as exc:  # noqa: BLE001 - report + fall back to the handoff recipe
            print(f"    failed: {exc}")
            print(f"    download by hand from https://doi.org/{_ZENODO_DOI} into {_DATA_DIR}")
            return 1
        print(f"    saved {dest.stat().st_size / 1e6:.0f} MB")
    return 0


def validate() -> int:
    """Inspect an extracted BPASS SSP HDF5: print datasets/shapes + the wavelength/age/Z axes
    so the plan Chunk-1 bake + parser are designed against the real format. Non-zero if
    nothing is found (doubles as a "did the fetch land" gate). Reports what it sees rather
    than asserting a schema — BPASS HDF5 layouts vary across versions."""
    if not _DATA_DIR.is_dir():
        print(f"No BPASS data under {_DATA_DIR}.")
        print(f"Run  python -m star_sim.fetch_bpass --download  (opt-in ~1 GB), or fetch by")
        print(f"hand from https://doi.org/{_ZENODO_DOI} into that folder, then re-run.")
        return 1

    files = _find_h5(_DATA_DIR)
    if not files:
        print(f"{_DATA_DIR} exists but holds no .h5/.hdf5 files — see the recipe (--download).")
        return 1

    try:
        import h5py  # optional dep — only for this validator / the future bake
    except ImportError:
        print(f"Found {len(files)} HDF5 file(s) under {_DATA_DIR}:")
        for f in files[:10]:
            print(f"  {f.relative_to(_DATA_DIR)}  ({f.stat().st_size / 1e6:.0f} MB)")
        print("\nInstall h5py to inspect the schema:  pip install h5py")
        return 0

    f0 = files[0]
    print(f"Inspecting {f0.relative_to(_DATA_DIR)}  ({f0.stat().st_size / 1e6:.0f} MB) of "
          f"{len(files)} file(s):\n")

    def _describe(name: str, obj: object) -> None:  # h5py visitor
        import h5py
        if isinstance(obj, h5py.Dataset):
            print(f"  dataset  {name:40s} shape={obj.shape} dtype={obj.dtype}")
        elif isinstance(obj, h5py.Group):
            print(f"  group    {name}")

    with h5py.File(f0, "r") as h5:
        top = list(h5.keys())
        print(f"  top-level keys ({len(top)}): {top[:20]}{' …' if len(top) > 20 else ''}\n")
        # Full walk (bounded) so we see the real Z/age/wavelength layout.
        count = [0]

        def _visit(name: str, obj: object) -> None:
            if count[0] >= 60:
                return
            _describe(name, obj)
            count[0] += 1

        h5.visititems(_visit)
        if count[0] >= 60:
            print("  … (truncated at 60 entries)")

        # Attributes often carry the age/metallicity axes — surface them.
        if h5.attrs:
            print(f"\n  root attrs: {dict(list(h5.attrs.items())[:12])}")

    print("\nSchema captured — design the plan Chunk-1 bake/parser against THIS "
          "(docs/plans/coeval-ensemble-overlay.md).")
    return 0


if __name__ == "__main__":
    if "--download" in sys.argv[1:]:
        rc = download()
        if rc != 0:
            sys.exit(rc)
    sys.exit(validate())
