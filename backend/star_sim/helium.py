"""helium.py — the initial-helium (Y) what-if overlay sibling.

Phase 2 of `docs/plans/tempered-lineage-inspiral.md`. Globular-cluster CMDs
(omega Cen, NGC 2808) show a **He-enhanced second generation** (Y ~ 0.35-0.40 vs.
primordial ~0.25) at the *same* [Fe/H] as the first generation. At fixed
mass/[Fe/H], raising Y raises the mean molecular weight mu, so by homology the
star is **more luminous, hotter (bluer), and shorter-lived** (tau_MS = M/L falls)
— the horizontal-branch "second-parameter" effect.

This is a **what-if overlay sibling**, like Ap/Bp and gravity-darkening — it
bypasses `PROVIDER` entirely and is NEVER compared against the live MIST spine.
The whole honesty basis is "matched everything but Y": a He-enhanced MESA track is
only ever shown next to a MESA **baseline** track run with the identical inlist,
Y the sole difference. Comparing self-run MESA to MIST would conflate the He
effect with the already-documented MESA-vs-MIST systematic (`test_mesa_vs_mist.py`
exists precisely to keep those honest).

Data: `data/mesa_helium/{baseline,enhanced}/<M>Msun/history.data` — six self-run
MESA runs (3 masses x 2 compositions, solar Z=0.0152, see
`backend/docs/mesa_helium_recipe.md`). We **reuse `MESAProvider`'s history parser**
(`_build_track` / `_state_from_track`) rather than writing a third one — the plan
mandates it and the runs are byte-format-identical to the provider's grid. Only the
free parsing helpers are imported: this stays a clean §3 sibling that emits
`StellarState` directly and never routes through the provider.

The pair members are keyed by their **ZAMS surface helium** (`Ys[0]`, the initial Y
before burning), not by directory name — dir names are human clarity only. Within a
mass group the lower-Y member is the baseline, the higher-Y member the enhanced.
"""

from __future__ import annotations

import glob
import os
from dataclasses import asdict
from pathlib import Path

import numpy as np

from .providers.mesa import _MesaTrack, _build_track, _state_from_track

# data/mesa_helium/ sits at the repo root: star_sim/helium.py -> parents
#   [0]=star_sim [1]=backend [2]=repo root  (same anchor as structure.py/spectra.py)
_REPO_ROOT = Path(__file__).resolve().parents[2]
HELIUM_DATA_DIR = Path(
    os.environ.get("STAR_SIM_HELIUM_DIR", _REPO_ROOT / "data" / "mesa_helium")
)


class HeliumDataMissing(RuntimeError):
    """No He-enhanced MESA runs are present under `HELIUM_DATA_DIR`.

    The API maps this to a 503 with an actionable hint, exactly like a missing MESA
    profile grid — the app stays up; only `/helium` is unavailable until the runs are
    generated (see `backend/docs/mesa_helium_recipe.md`)."""


_MISSING_HINT = (
    "No initial-helium MESA runs found under {data_dir}. Generate them once by running "
    "the baseline+enhanced batch in Docker MESA (see backend/docs/mesa_helium_recipe.md), "
    "then copy the history.data files into data/mesa_helium/{{baseline,enhanced}}/<M>Msun/."
)


class _HeliumPair:
    """One mass's baseline+enhanced MESA track pair, ordered by ZAMS Y.

    `baseline`/`enhanced` are `_MesaTrack`s from the reused MESA parser; `mass` is
    their shared true initial mass. τ_MS is the windowed main-sequence lifetime
    (age of the last exposed row minus the ZAMS row — the run stops at central-H
    exhaustion, so the last row is TAMS; subtracting the ZAMS age removes the pre-MS
    contribution the window still carries in row 0)."""

    def __init__(self, mass: float, baseline: _MesaTrack, enhanced: _MesaTrack) -> None:
        self.mass = mass
        self.baseline = baseline
        self.enhanced = enhanced

    @staticmethod
    def _y_init(t: _MesaTrack) -> float:
        return float(t.Ys[0])

    @staticmethod
    def _tau_ms_gyr(t: _MesaTrack) -> float:
        return float(t.age[-1] - t.age[0]) / 1e9


# Lazily-built index: mass -> _HeliumPair, and the sorted mass grid for snapping.
_pairs_by_mass: dict[float, _HeliumPair] | None = None
_mass_grid: np.ndarray | None = None


def _find_history_files() -> list[str]:
    return sorted(
        glob.glob(str(HELIUM_DATA_DIR / "**" / "history.data"), recursive=True)
    )


def helium_available() -> bool:
    """True if any He-enhanced MESA runs are on disk — the data-derived honesty gate.

    The frontend reads this (via `/helium_status`) to decide whether to even SHOW the
    overlay toggle: MESA data is never committed/hosted (unlike MIST), so a fresh public
    clone has none, and a control that can only ever 503 shouldn't appear (the project's
    "don't ship a control nobody can see work" rule, same stance as `/rotation_status`).
    A cheap glob, never parses — safe to call on every gate re-evaluation."""
    return len(_find_history_files()) > 0


def _ensure_loaded() -> None:
    """Parse every run once, group by initial mass, pair by ZAMS-Y ordering.

    Pairing is derived from the runs themselves, never from directory names: within
    each mass group the two members are sorted by ZAMS surface He, lower = baseline,
    higher = enhanced. Exactly two members per mass is asserted so a missing or stray
    run fails loudly here rather than silently mispairing downstream."""
    global _pairs_by_mass, _mass_grid
    if _pairs_by_mass is not None:
        return

    files = _find_history_files()
    if not files:
        raise HeliumDataMissing(_MISSING_HINT.format(data_dir=HELIUM_DATA_DIR))

    tracks = [t for f in files if (t := _build_track(f)) is not None]
    if not tracks:
        raise HeliumDataMissing(_MISSING_HINT.format(data_dir=HELIUM_DATA_DIR))

    groups: dict[float, list[_MesaTrack]] = {}
    for t in tracks:
        groups.setdefault(round(t.minit, 3), []).append(t)

    pairs: dict[float, _HeliumPair] = {}
    for mass, members in groups.items():
        if len(members) != 2:
            raise HeliumDataMissing(
                f"{HELIUM_DATA_DIR}: expected exactly a baseline+enhanced pair at "
                f"{mass} M_sun, found {len(members)} run(s) — check the batch is complete."
            )
        members.sort(key=_HeliumPair._y_init)   # lower Y = baseline, higher = enhanced
        base, enh = members
        if not (_HeliumPair._y_init(enh) > _HeliumPair._y_init(base)):
            raise HeliumDataMissing(
                f"{HELIUM_DATA_DIR}: the two {mass} M_sun runs have indistinguishable ZAMS "
                f"Y ({_HeliumPair._y_init(base):.4f}) — cannot tell baseline from enhanced."
            )
        pairs[mass] = _HeliumPair(mass, base, enh)

    _pairs_by_mass = pairs
    _mass_grid = np.array(sorted(pairs))


def _snap_mass(mass: float) -> float:
    """Nearest available grid mass (the grid is discrete — 1/2/6 M_sun, solar Z).

    Snap-always (like `/structure` and `/binary`): out-of-grid requests snap to the
    nearest node and are flagged in-band by the route, never 422'd. The route's Query
    bound reserves 422 for structurally invalid mass <= 0."""
    assert _mass_grid is not None
    i = int(np.argmin(np.abs(_mass_grid - mass)))
    return float(_mass_grid[i])


def _track_block(t: _MesaTrack) -> dict:
    """Serialize one MESA track as {y_init, tau_ms_gyr, zams:{teff,l}, states:[...]}.

    `states` are the exact §3 `StellarState` shape (via `_state_from_track` per row),
    so the HR overlay consumes them like any /track payload. The ZAMS scalars and
    τ_MS are surfaced explicitly because τ_MS — the shorter-lifetime effect — has no
    axis on an HR diagram and would otherwise be invisible (see the frontend caption)."""
    states = [_state_from_track(t, float(i)) for i in range(t.age.size)]
    zams = states[0]
    return {
        "y_init": round(_HeliumPair._y_init(t), 4),
        "tau_ms_gyr": _HeliumPair._tau_ms_gyr(t),
        "zams": {"teff_k": zams.Teff_K, "l_lsun": zams.L_lsun},
        "states": [asdict(s) for s in states],
    }


def helium_overlay(mass: float) -> dict:
    """(mass) -> the baseline+enhanced MESA track pair for the He-enhanced what-if.

    Snaps `mass` to the nearest grid mass and returns both self-run MESA tracks —
    same inlist, only initial Y differs — with each track's ZAMS Teff/L and windowed
    τ_MS. The frontend overlays the two on the HR diagram (MIST spine hidden) and
    reads the τ_MS pair into the caption. This never touches `PROVIDER`."""
    _ensure_loaded()
    snapped = _snap_mass(mass)
    pair = _pairs_by_mass[snapped]   # type: ignore[index]
    return {
        "mass_requested": float(mass),
        "mass_snapped": snapped,
        "mass_snapped_far": abs(snapped - mass) > 0.25 * snapped,
        "baseline": _track_block(pair.baseline),
        "enhanced": _track_block(pair.enhanced),
    }
