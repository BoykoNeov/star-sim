"""Shared test fixtures / markers.

The default `PROVIDER` is now `MISTProvider`, which needs the MIST grids on disk
(fetched via `python -m star_sim.fetch_mist`, never committed — see spec §6).
A fresh checkout won't have them, so MIST-dependent tests must *skip*, not fail.
`requires_mist_data` is that guard; use it on any test that touches real grids
(directly, or through the API now that PROVIDER routes to MIST).
"""

from __future__ import annotations

import pytest

from star_sim.providers.mist import DATA_DIR, _feh_from_path, _find_eep_dir, _find_eep_dirs


def mist_data_available() -> bool:
    return _find_eep_dir(DATA_DIR) is not None


def mist_fehs_available() -> set[float]:
    """[Fe/H] values whose grids are present on disk (from the dir names)."""
    return {
        fh for d in _find_eep_dirs(DATA_DIR)
        if (fh := _feh_from_path(d)) is not None
    }


requires_mist_data = pytest.mark.skipif(
    not mist_data_available(),
    reason="MIST grids not fetched — run: python -m star_sim.fetch_mist",
)

# The metallicity-axis tests need >=2 grids; the held-out / dead-corner tests need
# the specific m050/p000/p050 trio (p000 is the ground truth the others bracket).
requires_mist_multifeh = pytest.mark.skipif(
    len(mist_fehs_available()) < 2,
    reason="needs >=2 MIST metallicity grids — e.g. `python -m star_sim.fetch_mist --feh m050`",
)

_HELDOUT_FEHS = {-0.5, 0.0, 0.5}
requires_mist_heldout_feh = pytest.mark.skipif(
    not _HELDOUT_FEHS.issubset(mist_fehs_available()),
    reason="needs the m050/p000/p050 grids — fetch with `--feh m050` and `--feh p050`",
)
