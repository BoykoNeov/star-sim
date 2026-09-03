"""Shared test fixtures / markers — one table of datasets, one gate per dataset.

Almost every grid this project reads is fetched or baked on the host and never
committed (MIST, MESA, the spectrum cubes, POSYDON, BPASS…). A fresh checkout has
none of them, so a test that touches real data must **skip, not fail** — that is
what the `requires_*` markers below are for, and what CI's data-free job checks.

The shape: `_DATASETS` maps a short dataset name to `(predicate, reason)`, and
`requires(name)` turns one row into a skip marker. Every marker is then a single
line, so adding a dataset is one table row plus one alias rather than a docstring'd
predicate, a four-line `pytest.mark.skipif`, and a comment repeating the docstring.
`pytest_report_header` prints the table at the top of a run, so `pytest
--collect-only` says which data is present and which gates are therefore closed.

Two things that look like sloppiness and are not:

  * **The sibling imports inside the predicates stay deferred.** Hoisting them to
    module scope would make *collecting the suite at all* depend on every sibling
    importing cleanly — the opposite of the point.
  * **A registry buys no laziness.** `pytest.mark.skipif` takes a bool, not a
    callable, so every predicate still runs at import. The wins are line count, one
    place per dataset, and the report header — not deferred evaluation.
"""

from __future__ import annotations

import glob
from collections.abc import Callable
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

# --- shapes several datasets share -------------------------------------------


def _has_npz(baked_dir: Path, n: int = 1) -> bool:
    """`n` or more baked `.npz` buckets under `baked_dir` — the POSYDON gates' shape.

    `n=1` is "this grid was baked at all"; `n=2` is "there is a metallicity *axis*
    to snap along", which is what the multi-[Fe/H] tests need."""
    return baked_dir.is_dir() and len(list(baked_dir.glob("*.npz"))) >= n


_MIST_GRIDS: set[tuple[float | None, float | None]] | None = None


def _mist_grids() -> set[tuple[float | None, float | None]]:
    """Every ([Fe/H], v/vcrit) MIST grid on disk, read once from the directory names.

    All ten MIST gates below are a question about this one set: how many
    metallicities, how many rotation rates, does a specific trio bracket a held-out
    value, is the low-Z *rotating* grid here. Either coordinate is None when the
    directory name doesn't carry it."""
    global _MIST_GRIDS
    if _MIST_GRIDS is None:
        _MIST_GRIDS = {(_feh_from_path(d), _vvcrit_from_path(d)) for d in _find_eep_dirs(DATA_DIR)}
    return _MIST_GRIDS


def _mist_fehs(rotating: bool = False) -> set[float]:
    """The metallicities on disk — all of them, or only those with a rotating grid."""
    return {feh for feh, vc in _mist_grids()
            if feh is not None and (not rotating or (vc is not None and vc > 0.0))}


def _mist_vvcrits() -> set[float]:
    return {vc for _, vc in _mist_grids() if vc is not None}


_PROFILES: list | None = None


def _profiles() -> list:
    """The MESA interior-structure snapshots on disk, indexed ONCE.

    The four `structure_*` slice gates each ask a different question of the same
    index — is there a massive (convective-core) slice, a fully-convective low-mass
    one, a non-solar-Z one, a transitional one — and each used to build its own
    `_ProfileIndex()`. Empty when no profiles are present."""
    global _PROFILES
    if _PROFILES is None:
        from star_sim.structure import StructureDataMissing, _ProfileIndex

        try:
            _PROFILES = list(_ProfileIndex().available())
        except StructureDataMissing:
            _PROFILES = []
    return _PROFILES


def _mesa_solar() -> bool:
    """True if the MESA data includes a near-solar [Fe/H] bucket. The fetched bearums
    grid is metal-poor only ([Fe/H]~-0.84); the solar bucket is a manual drop-in (see
    backend/docs/mesa_solar_recipe.md), so this stays closed until it's added."""
    if not _find_history_files(MESA_DATA_DIR):
        return False
    try:
        return MESAProvider().parameter_ranges()["feh"]["max"] >= -0.2
    except Exception:
        return False


# The [Fe/H] trio the held-out accuracy tests need: p000 is the ground truth, m050
# and p050 are the bracket that must reproduce it without seeing it.
_HELDOUT_FEHS = {-0.5, 0.0, 0.5}


# --- the dataset table --------------------------------------------------------
# name -> (is the data present?, what to run if it isn't). The `reason` is what a
# contributor reads in `-rs` output, so it names the fetch/bake command, not the
# predicate. Ordered spine-outward: MIST, MESA, spectra, structure, the what-if
# overlays, the ensembles, the binary grids.

_DATASETS: dict[str, tuple[Callable[[], bool], str]] = {
    # -- the spine's own grids --
    "mist": (
        lambda: _find_eep_dir(DATA_DIR) is not None,
        "MIST grids not fetched — run: python -m star_sim.fetch_mist",
    ),
    # The hosted download (`python -m star_sim.fetch_mist_baked`) ships cache-only
    # buckets: a fully working provider with NO raw text tracks. A test that reads a
    # raw track as *ground truth* gates on this, or a cache-only clone fails not skips.
    "mist_raw_tracks": (
        lambda: any(
            glob.glob(str(d / "*.track.eep"))
            or glob.glob(str(d / "**" / "*.track.eep"), recursive=True)
            for d in _find_eep_dirs(DATA_DIR)
        ),
        "needs raw MIST `.track.eep` files as ground truth (the hosted cache-only "
        "download has none) — run: python -m star_sim.fetch_mist",
    ),
    "mist_multifeh": (
        lambda: len(_mist_fehs()) >= 2,
        "needs >=2 MIST metallicity grids — e.g. `python -m star_sim.fetch_mist --feh m050`",
    ),
    "mist_heldout_feh": (
        lambda: _HELDOUT_FEHS <= _mist_fehs(),
        "needs the m050/p000/p050 grids — fetch with `--feh m050` and `--feh p050`",
    ),
    # The MESA-vs-MIST cross-validation needs the two MIST grids that bracket the
    # sample MESA grid's Z=0.00218 ([Fe/H]~-0.84): m100 (-1.0) and m075 (-0.75).
    "mist_lowz": (
        lambda: {-1.0, -0.75} <= _mist_fehs(),
        "needs the m100/m075 MIST grids — fetch with `--feh m075,m100`",
    ),
    # The *solar* cross-check needs m050 (Z~0.005) and p000 (Z~0.0164) to bracket the
    # solar MESA bucket's ZAMS Z=0.01523. p000 alone is *above* it, so it can't bracket.
    "mist_solar_bracket": (
        lambda: {-0.5, 0.0} <= _mist_fehs(),
        "needs the m050/p000 MIST grids to bracket the solar MESA Z — fetch with `--feh m050`",
    ),
    # Rotation: the contamination check compares a rotating against a non-rotating grid
    # at the same [Fe/H], so it needs both buckets — hence >=2 rates, not >=1 rotating.
    "mist_rotation": (
        lambda: len(_mist_vvcrits()) >= 2,
        "needs a rotating MIST grid — run `python -m star_sim.fetch_mist --vvcrit 0.4`",
    ),
    "mist_rotation_multifeh": (
        lambda: len(_mist_fehs(rotating=True)) >= 2,
        "needs >=2 rotating MIST metallicity grids — e.g. `--vvcrit 0.4 --feh m075`",
    ),
    "mist_rotation_heldout_feh": (
        lambda: _HELDOUT_FEHS <= _mist_fehs(rotating=True),
        "needs the rotating m050/p000/p050 grids — fetch with `--vvcrit 0.4 --feh m050,p050`",
    ),
    # The CHE / low-metallicity rotation payoff lives on the rotating m100 grid.
    "mist_rotation_lowz": (
        lambda: any(feh == -1.0 and vc is not None and vc > 0.0 for feh, vc in _mist_grids()),
        "needs the low-Z rotating grid — run `python -m star_sim.fetch_mist --vvcrit 0.4 --feh m100`",
    ),
    # MESAProvider needs offline MESA history.data runs (see fetch_mesa.py provenance).
    "mesa": (
        lambda: len(_find_history_files(MESA_DATA_DIR)) > 0,
        "MESA runs not fetched — run: python -m star_sim.fetch_mesa",
    ),
    "mesa_solar": (
        _mesa_solar,
        "no near-solar MESA bucket — see backend/docs/mesa_solar_recipe.md",
    ),

    # -- the spectrum cubes: five different sources, one "is it baked?" shape --
    # Each is baked once on the host and never committed. The recipes are genuinely
    # different, so each reason carries its own verbatim (the §1.2 `missing_hint`
    # finding: these are hand-written recipes, not a template with a slot).
    "spectra": (
        lambda: (SPECTRA_DATA_DIR / GRID_FILENAME).is_file(),
        "spectrum grid not baked — see backend/docs/msg_spectra_build_recipe.md",
    ),
    "wd_spectra": (
        lambda: (SPECTRA_DATA_DIR / WD_GRID_FILENAME).is_file(),
        "WD spectrum grid not baked — run fetch_koester + scripts/bake_wd_spectra.py",
    ),
    "wr_spectra": (
        lambda: (SPECTRA_DATA_DIR / WR_GRID_FILENAME).is_file(),
        "WR spectrum grid not baked — run fetch_powr + scripts/bake_wr_spectra.py",
    ),
    "alpha_spectra": (
        lambda: (SPECTRA_DATA_DIR / ALPHA_GRID_FILENAME).is_file(),
        "alpha spectrum grid not baked — run fetch_coelho + scripts/bake_alpha_spectra.py",
    ),
    "stripped_spectra": (
        lambda: (SPECTRA_DATA_DIR / STRIPPED_GRID_FILENAME).is_file(),
        "stripped-star spectrum grid not baked — run scripts/bake_stripped_spectra.py "
        "(needs the Götberg spectra tree; see docs/plans/stripped-consort-unveiling.md)",
    ),

    # -- interior structure: one "any profiles?" gate + four "which slice?" gates --
    # The slice gates exist because the 1 M☉ solar run alone satisfies `structure`, so
    # without them the regime-specific tests would FAIL rather than skip on a checkout
    # that only has the Sun. Each band excludes the slices already on disk.
    "structure": (
        lambda: len(glob.glob(str(_profiles_dir() / "**" / "profile*.data"), recursive=True)) > 0,
        "no MESA profiles — see backend/docs/mesa_structure_recipe.md",
    ),
    "structure_massive": (          # convective core ↔ radiative envelope flip
        lambda: any(m.mass_init >= 4.0 for m in _profiles()),
        "no massive MESA profile slice (2/6 M☉) — see backend/docs/mesa_structure_recipe.md §6",
    ),
    "structure_lowmass": (          # below the ~0.35 M☉ fully-convective boundary
        lambda: any(m.mass_init <= 0.5 for m in _profiles()),
        "no low-mass MESA profile slice (0.25 M☉) — see backend/docs/mesa_structure_recipe.md §9",
    ),
    "structure_multifeh": (         # the convective envelope shallows as [Fe/H] drops
        lambda: any(abs(m.feh) > 0.3 for m in _profiles()),
        "no non-solar-Z MESA profile slice ([Fe/H]=−1/+0.5) — "
        "see backend/docs/mesa_structure_recipe.md §10",
    ),
    # ~1.3 M☉: a convective core AND a convective envelope at once. The band excludes
    # both the 1.0 M☉ Sun and the 2.0 M☉ convective-core slice, either of which is
    # otherwise on disk — so this falls in the gap between massive (≥4) and lowmass (≤0.5).
    "structure_transitional": (
        lambda: any(1.1 <= m.mass_init <= 1.5 for m in _profiles()),
        "no transitional MESA profile slice (~1.3 M☉) — "
        "see backend/docs/mesa_structure_recipe.md §13",
    ),

    # -- the what-if overlays: self-run baseline+enhanced MESA pairs, host-built --
    "helium": (
        lambda: len(_helium_runs()) > 0,
        "no initial-helium MESA runs — see backend/docs/mesa_helium_recipe.md",
    ),
    "alpha": (
        lambda: len(_alpha_runs()) > 0,
        "no α-enhanced MESA runs — see backend/docs/mesa_alpha_recipe.md",
    ),

    # -- the ensembles --
    "bpass": (
        lambda: _sibling_flag("bpass", "bpass_available"),
        "no baked BPASS cube (data/bpass/bpass_ssp.npz) — see scripts/bake_bpass_spectra.py",
    ),
    # A DIFFERENT cube from the SED one: the HR-diagram number-density grid.
    "bpass_hrd": (
        lambda: _sibling_flag("bpass", "hrd_available"),
        "no baked BPASS HRD cube (data/bpass/bpass_hrd.npz) — see scripts/bake_bpass_hrd.py",
    ),
    # The published MIST v2.5 `.iso` grid — a separate download from the EEP tracks.
    "isochrone": (
        lambda: _sibling_flag("isochrone", "isochrone_available"),
        "no MIST .iso grid (data/mist_isochrones/) — run python -m star_sim.fetch_mist_iso",
    ),

    # -- the binary grids --
    # The Götberg *parameter table* is committed, so the binary sibling's parse/snap/
    # validity tests always run; only the SED-consistency regression (the check that the
    # transcribed table matches the ground-truth spectra to ≤0.07 dex) needs the tree.
    "gotberg": (
        lambda: len(glob.glob(str(_repo_root() / "data" / "gotberg_stripped" / "grid_014"
                                  / "**" / "SED.txt"), recursive=True)) > 0,
        "Götberg stripped-star SEDs not present — host-fetch the VizieR tarball "
        "into data/gotberg_stripped/ (see docs/plans/stripped-consort-unveiling.md)",
    ),
    # POSYDON: one multi-GB Zenodo tarball, several internal grids, each baked to its
    # own directory of per-metallicity `.npz` buckets by scripts/bake_posydon.py.
    "posydon": (
        lambda: _has_npz(_posydon_dir("posydon", "BAKED_DIR")),
        "no baked POSYDON grid — run fetch_posydon.py's recipe then scripts/bake_posydon.py "
        "(see docs/plans/entwined-consort-inspiral.md)",
    ),
    "posydon_co": (
        lambda: _has_npz(_posydon_dir("posydon_co", "BAKED_CO_DIR")),
        "no baked POSYDON CO-HMS_RLO grid — run scripts/bake_posydon.py --grid-type "
        "co-hms-rlo (see docs/plans/tempered-lineage-inspiral.md)",
    ),
    "posydon_co_multifeh": (
        lambda: _has_npz(_posydon_dir("posydon_co", "BAKED_CO_DIR"), 2),
        "needs >=2 baked POSYDON CO-HMS_RLO metallicity grids — bake another with "
        "scripts/bake_posydon.py --grid-type co-hms-rlo (Chunk 1c)",
    ),
    # BOTH He-star grids: the suite exercises one for the He-donor accretion payoff and
    # the other for the double-compact-object classification, so one alone won't do.
    "posydon_co_he": (
        lambda: all(_has_npz(_posydon_dir("posydon_co", d))
                    for d in ("BAKED_CO_HEMS_DIR", "BAKED_CO_HEMS_RLO_DIR")),
        "no baked POSYDON CO-HeMS / CO-HeMS_RLO grids — run scripts/bake_posydon.py "
        "--grid-type co-hems-rlo and --grid-type co-hems (see "
        "docs/plans/tempered-lineage-inspiral.md, Phase 1 Chunk 2a)",
    ),
    "posydon_co_he_multifeh": (
        lambda: all(_has_npz(_posydon_dir("posydon_co", d), 2)
                    for d in ("BAKED_CO_HEMS_DIR", "BAKED_CO_HEMS_RLO_DIR")),
        "needs >=2 baked metallicity grids for both He CO grids — bake more with "
        "scripts/bake_posydon.py --grid-type co-hems[-rlo] (Chunk 2c)",
    ),
}


# --- the deferred sibling lookups the table's lambdas call --------------------
# Each import stays inside its function: collecting the suite must not depend on
# every sibling importing cleanly, and a table row is no place for a statement.


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _profiles_dir() -> Path:
    from star_sim.structure import PROFILES_DATA_DIR

    return PROFILES_DATA_DIR


def _helium_runs() -> list:
    from star_sim.helium import _find_history_files as helium_histories

    return helium_histories()


def _alpha_runs() -> list:
    from star_sim.alpha import _find_history_files as alpha_histories

    return alpha_histories()


def _sibling_flag(module: str, func: str) -> bool:
    """Call a sibling's own `*_available()`. The sibling, not the test suite, owns the
    question of whether its grid is usable — its `/…_status` route answers from it."""
    from importlib import import_module

    return bool(getattr(import_module(f"star_sim.{module}"), func)())


def _posydon_dir(module: str, attr: str) -> Path:
    from importlib import import_module

    return getattr(import_module(f"star_sim.{module}"), attr)


# --- turning a row into a marker ---------------------------------------------


def requires(dataset: str) -> pytest.MarkDecorator:
    """Skip unless `dataset`'s data is on disk. A `KeyError` on an unknown name is
    the point: a typo must fail at import, not mint a marker that never skips."""
    predicate, reason = _DATASETS[dataset]
    return pytest.mark.skipif(not predicate(), reason=reason)


def pytest_report_header(config) -> list[str]:
    """List which datasets are present, so a run says up front what it is *not*
    testing. This is the legibility the table was for: a suite that skips half of
    itself should say so before the dots start, and `--collect-only` shows it too."""
    have = sorted(name for name, (predicate, _) in _DATASETS.items() if predicate())
    missing = sorted(set(_DATASETS) - set(have))
    return [
        f"data present ({len(have)}/{len(_DATASETS)}): {', '.join(have) or 'none'}",
        f"gated off ({len(missing)}): {', '.join(missing) or 'none'}",
    ]


# --- the markers the tests import, one line each ------------------------------

requires_mist_data = requires("mist")
requires_mist_raw_tracks = requires("mist_raw_tracks")
requires_mist_multifeh = requires("mist_multifeh")
requires_mist_heldout_feh = requires("mist_heldout_feh")
requires_mist_lowz = requires("mist_lowz")
requires_mist_solar_bracket = requires("mist_solar_bracket")
requires_mist_rotation = requires("mist_rotation")
requires_mist_rotation_multifeh = requires("mist_rotation_multifeh")
requires_mist_rotation_heldout_feh = requires("mist_rotation_heldout_feh")
requires_mist_rotation_lowz = requires("mist_rotation_lowz")
requires_mesa_data = requires("mesa")
requires_mesa_solar = requires("mesa_solar")
requires_spectra_data = requires("spectra")
requires_wd_spectra_data = requires("wd_spectra")
requires_wr_spectra_data = requires("wr_spectra")
requires_alpha_spectra_data = requires("alpha_spectra")
requires_stripped_spectra_data = requires("stripped_spectra")
requires_structure_data = requires("structure")
requires_structure_massive = requires("structure_massive")
requires_structure_lowmass = requires("structure_lowmass")
requires_structure_multifeh = requires("structure_multifeh")
requires_structure_transitional = requires("structure_transitional")
requires_helium_data = requires("helium")
requires_alpha_data = requires("alpha")
requires_bpass_data = requires("bpass")
requires_bpass_hrd_data = requires("bpass_hrd")
requires_isochrone_data = requires("isochrone")
requires_gotberg_data = requires("gotberg")
requires_posydon_data = requires("posydon")
requires_posydon_co_data = requires("posydon_co")
requires_posydon_co_multifeh = requires("posydon_co_multifeh")
requires_posydon_co_he_data = requires("posydon_co_he")
requires_posydon_co_he_multifeh = requires("posydon_co_he_multifeh")
