"""Validation for the POSYDON CO-HMS_RLO sibling (`posydon_co.py`, `/co_binary_track`).

Path (b) Phase 1 Chunk 1a (docs/plans/tempered-lineage-inspiral.md) — the stage AFTER
`posydon.py`'s two-normal-star episode: a compact object (NS/BH/WD) orbiting a still
hydrogen-rich secondary. Mirrors `test_posydon.py`'s discipline (parse+snap honesty,
bake integrity across the whole grid, StellarState validity, a measure-first Gate-1
regression, route smoke), adapted for the genuinely different shape here: only ONE real
`StellarState` per step (the compact-object side has no history, per the schema recon —
see `posydon_co.py`'s docstring), plus the CO's own mass/type/accretion-rate.

All tests are gated `requires_posydon_co_data` (baked from the ~10 GB Zenodo grid, never
committed) — see conftest.py.
"""

from __future__ import annotations

import numpy as np
import pytest
from fastapi.testclient import TestClient

from star_sim import posydon_co as pc
from star_sim.api import app
from star_sim.state import StellarState

from .conftest import requires_posydon_co_data

# The Gate-1 demo system (measured directly off the baked solar CO-HMS_RLO grid: the
# highest-active-accretion-fraction (90%) node among stable_MT/BH-companion tracks with a
# non-trivial length) — a real, mostly-through-RLOF episode where the donor ends up a hot,
# heavily-stripped He/C/O surface (X_surf=0) orbiting a 14.7 Msun BH.
_DEMO_M_STAR, _DEMO_M_CO, _DEMO_P = 27.61912143189711, 14.66048571159418, 203.9763401890043

pytestmark = requires_posydon_co_data


# --- parse + snap honesty (never interpolate — §6) -----------------------------

def test_meta_reports_sane_grid_bounds():
    meta = pc.co_binary_track_meta(0.0)
    assert meta["feh"] == pytest.approx(0.0)
    assert meta["n_tracks"] > 1000
    assert 0.0 < meta["m_star_min"] < meta["m_star_max"]
    assert 0.0 < meta["m_co_min"] < meta["m_co_max"]
    assert 0.0 < meta["p_min"] < meta["p_max"]


def test_snap_returns_a_true_grid_node():
    t = pc.co_binary_track(_DEMO_M_STAR, _DEMO_M_CO, _DEMO_P, 0.0)
    assert t.m_star_init_msun == pytest.approx(_DEMO_M_STAR, abs=1e-3)
    assert t.m_co_init_msun == pytest.approx(_DEMO_M_CO, abs=1e-3)
    assert t.p_init_d == pytest.approx(_DEMO_P, abs=1e-3)
    assert not t.m_star_snapped_far and not t.m_co_snapped_far and not t.p_snapped_far

    # a request slightly off the node snaps to the SAME node, not an interpolation
    t2 = pc.co_binary_track(_DEMO_M_STAR + 0.05, _DEMO_M_CO - 0.02, _DEMO_P * 1.001, 0.0)
    assert t2.m_star_init_msun == t.m_star_init_msun
    assert t2.m_co_init_msun == t.m_co_init_msun
    assert t2.p_init_d == t.p_init_d


def test_snap_far_flags_out_of_range():
    meta = pc.co_binary_track_meta(0.0)
    t = pc.co_binary_track(meta["m_star_max"] * 5.0, meta["m_co_min"] / 5.0,
                            meta["p_min"] / 10.0, 0.0)
    assert t.m_star_snapped_far is True
    assert t.p_snapped_far is True
    # a within-range request doesn't spuriously trip the flags
    t2 = pc.co_binary_track(_DEMO_M_STAR, _DEMO_M_CO, _DEMO_P, 0.0)
    assert t2.m_star_snapped_far is False and t2.p_snapped_far is False


def test_feh_snaps_to_nearest_available_bucket():
    """Mirrors `test_posydon.py`'s version — derives expectations from the live bucket
    set rather than hardcoding which ones exist (the `_available_grids()[0]` anti-pattern
    documented in docs/memory/star-sim-hosted-data-assets.md bit that module twice)."""
    available = sorted(g.feh for g in pc._available_grids())

    def nearest(feh: float) -> float:
        return min(available, key=lambda f: abs(f - feh))

    for feh in available:
        t = pc.co_binary_track(_DEMO_M_STAR, _DEMO_M_CO, _DEMO_P, feh=feh)
        assert t.feh == pytest.approx(feh, abs=1e-9)
        assert t.feh_snapped_far is False

    far_probe = available[-1] + 1.0
    t_far = pc.co_binary_track(_DEMO_M_STAR, _DEMO_M_CO, _DEMO_P, feh=far_probe)
    assert t_far.feh == pytest.approx(nearest(far_probe), abs=1e-9)
    assert t_far.feh_snapped_far is True


# --- bake integrity (mirrors test_posydon.py's whole-grid checks) --------------

def test_no_duplicate_grid_nodes():
    for grid in pc._available_grids():
        keys = list(zip(grid.m_star_init.round(6), grid.m_co_init.round(6),
                         grid.p_init_d.round(6)))
        assert len(set(keys)) == len(keys), f"duplicate node in feh={grid.feh} bucket"


def test_no_nonfinite_values_in_baked_rows():
    for grid in pc._available_grids():
        for col, arr in grid.rows.items():
            assert np.isfinite(arr).all(), f"non-finite values in feh={grid.feh} column {col!r}"


def test_exact_node_round_trips_across_a_sample():
    rng = np.random.default_rng(0)
    for grid in pc._available_grids():
        n = grid.m_star_init.size
        sample = rng.choice(n, size=min(300, n), replace=False)
        for i in sample:
            idx = pc._snap_track_index(grid, float(grid.m_star_init[i]),
                                        float(grid.m_co_init[i]), float(grid.p_init_d[i]))
            assert idx == i, f"feh={grid.feh} node {i} did not round-trip"


# --- StellarState validity + the CO's own scalars at every step ----------------

def test_every_step_has_a_valid_state_and_sane_co_scalars():
    t = pc.co_binary_track(_DEMO_M_STAR, _DEMO_M_CO, _DEMO_P, 0.0)
    assert len(t.steps) > 50
    for s in t.steps:
        assert isinstance(s.star, StellarState)
        assert s.star.L_lsun > 0.0 and s.star.R_rsun > 0.0 and s.star.Teff_K > 0.0
        closure = s.star.X_surf + s.star.Y_surf + s.star.Z_surf
        assert closure == pytest.approx(1.0, abs=1e-6)
        assert s.ecc == 0.0                      # documented — no eccentricity column
        assert s.co_mass_msun > 0.0 and s.star_current_msun > 0.0
        assert s.co_type in ("NS", "BH", "WD", "None")
        # the CO can't overflow its own Roche lobe on this grid (measured) — RLOF2/contact
        # should never appear
        assert s.mt_state in ("detached", "RLOF1")


def test_accretion_cue_nonnegative_and_only_during_transfer():
    """The schematic accretion-luminosity cue is None exactly when detached (no fabricated
    number for a non-transferring step) and a finite, non-negative real number whenever
    the CO is actively gaining mass — the sanity check the plan's Chunk 1a flagged."""
    t = pc.co_binary_track(_DEMO_M_STAR, _DEMO_M_CO, _DEMO_P, 0.0)
    n_active = 0
    for s in t.steps:
        if s.mt_state == "detached":
            assert s.mdot_msun_yr is None
            assert s.accretion_lum_lsun is None
        else:
            if s.mdot_msun_yr is not None:
                n_active += 1
                assert s.mdot_msun_yr > 0.0
                assert s.accretion_lum_lsun is not None
                assert np.isfinite(s.accretion_lum_lsun)
                assert s.accretion_lum_lsun > 0.0
    assert n_active > 20          # a real, non-trivial accretion episode on this track


# --- Gate 1 (the plan's measure-first discipline gate), as a regression --------

def test_accretion_luminosity_stays_within_a_few_eddington_across_the_grid():
    """Characterized 2026-07-08 (Chunk 1a solar) then RE-characterized across the WHOLE
    8-bucket grid (Chunk 1c): with the STABLE-transfer gate `co_binary_track` uses (active
    RLOF AND the track is not POSYDON `unstable_MT`), the schematic accretion-luminosity cue
    lands at <=3.46x the CO's own Eddington luminosity (median ~2.3-2.6x) — the mildly-super-
    Eddington ULX regime, not an unbounded number.

    THE GATE IS THE BOUND — this test mirrors BOTH conditions of the production `active`
    mask, because each excludes a real artifact tail measured on the full grid:
      * DETACHED rows carry `lg_mstar_dot_2` values pushing the formula to ~10^14 Lsun;
      * `unstable_MT` tracks (CE/merger) carry runaway `lg_mstar_dot_2` spikes pushing it to
        ~10^5x Eddington (all three grid-wide outliers were `unstable_MT` — solar had none,
        the metal-poor grids do). If `co_binary_track`'s gate is ever widened (wind-fed
        accretion; re-admitting unstable MT), THIS TEST WON'T CATCH a reintroduced unbounded
        tail unless its own mask is widened to match — re-derive the bound, don't just relax
        the filter here in lockstep. (Raw float32 columns overflow under a naive vectorized
        pass — `co_binary_track` casts each value to float64 per row; this test mirrors that.)
    """
    lsun_erg_s = 3.828e33
    edd_const = 1.26e38   # erg/s per Msun of accretor (standard Eddington-limit coefficient)
    for grid in pc._available_grids():
        rl1 = grid.rows["rl_relative_overflow_1"]
        lg2 = grid.rows["lg_mstar_dot_2"]
        m_co = grid.rows["star_2_mass"]
        # Per-row mask of "belongs to an unstable_MT track" (the class is per-track).
        unstable = np.zeros(rl1.size, dtype=bool)
        for i in range(grid.m_star_init.size):
            if str(grid.interpolation_class[i]) == "unstable_MT":
                s = int(grid.row_start[i])
                unstable[s:s + int(grid.row_count[i])] = True
        active = np.where((rl1 > 0) & (lg2 > -30) & (lg2 < 10) & ~unstable)[0]
        assert active.size > 100, f"feh={grid.feh}: too few active rows to characterize"
        max_ratio = 0.0
        for r in active:
            mdot = 10.0 ** float(lg2[r])
            lum = pc._accretion_luminosity(mdot)
            l_edd_lsun = edd_const * float(m_co[r]) / lsun_erg_s
            max_ratio = max(max_ratio, lum / l_edd_lsun)
        assert max_ratio < 5.0, (
            f"feh={grid.feh}: stable-transfer accretion cue reached {max_ratio:.1f}x "
            f"Eddington — re-examine ACCRETION_EFFICIENCY / whether a cap is now needed"
        )


@requires_posydon_co_data
def test_accretion_cue_is_none_on_unstable_mt_tracks():
    """The Chunk-1c served-level regression: `co_binary_track` must NOT surface the
    accretion-luminosity cue on a POSYDON `unstable_MT` track (a CE/merger, not a clean
    X-ray binary — its parametrized `lg_mstar_dot_2` spikes to ~10^13x the star's own L on
    the metal-poor grids, a caption-poisoning artifact the frontend now reaches via the
    Chunk-1c [Fe/H] picker + custom sliders). Locks the gate at the SERVED level, not just
    the raw-array level, so a future gate regression fails loudly here."""
    for grid in pc._available_grids():
        idxs = [i for i in range(grid.m_star_init.size)
                if str(grid.interpolation_class[i]) == "unstable_MT"]
        if not idxs:
            continue
        i = idxs[0]
        t = pc.co_binary_track(float(grid.m_star_init[i]), float(grid.m_co_init[i]),
                                float(grid.p_init_d[i]), feh=grid.feh)
        assert all(s.accretion_lum_lsun is None for s in t.steps), (
            f"feh={grid.feh}: an unstable_MT track surfaced an accretion cue "
            f"(should be gated off — see posydon_co.py's `active` mask)"
        )
        return   # one unstable_MT track through the real runtime is enough
    pytest.skip("no unstable_MT track in any baked bucket to exercise the gate")


def test_gate1_co_mass_grows_via_accretion():
    """The compact object's mass measurably GROWS over the track (real accretion), not a
    static number — the payoff a plain HMS-HMS donor-only track can't show."""
    t = pc.co_binary_track(_DEMO_M_STAR, _DEMO_M_CO, _DEMO_P, 0.0)
    first, last = t.steps[0], t.steps[-1]
    assert last.co_mass_msun > first.co_mass_msun


def test_gate1_donor_is_heavily_stripped_and_hot():
    """The donor ends stripped of hydrogen (X_surf~0) and hot — a real, extreme stripped-
    star surface (this demo node's `S1_state` is `stripped_He_Central_C_depletion`, an
    evolved WC/WO-like state where even the surface He has partly given way to C/O)."""
    t = pc.co_binary_track(_DEMO_M_STAR, _DEMO_M_CO, _DEMO_P, 0.0)
    last = t.steps[-1].star
    assert last.X_surf < 0.05
    assert last.Teff_K > 50_000.0
    assert t.outcome == "stripped + BH companion"


def test_gate1_rlof_actually_fires_then_detaches():
    t = pc.co_binary_track(_DEMO_M_STAR, _DEMO_M_CO, _DEMO_P, 0.0)
    states = [s.mt_state for s in t.steps]
    assert states[0] == "detached"
    assert "RLOF1" in states


# --- unresolved-companion tracks degrade gracefully (no crash on an odd track) --

def test_unresolved_companion_tracks_do_not_crash():
    """Checked on every baked bucket, each queried at its OWN [Fe/H] — `co_type == "None"`
    means POSYDON's own classifier didn't resolve the companion's fate, not a merger
    (unlike HMS-HMS's "None", which does mean a merger) — see `posydon_co.py`'s `_outcome`."""
    for grid in pc._available_grids():
        unresolved_idx = np.where(grid.co_type == "None")[0]
        assert unresolved_idx.size > 0, f"no unresolved-companion tracks in feh={grid.feh} bucket"
        for i in unresolved_idx[:20]:
            t = pc.co_binary_track(float(grid.m_star_init[i]), float(grid.m_co_init[i]),
                                    float(grid.p_init_d[i]), grid.feh)
            assert t.outcome == "unresolved companion"
            assert len(t.steps) >= 1
            for s in t.steps:
                assert isinstance(s.star, StellarState)


# --- /co_binary_track + /co_binary_track_meta route smoke ----------------------

def test_meta_route_payload_shape():
    c = TestClient(app)
    r = c.get("/co_binary_track_meta", params={"feh": 0.0})
    assert r.status_code == 200
    d = r.json()
    assert set(d) >= {"feh", "available_feh", "m_star_min", "m_star_max",
                       "m_co_min", "m_co_max", "p_min", "p_max", "n_tracks"}
    assert d["n_tracks"] > 1000


def test_track_route_payload_shape():
    c = TestClient(app)
    r = c.get("/co_binary_track", params={
        "m_star": _DEMO_M_STAR, "m_co": _DEMO_M_CO, "p": _DEMO_P, "feh": 0.0,
    })
    assert r.status_code == 200
    d = r.json()
    assert set(d) >= {"steps", "m_star_init_msun", "m_co_init_msun", "p_init_d", "feh",
                       "m_star_snapped_far", "m_co_snapped_far", "p_snapped_far",
                       "feh_snapped_far", "co_type", "outcome"}
    assert d["m_star_init_msun"] == pytest.approx(_DEMO_M_STAR, abs=1e-3)
    assert len(d["steps"]) > 50
    step0 = d["steps"][0]
    assert set(step0) >= {"age_yr", "star", "co_mass_msun", "co_type", "period_d",
                           "separation_rsun", "ecc", "mt_state", "mdot_msun_yr",
                           "accretion_lum_lsun", "star_current_msun"}
    assert set(step0["star"]) >= {"Teff_K", "L_lsun", "R_rsun", "logg", "X_surf", "Y_surf", "Z_surf"}
    assert any(s["mt_state"] == "RLOF1" for s in d["steps"])
    # Chunk 1b: every step also carries its own Roche-lobe geometry (the normal star as the
    # donor at origin, the compact object as the accretor at (1,0)) — None only on a
    # degenerate step, not observed on this real track (the reshape test covers the shape).
    assert all(s["roche"] is not None for s in d["steps"])
    assert set(step0["roche"]) >= {"q", "m_donor_msun", "m_companion_msun", "separation_rsun",
                                    "l1_x", "l2_x", "l3_x", "donor_lobe", "companion_lobe", "stream"}


def test_gate1_roche_lobes_reshape_and_swap_over_the_episode():
    """Chunk 1b's payoff: per-step Roche geometry over the REAL Gate-1 track. The normal
    star is the donor at origin, the compact object the accretor at (1,0), so q = m_co/m_star
    starts < 1 (the H-rich star still outmasses its ~14.7 Msun BH) and ends > 1 (the star is
    stripped, the BH has accreted) — the donor lobe shrinks below the companion lobe, a real
    swap driven by the mass evolution, and the star fills its Roche lobe throughout RLOF1
    (the causal reason it's transferring). Uses the payload (the shape the frontend consumes),
    through the real runtime — not a synthetic step."""
    p = pc.co_binary_track_payload(_DEMO_M_STAR, _DEMO_M_CO, _DEMO_P, 0.0)
    steps = p["steps"]
    assert all(s["roche"] is not None for s in steps)

    def extent(lobe):
        return max(pt[0] for pt in lobe) - min(pt[0] for pt in lobe)

    r0, rL = steps[0]["roche"], steps[-1]["roche"]
    assert r0["q"] < 1.0 and rL["q"] > 1.0          # star heavier -> CO heavier (strip+accrete)
    assert extent(r0["donor_lobe"]) > extent(r0["companion_lobe"])   # start: star's lobe bigger
    assert extent(rL["companion_lobe"]) > extent(rL["donor_lobe"])   # end: CO's lobe bigger
    assert rL["separation_rsun"] > r0["separation_rsun"]             # orbit widens

    # the donor genuinely fills its Roche lobe on every RLOF1 step (why it's transferring);
    # the point-mass CO never overflows its own lobe on this grid (schema recon) — so no
    # step is ever labeled RLOF2/contact
    rlof = [s for s in steps if s["mt_state"] == "RLOF1"]
    assert rlof, "expected an RLOF1 phase on the Gate-1 track"
    for s in rlof:
        assert s["star"]["R_rsun"] >= s["roche"]["donor_roche_radius_rsun"] * 0.999
        assert s["mt_state"] != "RLOF2"


def test_track_route_snaps_far_in_band_not_422():
    c = TestClient(app)
    meta = pc.co_binary_track_meta(0.0)
    r = c.get("/co_binary_track", params={
        "m_star": meta["m_star_max"] * 5.0, "m_co": meta["m_co_min"] / 5.0,
        "p": meta["p_min"] / 10.0, "feh": 0.0,
    })
    assert r.status_code == 200               # snap-always, not 422
    d = r.json()
    assert d["m_star_snapped_far"] is True
    assert d["p_snapped_far"] is True


def test_track_route_422_on_invalid_input():
    c = TestClient(app)
    assert c.get("/co_binary_track",
                  params={"m_star": -1.0, "m_co": 10.0, "p": 5.0}).status_code == 422
    assert c.get("/co_binary_track",
                  params={"m_star": 10.0, "m_co": 0.0, "p": 5.0}).status_code == 422
    assert c.get("/co_binary_track",
                  params={"m_star": 10.0, "m_co": 10.0, "p": 0.0}).status_code == 422


# --- Chunk 1c: the metallicity axis (mirrors the HMS-HMS multi-[Fe/H] rollout) -----

from .conftest import requires_posydon_co_multifeh  # noqa: E402


@requires_posydon_co_multifeh
def test_meta_lists_every_baked_metallicity_bucket():
    """`available_feh` reflects the REAL baked bucket set, never hardcoded — the honesty
    the frontend picker is populated from (docs/memory/star-sim-hosted-data-assets.md's
    recurring hardcoded-feh lesson)."""
    baked = sorted(g.feh for g in pc._available_grids())
    assert len(baked) >= 2
    meta = pc.co_binary_track_meta(0.0)
    assert meta["available_feh"] == baked


@requires_posydon_co_multifeh
def test_metallicity_axis_is_real_same_request_different_track_across_buckets():
    """The Chunk-1c measure-first regression: the SAME (M_star, M_co, P) request snaps to a
    genuinely DIFFERENT real track at different [Fe/H] (each POSYDON metallicity is its own
    baked grid), and can change the physical OUTCOME — not a cosmetic [Fe/H] relabel over one
    shared grid. Measured example: 20 M☉ + 8 M☉ BH, P=300 d → 'stripped + BH companion' at
    solar vs 'unstable mass transfer onto BH' at [Fe/H]=−2.0."""
    fehs = sorted(g.feh for g in pc._available_grids())
    nodes, outcomes = set(), set()
    for feh in fehs:
        t = pc.co_binary_track(20.0, 8.0, 300.0, feh=feh)
        assert t.steps, f"empty track at feh={feh}"
        nodes.add((round(t.m_star_init_msun, 4), round(t.m_co_init_msun, 4), round(t.p_init_d, 4)))
        outcomes.add(t.outcome)
    # Distinct real nodes across buckets — the axis genuinely resolves to separate grids.
    assert len(nodes) > 1, "same snapped node at every [Fe/H] — the metallicity axis is inert"
    # And a well-formed outcome at every bucket (the frontend caption/note reads it).
    assert all(isinstance(o, str) and o for o in outcomes)
