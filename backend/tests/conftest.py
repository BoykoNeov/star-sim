"""Shared test fixtures / markers.

The default `PROVIDER` is now `MISTProvider`, which needs the MIST grids on disk
(fetched via `python -m star_sim.fetch_mist`, never committed — see spec §6).
A fresh checkout won't have them, so MIST-dependent tests must *skip*, not fail.
`requires_mist_data` is that guard; use it on any test that touches real grids
(directly, or through the API now that PROVIDER routes to MIST).
"""

from __future__ import annotations

import pytest

from star_sim.providers.mist import DATA_DIR, _find_eep_dir


def mist_data_available() -> bool:
    return _find_eep_dir(DATA_DIR) is not None


requires_mist_data = pytest.mark.skipif(
    not mist_data_available(),
    reason="MIST grids not fetched — run: python -m star_sim.fetch_mist",
)
