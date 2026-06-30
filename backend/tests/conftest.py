"""Shared test fixtures / markers.

The default `PROVIDER` is now `MISTProvider`, which needs the MIST grids on disk
(fetched via `python -m star_sim.fetch_mist`, never committed — see spec §6).
A fresh checkout won't have them, so MIST-dependent tests must *skip*, not fail.
`requires_mist_data` is that guard; use it on any test that touches real grids
(directly, or through the API now that PROVIDER routes to MIST).
"""

from __future__ import annotations

import pytest

from star_sim.providers.mesa import MESA_DATA_DIR, MESAProvider, _find_history_files
from star_sim.providers.mist import (
    DATA_DIR,
    _feh_from_path,
    _find_eep_dir,
    _find_eep_dirs,
    _vvcrit_from_path,
)
from star_sim.spectra import (
    GRID_FILENAME,
    SPECTRA_DATA_DIR,
    WD_GRID_FILENAME,
    WR_GRID_FILENAME,
)


def mist_data_available() -> bool:
    return _find_eep_dir(DATA_DIR) is not None


def mesa_data_available() -> bool:
    return len(_find_history_files(MESA_DATA_DIR)) > 0


def mesa_solar_available() -> bool:
    """True if the MESA data includes a near-solar [Fe/H] bucket. The fetched
    bearums grid is metal-poor only ([Fe/H]~-0.84); the solar bucket is a manual
    drop-in (see backend/docs/mesa_solar_recipe.md), so this skips until it's added."""
    if not mesa_data_available():
        return False
    try:
        return MESAProvider().parameter_ranges()["feh"]["max"] >= -0.2
    except Exception:
        return False


def mist_fehs_available() -> set[float]:
    """[Fe/H] values whose grids are present on disk (from the dir names)."""
    return {
        fh for d in _find_eep_dirs(DATA_DIR)
        if (fh := _feh_from_path(d)) is not None
    }


def mist_vvcrits_available() -> set[float]:
    """v/vcrit rotation rates whose grids are present on disk (from the dir names)."""
    return {
        vc for d in _find_eep_dirs(DATA_DIR)
        if (vc := _vvcrit_from_path(d)) is not None
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

# The rotation-axis tests need both a non-rotating and a rotating grid at the same
# [Fe/H] (the bucket the contamination check compares). Fetch the rotating solar
# grid with `python -m star_sim.fetch_mist --vvcrit 0.4`.
requires_mist_rotation = pytest.mark.skipif(
    len(mist_vvcrits_available()) < 2,
    reason="needs a rotating MIST grid — run `python -m star_sim.fetch_mist --vvcrit 0.4`",
)

_HELDOUT_FEHS = {-0.5, 0.0, 0.5}
requires_mist_heldout_feh = pytest.mark.skipif(
    not _HELDOUT_FEHS.issubset(mist_fehs_available()),
    reason="needs the m050/p000/p050 grids — fetch with `--feh m050` and `--feh p050`",
)

# MESAProvider needs offline MESA history.data runs (fetched via
# `python -m star_sim.fetch_mesa`, never committed — see fetch_mesa.py provenance).
requires_mesa_data = pytest.mark.skipif(
    not mesa_data_available(),
    reason="MESA runs not fetched — run: python -m star_sim.fetch_mesa",
)

# The MESA-vs-MIST cross-validation needs the two MIST grids that bracket the
# sample MESA grid's Z=0.00218 ([Fe/H]~-0.84): m100 (-1.0) and m075 (-0.75).
_MESA_BRACKET_FEHS = {-1.0, -0.75}
requires_mist_lowz = pytest.mark.skipif(
    not _MESA_BRACKET_FEHS.issubset(mist_fehs_available()),
    reason="needs the m100/m075 MIST grids — fetch with `--feh m075,m100`",
)

# The solar MESA-vs-MIST cross-validation needs the near-solar MESA bucket and
# the two MIST grids that bracket its ZAMS Z=0.01523: m050 (Z~0.005) and p000
# (Z~0.0164). p000 alone is *above* the MESA Z, so it cannot bracket it.
requires_mesa_solar = pytest.mark.skipif(
    not mesa_solar_available(),
    reason="no near-solar MESA bucket — see backend/docs/mesa_solar_recipe.md",
)

_SOLAR_BRACKET_FEHS = {-0.5, 0.0}
requires_mist_solar_bracket = pytest.mark.skipif(
    not _SOLAR_BRACKET_FEHS.issubset(mist_fehs_available()),
    reason="needs the m050/p000 MIST grids to bracket the solar MESA Z — fetch with `--feh m050`",
)


def spectra_data_available() -> bool:
    return (SPECTRA_DATA_DIR / GRID_FILENAME).is_file()


# The /spectrum line-physics tests need the baked spectrum grid (built once in the
# MSG container, never committed — see backend/docs/msg_spectra_build_recipe.md).
requires_spectra_data = pytest.mark.skipif(
    not spectra_data_available(),
    reason="spectrum grid not baked — see backend/docs/msg_spectra_build_recipe.md",
)


def wd_spectra_data_available() -> bool:
    return (SPECTRA_DATA_DIR / WD_GRID_FILENAME).is_file()


# The /wd_spectrum (Koester DA) tests need the baked white-dwarf cube — fetched +
# baked on the host (never committed): `python -m star_sim.fetch_koester` then
# `python scripts/bake_wd_spectra.py` (endgame Chunk 6).
requires_wd_spectra_data = pytest.mark.skipif(
    not wd_spectra_data_available(),
    reason="WD spectrum grid not baked — run fetch_koester + scripts/bake_wd_spectra.py",
)


def wr_spectra_data_available() -> bool:
    return (SPECTRA_DATA_DIR / WR_GRID_FILENAME).is_file()


# The /wr_spectrum (PoWR Wolf-Rayet) tests need the baked WR cube — fetched + baked on
# the host (never committed): `python -m star_sim.fetch_powr` then
# `python scripts/bake_wr_spectra.py` (endgame Chunk 7).
requires_wr_spectra_data = pytest.mark.skipif(
    not wr_spectra_data_available(),
    reason="WR spectrum grid not baked — run fetch_powr + scripts/bake_wr_spectra.py",
)
