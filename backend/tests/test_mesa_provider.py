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

from star_sim.provider import ParameterOutOfRange, StellarStateProvider
from star_sim.providers import MESAProvider
from star_sim.providers.mesa import (
    _build_track,
    _dedup_by_model_number,
    _read_mesa_history,
)
from star_sim.state import StellarState

from .conftest import requires_mesa_data

FIXTURE = Path(__file__).parent / "fixtures" / "synthetic_history.data"


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


# --- physical-sanity tests on the real sample grid (gated) -------------------
@pytest.fixture(scope="module")
def provider() -> MESAProvider:
    return MESAProvider()


@requires_mesa_data
def test_real_grid_loads_with_expected_masses(provider):
    r = provider.parameter_ranges()
    assert r["mass_msun"]["min"] == pytest.approx(1.0)
    assert r["mass_msun"]["max"] == pytest.approx(20.0)
    # the tutorial grid is metal-poor (~[Fe/H] -0.84), a single metallicity
    assert -1.0 < r["feh"]["min"] < -0.6
    assert r["feh"]["min"] == r["feh"]["max"]


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
