"""Build-time bake of the BPASS coeval-population SSP-spectrum cube — Chunk 1 of the
coeval-ensemble overlay (docs/plans/coeval-ensemble-overlay.md).

The population overlay (`bpass.py`, `/population`, the SED-panel overlay) shows a whole
*coeval stellar population* — a million stars born together at the marker's metallicity,
seen at the marker's age — beside the one star the user picked, split **single-star vs
binary**. The headline (Gate 0, measured off these files 2026-07-10): binaries keep the
population UV/ionizing-bright far longer than single-star evolution can (stripped hot stars,
blue stragglers, hot subdwarfs) — up to ~256× more ionizing (<912 A) flux at 10–300 Myr,
~26× more FUV (1500 A) at ~1 Gyr, while the optical bulk is unchanged.

INPUT (the landed BPASS v2.3 SSP-spectra pair, Zenodo 10.5281/zenodo.6383329, CC-BY 4.0 —
see fetch_bpass.py; this is the Benson/Galacticus repackaging, ONE clean cube per file):
    data/bpass/SSP_Spectra_BPASSv2.3_sin-imf135_300-alpha+00.hdf5   (single-star)
    data/bpass/SSP_Spectra_BPASSv2.3_bin-imf135_300-alpha+00.hdf5   (includes binaries)
Each holds four datasets (MEASURED, not recalled):
    spectra        (13 Z, 51 age, 100000 lambda) float64, units L_sun/Hz (f_nu) per 1e6 Msun
    metallicities  (13,)  ALREADY [Fe/H]=log10(Z/0.020) (Zsun=0.020), -3.30103..+0.30103
    ages           (51,)  LINEAR age in Gyr, log-spaced 0.001..100.0 (= 1 Myr..100 Gyr)
    wavelengths    (100000,) 1..100000 Angstrom, 1 Angstrom step

OUTPUT: a compact `data/bpass/bpass_ssp.npz` (~6 MB, gitignored like every other grid):
    bake_version   int
    feh            (13,)  the [Fe/H] axis, copied verbatim (already [Fe/H])
    age_gyr        (51,)  the age axis, verbatim
    lam_ang        (Nlam,) log-rebinned wavelength BIN CENTRES (Angstrom)
    spectra_sin    (13, 51, Nlam) float32  f_nu [Lsun/Hz per 1e6 Msun], log-rebinned
    spectra_bin    (13, 51, Nlam) float32  same, from the binary file
    flux_unit, grid_name, zsun_bpass  provenance

DECIMATION: the SED panel is a log-lambda axis over ~5 decades (1..1e5 A); the native
100000-point 1-A grid is overkill. We rebin to ~1200 LOG-spaced bins by AVERAGING f_nu
within each bin (NOT nearest-sample) so the Lyman (912 A) / Balmer (3646 A) continuum
breaks stay faithful — the advisor's flag. f_nu (the native quantity) is what we average;
bpass.py converts the rebinned f_nu to f_lambda (x c/lambda^2) at serve time.

Run on the host after the pair is landed (see fetch_bpass.py):
    python -m star_sim.fetch_bpass --download   # or fetch by hand into data/bpass/
    python scripts/bake_bpass_spectra.py        # -> data/bpass/bpass_ssp.npz

Cite Eldridge et al. 2017 (PASA 34, e058); Stanway & Eldridge 2018 (MNRAS 479, 75);
BPASS v2.3 (Byrne et al. 2022 / the v2.3 release paper) on use.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

# Must match bpass.py's BAKE_VERSION_BPASS; a stale cube is rejected at load.
BAKE_VERSION = 1

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DATA_DIR = _REPO_ROOT / "data" / "bpass"
_SIN = "SSP_Spectra_BPASSv2.3_sin-imf135_300-alpha+00.hdf5"
_BIN = "SSP_Spectra_BPASSv2.3_bin-imf135_300-alpha+00.hdf5"
_OUT = "bpass_ssp.npz"

_ZSUN_BPASS = 0.020   # BPASS metallicity convention: [Fe/H] = log10(Z/0.020)


def _log_rebin_average(lam: np.ndarray, cube: np.ndarray, n_bins: int) -> tuple[np.ndarray, np.ndarray]:
    """Rebin a (Z, age, lambda) f_nu cube onto n_bins LOG-spaced wavelength bins by
    AVERAGING within each bin (faithful continuum breaks — not nearest-sample).

    Returns (bin_centres_ang, rebinned_cube). Empty bins (none at this resolution over a
    contiguous 1-A grid) would fall back to the nearest sample, but the ~83-A-per-bin
    coarsest bin still contains ~83 native points, so every bin is populated."""
    log_edges = np.linspace(np.log10(lam[0]), np.log10(lam[-1]), n_bins + 1)
    edges = 10.0 ** log_edges
    centres = 10.0 ** (0.5 * (log_edges[:-1] + log_edges[1:]))
    # Which bin each native lambda falls into (0..n_bins-1).
    idx = np.clip(np.digitize(lam, edges) - 1, 0, n_bins - 1)
    counts = np.bincount(idx, minlength=n_bins).astype(float)
    counts[counts == 0] = 1.0  # guard (no empty bins in practice)
    nZ, nAge, _ = cube.shape
    out = np.empty((nZ, nAge, n_bins), dtype=np.float64)
    for zi in range(nZ):
        for ai in range(nAge):
            # sum f_nu into bins, then divide by the native-point count -> mean f_nu per bin
            out[zi, ai] = np.bincount(idx, weights=cube[zi, ai], minlength=n_bins) / counts
    return centres, out


def bake(n_bins: int = 1200) -> int:
    try:
        import h5py
    except ImportError:
        print("h5py is required for the bake:  pip install h5py")
        return 1

    sin_p, bin_p = _DATA_DIR / _SIN, _DATA_DIR / _BIN
    for p in (sin_p, bin_p):
        if not p.is_file():
            print(f"Missing {p} -- run  python -m star_sim.fetch_bpass --download  first.")
            return 1

    def load(p):
        with h5py.File(p, "r") as h:
            return (np.asarray(h["spectra"], dtype=np.float64),
                    np.asarray(h["ages"], dtype=np.float64),
                    np.asarray(h["metallicities"], dtype=np.float64),
                    np.asarray(h["wavelengths"], dtype=np.float64))

    print(f"Reading {_SIN} ...")
    sp_sin, ages, fehs, lam = load(sin_p)
    print(f"Reading {_BIN} ...")
    sp_bin, ages2, fehs2, lam2 = load(bin_p)

    # The two files MUST share axes (same repackaging) — assert so a mismatched pair fails
    # loudly here, not as a silent misalignment downstream.
    if not (np.allclose(ages, ages2) and np.allclose(fehs, fehs2) and np.allclose(lam, lam2)):
        print("ERROR: sin/bin axes differ -- not a matched pair.")
        return 1

    print(f"  axes: {fehs.size} [Fe/H] x {ages.size} age x {lam.size} lambda")
    print(f"  rebinning lambda {lam[0]:.0f}..{lam[-1]:.0f} A -> {n_bins} log bins (averaging f_nu)")
    centres, reb_sin = _log_rebin_average(lam, sp_sin, n_bins)
    _, reb_bin = _log_rebin_average(lam, sp_bin, n_bins)

    out = _DATA_DIR / _OUT
    np.savez_compressed(
        out,
        bake_version=np.int64(BAKE_VERSION),
        feh=fehs.astype(np.float64),
        age_gyr=ages.astype(np.float64),
        lam_ang=centres.astype(np.float64),
        spectra_sin=reb_sin.astype(np.float32),
        spectra_bin=reb_bin.astype(np.float32),
        flux_unit=np.str_("Lsun/Hz per 1e6 Msun (f_nu)"),
        grid_name=np.str_("BPASSv2.3-imf135_300-alpha+00"),
        zsun_bpass=np.float64(_ZSUN_BPASS),
    )
    size_mb = out.stat().st_size / 1e6
    print(f"\nWrote {out}  ({size_mb:.1f} MB)  bake_version={BAKE_VERSION}")
    print("Design bpass.py / the /population route against THIS .npz.")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--bins", type=int, default=1200, help="log-spaced wavelength bins (default 1200)")
    args = ap.parse_args()
    sys.exit(bake(args.bins))
