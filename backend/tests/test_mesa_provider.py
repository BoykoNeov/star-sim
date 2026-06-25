"""Tests for MESAProvider — the second real provider (offline MESA history.data).

Three tiers:
  * **Parser/builder unit tests** on a tiny committed synthetic `history.data`
    fixture — always run (no MESA download needed). They pin the raw-format
    parse, the retry-row dedup, and the ZAMS/window/phase/[Fe/H] derivation.
  * **Provider API tests** on a tmp-dir copy of that fixture — also always run.
    They exercise the public §3 surface (ranges/track/state_at/snap/errors)
    end to end without real data.
  * **Physical-sanity tests** on the real sample grid — gated by
    `requires_mesa_data` (skip if `python -m star_sim.fetch_mesa` hasn't run).

The MESA-vs-MIST cross-validation (the "validate MIST" payoff) lives in its own
file, tests/test_mesa_vs_mist.py.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

from star_sim.provider import EndgameResult, ParameterOutOfRange, StellarStateProvider
from star_sim.providers import MESAProvider
from star_sim.providers.mesa import (
    _build_track,
    _dedup_by_model_number,
    _read_mesa_history,
)
from star_sim.state import StellarState

from .conftest import requires_mesa_data

FIXTURE = Path(__file__).parent / "fixtures" / "synthetic_history.data"


def _history_text(mass: float, x_surf: float, y_surf: float) -> str:
    """A minimal valid MESA `history.data` string for one synthetic run.

    The column set/order matches the committed fixture so the *real* parser
    handles it (whitespace-tokenized, so the exact spacing is irrelevant). Only
    `star_mass` and the **surface** abundances are parametrized — those set the
    run's mass and its derived [Fe/H] bucket. The center-H/He evolution (hence the
    ZAMS trim and the phase labels) is shared across buckets on purpose: the
    multi-Z tests below only exercise the snap routing / ranges, not physics.
    """
    z = 1.0 - x_surf - y_surf
    # (model, star_age, log_L, log_Teff, radius, log_g, center_h1, center_he4)
    rows = [
        (1, 1.0e2, 0.10, 3.760, 0.90, 4.50, 0.7200, 0.26480),  # pre-MS -> trimmed at ZAMS
        (2, 5.0e7, 0.00, 3.762, 0.88, 4.52, 0.7180, 0.26680),  # ZAMS
        (3, 1.0e9, 0.05, 3.763, 0.90, 4.50, 0.6000, 0.38480),  # MS
        (4, 3.0e9, 0.12, 3.765, 0.95, 4.45, 0.4000, 0.58480),  # MS
        (5, 5.0e9, 0.20, 3.766, 1.00, 4.40, 0.2000, 0.78480),  # late MS
        (6, 8.0e9, 1.50, 3.700, 5.00, 3.50, 0.0000, 0.98480),  # RGB
        (7, 9.0e9, 2.00, 3.650, 8.00, 3.00, 0.0000, 0.50000),  # CHeB
    ]
    head = (
        "         1            2            3\n"
        "version_number    initial_mass    initial_z\n"
        f"         12115     {mass:.6E}    {z:.6E}\n"
        "\n"
        "         1            2            3            4            5            6            7            8            9           10           11\n"
        "  model_number     star_age    star_mass        log_L     log_Teff"
        "       radius        log_g    center_h1   center_he4   surface_h1  surface_he4\n"
    )
    body = "\n".join(
        f"{m:14d} {age:.4E} {mass:.4E} {logl:.4E} {logt:.4E} {rad:.4E} {logg:.4E} "
        f"{ch1:.4E} {che4:.4E} {x_surf:.4E} {y_surf:.4E}"
        for (m, age, logl, logt, rad, logg, ch1, che4) in rows
    )
    return head + body + "\n"


# --- parser / builder unit tests (always run) --------------------------------
def test_read_mesa_history_parses_header_and_columns():
    header, data = _read_mesa_history(str(FIXTURE))
    # header block: names -> values
    assert header["initial_mass"] == "1.000000E+00"
    assert math.isclose(float(header["initial_z"]), 0.0152, rel_tol=1e-6)
    # data block: all 11 columns present, 9 raw rows (incl. 2 stale retry rows)
    assert set(data) >= {"model_number", "star_age", "log_L", "center_h1", "surface_h1"}
    assert data["star_age"].size == 9


def test_dedup_keeps_last_write_per_model_number():
    _, data = _read_mesa_history(str(FIXTURE))
    deduped = _dedup_by_model_number(data)
    # 9 raw rows, models 4 and 5 each written twice -> 7 unique, ordered by model#
    assert deduped["model_number"].tolist() == [1, 2, 3, 4, 5, 6, 7]
    # the *last* (corrected) write wins: model 4's new log_L is 0.12, not the stale 0.10
    i4 = int(np.where(deduped["model_number"] == 4)[0][0])
    assert math.isclose(deduped["log_L"][i4], 0.12, abs_tol=1e-9)


def test_build_track_windows_dedups_and_labels():
    t = _build_track(str(FIXTURE))
    assert t is not None
    # pre-MS row (model 1) trimmed; 6 rows remain (models 2..7)
    assert t.age.size == 6
    # age strictly increasing (dedup + safety mask did their job)
    assert np.all(np.diff(t.age) > 0)
    # ZAMS trim landed on the MS, not the pre-MS row
    assert t.Xc[0] < 0.72
    # derived [Fe/H]: Z = 1-0.72-0.2648 = 0.0152 = Z_sun -> 0.0
    assert math.isclose(t.feh, 0.0, abs_tol=1e-2)
    assert math.isclose(t.minit, 1.0, abs_tol=1e-6)
    # coarse phase labels: MS while core H burns, then RGB, then CHeB
    assert list(t.phase) == ["MS", "MS", "MS", "MS", "RGB", "CHeB"]
    # the corrected model-4 row (log_L=0.12) is what made it into the track
    assert math.isclose(10.0 ** t.logL[2], 10.0 ** 0.12, rel_tol=1e-9)


# --- provider API tests on synthetic data (always run) -----------------------
@pytest.fixture()
def synth_provider(tmp_path) -> MESAProvider:
    """A provider backed by a tmp-dir copy of the committed fixture (as history.data)."""
    run = tmp_path / "1Msun"
    run.mkdir()
    (run / "history.data").write_text(FIXTURE.read_text())
    return MESAProvider(data_dir=tmp_path)


def test_satisfies_provider_protocol():
    # runtime_checkable Protocol: structural conformance to the §3 boundary (no data).
    assert isinstance(MESAProvider(), StellarStateProvider)


def test_mesa_has_no_endgame():
    """MESA tutorial runs stop on/near the MS, so MESAProvider exposes no stellar
    endgame: type='none' for any input (no data load, no snap, no raise). This keeps
    the /endgame route provider-agnostic (§3) — only MISTProvider has endgame data."""
    res = MESAProvider().endgame(1.0, 0.0)
    assert isinstance(res, EndgameResult)
    assert res.type == "none"
    assert res.states == []


def test_synth_ranges_and_feh(synth_provider):
    r = synth_provider.parameter_ranges()
    assert r["mass_msun"] == {"min": 1.0, "max": 1.0}
    assert math.isclose(r["feh"]["min"], 0.0, abs_tol=1e-2)
    assert r["feh"]["min"] == r["feh"]["max"]   # single-metallicity grid -> a point


def test_synth_track_is_stellarstates_ordered_by_eep(synth_provider):
    states = synth_provider.track(1.0, 0.0)
    assert len(states) == 6
    assert all(isinstance(s, StellarState) for s in states)
    # eep is a monotonic row index; age strictly increasing
    assert all(states[i].eep < states[i + 1].eep for i in range(len(states) - 1))
    assert all(states[i].age_yr < states[i + 1].age_yr for i in range(len(states) - 1))
    # no isotope columns -> per-element breakdown degrades to empty (§3 graceful)
    assert states[0].metals_surf == {} and states[0].metals_core == {}


def test_synth_state_at_clamps_age_no_extrapolation(synth_provider):
    lo, hi = synth_provider.age_range(1.0, 0.0)
    young = synth_provider.state_at(1.0, 0.0, 0.0)         # below window
    old = synth_provider.state_at(1.0, 0.0, 1e15)          # above window
    assert young.age_yr == pytest.approx(lo)
    assert old.age_yr == pytest.approx(hi)


def test_synth_out_of_range_raises(synth_provider):
    with pytest.raises(ParameterOutOfRange):
        synth_provider.state_at(5.0, 0.0, 1e9)             # mass off the (1,1) grid
    with pytest.raises(ParameterOutOfRange):
        synth_provider.state_at(1.0, 0.5, 1e9)             # [Fe/H] off the single grid
        # NB: 0.5 is *outside* the single-Z grid [0,0], so it still raises (snap
        # only kicks in for in-range [Fe/H] — see the multi-Z tests below).


# --- multi-metallicity snap path on synthetic data (always run) --------------
@pytest.fixture()
def multiz_provider(tmp_path) -> MESAProvider:
    """Two [Fe/H] buckets — solar (1.0 & 2.0 Msun) + metal-poor -0.5 (1.0 Msun) —
    written as separate runs under one data dir. Deliberately *non-rectangular*
    (the solar bucket has an extra mass), so the snap-feh-then-mass path and the
    per-feh mass_range are exercised always-on, without any real download."""
    def write(sub: str, mass: float, x: float, y: float) -> None:
        d = tmp_path / sub
        d.mkdir()
        (d / "history.data").write_text(_history_text(mass, x, y))

    write("solar_1", 1.0, 0.7200, 0.26480)   # Z=0.0152  -> [Fe/H] 0.0
    write("solar_2", 2.0, 0.7200, 0.26480)   # Z=0.0152  -> [Fe/H] 0.0
    write("mp_1", 1.0, 0.7500, 0.24520)      # Z=0.0048  -> [Fe/H] -0.50
    return MESAProvider(data_dir=tmp_path)


def test_multiz_feh_is_a_real_span(multiz_provider):
    r = multiz_provider.parameter_ranges()
    assert r["feh"]["min"] == pytest.approx(-0.50, abs=1e-9)
    assert r["feh"]["max"] == pytest.approx(0.0, abs=1e-9)
    assert r["feh"]["min"] != r["feh"]["max"]            # no longer a pinned point
    assert r["mass_msun"] == {"min": 1.0, "max": 2.0}    # global span across buckets


def test_multiz_mass_range_is_per_feh_nonrectangular(multiz_provider):
    assert multiz_provider.mass_range(0.0) == (1.0, 2.0)    # solar has two masses
    assert multiz_provider.mass_range(-0.5) == (1.0, 1.0)   # metal-poor has one


def test_multiz_snaps_feh_and_reports_true_value(multiz_provider):
    # -0.1 is nearer solar (0.0) -> snaps there, reports the *true* grid [Fe/H].
    near_solar = multiz_provider.state_at(1.0, -0.1, 1e9)
    assert near_solar.feh_init == pytest.approx(0.0, abs=1e-9)
    # -0.4 is nearer -0.5 -> snaps to the metal-poor bucket.
    near_mp = multiz_provider.state_at(1.0, -0.4, 1e9)
    assert near_mp.feh_init == pytest.approx(-0.5, abs=1e-9)


def test_multiz_snaps_mass_within_bucket(multiz_provider):
    # 1.6 at solar -> nearest mass 2.0 (|1.6-2| < |1.6-1|); true mass reported.
    s = multiz_provider.state_at(1.6, 0.0, 1e9)
    assert s.mass_init_msun == 2.0
    # the metal-poor bucket has only 1.0, so 1.6 is off *that* bucket -> raises
    # (the domain is non-rectangular; no silent cross-bucket borrow).
    with pytest.raises(ParameterOutOfRange):
        multiz_provider.state_at(1.6, -0.5, 1e9)


def test_multiz_out_of_grid_feh_raises(multiz_provider):
    with pytest.raises(ParameterOutOfRange):
        multiz_provider.state_at(1.0, 0.6, 1e9)     # above max [Fe/H] (0.0)
    with pytest.raises(ParameterOutOfRange):
        multiz_provider.state_at(1.0, -1.0, 1e9)    # below min [Fe/H] (-0.5)


# --- physical-sanity tests on the real sample grid (gated) -------------------
@pytest.fixture(scope="module")
def provider() -> MESAProvider:
    return MESAProvider()


@requires_mesa_data
def test_real_grid_loads_with_expected_masses(provider):
    r = provider.parameter_ranges()
    assert r["mass_msun"]["min"] == pytest.approx(1.0)
    assert r["mass_msun"]["max"] == pytest.approx(20.0)
    # The metal-poor bearums tutorial grid (~[Fe/H] -0.84) is always the lowest
    # bucket. A solar grid may be dropped in alongside it (multi-Z by snapping),
    # so we do NOT assume it's the only metallicity -- only that the bearums
    # bucket is present, metal-poor, and carries all 7 of its sample masses.
    bearums_feh = r["feh"]["min"]
    assert -1.0 < bearums_feh < -0.6
    assert provider.mass_range(bearums_feh) == (1.0, 20.0)


@requires_mesa_data
def test_real_one_msun_is_metal_poor_dwarf(provider):
    feh = provider.parameter_ranges()["feh"]["min"]
    zams = provider.track(1.0, feh)[0]
    # a metal-poor 1 M_sun ZAMS star: hotter & a bit brighter than the solar Sun,
    # but still order-unity L, MS, with the grid's sub-solar Z.
    assert 1.0 < zams.L_lsun < 2.5
    assert 6000 < zams.Teff_K < 7000
    assert 0.85 < zams.R_rsun < 1.1
    assert zams.phase == "MS"
    assert zams.Z_surf < 0.005


@requires_mesa_data
def test_real_track_monotonic_and_ordered(provider):
    feh = provider.parameter_ranges()["feh"]["min"]
    for mass in (1, 2, 6, 20):
        tr = provider.track(mass, feh)
        assert len(tr) > 10
        assert all(tr[i].age_yr < tr[i + 1].age_yr for i in range(len(tr) - 1))
        assert all(tr[i].eep < tr[i + 1].eep for i in range(len(tr) - 1))
        assert tr[0].phase == "MS"               # every run starts on the MS


@requires_mesa_data
def test_real_snap_reports_true_mass(provider):
    feh = provider.parameter_ranges()["feh"]["min"]
    # 3.0 is off-grid; the nearest run is 2.0 (|3-2| < |3-4| ties to the lower).
    s = provider.state_at(3.0, feh, 1e8)
    assert s.mass_init_msun in (2.0, 4.0)        # a *real* run mass, never 3.0
    # and it never silently extrapolates: out of the bounding span raises.
    with pytest.raises(ParameterOutOfRange):
        provider.state_at(50.0, feh, 1e8)
