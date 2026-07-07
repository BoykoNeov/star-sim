"""Validation for the POSYDON co-evolved-binary sibling (`posydon.py`, `/binary_track`).

Path (b) Chunk 4a — the first TIME-SERIES, TWO-BODY sibling (docs/plans/
entwined-consort-inspiral.md). Unlike `binary.py`'s Götberg snapshot, a POSYDON track
is a real MESA-binary run: both stars' full history + the orbit through time. The
anchors here mirror `test_binary.py`'s discipline:

  * parse + snap honesty (a request lands on a TRUE grid node in (M1, q, P), never an
    interpolation — §6);
  * both stars' `StellarState`s are valid at every step;
  * **Gate 0** (the plan's measure-first discipline gate), as a regression: through the
    real runtime path, the demo system (M1=8.83, q=0.6, P=3.73 d) shows the two markers'
    mass ordering CROSS (the Algol reversal happening live), the orbital period WIDEN
    through the mass-transfer episode, and `mt_state` actually fire RLOF1 then return to
    detached — the payoff a snapshot can't give. If this ever degenerates to two
    independent single stars evolving side by side with no crossing, the feature is dead.

All tests are gated `requires_posydon_data` (baked from the ~10 GB Zenodo grid, never
committed) — see conftest.py.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from star_sim import posydon as pd
from star_sim.api import app
from star_sim.state import StellarState

from .conftest import requires_posydon_data

# The Gate-0 demo system (measured directly off the raw grid before this module was
# written — run86 of the solar HMS-HMS grid): a real detached -> RLOF -> detached
# episode that strips the initially-heavier star down to a hot He core while its
# companion becomes the more massive object.
_DEMO_M1, _DEMO_Q, _DEMO_P = 8.83, 0.6, 3.73


pytestmark = requires_posydon_data


# --- parse + snap honesty (never interpolate — §6) -----------------------------

def test_meta_reports_sane_grid_bounds():
    meta = pd.binary_track_meta(0.0)
    assert meta["feh"] == pytest.approx(0.0)
    assert meta["n_tracks"] > 1000
    assert 0.0 < meta["m1_min"] < meta["m1_max"]
    assert 0.0 < meta["q_min"] <= meta["q_max"] <= 1.0
    assert 0.0 < meta["p_min"] < meta["p_max"]


def test_snap_returns_a_true_grid_node():
    t = pd.binary_track(_DEMO_M1, _DEMO_Q, _DEMO_P, 0.0)
    # _DEMO_M1/_DEMO_P are rounded display values (measured via %.2f) of the real node —
    # close enough to snap to it, but not bit-identical, hence the loose tolerance here.
    assert t.m1_init_msun == pytest.approx(_DEMO_M1, abs=0.01)
    assert t.q_init == pytest.approx(_DEMO_Q, abs=0.01)
    assert t.p_init_d == pytest.approx(_DEMO_P, abs=0.01)
    assert not t.m1_snapped_far and not t.q_snapped_far and not t.p_snapped_far

    # a request slightly off the node snaps to the SAME node, not an interpolation
    t2 = pd.binary_track(_DEMO_M1 + 0.05, _DEMO_Q + 0.01, _DEMO_P - 0.02, 0.0)
    assert t2.m1_init_msun == t.m1_init_msun
    assert t2.q_init == t.q_init
    assert t2.p_init_d == t.p_init_d


def test_snap_far_flags_out_of_range():
    meta = pd.binary_track_meta(0.0)
    t = pd.binary_track(meta["m1_max"] * 5.0, 0.99, meta["p_min"] / 10.0, 0.0)
    assert t.m1_snapped_far is True
    assert t.p_snapped_far is True
    # a within-range request doesn't spuriously trip the flags
    t2 = pd.binary_track(_DEMO_M1, _DEMO_Q, _DEMO_P, 0.0)
    assert t2.m1_snapped_far is False and t2.p_snapped_far is False


def test_feh_snaps_to_nearest_available_bucket():
    """Only the solar bucket is baked (Chunk 4a is solar-first) — any [Fe/H] snaps to it
    and is flagged far unless it's actually close."""
    t = pd.binary_track(_DEMO_M1, _DEMO_Q, _DEMO_P, feh=-0.8)
    assert t.feh == pytest.approx(0.0, abs=1e-9)
    assert t.feh_snapped_far is True
    t0 = pd.binary_track(_DEMO_M1, _DEMO_Q, _DEMO_P, feh=0.0)
    assert t0.feh_snapped_far is False


# --- StellarState validity at every step ----------------------------------------

def test_every_step_has_two_valid_states():
    t = pd.binary_track(_DEMO_M1, _DEMO_Q, _DEMO_P, 0.0)
    assert len(t.steps) > 100          # the demo system is a long (~271-row) track
    for s in t.steps:
        for star in (s.star_1, s.star_2):
            assert star is not None
            assert isinstance(star, StellarState)
            assert star.L_lsun > 0.0 and star.R_rsun > 0.0 and star.Teff_K > 0.0
            closure = star.X_surf + star.Y_surf + star.Z_surf
            assert closure == pytest.approx(1.0, abs=1e-6)
        assert s.ecc == 0.0             # documented — no eccentricity column on this grid
        assert s.m1_current_msun > 0.0 and s.m2_current_msun > 0.0
        assert s.mt_state in ("detached", "RLOF1", "RLOF2", "contact")


def test_mass_init_is_constant_down_the_track_current_mass_is_not():
    """`mass_init_msun` on each StellarState is the STAR's own initial mass (constant);
    the changing (transferred) mass rides as the BinaryStep routing scalar."""
    t = pd.binary_track(_DEMO_M1, _DEMO_Q, _DEMO_P, 0.0)
    m1_inits = {s.star_1.mass_init_msun for s in t.steps}
    m2_inits = {s.star_2.mass_init_msun for s in t.steps}
    assert len(m1_inits) == 1 and next(iter(m1_inits)) == pytest.approx(_DEMO_M1, abs=0.01)
    assert len(m2_inits) == 1 and next(iter(m2_inits)) == pytest.approx(_DEMO_Q * _DEMO_M1, abs=0.01)
    # but the CURRENT mass (the routing scalar) actually changes — that's the whole story
    current_m1 = {s.m1_current_msun for s in t.steps}
    assert len(current_m1) > 50


# --- Gate 0 (the plan's measure-first discipline gate), as a regression --------

def test_gate0_mass_ordering_crosses():
    """The donor starts heavier and ends lighter than the companion — the Algol reversal
    happening AS THE TRACK PLAYS, not just true at the endpoints."""
    t = pd.binary_track(_DEMO_M1, _DEMO_Q, _DEMO_P, 0.0)
    first, last = t.steps[0], t.steps[-1]
    assert first.m1_current_msun > first.m2_current_msun     # starts: donor heavier
    assert last.m1_current_msun < last.m2_current_msun       # ends: donor lighter (stripped)
    crossings = sum(
        1 for a, b in zip(t.steps, t.steps[1:])
        if (a.m1_current_msun - a.m2_current_msun) * (b.m1_current_msun - b.m2_current_msun) < 0
    )
    assert crossings >= 1


def test_gate0_orbit_widens_through_mass_transfer():
    """The orbital period measurably widens across the RLOF episode — the Roche lobes
    visibly reshaping, not a static number."""
    t = pd.binary_track(_DEMO_M1, _DEMO_Q, _DEMO_P, 0.0)
    assert t.steps[-1].period_d > t.steps[0].period_d * 1.5
    assert t.steps[-1].separation_rsun > t.steps[0].separation_rsun * 1.1


def test_gate0_rlof_actually_fires_then_detaches():
    """A real detached -> RLOF -> detached sequence exists in the slice, so a live Roche
    panel's stream would actually turn on and off (not permanently one state)."""
    t = pd.binary_track(_DEMO_M1, _DEMO_Q, _DEMO_P, 0.0)
    states = [s.mt_state for s in t.steps]
    assert states[0] == "detached"
    assert "RLOF1" in states
    assert states[-1] == "detached"


def test_gate0_outcome_is_stripped_plus_companion():
    t = pd.binary_track(_DEMO_M1, _DEMO_Q, _DEMO_P, 0.0)
    assert t.outcome == "stripped + companion"
    # and the physical payoff: the donor ends a hot, compact, He-rich object
    last1 = t.steps[-1].star_1
    assert last1.Teff_K > 50_000.0
    assert last1.Y_surf > 0.5


# --- merger tracks degrade gracefully (no crash on a short/odd track) ----------

def test_merger_outcome_tracks_do_not_crash():
    grid = pd._available_grids()[0]
    import numpy as np
    merger_idx = np.where(grid.s1_state == "None")[0]
    assert merger_idx.size > 0
    for i in merger_idx[:20]:
        t = pd.binary_track(float(grid.m1_init[i]), float(grid.q_init[i]),
                             float(grid.p_init_d[i]), 0.0)
        assert t.outcome == "merger"
        assert len(t.steps) >= 1
        for s in t.steps:
            assert s.star_1 is not None    # star_2 may in principle be None (a merger row
            if s.star_2 is not None:       # explicitly losing a star); not observed on this
                assert isinstance(s.star_2, StellarState)  # grid, but handled either way


# --- /binary_track + /binary_track_meta route smoke ----------------------------

def test_meta_route_payload_shape():
    c = TestClient(app)
    r = c.get("/binary_track_meta", params={"feh": 0.0})
    assert r.status_code == 200
    d = r.json()
    assert set(d) >= {"feh", "available_feh", "m1_min", "m1_max", "q_min", "q_max",
                       "p_min", "p_max", "n_tracks"}
    assert d["n_tracks"] > 1000


def test_track_route_payload_shape():
    c = TestClient(app)
    r = c.get("/binary_track", params={"m1": _DEMO_M1, "q": _DEMO_Q, "p": _DEMO_P, "feh": 0.0})
    assert r.status_code == 200
    d = r.json()
    assert set(d) >= {"steps", "m1_init_msun", "q_init", "p_init_d", "feh",
                       "m1_snapped_far", "q_snapped_far", "p_snapped_far",
                       "feh_snapped_far", "outcome"}
    assert d["m1_init_msun"] == pytest.approx(_DEMO_M1, abs=0.01)
    assert len(d["steps"]) > 100
    step0 = d["steps"][0]
    assert set(step0) >= {"age_yr", "star_1", "star_2", "period_d", "separation_rsun",
                           "ecc", "mt_state", "mdot_msun_yr", "m1_current_msun",
                           "m2_current_msun"}
    assert set(step0["star_1"]) >= {"Teff_K", "L_lsun", "R_rsun", "logg", "X_surf", "Y_surf", "Z_surf"}
    assert any(s["mt_state"] == "RLOF1" for s in d["steps"])


def test_track_route_snaps_far_in_band_not_422():
    c = TestClient(app)
    meta = pd.binary_track_meta(0.0)
    r = c.get("/binary_track", params={
        "m1": meta["m1_max"] * 5.0, "q": 0.9, "p": meta["p_min"] / 10.0, "feh": 0.0,
    })
    assert r.status_code == 200               # snap-always, not 422
    d = r.json()
    assert d["m1_snapped_far"] is True
    assert d["p_snapped_far"] is True


def test_track_route_422_on_invalid_input():
    c = TestClient(app)
    assert c.get("/binary_track", params={"m1": -1.0, "q": 0.6, "p": 3.73}).status_code == 422
    assert c.get("/binary_track", params={"m1": 8.83, "q": 0.0, "p": 3.73}).status_code == 422
    assert c.get("/binary_track", params={"m1": 8.83, "q": 1.5, "p": 3.73}).status_code == 422
    assert c.get("/binary_track", params={"m1": 8.83, "q": 0.6, "p": 0.0}).status_code == 422
