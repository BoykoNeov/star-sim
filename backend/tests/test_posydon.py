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

import numpy as np
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


# --- bake integrity (advisor-flagged; cheap to check across the WHOLE grid) ----

def test_no_duplicate_grid_nodes():
    """Several rerun campaigns feed this grid (`rerun_reverse_MT_grid...`,
    `rerun_LBV_wind...`) — if two runs shared (M1,q,P), `argmin` would silently pick
    whichever sits first in array order rather than a deliberate choice. Measured: none
    do on the solar grid, but this pins it as a regression rather than an assumption."""
    grid = pd._available_grids()[0]
    keys = list(zip(grid.m1_init.round(6), grid.q_init.round(6), grid.p_init_d.round(6)))
    assert len(set(keys)) == len(keys)


def test_no_nonfinite_values_in_baked_rows():
    """A row with finite mass but a non-finite log_L/log_Teff/log_R (plausible at a
    CE/disruption row) would slip past the bake's mass-only truncation guard and surface
    as NaN in the JSON payload. Measured: none on the solar grid — this pins it."""
    grid = pd._available_grids()[0]
    for col, arr in grid.rows.items():
        assert np.isfinite(arr).all(), f"non-finite values in row column {col!r}"


def test_exact_node_round_trips_across_a_sample():
    """A much stronger snap check than perturbing one demo node: every one of a large
    random sample of REAL grid nodes must snap back to itself exactly (distance 0) — if
    the log-M1/log-P/linear-q metric were imbalanced, or two nodes were near-duplicates,
    some would snap to a neighbor instead."""
    grid = pd._available_grids()[0]
    rng = np.random.default_rng(0)
    n = grid.m1_init.size
    sample = rng.choice(n, size=min(300, n), replace=False)
    for i in sample:
        idx = pd._snap_track_index(grid, float(grid.m1_init[i]), float(grid.q_init[i]),
                                    float(grid.p_init_d[i]))
        assert idx == i


def test_decimation_preserves_the_rlof_episode():
    """`_decimate` force-keeps RLOF/contact rows on top of its uniform stride — a track
    long enough to be capped could otherwise straddle a short RLOF episode entirely,
    leaving `outcome="stripped + companion"` with no surviving row where the transfer
    actually shows. Scoped to tracks that (a) actually ended up stripped and (b) hit the
    decimation cap (>=300 rows) — the population where straddling could happen at all.

    NOT asserted at 0: one measured case (M1=5.34, q=0.95, P=5179 d — a WIDE, ~14-year
    orbit) is genuinely stripped via slow WIND mass loss with no row EVER crossing
    rl_relative_overflow>0 in the raw (pre-decimation) data — `_decimate`'s must_keep
    has nothing to force-keep there, so it isn't a decimation bug. The bound (<=2) pins
    the count so a REAL regression (the fix silently breaking) still trips this."""
    grid = pd._available_grids()[0]
    rl1 = grid.rows["rl_relative_overflow_1"]
    rl2 = grid.rows["rl_relative_overflow_2"]
    stripped = np.array([
        "stripped_He" in s1 or "stripped_He" in s2 or "accreted" in s2
        for s1, s2 in zip(grid.s1_state, grid.s2_state)
    ])
    capped = grid.row_count >= 300
    target = np.where(stripped & capped)[0]
    assert len(target) > 50          # a real, non-trivial population to check
    lost = 0
    for i in target:
        start, cnt = int(grid.row_start[i]), int(grid.row_count[i])
        seg1, seg2 = rl1[start:start + cnt], rl2[start:start + cnt]
        if not (np.any(seg1 > 0) or np.any(seg2 > 0)):
            lost += 1
    assert lost <= 2, f"{lost}/{len(target)} stripped+capped tracks lost their RLOF episode"


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


def test_gate0_roche_lobes_reshape_through_the_episode():
    """Path (b) Chunk 4b's payoff: the per-step Roche geometry (`binary.track_roche_geometry`)
    over the REAL Gate-0 track — the lobes visibly tighten/reshape as q(t)/a(t) evolve, and
    the donor's lobe (bigger pre-reversal) ends up SMALLER than the companion's (post-
    reversal), through the real runtime — not a synthetic step like test_binary.py's."""
    from star_sim.binary import track_roche_geometry
    t = pd.binary_track(_DEMO_M1, _DEMO_Q, _DEMO_P, 0.0)
    geo = track_roche_geometry(t.steps)
    assert all(g is not None for g in geo)   # no degenerate step on this real track

    def extent(lobe):
        return max(p[0] for p in lobe) - min(p[0] for p in lobe)

    d0, c0 = extent(geo[0]["donor_lobe"]), extent(geo[0]["companion_lobe"])
    d1, c1 = extent(geo[-1]["donor_lobe"]), extent(geo[-1]["companion_lobe"])
    assert d0 > c0            # starts: donor (heavier) has the bigger lobe
    assert c1 > d1            # ends: companion (now heavier) has the bigger lobe
    # the physical scale genuinely changes (not just a q-only reshape at fixed size)
    assert geo[-1]["separation_rsun"] > geo[0]["separation_rsun"]


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
    # path (b) Chunk 4b: every step also carries its own Roche-lobe geometry (None only on
    # a degenerate step, not observed on this real track — the Gate-0 test covers the shape)
    assert all(s["roche"] is not None for s in d["steps"])
    assert set(step0["roche"]) >= {"q", "m_donor_msun", "m_companion_msun", "separation_rsun",
                                    "l1_x", "l2_x", "l3_x", "donor_lobe", "companion_lobe", "stream"}


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
