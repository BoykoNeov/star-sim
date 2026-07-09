"""alpha.py — the α-enhanced (equivalent-Z) what-if overlay sibling.

Phase 3 of `docs/plans/tempered-lineage-inspiral.md`. [α/Fe] (O, Ne, Mg, Si, S,
Ca, Ti vs. the Fe-peak) is a star-formation-history clock: old, fast-formed
populations (halo, thick disk, globular clusters) lock in high [α/Fe] (~+0.4). O
and Mg dominate the metal *mass* budget, so at fixed [Fe/H] α-enhancement raises
the true total metallicity Z — raising envelope opacity and pushing the track
**cooler (redder), slightly fainter, and longer-lived** at fixed mass (the
**opposite sign** from the initial-He effect of Phase 2).

**The equivalent-Z decision (advisor-endorsed).** MESA ships only solar-scaled
opacity tables (Type-1 on the MS; Type-2 only blends in when H-poor), so a
"matching α-enhanced table" isn't in the box. Salaris, Chieffi & Straniero (1993)
showed an α-enhanced track is reproduced *to a few percent* by a **scaled-solar
track at the equivalent total metallicity**
`[M/H] = [Fe/H] + log10(0.638·10^[α/Fe] + 0.362)` — a residual below what this sim
resolves. So the "enhanced" member here is a scaled-solar MESA run at the equivalent
Z, and the honest framing (owned by the frontend caption) is: at fixed [Fe/H] the
**track** responds to α *only* through total Z; α's distinctive fingerprint is
**spectroscopic** (the already-shipped Coelho α-toggle), not evolutionary. The
equivalent-Z model is scaled-solar — Fe is NOT held at solar in its interior — so
this is a track-equivalence claim, never "the α-boosted mixture is modeled."

Like Phase 2's `helium.py`, this is a **what-if overlay sibling** — it bypasses
`PROVIDER` and is NEVER compared against the live MIST spine (a self-run-MESA vs.
MIST comparison would conflate the effect with the documented MESA-vs-MIST
systematic). The enhanced track is only ever drawn against its own MESA **baseline**
(identical inlist, the equivalent Z the sole difference).

Data: `data/mesa_alpha/{baseline,enhanced}/<M>Msun/history.data` — six self-run MESA
runs (3 masses × 2 compositions, solar [Fe/H], see `backend/docs/mesa_alpha_recipe.md`).
We **reuse `MESAProvider`'s history parser** (`_build_track` / `_state_from_track`),
exactly like `helium.py`. The pair members are keyed by their **ZAMS surface Z**
(`1 − Xs[0] − Ys[0]`, the initial metallicity before burning), not by directory name;
within a mass group the lower-Z member is the baseline, the higher-Z the enhanced.
"""

from __future__ import annotations

import glob
import math
import os
from dataclasses import asdict
from pathlib import Path

import numpy as np

from .providers.mesa import _MesaTrack, _build_track, _state_from_track

# data/mesa_alpha/ sits at the repo root: star_sim/alpha.py -> parents
#   [0]=star_sim [1]=backend [2]=repo root  (same anchor as helium.py/structure.py)
_REPO_ROOT = Path(__file__).resolve().parents[2]
ALPHA_DATA_DIR = Path(
    os.environ.get("STAR_SIM_ALPHA_DIR", _REPO_ROOT / "data" / "mesa_alpha")
)

# Project solar metallicity (Z_sun = 0.0152) — the [M/H] zero point, matching the
# rest of the sim (mesa_solar_recipe.md, MISTProvider). Only used for the label
# scalars ([M/H] = log10(Z/Z_sun)); the physics is entirely in the MESA runs.
_Z_SUN = 0.0152

# Salaris, Chieffi & Straniero (1993) equivalent-metallicity coefficients:
#   Z_alpha / Z_scaled-solar = 0.638·10^[α/Fe] + 0.362  (at fixed [Fe/H]).
# We invert this to *derive* the represented [α/Fe] from the measured baseline vs.
# enhanced Z ratio, so the label is data-derived, never hardcoded.
_SALARIS_A = 0.638
_SALARIS_B = 0.362


def _alpha_fe_from_z_ratio(z_enh: float, z_base: float) -> float:
    """The [α/Fe] the enhanced run represents, inverted from its Z ratio (Salaris 1993).

    `factor = Z_enh/Z_base = 0.638·10^[α/Fe] + 0.362`  =>
    `[α/Fe] = log10((factor − 0.362) / 0.638)`. For the shipped pair
    (0.0299/0.0152 ≈ 1.966) this returns ≈ +0.40 — the value the recipe targeted,
    recovered from the actual runs rather than asserted."""
    factor = z_enh / z_base
    inner = (factor - _SALARIS_B) / _SALARIS_A
    return float(math.log10(inner)) if inner > 0 else 0.0


class AlphaDataMissing(RuntimeError):
    """No α-enhanced MESA runs are present under `ALPHA_DATA_DIR`.

    The API maps this to a 503 with an actionable hint, exactly like the initial-He
    sibling — the app stays up; only `/alpha` is unavailable until the runs are
    generated (see `backend/docs/mesa_alpha_recipe.md`)."""


_MISSING_HINT = (
    "No α-enhanced MESA runs found under {data_dir}. Generate them once by running the "
    "baseline+enhanced (equivalent-Z) batch in Docker MESA (see "
    "backend/docs/mesa_alpha_recipe.md), then copy the history.data files into "
    "data/mesa_alpha/{{baseline,enhanced}}/<M>Msun/."
)


class _AlphaPair:
    """One mass's baseline+enhanced MESA track pair, ordered by ZAMS Z.

    `baseline`/`enhanced` are `_MesaTrack`s from the reused MESA parser; `mass` is
    their shared true initial mass. τ_MS is the windowed main-sequence lifetime
    (age of the last exposed row minus the ZAMS row — the run stops at central-H
    exhaustion, so the last row is TAMS)."""

    def __init__(self, mass: float, baseline: _MesaTrack, enhanced: _MesaTrack) -> None:
        self.mass = mass
        self.baseline = baseline
        self.enhanced = enhanced

    @staticmethod
    def _z_init(t: _MesaTrack) -> float:
        """ZAMS surface metallicity = 1 − X − Y at row 0 (the initial Z before burning)."""
        return float(1.0 - t.Xs[0] - t.Ys[0])

    @staticmethod
    def _tau_ms_gyr(t: _MesaTrack) -> float:
        return float(t.age[-1] - t.age[0]) / 1e9


# Lazily-built index: mass -> _AlphaPair, and the sorted mass grid for snapping.
_pairs_by_mass: dict[float, _AlphaPair] | None = None
_mass_grid: np.ndarray | None = None


def _find_history_files() -> list[str]:
    return sorted(
        glob.glob(str(ALPHA_DATA_DIR / "**" / "history.data"), recursive=True)
    )


def alpha_available() -> bool:
    """True if any α-enhanced MESA runs are on disk — the data-derived honesty gate.

    The frontend reads this (via `/alpha_status`) to decide whether to even SHOW the
    overlay toggle: MESA data is never committed/hosted, so a fresh public clone has
    none, and a control that can only ever 503 shouldn't appear (the project's "don't
    ship a control nobody can see work" rule, same stance as `/helium_status`)."""
    return len(_find_history_files()) > 0


def _ensure_loaded() -> None:
    """Parse every run once, group by initial mass, pair by ZAMS-Z ordering.

    Pairing is derived from the runs themselves, never from directory names: within
    each mass group the two members are sorted by ZAMS surface Z, lower = baseline,
    higher = enhanced. Exactly two members per mass is asserted so a missing or stray
    run fails loudly here rather than silently mispairing downstream."""
    global _pairs_by_mass, _mass_grid
    if _pairs_by_mass is not None:
        return

    files = _find_history_files()
    if not files:
        raise AlphaDataMissing(_MISSING_HINT.format(data_dir=ALPHA_DATA_DIR))

    tracks = [t for f in files if (t := _build_track(f)) is not None]
    if not tracks:
        raise AlphaDataMissing(_MISSING_HINT.format(data_dir=ALPHA_DATA_DIR))

    groups: dict[float, list[_MesaTrack]] = {}
    for t in tracks:
        groups.setdefault(round(t.minit, 3), []).append(t)

    pairs: dict[float, _AlphaPair] = {}
    for mass, members in groups.items():
        if len(members) != 2:
            raise AlphaDataMissing(
                f"{ALPHA_DATA_DIR}: expected exactly a baseline+enhanced pair at "
                f"{mass} M_sun, found {len(members)} run(s) — check the batch is complete."
            )
        members.sort(key=_AlphaPair._z_init)   # lower Z = baseline, higher = enhanced
        base, enh = members
        if not (_AlphaPair._z_init(enh) > _AlphaPair._z_init(base) * 1.05):
            raise AlphaDataMissing(
                f"{ALPHA_DATA_DIR}: the two {mass} M_sun runs have indistinguishable ZAMS "
                f"Z ({_AlphaPair._z_init(base):.4f}) — cannot tell baseline from enhanced."
            )
        pairs[mass] = _AlphaPair(mass, base, enh)

    _pairs_by_mass = pairs
    _mass_grid = np.array(sorted(pairs))


def _snap_mass(mass: float) -> float:
    """Nearest available grid mass (the grid is discrete — 1/2/6 M_sun, solar [Fe/H]).

    Snap-always (like `/helium` and `/structure`): out-of-grid requests snap to the
    nearest node and are flagged in-band by the route, never 422'd. The route's Query
    bound reserves 422 for structurally invalid mass <= 0."""
    assert _mass_grid is not None
    i = int(np.argmin(np.abs(_mass_grid - mass)))
    return float(_mass_grid[i])


def _track_block(t: _MesaTrack) -> dict:
    """Serialize one MESA track as {z_init, mh, tau_ms_gyr, zams:{teff,l}, states:[...]}.

    `states` are the exact §3 `StellarState` shape (via `_state_from_track` per row),
    so the HR overlay consumes them like any /track payload. The ZAMS scalars and τ_MS
    are surfaced explicitly because τ_MS — the *longer*-lifetime effect — has no axis on
    an HR diagram and would otherwise be invisible (see the frontend caption). `mh` is
    the equivalent [M/H] = log10(Z/Z_sun) — the axis the track actually sees."""
    states = [_state_from_track(t, float(i)) for i in range(t.age.size)]
    zams = states[0]
    z_init = _AlphaPair._z_init(t)
    return {
        "z_init": round(z_init, 5),
        "mh": round(math.log10(z_init / _Z_SUN), 4),
        "tau_ms_gyr": _AlphaPair._tau_ms_gyr(t),
        "zams": {"teff_k": zams.Teff_K, "l_lsun": zams.L_lsun},
        "states": [asdict(s) for s in states],
    }


def alpha_overlay(mass: float) -> dict:
    """(mass) -> the baseline vs. α-enhanced (equivalent-Z) MESA track pair.

    Snaps `mass` to the nearest grid mass and returns both self-run MESA tracks — same
    inlist, only the equivalent total Z differs — with each track's ZAMS Teff/L, its
    equivalent [M/H], and windowed τ_MS. `alpha_fe` is the represented [α/Fe], *derived*
    from the measured baseline/enhanced Z ratio via the inverted Salaris relation (not
    hardcoded). The frontend overlays the two on the HR diagram (MIST spine hidden) and
    pairs the caption with the spectrum-only Coelho α-toggle. This never touches
    `PROVIDER`."""
    _ensure_loaded()
    snapped = _snap_mass(mass)
    pair = _pairs_by_mass[snapped]   # type: ignore[index]
    base_block = _track_block(pair.baseline)
    enh_block = _track_block(pair.enhanced)
    return {
        "mass_requested": float(mass),
        "mass_snapped": snapped,
        "mass_snapped_far": abs(snapped - mass) > 0.25 * snapped,
        "alpha_fe": round(_alpha_fe_from_z_ratio(enh_block["z_init"], base_block["z_init"]), 3),
        "baseline": base_block,
        "enhanced": enh_block,
    }
