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

**Band scope.** Which bands are *usable* is not decided here — it is decided by the
spectrum cube that is actually loaded. `photometry.py` keeps only the bands whose
transmission lies inside the served λ range and reports the rest as unavailable, so
this table can list a band before the data that supports it exists.

The v1 cube covered **3001–8999 Å (optical only)**: B and V (the flagship (B−V, M_V)
CMD) plus Gaia BP as a verification band, with Gaia G truncated and Gaia RP + 2MASS
JHK entirely off the red edge — excluded, because blackbody-filling them would be the
invisible-Na trap. The **v2 near-IR cube reaches 2.5 µm** (Göttingen MedRes-R on the
cool end, CAP18/OSTAR already there), which is what makes **Gaia G/RP** and **2MASS
J/H/Ks** real rather than extrapolated. They are listed below for that cube; on an
older cube they simply do not appear in the payload.

Run once (idempotent; the result is committed, so this only re-runs on a band change):

    python -m star_sim.fetch_filters

Cite: Rodrigo, Solano & Bayo (2012) / Rodrigo & Solano (2020), the SVO Filter Profile
Service; the Bessell (1990) UBVRI system; Gaia DR3 (Riello et al. 2021) passbands;
2MASS (Cohen, Wheaton & Megeath 2003).
"""

from __future__ import annotations

import json
import re
import sys
import urllib.request
from pathlib import Path

from ._fetch import user_agent

# star_sim/data/ sits beside this module (the committed-asset home, like gotberg).
_DATA_DIR = Path(__file__).resolve().parent / "data"
FILTERS_JSON = _DATA_DIR / "filters.json"

_FPS_BASE = "http://svo2.cab.inta-csic.es/theory/fps"
_USER_AGENT = user_agent("Axis A photometry, SVO FPS")

# The bands we bake: (short name, SVO id, role). B/V are the flagship (B−V, M_V) CMD;
# BP/G/RP are Gaia DR3 (photon counters — a different detector-type code path), and
# J/H/Ks are 2MASS. The last five need a cube that reaches past 1 µm; on a narrower
# cube `photometry.py` drops them rather than integrating over a missing red tail.
_BANDS: list[tuple[str, str, str]] = [
    ("B", "Generic/Bessell.B", "Johnson-Cousins B (Bessell 1990), energy counter"),
    ("V", "Generic/Bessell.V", "Johnson-Cousins V (Bessell 1990), energy counter"),
    ("BP", "GAIA/GAIA3.Gbp", "Gaia DR3 BP, photon counter (verification band)"),
    ("G", "GAIA/GAIA3.G", "Gaia DR3 G, photon counter (needs λ to ~1.05 µm)"),
    ("RP", "GAIA/GAIA3.Grp", "Gaia DR3 RP, photon counter (needs λ to ~1.05 µm)"),
    ("J", "2MASS/2MASS.J", "2MASS J (Cohen 2003), 1.24 µm"),
    ("H", "2MASS/2MASS.H", "2MASS H (Cohen 2003), 1.66 µm"),
    ("Ks", "2MASS/2MASS.Ks", "2MASS Ks (Cohen 2003), 2.16 µm"),
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
            "UBVRI; Gaia DR3 (Riello et al. 2021); 2MASS (Cohen et al. 2003). Vega "
            "magnitude system; zero-points in Jy, detector_type 0=energy 1=photon."
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
