"""Fetch filter transmission curves + Vega zero-points for Axis A (the observer's
view: distance + extinction + observational CMD).

Axis A turns the *intrinsic* star (logTeff, logL, surface F_λ) into what a telescope
records — an **apparent** magnitude, reddened by dust and dimmed by distance. The
payoff is the observational **colour–magnitude diagram** (B−V, M_V), the observer's
HR diagram, which composes with the Axis-B isochrone into a real cluster CMD.

Synthetic photometry needs, per band: the transmission curve T(λ), the Vega
zero-point flux (so a Vega-relative magnitude is defined), and the **detector type**
(energy counter vs photon counter — they weight the band integral differently). All
three come from the **SVO Filter Profile Service** (the same source the spectra panel
already uses for Coelho/TMAP/Koester), a plain HTTP fetch — no Docker/pymsg.

Unlike the big spectrum grids, the filter data is *tiny* (a few hundred points per
band), so — like `star_sim/data/gotberg_z014.csv` — the baked result is **committed**
to the repo as `star_sim/data/filters.json`; `photometry.py` reads it directly and
`/photometry` works on a fresh clone (gated only on the spectrum cube it convolves).

**Band scope (measured — see the Axis-A plan / advisor Gate 0):** the main absorption
cube covers **3001–8999 Å (optical only)**, so the clean, fully-in-cube bands are
**Johnson–Cousins (Bessell) B and V** — the flagship (B−V, M_V) CMD — plus **Gaia BP**
as a verification band. Gaia G is truncated (red tail past 8999 Å → ~0.05–0.13 mag
error), Gaia RP and 2MASS JHK fall entirely off the red edge, so they are deliberately
excluded (blackbody-filling them would be the invisible-Na trap). A true Gaia CMD would
need a wider cube re-bake — a future extension, out of scope here.

Run once (idempotent; the result is committed, so this only re-runs on a band change):

    python -m star_sim.fetch_filters

Cite: Rodrigo, Solano & Bayo (2012) / Rodrigo & Solano (2020), the SVO Filter Profile
Service; the Bessell (1990) UBVRI system; Gaia DR3 (Riello et al. 2021) passbands.
"""

from __future__ import annotations

import json
import re
import sys
import urllib.request
from pathlib import Path

# star_sim/data/ sits beside this module (the committed-asset home, like gotberg).
_DATA_DIR = Path(__file__).resolve().parent / "data"
FILTERS_JSON = _DATA_DIR / "filters.json"

_FPS_BASE = "http://svo2.cab.inta-csic.es/theory/fps"
_USER_AGENT = "star-sim/0.1 (+local teaching tool; Axis A photometry, SVO FPS)"

# The bands we bake: (short name, SVO id, role). B/V are the flagship (B−V, M_V) CMD;
# BP is a photon-counting verification band (a different detector-type code path).
_BANDS: list[tuple[str, str, str]] = [
    ("B", "Generic/Bessell.B", "Johnson-Cousins B (Bessell 1990), energy counter"),
    ("V", "Generic/Bessell.V", "Johnson-Cousins V (Bessell 1990), energy counter"),
    ("BP", "GAIA/GAIA3.Gbp", "Gaia DR3 BP, photon counter (verification band)"),
]

# The FPS scalar PARAMs we keep, with the type to cast them to.
_META_KEYS = {
    "ZeroPoint": float,          # Vega zero-point flux, in ZeroPointUnit (Jy)
    "ZeroPointUnit": str,
    "DetectorType": int,         # 0 = energy counter, 1 = photon counter
    "WavelengthPivot": float,    # pivot wavelength / Å (f_ν <-> f_λ reference)
    "WavelengthUnit": str,
    "MagSys": str,               # Vega / AB / ST
}


def _http_get(url: str, timeout: int = 60) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _fetch_transmission(svo_id: str) -> tuple[list[float], list[float]]:
    """The ASCII transmission curve: two columns, λ/Å and dimensionless T(λ)."""
    txt = _http_get(f"{_FPS_BASE}/getdata.php?format=ascii&id={svo_id}").decode(
        "utf-8", "replace"
    )
    lam, trans = [], []
    for line in txt.strip().splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        lam.append(float(parts[0]))
        trans.append(float(parts[1]))
    if len(lam) < 3:
        raise RuntimeError(f"transmission for {svo_id} too short ({len(lam)} pts)")
    return lam, trans


def _fetch_meta(svo_id: str) -> dict:
    """The scalar band metadata (ZeroPoint, DetectorType, pivot, …) from the FPS XML."""
    xml = _http_get(f"{_FPS_BASE}/fps.php?ID={svo_id}").decode("utf-8", "replace")
    meta: dict = {}
    for key, cast in _META_KEYS.items():
        m = re.search(rf'name="{key}"[^>]*value="([^"]*)"', xml)
        if m is None:
            raise RuntimeError(f"FPS XML for {svo_id} missing PARAM {key!r}")
        meta[key] = cast(m.group(1))
    return meta


def build() -> dict:
    """Fetch every band and assemble the committed JSON payload."""
    bands: dict[str, dict] = {}
    for name, svo_id, role in _BANDS:
        print(f"  {name:3s} {svo_id} …", flush=True)
        lam, trans = _fetch_transmission(svo_id)
        meta = _fetch_meta(svo_id)
        if meta["WavelengthUnit"] != "Angstrom":
            raise RuntimeError(
                f"{svo_id} transmission is in {meta['WavelengthUnit']}, expected Angstrom"
            )
        if meta["ZeroPointUnit"] != "Jy":
            raise RuntimeError(
                f"{svo_id} zero-point is in {meta['ZeroPointUnit']}, expected Jy"
            )
        bands[name] = {
            "svo_id": svo_id,
            "role": role,
            "zp_jy": meta["ZeroPoint"],
            "detector_type": meta["DetectorType"],  # 0 energy, 1 photon
            "pivot_ang": meta["WavelengthPivot"],
            "mag_sys": meta["MagSys"],
            "lam_ang": lam,
            "trans": trans,
        }
    return {
        "provenance": (
            "SVO Filter Profile Service (Rodrigo & Solano 2020); Bessell (1990) "
            "UBVRI; Gaia DR3 (Riello et al. 2021). Vega magnitude system; "
            "zero-points in Jy, detector_type 0=energy 1=photon."
        ),
        "wavelength_unit": "Angstrom",
        "zeropoint_unit": "Jy",
        "bands": bands,
    }


def main(argv: list[str] | None = None) -> int:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Fetching {len(_BANDS)} filter curves from the SVO FPS …")
    payload = build()
    FILTERS_JSON.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    kb = FILTERS_JSON.stat().st_size / 1024
    print(f"Wrote {FILTERS_JSON} ({kb:.1f} kB, {len(payload['bands'])} bands).")
    print("This asset is COMMITTED — re-run only to add/change a band, then commit it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
