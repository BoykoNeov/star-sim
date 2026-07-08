"""Validation for the POSYDON CO-HeMS / CO-HeMS_RLO He-star siblings (the double-compact-
object channel) — path (b) Phase 1 Chunk 2a (docs/plans/tempered-lineage-inspiral.md).

The stage AFTER `test_posydon_co.py`'s CO-HMS_RLO episode: the surviving secondary has ALSO
been stripped to a bare He star orbiting the compact object — the direct progenitor of a
BH-BH / NS-BH / NS-NS gravitational-wave-merger binary. Mirrors `test_posydon_co.py`'s
discipline (parse+snap honesty, whole-grid bake integrity, StellarState validity, the
accretion-cue Eddington-bound regression) and adds the genuinely new pieces:
  * the surviving star is a HE star (He-rich surface, X_surf~0);
  * the DCO-classification payoff (`CoBinaryTrack.dco`) — assert its POSITIVE PRESENCE on
    the He kinds + correct labels (BH+BH / NS+NS / WD -> no DCO), not just tolerance;
  * the Eddington bound is RE-DERIVED on both He solar grids (NOT assumed to inherit
    CO-HMS_RLO's 3.46x — He Case-BB/BC transfer can differ; measured 3.47x, solar-scoped);
  * the `kind` parameter (VALID_KINDS) and the one-letter co-hms-rlo/co-hems-rlo hazard.

Data-gated `requires_posydon_co_he_data` (both He grids baked; never committed) — see
conftest.py. The pure `dco_classification` unit tests below are UNGATED (no data needed).
"""

from __future__ import annotations

import math

import numpy as np
import pytest
from fastapi.testclient import TestClient

from star_sim import posydon_co as pc
from star_sim.api import app
from star_sim.state import StellarState

from .conftest import requires_posydon_co_he_data

# --- demo/regression nodes (measured directly off the baked solar He grids 2026-07-08) -----
# CO-HeMS_RLO: a moderate He-donor X-ray binary — stable_MT onto a ~10 Msun BH, a real
# accretion episode (31 active rows, the CO grows ~0.72 Msun), the He star ends WD (no DCO).
_RLO_M_STAR, _RLO_M_CO, _RLO_P = 1.422924, 10.248538, 0.045189
# CO-HeMS: a clean, comparable-mass BH+BH DCO progenitor (the GW-source payoff).
_DCO_M_STAR, _DCO_M_CO, _DCO_P = 16.559711, 5.990075, 0.561443
# CO-HeMS: a NS+NS DCO, and a WD-remnant "no DCO" node (POSYDON predicts S1 -> a white dwarf).
_NSNS_M_STAR, _NSNS_M_CO, _NSNS_P = 5.794660, 1.710920, 0.904071
_NODCO_M_STAR, _NODCO_M_CO, _NODCO_P = 0.500000, 2.046317, 0.348666

_HE_KINDS = ("co-hems", "co-hems-rlo")
# a representative in-grid node per kind, for the shared snap-honesty checks
_KIND_DEMO = {
    "co-hems": (_DCO_M_STAR, _DCO_M_CO, _DCO_P),
    "co-hems-rlo": (_RLO_M_STAR, _RLO_M_CO, _RLO_P),
}


# =============================================================================================
# Pure `dco_classification` unit tests — no data, always run (the classifier logic itself)
# =============================================================================================

def test_dco_classifier_both_ns_bh_are_merger_progenitors():
    for r1, r2, want in [("BH", "BH", "BH + BH merger progenitor"),
                          ("NS", "BH", "NS + BH merger progenitor"),
                          ("BH", "NS", "NS + BH merger progenitor"),   # order-independent
                          ("NS", "NS", "NS + NS merger progenitor")]:
        d = pc.dco_classification(r1, r2, 10.0, 12.0, "CCSN", "S1_SN_MODEL_v2_01")
        assert d.is_dco is True
        assert d.label == want


def test_dco_classifier_wd_remnant_is_no_dco():
    for r1, r2 in [("WD", "BH"), ("NS", "WD"), ("WD", "WD")]:
        d = pc.dco_classification(r1, r2, 0.8, 5.0, "WD", "S1_SN_MODEL_v2_01")
        assert d.is_dco is False
        assert "white dwarf" in d.label


def test_dco_classifier_unresolved_is_no_dco():
    for r1, r2 in [("None", "BH"), ("BH", "None"), ("None", "None"), ("junk", "BH")]:
        d = pc.dco_classification(r1, r2, float("nan"), 5.0, "None", "S1_SN_MODEL_v2_01")
        assert d.is_dco is False
        # an unknown/absent remnant type is normalized to "None" and reads as unresolved
        assert d.s1_remnant_type in ("None", "BH")


def test_dco_classifier_nan_mass_becomes_none():
    d = pc.dco_classification("BH", "BH", float("nan"), 12.0, "CCSN", "S1_SN_MODEL_v2_01")
    assert d.s1_remnant_mass_msun is None
    assert d.is_dco is True     # the TYPE still classifies; only the mass is unresolved


# =============================================================================================
# Data-gated tests
# =============================================================================================

pytestmark = requires_posydon_co_he_data


# --- parse + snap honesty (never interpolate — §6), both He kinds ----------------------------

@pytest.mark.parametrize("kind", _HE_KINDS)
def test_meta_reports_sane_grid_bounds(kind):
    meta = pc.co_binary_track_meta(0.0, kind=kind)
    assert meta["kind"] == kind
    assert meta["n_tracks"] > 1000
    assert 0.0 < meta["m_star_min"] < meta["m_star_max"]
    assert 0.0 < meta["m_co_min"] < meta["m_co_max"]
    assert 0.0 < meta["p_min"] < meta["p_max"]


@pytest.mark.parametrize("kind", _HE_KINDS)
def test_snap_returns_a_true_grid_node(kind):
    m_star, m_co, p = _KIND_DEMO[kind]
    t = pc.co_binary_track(m_star, m_co, p, 0.0, kind=kind)
    assert t.kind == kind
    assert t.m_star_init_msun == pytest.approx(m_star, abs=1e-3)
    assert t.m_co_init_msun == pytest.approx(m_co, abs=1e-3)
    assert t.p_init_d == pytest.approx(p, abs=1e-3)
    assert not (t.m_star_snapped_far or t.m_co_snapped_far or t.p_snapped_far)

    # a small perturbation snaps to the SAME node, not an interpolation
    t2 = pc.co_binary_track(m_star * 1.001, m_co * 0.999, p * 1.001, 0.0, kind=kind)
    assert (t2.m_star_init_msun, t2.m_co_init_msun, t2.p_init_d) == (
        t.m_star_init_msun, t.m_co_init_msun, t.p_init_d)


@pytest.mark.parametrize("kind", _HE_KINDS)
def test_exact_node_round_trips_across_a_sample(kind):
    rng = np.random.default_rng(0)
    for grid in pc._available_grids(kind):
        n = grid.m_star_init.size
        sample = rng.choice(n, size=min(300, n), replace=False)
        for i in sample:
            idx = pc._snap_track_index(grid, float(grid.m_star_init[i]),
                                        float(grid.m_co_init[i]), float(grid.p_init_d[i]))
            assert idx == i, f"kind={kind} node {i} did not round-trip"


@pytest.mark.parametrize("kind", _HE_KINDS)
def test_no_duplicate_grid_nodes(kind):
    for grid in pc._available_grids(kind):
        keys = list(zip(grid.m_star_init.round(6), grid.m_co_init.round(6),
                         grid.p_init_d.round(6)))
        assert len(set(keys)) == len(keys), f"duplicate node in kind={kind} feh={grid.feh}"


@pytest.mark.parametrize("kind", _HE_KINDS)
def test_no_nonfinite_values_in_baked_rows(kind):
    for grid in pc._available_grids(kind):
        for col, arr in grid.rows.items():
            assert np.isfinite(arr).all(), f"non-finite in kind={kind} feh={grid.feh} col {col!r}"


@pytest.mark.parametrize("kind", _HE_KINDS)
def test_snap_far_flags_out_of_range(kind):
    meta = pc.co_binary_track_meta(0.0, kind=kind)
    t = pc.co_binary_track(meta["m_star_max"] * 5.0, meta["m_co_min"] / 5.0,
                            meta["p_min"] / 10.0, 0.0, kind=kind)
    assert t.m_star_snapped_far is True
    assert t.p_snapped_far is True


# --- the surviving star is a real HE star ---------------------------------------------------

@pytest.mark.parametrize("kind", _HE_KINDS)
def test_every_step_has_a_valid_state_and_sane_co_scalars(kind):
    m_star, m_co, p = _KIND_DEMO[kind]
    t = pc.co_binary_track(m_star, m_co, p, 0.0, kind=kind)
    assert len(t.steps) > 10
    for s in t.steps:
        assert isinstance(s.star, StellarState)
        assert s.star.L_lsun > 0.0 and s.star.R_rsun > 0.0 and s.star.Teff_K > 0.0
        assert s.star.X_surf + s.star.Y_surf + s.star.Z_surf == pytest.approx(1.0, abs=1e-6)
        assert s.ecc == 0.0
        assert s.co_mass_msun > 0.0 and s.star_current_msun > 0.0
        assert s.co_type in ("NS", "BH", "WD", "None")
        assert s.mt_state in ("detached", "RLOF1")


@pytest.mark.parametrize("kind", _HE_KINDS)
def test_surviving_star_is_hydrogen_stripped(kind):
    """The whole point of these grids vs CO-HMS_RLO: the secondary is a bare stripped star,
    not a H-rich one. The defining, robust trait is HYDROGEN DEPLETION — its surface is
    H-poor. (He-DOMINANCE is NOT robust: a less-evolved He star is He-rich (measured demo
    Y_surf~0.986), but an evolved massive one is a WC/WO-like surface where the He has burned
    to C/O (measured demo Y_surf~0.34, C/O-dominated) — both are stripped, only X_surf is a
    reliable discriminator.) Assert H-depletion, and that the rest of the budget is the
    He + burning-product (C/O) surface, not hydrogen."""
    m_star, m_co, p = _KIND_DEMO[kind]
    t = pc.co_binary_track(m_star, m_co, p, 0.0, kind=kind)
    mid = t.steps[len(t.steps) // 2].star
    assert mid.X_surf < 0.3, f"kind={kind}: surface not H-depleted (X_surf={mid.X_surf})"
    assert (mid.Y_surf + mid.Z_surf) > 0.7, f"kind={kind}: non-H budget too small"


# --- the He-donor accretion payoff (CO-HeMS_RLO) --------------------------------------------

def test_rlo_accretion_cue_fires_and_co_grows():
    """CO-HeMS_RLO's payoff: a He (Case BB/BC) donor overflows onto the compact object — the
    accretion cue fires (finite, positive, only during transfer) and the CO measurably gains
    mass, the same distinguishable X-ray-binary phase as CO-HMS_RLO but with a He donor."""
    t = pc.co_binary_track(_RLO_M_STAR, _RLO_M_CO, _RLO_P, 0.0, kind="co-hems-rlo")
    n_active = 0
    for s in t.steps:
        if s.mt_state == "detached":
            assert s.mdot_msun_yr is None and s.accretion_lum_lsun is None
        elif s.mdot_msun_yr is not None:
            n_active += 1
            assert s.mdot_msun_yr > 0.0
            assert s.accretion_lum_lsun is not None and np.isfinite(s.accretion_lum_lsun)
            assert s.accretion_lum_lsun > 0.0
    assert n_active > 15, "expected a real He-donor accretion episode"
    assert t.steps[-1].co_mass_msun > t.steps[0].co_mass_msun, "CO should accrete mass"


# CO-HeMS is no_MT (detached-inspiral)-dominated — the accretion cue is HONESTLY None on most
# tracks. A truly detached (no RLOF ever) NS-companion node — the cue must stay None throughout.
_DETACHED_M_STAR, _DETACHED_M_CO, _DETACHED_P = 16.559711, 2.447463, 105.966338


def test_detached_no_mt_node_has_no_accretion_cue():
    """Locks the "don't fix the honest None": a detached CO-HeMS inspiral (no Roche-lobe
    overflow) surfaces NO accretion cue — every step is detached with mdot/lum None. This is
    correct behavior (the detached-inspiral phase has no accretion), not a gap to paper over."""
    t = pc.co_binary_track(_DETACHED_M_STAR, _DETACHED_M_CO, _DETACHED_P, 0.0, kind="co-hems")
    assert t.outcome != "unresolved companion"
    assert all(s.mt_state == "detached" for s in t.steps)
    assert all(s.mdot_msun_yr is None and s.accretion_lum_lsun is None for s in t.steps)


@pytest.mark.parametrize("kind", _HE_KINDS)
def test_unresolved_companion_tracks_do_not_crash(kind):
    """`co_type == "None"` means POSYDON's own classifier didn't resolve the companion's fate
    (not a merger — unlike HMS-HMS's "None") — the track still yields valid states + an honest
    outcome, and no DCO is claimed (an unresolved S2 can't pair into a merger)."""
    for grid in pc._available_grids(kind):
        unresolved = np.where(grid.co_type == "None")[0]
        assert unresolved.size > 0, f"kind={kind} feh={grid.feh}: no unresolved-companion tracks"
        for i in unresolved[:15]:
            t = pc.co_binary_track(float(grid.m_star_init[i]), float(grid.m_co_init[i]),
                                    float(grid.p_init_d[i]), grid.feh, kind=kind)
            assert t.outcome == "unresolved companion"
            assert len(t.steps) >= 1
            for s in t.steps:
                assert isinstance(s.star, StellarState)
            # the DCO endpoint (if built) is honestly not a merger when S2 is unresolved
            if t.dco is not None:
                assert t.dco.is_dco is False


# --- the DCO-classification payoff (assert POSITIVE presence, not tolerance) ----------------

def test_dco_is_present_and_classifies_bh_bh():
    """The Chunk-2a DCO regression (advisor trap #1: positive presence). A known comparable-
    mass BH+BH node classifies correctly through the real runtime — `dco is not None` (the
    optional SN-scalar load did NOT silently degrade), is_dco True, the right label + types."""
    t = pc.co_binary_track(_DCO_M_STAR, _DCO_M_CO, _DCO_P, 0.0, kind="co-hems")
    assert t.dco is not None, "DCO classification must be present on a He kind (not degraded)"
    assert t.dco.is_dco is True
    assert t.dco.label == "BH + BH merger progenitor"
    assert t.dco.s1_remnant_type == "BH" and t.dco.s2_co_type == "BH"
    assert t.dco.s1_remnant_mass_msun is not None and t.dco.s1_remnant_mass_msun > 0.0
    assert t.dco.s2_mass_msun > 0.0
    assert t.dco.sn_model == "S1_SN_MODEL_v2_01"


def test_dco_classifies_ns_ns():
    t = pc.co_binary_track(_NSNS_M_STAR, _NSNS_M_CO, _NSNS_P, 0.0, kind="co-hems")
    assert t.dco is not None and t.dco.is_dco is True
    assert t.dco.label == "NS + NS merger progenitor"
    assert t.dco.s1_remnant_type == "NS" and t.dco.s2_co_type == "NS"


def test_dco_honest_no_merger_on_wd_remnant():
    """Not every CO-HeMS system makes a merger — when POSYDON predicts the He star collapses
    to a white dwarf, `dco` is present but is_dco=False with an honest label (the plan's
    explicit honesty requirement)."""
    t = pc.co_binary_track(_NODCO_M_STAR, _NODCO_M_CO, _NODCO_P, 0.0, kind="co-hems")
    assert t.dco is not None
    assert t.dco.is_dco is False
    assert "white dwarf" in t.dco.label
    assert t.dco.s1_remnant_type == "WD"


def test_dco_s2_mass_is_post_accretion_final_row():
    """The S2 mass in the DCO pairing is the CO's FINAL-row (post-accretion) mass, not
    m_co_init (advisor #4) — on an accreting track the two differ."""
    t = pc.co_binary_track(_RLO_M_STAR, _RLO_M_CO, _RLO_P, 0.0, kind="co-hems-rlo")
    assert t.dco is not None
    assert t.dco.s2_mass_msun == pytest.approx(t.steps[-1].co_mass_msun, abs=1e-6)
    assert t.dco.s2_mass_msun > t.m_co_init_msun    # this node accretes


# --- Eddington bound RE-DERIVED across the He grids (do NOT assume 3.46x carries over) ------

def test_accretion_cue_within_a_few_eddington_across_he_grids():
    """RE-DERIVED for the He grids (the task's explicit requirement — He Case-BB/BC transfer
    could differ from an H donor). Measured 2026-07-08 across BOTH He SOLAR grids under the
    same three-part `active` gate (not detached AND not unstable_MT AND not WD): max 3.47x the
    CO's own Eddington luminosity — the same physical ULX ceiling as CO-HMS_RLO (POSYDON caps
    stable transfer). SOLAR-SCOPED: the metal-poor He buckets must be re-derived at Chunk 2c
    (CO-HMS_RLO's solar was clean but its metal-poor grids hit 505,221x — do not assume solar
    generalizes). Mirrors the three-part gate over raw float64-cast columns."""
    lsun_erg_s = 3.828e33
    edd_const = 1.26e38
    for kind in _HE_KINDS:
        for grid in pc._available_grids(kind):
            rl1 = grid.rows["rl_relative_overflow_1"]
            lg2 = grid.rows["lg_mstar_dot_2"]
            m_co = grid.rows["star_2_mass"]
            excluded = np.zeros(rl1.size, dtype=bool)
            for i in range(grid.m_star_init.size):
                if str(grid.interpolation_class[i]) == "unstable_MT" or str(grid.co_type[i]) == "WD":
                    s = int(grid.row_start[i])
                    excluded[s:s + int(grid.row_count[i])] = True
            active = np.where((rl1 > 0) & (lg2 > -30) & (lg2 < 10) & ~excluded)[0]
            assert active.size > 100, f"kind={kind} feh={grid.feh}: too few active rows"
            max_ratio = 0.0
            for r in active:
                lum = pc._accretion_luminosity(10.0 ** float(lg2[r]))
                max_ratio = max(max_ratio, lum / (edd_const * float(m_co[r]) / lsun_erg_s))
            assert max_ratio < 5.0, (
                f"kind={kind} feh={grid.feh}: cue reached {max_ratio:.1f}x Eddington — "
                f"re-examine ACCRETION_EFFICIENCY / whether a cap is now needed"
            )


def test_served_accretion_cue_is_bounded_and_only_in_regime():
    """Assert the bound on the SERVED cue (co_binary_track's own accretion_lum_lsun), not a
    reimplementation of the gate — so a string-compare / branch bug in the production gate
    fails loudly (the Chunk-1c-follow-up divergence lesson). Samples the cue-bearing (stable
    NS/BH) population on CO-HeMS_RLO (the RLOF grid — CO-HeMS is detached-dominated)."""
    lsun_erg_s = 3.828e33
    edd_const = 1.26e38
    rng = np.random.default_rng(1)
    total_cues = 0
    for grid in pc._available_grids("co-hems-rlo"):
        cueable = [i for i in range(grid.m_star_init.size)
                   if str(grid.co_type[i]) in ("NS", "BH")
                   and str(grid.interpolation_class[i]) != "unstable_MT"]
        assert cueable, f"feh={grid.feh}: no cue-bearing tracks"
        sample = rng.choice(cueable, size=min(60, len(cueable)), replace=False)
        for i in sample:
            t = pc.co_binary_track(float(grid.m_star_init[i]), float(grid.m_co_init[i]),
                                    float(grid.p_init_d[i]), feh=grid.feh, kind="co-hems-rlo")
            assert t.co_type in ("NS", "BH")
            for s in t.steps:
                if s.accretion_lum_lsun is None:
                    continue
                total_cues += 1
                ratio = s.accretion_lum_lsun / (edd_const * s.co_mass_msun / lsun_erg_s)
                assert ratio < 5.0, f"feh={grid.feh}: served cue {ratio:.1f}x Eddington"
    assert total_cues > 50, "too few served cues to be a meaningful bound check"


def test_accretion_cue_none_on_wd_and_unstable_mt_tracks():
    """The three-part gate holds at the SERVED level on the He grids too: no cue on a WD
    companion (eta=0.1 is the wrong regime) or an unstable_MT (CE/merger) track."""
    for kind in _HE_KINDS:
        checked_wd = checked_unstable = 0
        for grid in pc._available_grids(kind):
            for i in np.where(grid.co_type == "WD")[0][:10]:
                t = pc.co_binary_track(float(grid.m_star_init[i]), float(grid.m_co_init[i]),
                                        float(grid.p_init_d[i]), grid.feh, kind=kind)
                assert all(s.accretion_lum_lsun is None for s in t.steps)
                checked_wd += 1
            unstable = [i for i in range(grid.m_star_init.size)
                        if str(grid.interpolation_class[i]) == "unstable_MT"]
            for i in unstable[:5]:
                t = pc.co_binary_track(float(grid.m_star_init[i]), float(grid.m_co_init[i]),
                                        float(grid.p_init_d[i]), grid.feh, kind=kind)
                assert all(s.accretion_lum_lsun is None for s in t.steps)
                checked_unstable += 1
        assert checked_wd > 0 or checked_unstable > 0, f"kind={kind}: nothing exercised the gate"


# --- the `kind` axis + the one-letter co-hms-rlo/co-hems-rlo hazard -------------------------

def test_unknown_kind_raises_value_error():
    with pytest.raises(ValueError):
        pc.co_binary_track(10.0, 10.0, 5.0, kind="co-hms-hems")
    with pytest.raises(ValueError):
        pc.co_binary_track_meta(0.0, kind="nonsense")


def test_co_hems_rlo_and_co_hms_rlo_are_distinct_grids():
    """The one-letter hazard (advisor #5): a co-hems-rlo request must resolve to the He grid,
    never the H-rich co-hms-rlo grid. The same (M_star, M_co, P) snaps to genuinely different
    real nodes across the two kinds, and each returned node is a true member of its OWN grid."""
    req = (_DCO_M_STAR, _DCO_M_CO, _DCO_P)
    he = pc.co_binary_track(*req, 0.0, kind="co-hems-rlo")
    he_nodes = {(round(float(m), 4), round(float(c), 4), round(float(pp), 4))
                for g in pc._available_grids("co-hems-rlo")
                for m, c, pp in zip(g.m_star_init, g.m_co_init, g.p_init_d)}
    assert (round(he.m_star_init_msun, 4), round(he.m_co_init_msun, 4),
            round(he.p_init_d, 4)) in he_nodes
    assert he.dco is not None      # a He kind surfaces DCO; the H-rich co-hms-rlo would not


# --- /co_binary_track + /co_binary_track_meta route smoke (with kind) -----------------------

def test_meta_route_with_kind():
    c = TestClient(app)
    r = c.get("/co_binary_track_meta", params={"feh": 0.0, "kind": "co-hems"})
    assert r.status_code == 200
    d = r.json()
    assert d["kind"] == "co-hems"
    assert d["n_tracks"] > 1000


def test_track_route_with_kind_carries_dco():
    c = TestClient(app)
    r = c.get("/co_binary_track", params={
        "m_star": _DCO_M_STAR, "m_co": _DCO_M_CO, "p": _DCO_P, "feh": 0.0, "kind": "co-hems",
    })
    assert r.status_code == 200
    d = r.json()
    assert d["kind"] == "co-hems"
    assert len(d["steps"]) > 10
    assert d["dco"] is not None
    assert set(d["dco"]) >= {"is_dco", "label", "s1_remnant_type", "s2_co_type",
                              "s1_remnant_mass_msun", "s2_mass_msun", "sn_type", "sn_model"}
    assert d["dco"]["is_dco"] is True
    assert d["dco"]["label"] == "BH + BH merger progenitor"
    # each step still carries its Roche geometry (the CO-HMS_RLO Chunk-1b machinery reused)
    assert all(s["roche"] is not None for s in d["steps"])


def test_track_route_422_on_unknown_kind():
    c = TestClient(app)
    r = c.get("/co_binary_track", params={
        "m_star": _DCO_M_STAR, "m_co": _DCO_M_CO, "p": _DCO_P, "kind": "co-hms-hems"})
    assert r.status_code == 422


def test_track_route_422_on_invalid_input():
    c = TestClient(app)
    for bad in ({"m_star": -1.0, "m_co": 10.0, "p": 5.0},
                {"m_star": 10.0, "m_co": 0.0, "p": 5.0},
                {"m_star": 10.0, "m_co": 10.0, "p": 0.0}):
        assert c.get("/co_binary_track",
                      params={**bad, "kind": "co-hems"}).status_code == 422


def test_track_route_snaps_far_in_band_not_422():
    c = TestClient(app)
    meta = pc.co_binary_track_meta(0.0, kind="co-hems")
    r = c.get("/co_binary_track", params={
        "m_star": meta["m_star_max"] * 5.0, "m_co": meta["m_co_min"] / 5.0,
        "p": meta["p_min"] / 10.0, "feh": 0.0, "kind": "co-hems",
    })
    assert r.status_code == 200
    assert r.json()["m_star_snapped_far"] is True
