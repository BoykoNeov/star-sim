"""Build-time bake of the BPASS coeval-population HR-DIAGRAM number-density cube — Chunk 2
of the coeval-ensemble overlay (docs/plans/coeval-ensemble-overlay.md).

Where Chunk 1 (bake_bpass_spectra.py) baked the integrated SSP *spectrum* onto the SED
panel, Chunk 2 bakes the population's *number density over the HR diagram* onto the HR
panel: at the marker's ([Fe/H], age), how many stars per 1e6 Msun sit in each (logTeff,
logL) cell — split single-star vs. +binaries. The headline (Gate 0, MEASURED off these
files 2026-07-10): the BINARY population lights up hot / stripped-He HRD cells the
SINGLE-star population leaves EMPTY —
    * hot region (logTeff>4.4) at 10–50 Myr: single = 0 stars, binary ~220–320 (blue
      stragglers / rejuvenated hot stars — single-star pops have no O stars that old);
    * stripped-He (low surface H) stars: single ~0 at every age, binary ~33x more overall.
That is the HR-panel analogue of Chunk 1's UV-longevity wedge, and something a single-star
sim structurally cannot show.

INPUT — a DIFFERENT release from Chunk 1's v2.3 SSP spectra (the v2.3 Zenodo record is
spectra-ONLY; confirmed). The HR-diagram "hrs" number-density files live in the BPASS
v2.2.1 fiducial-output release, the imf135_300 zip on the STARTER-KIT Zenodo record
10.5281/zenodo.7340797 (CC-BY; 1.5 GB). We never download the whole zip: Zenodo honours
HTTP range requests, so a tiny range-backed file object handed to zipfile reads the central
directory from the tail and then pulls only the 26 `hrs-{sin,bin}-imf135_300.z*.dat` members
(~0.3–0.8 MB compressed each). The v2.2.1-HRD vs v2.3-spectra version gap is a caption-owned
systematic (different panel, no byte-consistency requirement) — see the plan.

HRS FILE SCHEMA (from hoki.load._hrTL / hoki.hrdiagrams.HRDiagram — measured, not recalled):
    each hrs file is a (45900, 100) ASCII array = 51 ages x 9 blocks x 100 rows.
    The 9 blocks are 3 HR types {TL, Tg, TTG} x 3 surface-H bins {high, med, low}.
    We take TYPE TL (temperature/luminosity) = rows 0:15300:
        high_H  a[0:5100]     medium_H a[5100:10200]     low_H a[10200:15300]
    each reshaped (51, 100, 100).  grid[age, ti, li]:
        logTeff = 0.1 + 0.1*ti   (ti 0..99 -> 0.1..10.0; REAL stars ti~33..55)
        logL    = -2.9 + 0.1*li  (li 0..99 -> -2.9..7.0)
    values = number of stars per 1e6 Msun in that cell at that age bin (the RAW, per-age
    count — hoki's extra dt time-weighting is only for stacking across an age RANGE; a single
    age snapshot uses the raw grid). all_H = high+med+low; low_H alone = the stripped/He stars.

AGES: the standard BPASS 51-bin grid, log age 6.0..11.0 (1 Myr..100 Gyr) -> age_gyr =
10**(logage-9), matching the Chunk-1 cube's age axis exactly (snap in log10 age).
METALLICITY: keyed by z-code in the FILENAME (zem5..z040), NOT an already-[Fe/H] axis like
the spectra cube — we map z-code -> Z -> [Fe/H]=log10(Z/0.020) ourselves (the plan's gotcha).

OUTPUT: a compact `data/bpass/bpass_hrd.npz` (~15 MB, gitignored like every other grid):
    bake_version   int
    feh            (13,)   [Fe/H]=log10(Z/0.020), ascending
    age_gyr        (51,)   10**(logage-9), matching bpass_ssp.npz
    logt           (nT,)   cropped logTeff bin centres (the occupied window + margin)
    logl           (nL,)   cropped logL bin centres
    dens_sin       (13,51,nT,nL) float32  stars/1e6Msun per cell, single-star (all surface-H)
    dens_bin       (13,51,nT,nL) float32  same, +binaries
    stripped_sin   (13,51) float32  low-surface-H (n1<1e-3) total per age, single
    stripped_bin   (13,51) float32  same, +binaries  (the ~33x stripped-star caption stat)
    grid_name, zsun_bpass   provenance

Run on the host (no local copy of the 1.5 GB zip needed — surgical range extraction):
    python scripts/bake_bpass_hrd.py            # -> data/bpass/bpass_hrd.npz
    python scripts/bake_bpass_hrd.py --from-dir <dir with hrs-*.dat>   # re-bake, no network

Cite Eldridge et al. 2017 (PASA 34, e058); Stanway & Eldridge 2018 (MNRAS 479, 75).
"""

from __future__ import annotations

import argparse
import io
import sys
import urllib.request
import zipfile
from pathlib import Path

import numpy as np

# Must match bpass.py's BAKE_VERSION_HRD; a stale cube is rejected at load.
BAKE_VERSION_HRD = 1

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DATA_DIR = _REPO_ROOT / "data" / "bpass"
_OUT = "bpass_hrd.npz"

_ZSUN_BPASS = 0.020
# The v2.2.1 fiducial-output zip on the starter-kit Zenodo record (CC-BY). Range-fetchable.
_ZIP_URL = "https://zenodo.org/api/records/7340797/files/bpass_v2.2.1_imf135_300.zip/content"
_ZIP_PREFIX = "bpass_v2.2.1_imf135_300/"

# z-code -> Z (BPASS convention). Ascending Z so the [Fe/H] axis comes out ascending, like
# the spectra cube. zem5=1e-5 .. z040=0.040.
_ZCODES = [
    ("zem5", 1e-5), ("zem4", 1e-4), ("z001", 0.001), ("z002", 0.002), ("z003", 0.003),
    ("z004", 0.004), ("z006", 0.006), ("z008", 0.008), ("z010", 0.010), ("z014", 0.014),
    ("z020", 0.020), ("z030", 0.030), ("z040", 0.040),
]

# TL-block row spans in the (45900,100) file (hoki.load._hrTL).
_TL_HI, _TL_MED, _TL_LO = (0, 5100), (5100, 10200), (10200, 15300)
LOGT_FULL = 0.1 - 0.1 + 0.1 * np.arange(1, 101)   # 0.1..10.0 (T_coord)
LOGL_FULL = -2.9 + 0.1 * np.arange(100)           # -2.9..7.0 (L_coord)
LOGAGE = 6.0 + 0.1 * np.arange(51)                # 6.0..11.0 (log yr)


class _HttpRangeFile(io.RawIOBase):
    """Lazy HTTP-range-backed seekable file — hand to zipfile to read the central directory
    (tail) + pull only the members we extract, never the whole 1.5 GB zip."""

    def __init__(self, url: str):
        self.url, self.pos = url, 0
        with urllib.request.urlopen(urllib.request.Request(url, method="HEAD")) as r:
            self.size = int(r.headers["Content-Length"])

    def seekable(self): return True
    def readable(self): return True
    def tell(self): return self.pos

    def seek(self, offset, whence=0):
        self.pos = offset if whence == 0 else self.pos + offset if whence == 1 else self.size + offset
        return self.pos

    def read(self, n=-1):
        if n is None or n < 0:
            n = self.size - self.pos
        if n == 0 or self.pos >= self.size:
            return b""
        end = min(self.pos + n, self.size) - 1
        req = urllib.request.Request(self.url, headers={"Range": f"bytes={self.pos}-{end}"})
        with urllib.request.urlopen(req) as r:
            data = r.read()
        self.pos += len(data)
        return data


def _parse_tl(text: bytes) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(45900,100) ASCII -> the three TL surface-H blocks, each (51,100,100)."""
    # np.fromstring(sep=" ") is the fast whitespace-ASCII path (handles "0.0E+00"); reshape
    # to the (45900,100) grid. The file is exactly 45900 rows x 100 cols.
    a = np.fromstring(text, dtype=float, sep=" ").reshape(45900, 100)
    hi = a[_TL_HI[0]:_TL_HI[1]].reshape(51, 100, 100)
    med = a[_TL_MED[0]:_TL_MED[1]].reshape(51, 100, 100)
    lo = a[_TL_LO[0]:_TL_LO[1]].reshape(51, 100, 100)
    return hi, med, lo


def _read_source(from_dir: Path | None):
    """Yield (zcode, kind, raw_bytes) for the 26 hrs files — from a local dir if given,
    else surgically from the Zenodo zip via range requests."""
    if from_dir is not None:
        for zc, _ in _ZCODES:
            for kind in ("sin", "bin"):
                p = from_dir / f"hrs-{kind}-imf135_300.{zc}.dat"
                if not p.is_file():
                    raise SystemExit(f"missing {p}")
                yield zc, kind, p.read_bytes()
        return
    print(f"Opening the v2.2.1 zip on Zenodo via range requests (no full download) ...")
    zf = zipfile.ZipFile(_HttpRangeFile(_ZIP_URL))
    for zc, _ in _ZCODES:
        for kind in ("sin", "bin"):
            name = f"{_ZIP_PREFIX}hrs-{kind}-imf135_300.{zc}.dat"
            print(f"  fetching {name.split('/')[-1]} ...")
            yield zc, kind, zf.read(name)


def bake(from_dir: Path | None) -> int:
    nZ, nAge = len(_ZCODES), 51
    dens_sin = np.zeros((nZ, nAge, 100, 100), np.float64)
    dens_bin = np.zeros((nZ, nAge, 100, 100), np.float64)
    strip_sin = np.zeros((nZ, nAge), np.float64)
    strip_bin = np.zeros((nZ, nAge), np.float64)

    zidx = {zc: i for i, (zc, _) in enumerate(_ZCODES)}
    for zc, kind, raw in _read_source(from_dir):
        hi, med, lo = _parse_tl(raw)
        all_H = hi + med + lo                    # (51,100,100)  [age, ti, li]
        strip = lo.sum(axis=(1, 2))              # (51,) low-surface-H total per age
        zi = zidx[zc]
        if kind == "sin":
            dens_sin[zi] = all_H; strip_sin[zi] = strip
        else:
            dens_bin[zi] = all_H; strip_bin[zi] = strip

    # Crop the T,L window to the OCCUPIED region (+1-cell margin) across the WHOLE cube —
    # the 100x100 grid runs logT 0.1..10.0 but real stars only occupy ~3.4..5.5, mostly empty
    # (the advisor's flag). Keep the bounding box of any nonzero cell in either population.
    occ = (dens_sin.sum(axis=(0, 1)) + dens_bin.sum(axis=(0, 1))) > 0   # (100,100) over ti,li
    ti_nz, li_nz = np.nonzero(occ)
    t0, t1 = max(ti_nz.min() - 1, 0), min(ti_nz.max() + 2, 100)
    l0, l1 = max(li_nz.min() - 1, 0), min(li_nz.max() + 2, 100)
    print(f"  occupied window: logT {LOGT_FULL[t0]:.1f}..{LOGT_FULL[t1-1]:.1f} "
          f"({t1-t0} bins), logL {LOGL_FULL[l0]:.1f}..{LOGL_FULL[l1-1]:.1f} ({l1-l0} bins)")

    feh = np.array([np.log10(z / _ZSUN_BPASS) for _, z in _ZCODES], float)
    age_gyr = 10.0 ** (LOGAGE - 9.0)

    out = _DATA_DIR / _OUT
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        out,
        bake_version=np.int64(BAKE_VERSION_HRD),
        feh=feh,
        age_gyr=age_gyr,
        logt=LOGT_FULL[t0:t1].astype(np.float64),
        logl=LOGL_FULL[l0:l1].astype(np.float64),
        dens_sin=dens_sin[:, :, t0:t1, l0:l1].astype(np.float32),
        dens_bin=dens_bin[:, :, t0:t1, l0:l1].astype(np.float32),
        stripped_sin=strip_sin.astype(np.float32),
        stripped_bin=strip_bin.astype(np.float32),
        grid_name=np.str_("BPASSv2.2.1-imf135_300 (HRD numbers)"),
        zsun_bpass=np.float64(_ZSUN_BPASS),
    )
    size_mb = out.stat().st_size / 1e6
    print(f"\nWrote {out}  ({size_mb:.1f} MB)  bake_version={BAKE_VERSION_HRD}")
    print(f"  [Fe/H] {feh[0]:.2f}..{feh[-1]:.2f} ({nZ}) x age {age_gyr[0]*1e3:.1f} Myr.."
          f"{age_gyr[-1]:.0f} Gyr ({nAge})")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--from-dir", type=Path, default=None,
                    help="re-bake from a dir of already-extracted hrs-*.dat (no network)")
    args = ap.parse_args()
    sys.exit(bake(args.from_dir))
