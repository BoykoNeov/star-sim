"""Shared test fixtures / markers.

The default `PROVIDER` is now `MISTProvider`, which needs the MIST grids on disk
(fetched via `python -m star_sim.fetch_mist`, never committed — see spec §6).
A fresh checkout won't have them, so MIST-dependent tests must *skip*, not fail.
`requires_mist_data` is that guard; use it on any test that touches real grids
(directly, or through the API now that PROVIDER routes to MIST).
"""

from __future__ import annotations

from pathlib import Path

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
    ALPHA_GRID_FILENAME,
    GRID_FILENAME,
    SPECTRA_DATA_DIR,
    STRIPPED_GRID_FILENAME,
    WD_GRID_FILENAME,
    WR_GRID_FILENAME,
)
from star_sim.structure import PROFILES_DATA_DIR


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


def mist_rotation_fehs_available() -> set[float]:
    """[Fe/H] values that have a *rotating* (vvcrit>0) grid on disk — the metallicity
    span of the rotating axis, which the within-bucket [Fe/H] interpolation tests
    need (≥2 to bracket, the m050/p000/p050 trio to hold one out)."""
    return {
        fh for d in _find_eep_dirs(DATA_DIR)
        if (vc := _vvcrit_from_path(d)) is not None and vc > 0.0
        and (fh := _feh_from_path(d)) is not None
    }


def mist_rotation_lowz_available() -> bool:
    """True if a *low-Z* rotating grid (m100, [Fe/H]=-1.0) is on disk — the grid
    that carries the CHE / low-metallicity rotation payoff."""
    return any(
        _vvcrit_from_path(d) and _vvcrit_from_path(d) > 0.0 and _feh_from_path(d) == -1.0
        for d in _find_eep_dirs(DATA_DIR)
    )


# The within-bucket [Fe/H] interpolation tests on the *rotating* axis need >=2
# rotating metallicity grids to bracket (mirrors requires_mist_multifeh, but for the
# vvcrit=0.4 axis). Fetch e.g. `python -m star_sim.fetch_mist --vvcrit 0.4 --feh m075`.
requires_mist_rotation_multifeh = pytest.mark.skipif(
    len(mist_rotation_fehs_available()) < 2,
    reason="needs >=2 rotating MIST metallicity grids — e.g. `--vvcrit 0.4 --feh m075`",
)


# The low-Z rotation tests need the rotating m100 grid (CHE lives at low Z).
requires_mist_rotation_lowz = pytest.mark.skipif(
    not mist_rotation_lowz_available(),
    reason="needs the low-Z rotating grid — run `python -m star_sim.fetch_mist --vvcrit 0.4 --feh m100`",
)

_HELDOUT_FEHS = {-0.5, 0.0, 0.5}
requires_mist_heldout_feh = pytest.mark.skipif(
    not _HELDOUT_FEHS.issubset(mist_fehs_available()),
    reason="needs the m050/p000/p050 grids — fetch with `--feh m050` and `--feh p050`",
)

# The held-out [Fe/H] accuracy test on the rotating axis needs the rotating
# m050/p000/p050 trio (p000 rotating is the ground truth the others bracket) — the
# vvcrit=0.4 analog of requires_mist_heldout_feh.
requires_mist_rotation_heldout_feh = pytest.mark.skipif(
    not _HELDOUT_FEHS.issubset(mist_rotation_fehs_available()),
    reason="needs the rotating m050/p000/p050 grids — fetch with `--vvcrit 0.4 --feh m050,p050`",
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


def alpha_spectra_data_available() -> bool:
    return (SPECTRA_DATA_DIR / ALPHA_GRID_FILENAME).is_file()


# The /alpha_spectrum ([alpha/Fe] Coelho cube) tests need the baked alpha cube —
# fetched + baked on the host (never committed): `python -m star_sim.fetch_coelho`
# then `python scripts/bake_alpha_spectra.py` (atlas Tier B).
requires_alpha_spectra_data = pytest.mark.skipif(
    not alpha_spectra_data_available(),
    reason="alpha spectrum grid not baked — run fetch_coelho + scripts/bake_alpha_spectra.py",
)


def stripped_spectra_data_available() -> bool:
    return (SPECTRA_DATA_DIR / STRIPPED_GRID_FILENAME).is_file()


# The /stripped_spectrum (Götberg binary-stripped-star cube, Chunk 3) tests need the
# baked stripped cube — baked on the host from the gitignored Götberg spectra tree
# (never committed): `python scripts/bake_stripped_spectra.py` (needs the tree from
# `python -m star_sim.fetch_gotberg`'s recipe under data/gotberg_stripped/).
requires_stripped_spectra_data = pytest.mark.skipif(
    not stripped_spectra_data_available(),
    reason="stripped-star spectrum grid not baked — run scripts/bake_stripped_spectra.py "
    "(needs the Götberg spectra tree; see docs/plans/stripped-consort-unveiling.md)",
)


def structure_data_available() -> bool:
    """True if any MESA interior-structure profile*.data snapshots are present.

    Generated offline by running MESA with profile snapshots enabled (never
    committed — see backend/docs/mesa_structure_recipe.md), so the /structure tests
    skip until they're dropped under data/mesa_profiles/."""
    import glob

    return len(glob.glob(str(PROFILES_DATA_DIR / "**" / "profile*.data"), recursive=True)) > 0


def structure_massive_available() -> bool:
    """True if a *massive* (convective-core) interior-structure slice is present.

    The 1 M☉ solar slice alone satisfies `structure_data_available()`, but the
    convective-core ↔ radiative-envelope flip test needs an intermediate-mass run
    (the 2/6 M☉ slice — see the recipe §6). Detect it by a snapshot whose initial
    mass is well above the solar slice, so the flip test *skips* (not fails) on a
    checkout that only has the 1 M☉ data."""
    from star_sim.structure import _ProfileIndex, StructureDataMissing

    try:
        return any(m.mass_init >= 4.0 for m in _ProfileIndex().available())
    except StructureDataMissing:
        return False


def structure_transitional_available() -> bool:
    """True if a *transitional* (double-convective) interior-structure slice is present.

    The 1 M☉ Sun and the 6/15/25 M☉ massive slices satisfy `structure_data_available()`,
    but the double-convective test — a ~1.3 M☉ star with a convective core AND a
    convective envelope at once — needs the transitional slice (recipe §13). It falls in
    the gating gap between `requires_structure_massive` (≥4 M☉) and
    `requires_structure_lowmass` (≤0.5 M☉), so without its own marker the test would
    *fail* (not skip) on a checkout without the 1.3 M☉ data. Detect it by a snapshot in
    the narrow transitional band (1.1 ≤ mass ≤ 1.5) — this excludes both the 1.0 M☉ Sun
    and the 2.0 M☉ convective-core slice, either of which is otherwise on disk."""
    from star_sim.structure import _ProfileIndex, StructureDataMissing

    try:
        return any(1.1 <= m.mass_init <= 1.5 for m in _ProfileIndex().available())
    except StructureDataMissing:
        return False


def structure_multifeh_available() -> bool:
    """True if a *non-solar-metallicity* interior-structure slice is present.

    The solar-Z slices (all at [Fe/H]=0) satisfy `structure_data_available()`, but the
    metallicity-axis test — the convective envelope shallows as [Fe/H] drops — needs at
    least one non-solar-Z 1 M☉ run (the [Fe/H]=−1 / +0.5 slices, see the recipe §10).
    Detect it by a snapshot whose [Fe/H] is well off solar, so that test *skips* (not
    fails) on a checkout with only the solar-Z data."""
    from star_sim.structure import _ProfileIndex, StructureDataMissing

    try:
        return any(abs(m.feh) > 0.3 for m in _ProfileIndex().available())
    except StructureDataMissing:
        return False


def structure_lowmass_available() -> bool:
    """True if a *low-mass, fully-convective* interior-structure slice is present.

    The 1 M☉ (or 2/6 M☉) slices satisfy `structure_data_available()`, but the
    fully-convective M-dwarf test needs a run below the ~0.35 M☉ fully-convective
    boundary (the 0.25 M☉ slice — see the recipe §9). Detect it by a snapshot whose
    initial mass is well below the solar slice, so that test *skips* (not fails) on a
    checkout without the low-mass data."""
    from star_sim.structure import _ProfileIndex, StructureDataMissing

    try:
        return any(m.mass_init <= 0.5 for m in _ProfileIndex().available())
    except StructureDataMissing:
        return False


# The /structure (real MESA interior-structure) tests need offline MESA profile
# snapshots — generated on the host, never committed (endgame's Lane-Emden successor).
requires_structure_data = pytest.mark.skipif(
    not structure_data_available(),
    reason="no MESA profiles — see backend/docs/mesa_structure_recipe.md",
)

# The convective-core flip test additionally needs the massive (2/6 M☉) slice — the
# 1 M☉ solar data alone would make it FAIL, not skip. See mesa_structure_recipe.md §6.
requires_structure_massive = pytest.mark.skipif(
    not structure_massive_available(),
    reason="no massive MESA profile slice (2/6 M☉) — see backend/docs/mesa_structure_recipe.md §6",
)

# The fully-convective M-dwarf test needs the low-mass (0.25 M☉) slice — the solar/
# massive data alone would make it FAIL, not skip. See mesa_structure_recipe.md §9.
requires_structure_lowmass = pytest.mark.skipif(
    not structure_lowmass_available(),
    reason="no low-mass MESA profile slice (0.25 M☉) — see backend/docs/mesa_structure_recipe.md §9",
)

# The metallicity-axis test needs a non-solar-Z 1 M☉ slice ([Fe/H]=−1 / +0.5) — the
# solar-Z data alone would make it FAIL, not skip. See mesa_structure_recipe.md §10.
requires_structure_multifeh = pytest.mark.skipif(
    not structure_multifeh_available(),
    reason="no non-solar-Z MESA profile slice ([Fe/H]=−1/+0.5) — see backend/docs/mesa_structure_recipe.md §10",
)

# The double-convective test needs the transitional (~1.3 M☉) slice — a mass with a
# convective core AND a convective envelope at once. The 1 M☉ / massive data alone would
# make it FAIL, not skip. See mesa_structure_recipe.md §13.
requires_structure_transitional = pytest.mark.skipif(
    not structure_transitional_available(),
    reason="no transitional MESA profile slice (~1.3 M☉) — see backend/docs/mesa_structure_recipe.md §13",
)


def gotberg_seds_available() -> bool:
    """True if the Götberg stripped-star SEDs (VizieR, gitignored) are on disk.

    The *parameter table* is committed to the repo (star_sim/data/gotberg_z014.csv), so
    the binary sibling's parse/snap/validity tests always run. Only the SED-consistency
    regression — the check that the LLM-transcribed table matches the ground-truth SEDs
    to ≤0.07 dex — reads the gitignored spectra tree, so it skips until those are fetched
    (browser-past-Anubis VizieR tarball → data/gotberg_stripped/, see
    docs/plans/stripped-consort-unveiling.md)."""
    import glob

    from star_sim.binary import GOTBERG_SOLAR_Z  # noqa: F401 (import-guard the package)

    _REPO_ROOT = Path(__file__).resolve().parents[2]
    grid = _REPO_ROOT / "data" / "gotberg_stripped" / "grid_014"
    return len(glob.glob(str(grid / "**" / "SED.txt"), recursive=True)) > 0


requires_gotberg_data = pytest.mark.skipif(
    not gotberg_seds_available(),
    reason="Götberg stripped-star SEDs not present — host-fetch the VizieR tarball "
    "into data/gotberg_stripped/ (see docs/plans/stripped-consort-unveiling.md)",
)


def posydon_data_available() -> bool:
    """True if at least one baked POSYDON grid npz is present.

    Baked on the host from an extracted POSYDON HMS-HMS grid (never committed —
    multi-GB Zenodo source, like MIST/MESA): `python -m star_sim.fetch_posydon`'s
    recipe, then `python scripts/bake_posydon.py --z-label <label> --feh <feh>`
    (docs/plans/entwined-consort-inspiral.md, Chunk 4a)."""
    from star_sim.posydon import BAKED_DIR

    return BAKED_DIR.is_dir() and any(BAKED_DIR.glob("*.npz"))


requires_posydon_data = pytest.mark.skipif(
    not posydon_data_available(),
    reason="no baked POSYDON grid — run fetch_posydon.py's recipe then "
    "scripts/bake_posydon.py (see docs/plans/entwined-consort-inspiral.md)",
)


def posydon_co_data_available() -> bool:
    """True if at least one baked POSYDON CO-HMS_RLO grid npz is present.

    Baked on the host from an extracted POSYDON CO-HMS_RLO grid (never committed — same
    multi-GB Zenodo tarball as the HMS-HMS grid, a different internal path):
    `scripts/bake_posydon.py --grid-type co-hms-rlo --z-label <label> --feh <feh>`
    (docs/plans/tempered-lineage-inspiral.md, Phase 1 Chunk 1a)."""
    from star_sim.posydon_co import BAKED_CO_DIR

    return BAKED_CO_DIR.is_dir() and any(BAKED_CO_DIR.glob("*.npz"))


requires_posydon_co_data = pytest.mark.skipif(
    not posydon_co_data_available(),
    reason="no baked POSYDON CO-HMS_RLO grid — run scripts/bake_posydon.py "
    "--grid-type co-hms-rlo (see docs/plans/tempered-lineage-inspiral.md)",
)


def posydon_co_multifeh_available() -> bool:
    """True if >=2 baked CO-HMS_RLO metallicity grids are present (the Chunk-1c axis).

    Bake more buckets with `scripts/bake_posydon.py --grid-type co-hms-rlo --z-label
    <label> --feh <feh>` (docs/plans/tempered-lineage-inspiral.md, Phase 1 Chunk 1c)."""
    from star_sim.posydon_co import BAKED_CO_DIR

    return BAKED_CO_DIR.is_dir() and len(list(BAKED_CO_DIR.glob("*.npz"))) >= 2


requires_posydon_co_multifeh = pytest.mark.skipif(
    not posydon_co_multifeh_available(),
    reason="needs >=2 baked POSYDON CO-HMS_RLO metallicity grids — bake another with "
    "scripts/bake_posydon.py --grid-type co-hms-rlo (Chunk 1c)",
)


def posydon_co_he_data_available() -> bool:
    """True if BOTH baked He-star CO grids (CO-HeMS + CO-HeMS_RLO) are present — the
    double-compact-object channel (Chunk 2a). The suite exercises both (one for the
    He-donor accretion payoff, one for the DCO-classification payoff), so both are needed.

    Baked on the host from the extracted He-star CO grids (never committed — same multi-GB
    Zenodo tarball, different internal paths):
    `scripts/bake_posydon.py --grid-type co-hems-rlo` and `--grid-type co-hems`
    (docs/plans/tempered-lineage-inspiral.md, Phase 1 Chunk 2a)."""
    from star_sim.posydon_co import BAKED_CO_HEMS_DIR, BAKED_CO_HEMS_RLO_DIR

    return (BAKED_CO_HEMS_DIR.is_dir() and any(BAKED_CO_HEMS_DIR.glob("*.npz"))
            and BAKED_CO_HEMS_RLO_DIR.is_dir() and any(BAKED_CO_HEMS_RLO_DIR.glob("*.npz")))


requires_posydon_co_he_data = pytest.mark.skipif(
    not posydon_co_he_data_available(),
    reason="no baked POSYDON CO-HeMS / CO-HeMS_RLO grids — run scripts/bake_posydon.py "
    "--grid-type co-hems-rlo and --grid-type co-hems (see "
    "docs/plans/tempered-lineage-inspiral.md, Phase 1 Chunk 2a)",
)


def posydon_co_he_multifeh_available() -> bool:
    """True if >=2 baked metallicity grids exist for BOTH He-star CO grids (the Chunk-2c
    axis). Bake more buckets with `scripts/bake_posydon.py --grid-type co-hems[-rlo]`."""
    from star_sim.posydon_co import BAKED_CO_HEMS_DIR, BAKED_CO_HEMS_RLO_DIR

    return (BAKED_CO_HEMS_DIR.is_dir() and len(list(BAKED_CO_HEMS_DIR.glob("*.npz"))) >= 2
            and BAKED_CO_HEMS_RLO_DIR.is_dir()
            and len(list(BAKED_CO_HEMS_RLO_DIR.glob("*.npz"))) >= 2)


requires_posydon_co_he_multifeh = pytest.mark.skipif(
    not posydon_co_he_multifeh_available(),
    reason="needs >=2 baked metallicity grids for both He CO grids — bake more with "
    "scripts/bake_posydon.py --grid-type co-hems[-rlo] (Chunk 2c)",
)
