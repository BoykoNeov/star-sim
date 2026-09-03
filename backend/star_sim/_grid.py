"""Shared grid arithmetic for the siblings that read a discrete (non-EEP) grid.

Every off-spine grid in this project **snaps to the nearest node** instead of
interpolating (CLAUDE.md, spec §6): MESA history runs, POSYDON baked grids, the
spectral cubes and the MESA profile index have no EEP-aligned axes, so blending
two of their nodes would mix evolutionary phases. This module holds the two
pieces of that discipline every one of them had hand-rolled:

- `snap_index` / `snap_value` — the nearest-node lookup, one implementation
  instead of the thirteen copies of `int(np.argmin(np.abs(grid - x)))`.
- `load_npz` / `require_bake_version` — the "this `.npz` was written by an older
  bake, refuse it rather than read fields that have since moved" gate.

Two things were measured and deliberately left OUT (see
`docs/plans/structure-refactor.md` §1.2 for the numbers):

- the `*_snapped_far` predicates — three incompatible meanings across the
  siblings (absolute, relative-to-the-node, and log-dex), so one `tol` argument
  would silently change one of them;
- the `_MISSING_HINT` templates — eight hand-written recipes with different
  fetch paths; a builder could only flatten them.

stdlib + numpy only, and it must stay that way: every sibling imports this, so
anything reached from here is reachable from a sibling (spec §3). The
architecture table pins it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

__all__ = ["snap_index", "snap_value", "load_npz", "require_bake_version"]


def snap_index(values: Any, x: float) -> int:
    """Index of the node in `values` nearest `x`; ties go to the lower index.

    `values` need not be sorted. The axis's *units* are the caller's business:
    when a grid is naturally logarithmic (ages, periods, initial masses) pass
    both sides already transformed — `snap_index(np.log10(ages), log_age)` —
    rather than expecting this to guess.
    """
    v = np.asarray(values, dtype=float)
    return int(np.argmin(np.abs(v - float(x))))


def snap_value(values: Any, x: float) -> float:
    """The node *value* nearest `x` — `snap_index`'s companion for the call sites
    that report the true grid value back to the user instead of indexing with it."""
    v = np.asarray(values, dtype=float)
    return float(v[snap_index(v, x)])


def require_bake_version(
    npz: Any,
    path: Path | str,
    *,
    expected: int,
    exc: type[Exception],
    rebake_cmd: str,
    key: str = "bake_version",
    what: str = "grid",
) -> int:
    """Raise `exc` unless the baked file's own version stamp equals `expected`.

    Every baked `.npz` carries the BAKE_VERSION of the script that wrote it. A
    mismatch is a data problem, not a bug, so the siblings raise their own
    `*DataMissing` (→ 503 with an actionable hint) rather than reading a field
    that has since changed shape. `exc` is that class; `rebake_cmd` is the one
    command that fixes it. Returns the version so a caller can report it.
    """
    ver = int(npz[key])
    if ver != expected:
        raise exc(
            f"baked {what} {path} is {key} {ver}, runtime wants {expected}; "
            f"re-bake with {rebake_cmd}"
        )
    return ver


def load_npz(
    path: Path | str,
    *,
    expected: int,
    exc: type[Exception],
    rebake_cmd: str,
    key: str = "bake_version",
    what: str = "grid",
) -> Any:
    """`np.load` + `require_bake_version`, for loaders that keep the handle open.

    (`allow_pickle=False` is numpy's own default; passed explicitly here so the
    one place that opens a baked cube says out loud that these files are arrays,
    never pickles.) Loaders that read inside a `with` block call
    `require_bake_version` directly instead.
    """
    npz = np.load(path, allow_pickle=False)
    require_bake_version(
        npz, path, expected=expected, exc=exc, rebake_cmd=rebake_cmd, key=key, what=what
    )
    return npz
