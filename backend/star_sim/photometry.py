"""Synthetic photometry + interstellar reddening for Axis A (the observer's view).

**A sibling to the §3 spine, not a provider and not a `StellarState`** — like
`spectra.py`/`lane_emden.py`/`bpass.py`. The intrinsic star (its surface F_λ, radius,
Teff) is unchanged; an *apparent* magnitude is a **view** of that state seen through a
telescope: dimmed by distance, reddened by dust, integrated through a filter. So
`/photometry` (like `/spectrum`) does **not** go through `PROVIDER`.

The pipeline, per band X:

    F_obs,λ = F_surf,λ · (R / d)² · 10^(−0.4 · A_λ)         (dilute + redden)
    <f_λ>   = ∫ F_obs,λ T_X(λ) w(λ) dλ / ∫ T_X(λ) w(λ) dλ   (band-average)
    m_X     = −2.5 log₁₀( <f_λ> / f_λ,ZP(X) )               (Vega magnitude)

where the weight `w(λ)` is **1 for an energy counter** (DetectorType 0, Bessell B/V)
and **λ for a photon counter** (DetectorType 1, Gaia BP), and `f_λ,ZP` is the band's
Vega zero-point flux (SVO tabulates it in Jy at the pivot wavelength). Extinction
`A_λ = A_V · A(λ)/A(V)` uses the Cardelli–Clayton–Mathis (1989) law parameterized by
R_V (default 3.1). The filter curves + zero-points + detector types are the committed
`data/filters.json` (`fetch_filters.py`).

**Absolute vs. apparent.** An *absolute* magnitude M_X is the mag at d = 10 pc with no
extinction (the star's intrinsic brightness); the *apparent* m_X adds the distance
modulus μ = 5 log₁₀(d/10 pc) and A_X. So the observational CMD plots (B−V)₀ vs M_V
(intrinsic) or reddened (B−V) vs m_V (as seen) — the observer's HR diagram, which
composes with the Axis-B isochrone into a real cluster colour–magnitude diagram.

**Scope (measured — Gate 0).** The main absorption cube is absolute physical surface
F_λ (the Sun integrates to ~98% of the Planck in-band σT⁴), so magnitudes anchor
correctly: the Sun lands at M_V ≈ 4.82 with the exact 10.00 distance modulus. The cube
covers only 3001–8999 Å, so the honest bands are B, V (flagship CMD) + BP (verification);
Gaia G/RP and 2MASS JHK fall off the red edge and are out of scope. The synthetic solar
B−V comes out ~0.04 blue of the observed 0.65 — a known B-band Vega-zero-point *convention*
offset (SVO Bessell.B 3908.5 Jy vs literature ~4000–4060), **common-mode** across the star,
its track, and the isochrone, so it cancels in their *relative* CMD placement (the star
still sits on the cluster locus, the turnoff still dates it).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np

# star_sim/data/filters.json — the committed filter asset (fetch_filters.py).
_DATA_DIR = Path(__file__).resolve().parent / "data"
FILTERS_JSON = Path(os.environ.get("STAR_SIM_FILTERS", _DATA_DIR / "filters.json"))

# Physical constants (cgs; wavelengths in Å).
_C_ANG_S = 2.99792458e18       # speed of light, Å/s
_RSUN_CM = 6.957e10            # solar radius, cm
_PC_CM = 3.0856775815e18       # parsec, cm
_JY_CGS = 1e-23                # 1 Jy = 1e-23 erg/s/cm²/Hz


class FiltersMissing(RuntimeError):
    """The committed filter asset is absent (should never happen in a real checkout).

    The API maps this to a 503 with an actionable hint, exactly like a missing baked
    grid — the app stays up; only /photometry is unavailable until it's restored.
    """


class _Filters:
    """Lazily-loaded filter set: per-band transmission + Vega zero-point + detector
    type, plus the ZP already converted to f_λ (erg/s/cm²/Å) via the pivot wavelength."""

    def __init__(self, path: Path):
        self.path = path
        data = json.loads(path.read_text(encoding="utf-8"))
        self.provenance = str(data.get("provenance", ""))
        self.bands: dict[str, dict] = {}
        for name, b in data["bands"].items():
            lam = np.asarray(b["lam_ang"], dtype=float)
            trans = np.asarray(b["trans"], dtype=float)
            pivot = float(b["pivot_ang"])
            # SVO tabulates the Vega zero-point as f_ν in Jy; convert to f_λ at the
            # band's pivot wavelength (defined so f_λ = f_ν·c/λ_p² for the band).
            zp_flam = float(b["zp_jy"]) * _JY_CGS * _C_ANG_S / pivot**2
            self.bands[name] = {
                "svo_id": b.get("svo_id", ""),
                "lam": lam,
                "trans": trans,
                "pivot": pivot,
                "zp_jy": float(b["zp_jy"]),
                "zp_flam": zp_flam,
                "detector_type": int(b["detector_type"]),  # 0 energy, 1 photon
            }


_CACHE: _Filters | None = None


def _load() -> _Filters:
    global _CACHE
    if _CACHE is None:
        if not FILTERS_JSON.is_file():
            raise FiltersMissing(
                f"Filter asset not found at {FILTERS_JSON}. It is committed to the "
                f"repo; regenerate with `python -m star_sim.fetch_filters`."
            )
        _CACHE = _Filters(FILTERS_JSON)
    return _CACHE


def band_names() -> list[str]:
    """The bands available for photometry (B, V, BP)."""
    return list(_load().bands.keys())


def ccm89(lam_ang: np.ndarray, rv: float = 3.1) -> np.ndarray:
    """Cardelli, Clayton & Mathis (1989) extinction law A(λ)/A(V), a closed-form curve
    parameterized by R_V. Covers optical/NIR (1.1 ≤ x ≤ 3.3 µm⁻¹) and near-UV
    (3.3 < x ≤ 8), which spans the 3001–8999 Å cube. λ in Å.

    Returns A(λ)/A(V) (so the extinction in mag is A_V · this); the observed extinction
    factor on the flux is 10^(−0.4 · A_V · A(λ)/A(V))."""
    lam = np.asarray(lam_ang, dtype=float)
    x = 1.0e4 / lam                       # inverse microns
    a = np.zeros_like(x)
    b = np.zeros_like(x)

    # Optical / NIR: 1.1 ≤ x ≤ 3.3 (CCM89 eq. 3a/3b, 7th-order polynomials in x−1.82).
    opt = (x >= 1.1) & (x <= 3.3)
    y = x[opt] - 1.82
    a[opt] = (1.0 + 0.17699 * y - 0.50447 * y**2 - 0.02427 * y**3 + 0.72085 * y**4
              + 0.01979 * y**5 - 0.77530 * y**6 + 0.32999 * y**7)
    b[opt] = (1.41338 * y + 2.28305 * y**2 + 1.07233 * y**3 - 5.38434 * y**4
              - 0.62251 * y**5 + 5.30260 * y**6 - 2.09002 * y**7)

    # Near-UV: 3.3 < x ≤ 8 (CCM89 eq. 4a/4b; F_a/F_b vanish below x = 5.9).
    uv = (x > 3.3) & (x <= 8.0)
    xu = x[uv]
    a[uv] = 1.752 - 0.316 * xu - 0.104 / ((xu - 4.67) ** 2 + 0.341)
    b[uv] = -3.090 + 1.825 * xu + 1.206 / ((xu - 4.62) ** 2 + 0.263)

    # Below 1.1 µm⁻¹ (λ > 9091 Å, off the cube) or above 8 the coefficients are left 0;
    # in practice every cube wavelength lands in the two covered branches above.
    return a + b / rv


def _band_mags(
    filt: dict,
    lam: np.ndarray,
    flux_obs: np.ndarray,
) -> np.ndarray:
    """Vega magnitudes for one band over a flux stack. `flux_obs` is the OBSERVED
    (diluted + reddened) F_λ, shape (N, nlam). Returns an (N,) array of magnitudes."""
    T = np.interp(lam, filt["lam"], filt["trans"], left=0.0, right=0.0)
    # Detector weighting: energy counter integrates T; photon counter integrates T·λ.
    w = T * lam if filt["detector_type"] == 1 else T
    den = np.trapezoid(w, lam)
    num = np.trapezoid(flux_obs * w[None, :], lam, axis=1)
    flam_mean = num / den
    return -2.5 * np.log10(flam_mean / filt["zp_flam"])


def band_mags_stack(
    lam: np.ndarray,
    flux_surface: np.ndarray,
    radius_rsun: np.ndarray,
    distance_pc: float,
    av: float = 0.0,
    rv: float = 3.1,
) -> dict[str, np.ndarray]:
    """The vectorized core: apparent Vega magnitudes in every band for a STACK of
    stars sharing one distance/extinction (A3 draws a whole track + isochrone this way,
    without N HTTP round-trips).

    Parameters
    ----------
    lam : (nlam,) wavelength grid / Å (the served spectrum's grid).
    flux_surface : (N, nlam) absolute surface F_λ per star (erg/s/cm²/Å).
    radius_rsun : (N,) stellar radius / R☉.
    distance_pc, av, rv : the observer's distance / pc, V-band extinction / mag, R_V.

    Returns {band: (N,) apparent magnitudes}. Set av=0 and distance_pc=10 for the
    intrinsic ABSOLUTE magnitudes.
    """
    lam = np.asarray(lam, dtype=float)
    flux_surface = np.atleast_2d(np.asarray(flux_surface, dtype=float))
    radius_rsun = np.atleast_1d(np.asarray(radius_rsun, dtype=float))

    # Geometric dilution (R/d)² and wavelength-dependent extinction (shared by all bands).
    d_cm = max(distance_pc, 1e-6) * _PC_CM
    dilute = (radius_rsun * _RSUN_CM / d_cm) ** 2          # (N,)
    ext = 10.0 ** (-0.4 * av * ccm89(lam, rv)) if av != 0.0 else np.ones_like(lam)
    flux_obs = flux_surface * dilute[:, None] * ext[None, :]  # (N, nlam)

    filts = _load().bands
    return {name: _band_mags(f, lam, flux_obs) for name, f in filts.items()}


def photometry_point(
    lam: np.ndarray,
    flux_surface: np.ndarray,
    radius_rsun: float,
    distance_pc: float = 10.0,
    av: float = 0.0,
    rv: float = 3.1,
) -> dict:
    """Photometry for a SINGLE star: both the intrinsic ABSOLUTE magnitudes/colour
    (M_X, at 10 pc, A=0) and the APPARENT ones as seen (m_X, at the given distance +
    extinction), plus the distance modulus and reddening E(B−V). The `/photometry`
    route's payload.

    Colours are formed from whichever of B/V are present (the flagship B−V); BP rides
    along as a verification magnitude.
    """
    lam = np.asarray(lam, dtype=float)
    flux1 = np.asarray(flux_surface, dtype=float)[None, :]
    r = np.asarray([radius_rsun], dtype=float)

    absolute = {k: float(v[0]) for k, v in
                band_mags_stack(lam, flux1, r, 10.0, av=0.0, rv=rv).items()}
    apparent = {k: float(v[0]) for k, v in
                band_mags_stack(lam, flux1, r, distance_pc, av=av, rv=rv).items()}

    mu = 5.0 * np.log10(max(distance_pc, 1e-6) / 10.0)
    out: dict = {
        "absolute_mag": absolute,      # M_X (intrinsic, 10 pc, no dust)
        "apparent_mag": apparent,      # m_X (this distance + extinction)
        "distance_pc": float(distance_pc),
        "distance_modulus": float(mu),
        "av": float(av),
        "rv": float(rv),
        "radius_rsun": float(radius_rsun),
        "bands": band_names(),
    }
    if "B" in absolute and "V" in absolute:
        out["bv0"] = absolute["B"] - absolute["V"]                 # intrinsic (B−V)₀
        out["bv_obs"] = apparent["B"] - apparent["V"]              # reddened, as seen
        out["ebv"] = out["bv_obs"] - out["bv0"]                    # E(B−V)
        out["mv_abs"] = absolute["V"]                              # the CMD ordinate
        out["mv_app"] = apparent["V"]
    return out
