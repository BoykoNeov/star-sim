"""The interpolation structures: `_Grid` / `_Axis`, and the blending arithmetic.

One `_Grid` is every mass track at one ([Fe/H], v/vcrit); one `_Axis` is every
`_Grid` at one rotation rate. That nesting is the shape of §6's two-axis scheme —
mass and [Fe/H] *interpolate*, rotation *snaps* — and the free functions below are
the arithmetic that does it: bracket a value on an ascending grid, weight the mass
axis in log M, and blend two already-windowed track dicts.

This module reads parsed tracks (`.parsing`) and is read by the provider class; it
holds no physics of its own beyond the blend.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from ...provider import ProviderDataMissing
from .parsing import _Track, _load_all_tracks

# [Fe/H] exact-hit tolerance: grid values are tenths of a dex, so this only
# collapses a true grid point to a no-blend short-circuit (the Sun must hit the
# solar grid exactly, not blend across it).
_FEH_TOL = 1e-3

# v/vcrit bucket-match tolerance: MIST publishes only {0.0, 0.4}, far apart, so this
# only identifies which discrete rotation bucket a request snaps to (never a blend).
_VVCRIT_TOL = 0.05


@dataclass
class _Grid:
    """All mass tracks at one [Fe/H] — the unit the metallicity axis interpolates.

    `masses` is ascending and parallel to `tracks`; `zams_row` is shared by every
    track in the grid (the EEP-alignment invariant, asserted at load).
    """

    feh: float
    vvcrit: float
    masses: np.ndarray
    tracks: list[_Track]
    zams_row: int


@dataclass
class _Axis:
    """All [Fe/H] grids at one rotation rate — the unit the rotation axis snaps to.

    Rotation (`vvcrit`) is a *grid-selection* axis, not an interpolation axis: MIST
    publishes only {0.0, 0.4}, so the provider partitions its grids into one `_Axis`
    per rotation rate and **snaps** between them (no third grid to interpolate
    toward), while the [Fe/H] axis still interpolates *within* an axis exactly as
    before. Each axis carries its own bracketing state (the `fehs` array, the mass
    bounding box, the shared ZAMS row) so the feh helpers operate on whichever axis
    the request selected — and the default vvcrit=0.0 axis reproduces the
    pre-rotation behavior bit-for-bit.
    """

    vvcrit: float
    grids: list[_Grid]          # ascending by feh
    fehs: np.ndarray
    mass_min: float
    mass_max: float
    zams_row: int


def _load_grid(eep_dir: Path, want_masses: tuple[float, ...] | None) -> _Grid | None:
    """Load one metallicity directory into a `_Grid`, or None if it's unusable.

    Loads the full parsed grid (cached), then keeps either *all* masses
    (`want_masses is None`, the default) or the subset nearest each requested mass
    (opt-in, snap-to-grid). Either way it checks the EEP-alignment invariant (one
    shared ZAMS row) before handing the grid downstream.
    """
    all_tracks, feh, vvcrit = _load_all_tracks(eep_dir)
    if not all_tracks:
        return None

    if want_masses is None:
        tracks = list(all_tracks)            # already ascending by mass
    else:
        by_mass = {round(t.minit, 2): t for t in all_tracks}
        grid_masses = np.array(sorted(by_mass))
        chosen: dict[float, _Track] = {}
        for want in want_masses:
            nearest = float(grid_masses[int(np.argmin(np.abs(grid_masses - want)))])
            chosen[round(nearest, 2)] = by_mass[round(nearest, 2)]
        tracks = [chosen[m] for m in sorted(chosen)]

    if len(tracks) < 2:
        return None

    # Row-index alignment is the load-bearing assumption (§6): ZAMS must sit at
    # the same row for every mass, or cross-mass interpolation is garbage.
    zams_rows = {t.zams_row for t in tracks}
    if len(zams_rows) != 1:
        raise ProviderDataMissing(
            f"MIST tracks in {eep_dir} disagree on the ZAMS row ({sorted(zams_rows)}); "
            "EEP alignment is broken — refusing to interpolate across phases."
        )

    return _Grid(
        feh=float(feh),
        vvcrit=float(vvcrit),
        masses=np.array([t.minit for t in tracks]),
        tracks=tracks,
        zams_row=tracks[0].zams_row,
    )


def _build_axis(vvcrit: float, grids: list[_Grid]) -> _Axis:
    """Assemble one rotation bucket's [Fe/H] grids into an `_Axis`.

    Sorts by [Fe/H] and re-checks the EEP-alignment invariant *within the
    bucket* (row N is the same phase for every grid, or the [Fe/H] blend is
    garbage). The mass bounding box is the union across the bucket's grids; a
    specific [Fe/H] can be narrower — see `mass_range()`.
    """
    grids = sorted(grids, key=lambda g: g.feh)
    zams_rows = {g.zams_row for g in grids}
    if len(zams_rows) != 1:
        raise ProviderDataMissing(
            f"MIST metallicity grids (vvcrit={vvcrit}) disagree on the ZAMS row "
            f"({sorted(zams_rows)}); EEP alignment is broken — refusing to "
            "interpolate across [Fe/H]."
        )
    return _Axis(
        vvcrit=float(vvcrit),
        grids=grids,
        fehs=np.array([g.feh for g in grids]),
        mass_min=float(min(g.masses[0] for g in grids)),
        mass_max=float(max(g.masses[-1] for g in grids)),
        zams_row=grids[0].zams_row,
    )


def _bracket(values: np.ndarray, x: float) -> tuple[int, int, float]:
    """Indices of the two `values` entries bracketing `x`, and the blend weight.

    Exact grid hit -> (i, i, 0.0). Otherwise w in (0,1) is the linear position
    from the lower to the upper bracket. `values` must be ascending.
    """
    if x <= values[0]:
        return 0, 0, 0.0
    if x >= values[-1]:
        n = values.size - 1
        return n, n, 0.0
    i_hi = int(np.searchsorted(values, x, side="left"))
    if values[i_hi] == x:
        return i_hi, i_hi, 0.0
    i_lo = i_hi - 1
    w = (x - values[i_lo]) / (values[i_hi] - values[i_lo])
    return i_lo, i_hi, float(w)


def _log_mass_weight(m_lo: float, m_hi: float, m: float) -> float:
    """Blend weight of `m` between the bracketing masses, linear in log(mass).

    0 at `m_lo`, 1 at `m_hi`. Used by `_grid_window` (see its docstring for the
    measured payoff). The [Fe/H] axis needs no analogue — [Fe/H] is already a log.
    """
    return math.log(m / m_lo) / math.log(m_hi / m_lo)


def _blend_windows(a: dict, b: dict, w: float) -> dict:
    """Blend two metallicity windows at fixed row index (the §6 outer loop).

    Truncate to the shorter window so both endpoints stay on real, aligned rows
    (row i is the same EEP in both). Structure quantities blend linearly in the
    [Fe/H] weight; `age` blends in log space (like the mass axis); `phase` is
    discrete and taken from the nearer grid. Blending logL etc. linearly makes the
    result a convex combination of the two grids at every EEP — so it *provably*
    lies between them on the HR diagram (the §10 lies-between property).
    """
    n = min(a["age"].size, b["age"].size)
    out: dict = {
        "age": 10.0 ** ((1.0 - w) * np.log10(a["age"][:n]) + w * np.log10(b["age"][:n])),
        "phase": (a["phase"] if w < 0.5 else b["phase"])[:n],
    }
    for k in ("logL", "logT", "logR", "logg", "Vrot", "Mdot",
              "Xs", "Ys", "Xc", "Yc",
              "Lis", "Bes", "Cs", "Ns", "Os", "Fs", "Nes", "Nas", "Mgs", "Als", "Sis", "Ps", "Ss", "Cas", "Tis", "Fes",
              "Lic", "Bec", "Cc", "Nc", "Oc", "Fc", "Nec", "Nac", "Mgc", "Alc", "Sic", "Pc", "Sc", "Cac", "Tic", "Fec"):
        out[k] = (1.0 - w) * a[k][:n] + w * b[k][:n]
    return out
