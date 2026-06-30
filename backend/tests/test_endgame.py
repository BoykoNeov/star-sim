"""§10 sanity checks for the stellar-endgame accessor (Chunk 1 of the WR/WD
gateway — docs/plans/smoldering-cinder-gateway.md).

The endgame exposes the rows *past* the normal `track()` window — a white dwarf's
cooling track or a Wolf-Rayet's wind sub-track — by **snapping to the nearest real
grid track** (no cross-mass/[Fe/H] interpolation: the thermal pulses can't be
coherently blended across mass, but one snapped star's pulses scrub fine — §6).

Tolerances/landmarks are *measured* off MIST v2.5 (re-verify if the grids change):
  * 1 M_sun solar -> WD: phase 5 (601 TPAGB) + phase 6 (312 post-AGB), final
    log g 7.95, Teff cools to 2393 K through a ~107 kK central-star (CSPN) peak,
    final star_mass 0.544 M_sun. age 11.7 -> 27.6 Gyr, strictly increasing.
  * solar WD<->SN boundary sits between 6.5 (WD, log g 8.70) and 7.0 (SN); 7-40
    M_sun end at TPAGB onset (one phase-5 row) -> SN dead end.
  * 60 M_sun solar -> WR: phase 9, Teff to ~249 kK, star_mass 60 -> 23.6 (stripped).
  * WR onset mass (lowest grid mass reaching phase 9), by [Fe/H]: +0.5 -> 35,
    0.0 -> 48, -0.5 -> 56 (more metals -> stronger winds -> strips at lower mass;
    slightly non-monotonic at low Z, hence derived-not-hardcoded).

Skipped when the grids aren't fetched (conftest.requires_mist_data).
"""

from __future__ import annotations

import numpy as np
import pytest

from fastapi.testclient import TestClient

from star_sim.api import app
from star_sim.provider import ParameterOutOfRange
from star_sim.providers import MISTProvider
from star_sim.state import StellarState

from .conftest import requires_mist_data, requires_mist_heldout_feh, requires_mist_lowz
from .test_stub_provider import EXPECTED_KEYS

pytestmark = requires_mist_data


@pytest.fixture(scope="module")
def provider() -> MISTProvider:
    return MISTProvider()


def _solar_grid_masses(provider: MISTProvider) -> np.ndarray:
    provider._ensure_loaded()
    grid = next(g for g in provider._grids if abs(g.feh) < 1e-6)
    return grid.masses


# --- classification across mass (WD below the boundary, SN in the gap, WR above) --
def test_classifier_wd_sn_wr_across_mass(provider):
    """The gateway's three live branches, classified from the snapped track's phases
    (never a hardcoded mass cut). At solar: low/intermediate mass -> WD, the
    7-40 M_sun gap -> SN (core-collapse / uncertain fate, not rendered), the massive
    end (above the WR onset ~48 M_sun) -> WR."""
    assert provider.endgame(1.0, 0.0).type == "WD"
    assert provider.endgame(3.0, 0.0).type == "WD"
    assert provider.endgame(6.0, 0.0).type == "WD"     # just below the WD/SN boundary
    for m in (10.0, 20.0, 40.0):
        assert provider.endgame(m, 0.0).type == "SN"   # the dead-end gap (no cooling, no WR)
    assert provider.endgame(50.0, 0.0).type == "WR"
    assert provider.endgame(60.0, 0.0).type == "WR"


def test_low_mass_has_no_endgame(provider):
    """A low-mass star is still alive at the grid's end (the universe isn't old
    enough): no exposed endgame, type='none', no states."""
    res = provider.endgame(0.1, 0.0)
    assert res.type == "none"
    assert res.states == []


@requires_mist_lowz
def test_low_mass_he_burner_is_not_misclassified_sn(provider):
    """The SN classifier must not call a low-mass blue-HB star a supernova.

    SN is "evolved past core-helium ignition (CHeB) AND retains more than a white
    dwarf's worth of mass". The phase guard alone isn't enough: a ~0.55 M_sun star
    at [Fe/H]=-1 ignites core helium (reaches CHeB) but its track truncates there
    holding only ~0.5 M_sun — a future white dwarf, not a core-collapse. The final
    mass falls well below the Chandrasekhar floor, so it stays 'none' (no remnant we
    expose), not 'SN'. (Mass 0.55 snaps to that exact HB track; 0.6 already carries a
    post-AGB row and is a normal WD.)"""
    res = provider.endgame(0.55, -1.0)
    assert res.type == "none"
    assert res.states == []


# --- white-dwarf endgame: phase coverage, cooling physics, masses ----------------
def test_wd_endgame_phase_coverage_and_states(provider):
    """The WD endgame carries the full scrubbable sequence as StellarStates: the
    thermal pulses (TPAGB) -> the central star -> cold-cinder cooling (post-AGB),
    and ends degenerate (log g > 7). The states are §3-clean StellarStates."""
    res = provider.endgame(1.0, 0.0)
    assert res.type == "WD"
    assert all(isinstance(s, StellarState) for s in res.states)
    phases = {s.phase for s in res.states}
    assert "TPAGB" in phases       # the thermal pulses (snapped to one real star — §6)
    assert "post-AGB" in phases    # the cooling track to the cinder
    assert res.states[-1].logg > 7.0   # the final state is a degenerate white dwarf
    assert res.states[-1].Teff_K < 4000.0   # ...cooled to a cold cinder (measured 2393 K)


def test_wd_cooling_track_is_monotonic_past_the_cspn_knee(provider):
    """The honest 'cooling-track monotonic' test. The endgame is NOT monotonic as a
    whole: the TPAGB thermal pulses make everything oscillate (that's *why* we snap
    instead of interpolate), and the post-AGB phase first *contracts to a ~100 kK
    central star* (Teff rises) before cooling. So:
      * over all post-AGB rows, log g increases monotonically (the degenerate
        contraction is one-way), and
      * past the central-star Teff peak (the CSPN 'knee'), the genuine cooling track
        has Teff and L falling monotonically to the cinder.
    """
    post = [s for s in provider.endgame(1.0, 0.0).states if s.phase == "post-AGB"]
    assert len(post) > 50

    # the ~100 kK central star (planetary-nebula nucleus) is in there
    teffs = [s.Teff_K for s in post]
    assert max(teffs) > 5.0e4                 # measured peak ~107 kK

    # log g rises monotonically across the whole post-AGB contraction+cooling
    loggs = [s.logg for s in post]
    assert loggs == sorted(loggs)             # non-decreasing
    assert loggs[-1] > loggs[0] + 1.0         # ...and a real net rise (to ~8)

    # past the central-star peak it is a clean cooling track: Teff and L fall
    knee = int(np.argmax(teffs))
    tail = post[knee:]
    assert len(tail) > 50
    assert [s.Teff_K for s in tail] == sorted((s.Teff_K for s in tail), reverse=True)
    assert [s.L_lsun for s in tail] == sorted((s.L_lsun for s in tail), reverse=True)


def test_wd_endgame_age_is_strictly_increasing(provider):
    """Chunk 2 scrubs the WD cooling by (log) age, inverting age->row, so the slice
    must have strictly increasing age — including across the thermal pulses (short in
    age but never folding). Measured 11.7 -> 27.6 Gyr over the 1 M_sun endgame."""
    ages = [s.age_yr for s in provider.endgame(1.0, 0.0).states]
    assert all(ages[i] < ages[i + 1] for i in range(len(ages) - 1))


def test_wd_final_mass_below_initial(provider):
    """The initial->final mass relation: a 1 M_sun star sheds its envelope and leaves
    a ~0.5 M_sun white dwarf. final_mass_msun is the current mass at the last row."""
    res = provider.endgame(1.0, 0.0)
    assert res.final_mass_msun is not None
    assert res.final_mass_msun < res.mass_init_msun
    assert res.final_mass_msun == pytest.approx(0.54, abs=0.05)   # measured 0.544


# --- Wolf-Rayet endgame ----------------------------------------------------------
def test_wr_endgame_phase_coverage_and_stripping(provider):
    """A massive star's WR sub-track: phase 9, very hot (the stripped core), and the
    current mass is far below the initial (winds have stripped the envelope)."""
    res = provider.endgame(60.0, 0.0)
    assert res.type == "WR"
    assert len(res.states) > 1
    assert all(s.phase == "WR" for s in res.states)
    assert max(s.Teff_K for s in res.states) > 1.0e5     # measured ~249 kK
    assert res.final_mass_msun < res.mass_init_msun       # stripped (60 -> ~24)
    assert res.final_mass_msun == pytest.approx(23.6, abs=2.0)


def test_sn_dead_end_has_no_states(provider):
    """The intermediate/massive gap that core-collapses: classified SN, but NOT
    rendered — the lone pre-collapse supergiant row is a low-gravity artifact, so
    states is empty (the gateway shows a 'not simulated' card instead)."""
    res = provider.endgame(20.0, 0.0)
    assert res.type == "SN"
    assert res.states == []
    assert res.wr_threshold_msun is not None   # still reports the grid's WR onset


# --- snap-to-track (never interpolate) -------------------------------------------
def test_endgame_snaps_to_true_grid_mass(provider):
    """The endgame snaps to the nearest real grid track and reports its *true* mass
    (the snap is honest, never a silent extrapolation — §6). An off-grid request
    comes back on a real grid point, not the requested value."""
    masses = _solar_grid_masses(provider)
    req = 1.03
    nearest = float(masses[int(np.argmin(np.abs(masses - req)))])
    res = provider.endgame(req, 0.0)
    assert res.mass_init_msun == nearest
    assert float(res.mass_init_msun) in set(float(m) for m in masses)


def test_endgame_eep_continues_past_the_window(provider):
    """Endgame states report their *continuing* EEP (they don't restart at ZAMS):
    every endgame row sits past the normal track's last EEP."""
    track = provider.track(1.0, 0.0)
    last_track_eep = track[-1].eep
    states = provider.endgame(1.0, 0.0).states
    assert states[0].eep > last_track_eep
    eeps = [s.eep for s in states]
    assert eeps == sorted(eeps)


# --- the WR threshold is derived from the data, and tracks metallicity -----------
@requires_mist_heldout_feh
def test_wr_threshold_tracks_metallicity(provider):
    """The WR onset mass is read off the grid (never hardcoded) and shifts with
    [Fe/H]: more metals -> stronger line-driven winds -> the envelope strips at a
    *lower* mass. Measured onset: +0.5 -> 35, 0.0 -> 48, -0.5 -> 56 M_sun. (Below
    -0.5 it is slightly non-monotonic — exactly why the gateway must derive it.)
    wr_threshold is a grid property, so it's the same for any mass at that [Fe/H]."""
    thr = {feh: provider.endgame(60.0, feh).wr_threshold_msun for feh in (0.5, 0.0, -0.5)}
    assert thr[0.5] < thr[0.0] < thr[-0.5]            # the metallicity trend
    assert 30.0 < thr[0.5] < 40.0                     # measured 35
    assert 45.0 < thr[0.0] < 52.0                     # measured 48
    assert 50.0 < thr[-0.5] < 60.0                    # measured 56


# --- guards ----------------------------------------------------------------------
def test_endgame_out_of_range_raises(provider):
    with pytest.raises(ParameterOutOfRange):
        provider.endgame(1000.0, 0.0)                 # mass past the grid
    feh_max = provider.parameter_ranges()["feh"]["max"]
    with pytest.raises(ParameterOutOfRange):
        provider.endgame(1.0, feh_max + 1.0)          # [Fe/H] past the grid


# --- the /endgame route: EndgameResult shape, states are exactly StellarState ----
def test_api_endgame_payload_shape():
    """The route serializes the EndgameResult and its states verbatim — no fields of
    its own (§3/§4). The classifier metadata is top-level; every state is exactly the
    StellarState shape the rest of the API uses."""
    client = TestClient(app)
    resp = client.get("/endgame", params={"mass": 1.0, "feh": 0.0})
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {
        "type", "mass_init_msun", "feh_init",
        "final_mass_msun", "wr_threshold_msun", "states",
    }
    assert body["type"] == "WD"
    assert isinstance(body["states"], list) and len(body["states"]) > 1
    assert all(set(row.keys()) == EXPECTED_KEYS for row in body["states"])


def test_api_endgame_out_of_range_is_422():
    client = TestClient(app)
    resp = client.get("/endgame", params={"mass": 999.0, "feh": 0.0})
    assert resp.status_code == 422


def test_api_endgame_meta_is_type_only():
    """`meta=1` serves the same routing metadata minus the heavy `states` list — the
    gateway button's fast path. It drops `states` (so the ~1 MB WD/WR track never ships
    just to render a button), adds an explicit `has_states` boolean mirroring the
    frontend's `states.length` guard, and the scalar fate fields are IDENTICAL to the
    full response (same provider call, same snap)."""
    client = TestClient(app)
    for mass, want_type, want_has in ((1.0, "WD", True), (20.0, "SN", False), (60.0, "WR", True)):
        full = client.get("/endgame", params={"mass": mass, "feh": 0.0}).json()
        meta = client.get("/endgame", params={"mass": mass, "feh": 0.0, "meta": 1}).json()
        assert meta["type"] == full["type"] == want_type
        assert meta["states"] == []                      # the bulk is dropped
        assert meta["has_states"] is want_has            # but the guard is preserved
        assert (len(full["states"]) > 0) is want_has     # ...and it matches the full result
        # the scalar routing fields are byte-for-byte the full ones (same snap)
        for k in ("mass_init_msun", "feh_init", "final_mass_msun", "wr_threshold_msun"):
            assert meta[k] == full[k]
        # the meta payload is a tiny fraction of the full one for a star with a track
        if want_has:
            assert len(str(meta)) < len(str(full)) / 100
