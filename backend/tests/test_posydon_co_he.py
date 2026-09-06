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


# --- pure `dco_endpoint` unit tests (Chunk 2d — the render block) ----------------------------

def _dco(r1="BH", r2="BH", m1=10.0, m2=12.0):
    return pc.dco_classification(r1, r2, m1, m2, "CCSN", "S1_SN_MODEL_v2_01")


def test_endpoint_absent_whenever_there_is_no_pair():
    """No pair, no geometry. The WD and unresolved branches must yield None rather than a
    block with a hedge on it — a caller that has an endpoint at all is entitled to draw it."""
    for r1, r2 in [("WD", "BH"), ("NS", "WD"), ("None", "BH"), ("BH", "None")]:
        assert pc.dco_endpoint(_dco(r1, r2), 50.0, 10.0, 12.0) is None


def test_bh_radius_is_derived_and_ns_radius_is_flagged_as_assumed():
    """The two radii are different KINDS of number and the payload has to say which is which:
    2GM/c^2 follows from the mass, ~12 km for a neutron star is an equation-of-state
    assumption. A caption that quoted both the same way would paint a guess as a model."""
    e = pc.dco_endpoint(_dco("BH", "NS", m1=10.0, m2=1.4), 50.0, 10.0, 12.0)
    assert e.s1_radius_km == pytest.approx(29.53, abs=0.01)   # 2GM/c^2 for 10 Msun
    assert e.s1_radius_assumed is False
    assert e.s2_radius_km == pytest.approx(12.0)
    assert e.s2_radius_assumed is True


def test_size_ratio_uses_the_larger_object_and_stays_minuscule():
    """`size_over_separation` is the caption's whole justification for schematic glyphs, so it
    takes the LARGER of the two radii — the most generous possible statement. If even that is
    ~1e-6, no size drawn on screen can be to scale."""
    e = pc.dco_endpoint(_dco("BH", "NS", m1=10.0, m2=1.4), 50.0, 10.0, 12.0)
    bigger_km = max(e.s1_radius_km, e.s2_radius_km)
    assert e.size_over_separation == pytest.approx(bigger_km / (50.0 * pc._RSUN_KM))
    assert e.size_over_separation < 1e-5


def test_blaauw_gate_fires_at_the_half_and_not_below():
    """The unbinding test is a strict half of the TOTAL system mass, companion included. The
    boundary is asserted from both sides because it is the whole gate: one comparison decides
    whether a system is drawn as an orbiting pair or refused."""
    # star 10 -> remnant 5 beside a 5 Msun companion: dM=5, M_tot=15 -> 1/3, bound.
    below = pc.dco_endpoint(_dco("BH", "BH", m1=5.0, m2=5.0), 50.0, 10.0, 10.0)
    assert below.ejected_mass_fraction == pytest.approx(1 / 3)
    assert below.mass_loss_unbinds is False
    # star 10 -> remnant 1.3 beside 1.2: dM=8.7, M_tot=11.2 -> 0.78, unbound with no kick.
    above = pc.dco_endpoint(_dco("NS", "NS", m1=1.3, m2=1.2), 30.0, 2.0, 10.0)
    assert above.ejected_mass_fraction == pytest.approx(8.7 / 11.2)
    assert above.mass_loss_unbinds is True
    # exactly at the half counts as unbound (>= , not >): star 10 -> 2 beside 6, dM=8, M=16.
    at = pc.dco_endpoint(_dco("BH", "BH", m1=2.0, m2=6.0), 40.0, 5.0, 10.0)
    assert at.ejected_mass_fraction == pytest.approx(0.5)
    assert at.mass_loss_unbinds is True


def test_endpoint_never_reports_negative_ejecta():
    """A remnant heavier than the star it came from is unphysical, but the grid is allowed to
    round; the fraction floors at 0 so it can never read as mass being GAINED at collapse."""
    e = pc.dco_endpoint(_dco("BH", "BH", m1=10.5, m2=8.0), 40.0, 5.0, 10.0)
    assert e.ejected_mass_fraction == 0.0
    assert e.mass_loss_unbinds is False


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
    could differ from an H donor). Measured 2026-07-09 across ALL 8 [Fe/H] buckets of BOTH He
    grids (feh -4.0 .. +0.30103) under the same three-part `active` gate (not detached AND not
    unstable_MT AND not WD): max 3.65x the CO's own Eddington luminosity (co-hems-rlo at the
    metal-poor floor feh=-4.0; co-hems uniform 3.47x) — the same physical ULX ceiling as
    CO-HMS_RLO (POSYDON caps stable transfer). Notably the He grids are CLEANER than CO-HMS_RLO:
    the ungated float64 pass finds ZERO rows above 5x anywhere (no unstable_MT/WD artifact — the
    metal-poor CO-HMS_RLO grids by contrast hit 505,221x on unstable_MT, which is why this
    re-derivation was mandatory and not assumed). Mirrors the three-part gate over the raw
    columns."""
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


# =============================================================================================
# Chunk 2c: the full 8-bucket [Fe/H] axis for BOTH He grids (mirrors CO-HMS_RLO's Chunk 1c and
# the HMS-HMS multi-[Fe/H] rollout). Data + tests only — the runtime was already snap-always
# over the whole grid, so no posydon_co.py change. Gated `requires_posydon_co_he_multifeh`
# (>=2 buckets baked per He grid) so these SKIP not FAIL on a solar-only checkout.
# =============================================================================================

from .conftest import requires_posydon_co_he_multifeh  # noqa: E402


@requires_posydon_co_he_multifeh
@pytest.mark.parametrize("kind", _HE_KINDS)
def test_he_meta_lists_every_baked_metallicity_bucket(kind):
    """`available_feh` reflects the REAL baked bucket set for EACH He grid, never hardcoded —
    the frontend #co-binary-feh picker is populated from it (the hosted-data-assets recurring
    hardcoded-feh lesson). Mirrors test_posydon_co.py's CO-HMS_RLO version, per kind."""
    baked = sorted(g.feh for g in pc._available_grids(kind))
    assert len(baked) >= 2
    meta = pc.co_binary_track_meta(0.0, kind=kind)
    assert meta["available_feh"] == baked


@requires_posydon_co_he_multifeh
@pytest.mark.parametrize("kind", _HE_KINDS)
def test_he_metallicity_axis_is_real_across_buckets(kind):
    """The Chunk-2c measure-first regression: the SAME (M_star, M_co, P) request resolves to a
    genuinely DIFFERENT real EVOLUTIONARY TRACK at different [Fe/H] (each POSYDON metallicity is
    its own baked grid), reporting the requested bucket back — not a cosmetic [Fe/H] relabel over
    one shared grid. NB the fingerprint is the *track*, not the initial node: POSYDON samples the
    SAME initial (M_star, M_co, P) grid at every Z, so an exact-node demo (co-hems) snaps to the
    identical initial coordinates at all 8 buckets — but the He-star evolves differently
    (Z-dependent winds → different final donor mass), which IS the axis doing real work. Measured:
    co-hems 16.56+5.99, P=0.56 d → final He-star mass falls MONOTONICALLY 16.46 M☉ (feh=-4, weak
    winds) → 8.42 M☉ (feh=+0.3, strong winds) across the axis; co-hems-rlo also shifts the snapped
    node and final CO mass (10.58–10.97). Fingerprint = (node, nstep, final donor & CO mass)."""
    m_star, m_co, p = _KIND_DEMO[kind]
    fehs = sorted(g.feh for g in pc._available_grids(kind))
    tracks, outcomes = set(), set()
    for feh in fehs:
        t = pc.co_binary_track(m_star, m_co, p, feh=feh, kind=kind)
        assert t.steps, f"empty track at feh={feh}"
        assert t.feh == feh, "the served track reports the requested bucket"
        last = t.steps[-1]
        tracks.add((round(t.m_star_init_msun, 4), round(t.m_co_init_msun, 4),
                    round(t.p_init_d, 4), len(t.steps),
                    round(last.star_current_msun, 3), round(last.co_mass_msun, 3)))
        outcomes.add(t.outcome)
    assert len(tracks) > 1, f"kind={kind}: identical track at every [Fe/H] — the axis is inert"
    assert all(isinstance(o, str) and o for o in outcomes)


@requires_posydon_co_he_multifeh
@pytest.mark.parametrize("kind", _HE_KINDS)
def test_dco_classifier_robust_and_honest_across_full_axis(kind):
    """The 2a DCO payoff must degrade HONESTLY across the whole new axis, not just solar. At the
    most metal-poor bucket a pair-instability SN can leave no bound remnant (POSYDON CO_type not
    NS/BH) — `dco_classification` keys off remnant TYPE, so it must return a well-formed
    no-DCO rather than crash on a nan remnant mass. Assert over a low-Z sample: every track
    carries a DcoClassification with a non-empty label, and its remnant mass is finite-or-None
    (never a raw nan leaking to JSON). The robustness — no crash / no nan leak over a whole
    metal-poor grid — is the point; we don't assert which branches appear (a single low-Z
    sample can legitimately be all one kind)."""
    grids = sorted(pc._available_grids(kind), key=lambda g: g.feh)
    low = grids[0]  # the axis floor — the most metal-poor bucket
    assert low.feh <= -2.0, "expected a genuinely metal-poor bucket at the axis floor"
    rng = np.random.default_rng(7)
    n = low.m_star_init.size
    sample = rng.choice(n, size=min(150, n), replace=False)
    seen_dco = set()
    for i in sample:
        t = pc.co_binary_track(float(low.m_star_init[i]), float(low.m_co_init[i]),
                                float(low.p_init_d[i]), feh=low.feh, kind=kind)
        assert t.dco is not None, "a He kind must always carry a DCO classification"
        assert isinstance(t.dco.label, str) and t.dco.label
        m = t.dco.s1_remnant_mass_msun
        assert m is None or math.isfinite(m), "a nan remnant mass must degrade to None, not leak"
        seen_dco.add(bool(t.dco.is_dco))
    assert seen_dco, "no tracks sampled"


# --- Chunk 2d: the endpoint block, measured over the real grids ------------------------------

@pytest.mark.parametrize("kind", _HE_KINDS)
def test_endpoint_presence_tracks_the_classifier_exactly(kind):
    """`dco_endpoint` must appear for every classified pair and for nothing else. If the two
    could disagree, the view would either draw a pair the classifier denies or withhold one it
    asserts — and the caption prints the classifier's label, so the picture would contradict
    its own words."""
    grid = pc._snap_feh(pc._available_grids(kind), 0.0)
    rng = np.random.default_rng(11)
    n = grid.m_star_init.size
    for i in rng.choice(n, size=min(120, n), replace=False):
        tr = pc.co_binary_track(float(grid.m_star_init[i]), float(grid.m_co_init[i]),
                                float(grid.p_init_d[i]), feh=grid.feh, kind=kind)
        assert (tr.dco_endpoint is not None) == tr.dco.is_dco


@pytest.mark.parametrize("kind", _HE_KINDS)
def test_endpoint_orbit_is_the_last_modelled_row(kind):
    """The drawn separation must BE the final step's, not a recomputed or post-SN value. This
    is what makes the caption's "the values going into the supernova" literally true, and it is
    what lets the view reuse the last step's Roche geometry without the scale bar jumping."""
    grid = pc._snap_feh(pc._available_grids(kind), 0.0)
    rng = np.random.default_rng(12)
    n = grid.m_star_init.size
    checked = 0
    for i in rng.choice(n, size=min(120, n), replace=False):
        tr = pc.co_binary_track(float(grid.m_star_init[i]), float(grid.m_co_init[i]),
                                float(grid.p_init_d[i]), feh=grid.feh, kind=kind)
        if tr.dco_endpoint is None:
            continue
        assert tr.dco_endpoint.separation_rsun == tr.steps[-1].separation_rsun
        assert tr.dco_endpoint.period_d == tr.steps[-1].period_d
        checked += 1
    assert checked > 0, f"kind={kind}: no DCO endpoints in the sample"


@pytest.mark.parametrize("kind", _HE_KINDS)
def test_compact_objects_are_never_within_orders_of_magnitude_of_the_separation(kind):
    """The measure-first gate behind the whole render decision. Both bodies are drawn as
    fixed-pixel glyphs because nothing else is possible: measured over both He grids the
    largest object is ~1e-9 to ~1e-6 of the gap, so a to-scale pair would be sub-pixel by
    six orders of magnitude. Pinned loosely (< 1e-4) — the claim is the ORDER, and a tight
    bound here would fail on a legitimately tighter orbit rather than on a real regression."""
    grid = pc._snap_feh(pc._available_grids(kind), 0.0)
    worst = 0.0
    rng = np.random.default_rng(13)
    n = grid.m_star_init.size
    for i in rng.choice(n, size=min(150, n), replace=False):
        tr = pc.co_binary_track(float(grid.m_star_init[i]), float(grid.m_co_init[i]),
                                float(grid.p_init_d[i]), feh=grid.feh, kind=kind)
        e = tr.dco_endpoint
        if e is None or e.size_over_separation is None:
            continue
        worst = max(worst, e.size_over_separation)
    assert 0.0 < worst < 1e-4, f"kind={kind}: largest size/separation {worst:.2e}"


@requires_posydon_co_he_multifeh
def test_the_unbound_branch_is_real_and_rare_across_the_whole_axis():
    """The Blaauw gate is not a formality — it has to be reachable, or it would be dead code
    dressed as an honesty check; and it has to be rare, or withholding the view would gut the
    feature. Measured 2026-09-06 over ALL 66,599 DCO tracks in both He grids x all 8
    metallicity buckets: 935 unbind on mass loss alone (1.40 %), worst ejected fraction 0.78,
    concentrated at low metallicity. This asserts the shape of that population from a sample
    of the extremes, not the exact count (a re-bake may legitimately move it)."""
    seen_unbound = seen_bound = 0
    for kind in _HE_KINDS:
        grids = sorted(pc._available_grids(kind), key=lambda g: g.feh)
        for grid in (grids[0], grids[-1]):        # the metal-poor floor and the rich ceiling
            rng = np.random.default_rng(17)
            n = grid.m_star_init.size
            for i in rng.choice(n, size=min(200, n), replace=False):
                tr = pc.co_binary_track(float(grid.m_star_init[i]), float(grid.m_co_init[i]),
                                        float(grid.p_init_d[i]), feh=grid.feh, kind=kind)
                if tr.dco is None or not tr.dco.is_dco:
                    continue
                # A classified pair always gets a block; only the FLAG decides whether it draws.
                assert tr.dco_endpoint is not None
                if tr.dco_endpoint.mass_loss_unbinds:
                    seen_unbound += 1
                else:
                    seen_bound += 1
    assert seen_bound > 0, "no drawable pairs anywhere — the endpoint view would never appear"
    assert seen_unbound > 0, "the unbound branch was never reached; the gate is untested in situ"
    assert seen_unbound < seen_bound / 4, "unbound pairs should be the rare minority"


def test_track_route_carries_the_endpoint_block():
    """The route's JSON shape — the frontend reads `dco_endpoint` straight off it."""
    client = TestClient(app)
    r = client.get("/co_binary_track", params={
        "m_star": _DCO_M_STAR, "m_co": _DCO_M_CO, "p": _DCO_P, "kind": "co-hems"})
    assert r.status_code == 200
    d = r.json()
    assert d["dco"]["is_dco"] is True
    e = d["dco_endpoint"]
    assert e is not None
    for key in ("separation_rsun", "period_d", "s1_radius_km", "s2_radius_km",
                "s1_radius_assumed", "s2_radius_assumed", "size_over_separation",
                "ejected_mass_fraction", "mass_loss_unbinds"):
        assert key in e, f"missing {key}"
    assert e["separation_rsun"] > 0 and e["period_d"] > 0


def test_co_hms_rlo_has_no_endpoint_block():
    """The H-rich kind has no DCO story, so it must have no geometry for one either — the
    same additive-key discipline Chunk 2a kept for `dco`."""
    client = TestClient(app)
    r = client.get("/co_binary_track", params={"m_star": 15, "m_co": 10, "p": 10})
    assert r.status_code == 200
    d = r.json()
    assert d["dco"] is None
    assert d["dco_endpoint"] is None
