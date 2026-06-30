"""Rotation (v/vcrit) axis — the §3 third selection axis (mass × [Fe/H] × vvcrit).

MIST v2.5 publishes a non-rotating (vvcrit=0.0) and a rotating (vvcrit=0.4) grid.
The provider partitions its grids into one `_Axis` per rotation rate and **snaps**
between them (no third grid to interpolate toward — §6), interpolating [Fe/H]×mass
only *within* a bucket. These tests pin three things:

  1. The default (non-rotating) axis is uncontaminated by the rotating grid — the
     regression the §10 Sun anchor (1.0 M_sun, where rotation is bit-identical to
     non-rotating) structurally cannot detect. This is the bug that exists the
     moment the rotating grid lands on disk if grids are keyed by [Fe/H] alone.
  2. Rotation reshapes the track where it physically bites — the main-sequence
     surface-N enrichment (the Hunter-diagram signature) at the massive end.
  3. Rotation is inert below the ~1.2 M_sun Kraft break (MIST ramps rotation in by
     mass; below it the rotating track is bit-identical to the non-rotating one).

Skipped unless the rotating grid is fetched (conftest.requires_mist_rotation).
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from fastapi.testclient import TestClient

from star_sim.api import app
from star_sim.providers import MISTProvider
from star_sim.providers._vendor import read_mist_models as rmm
from star_sim.providers.mist import DATA_DIR

from .conftest import (
    requires_mist_heldout_feh,
    requires_mist_rotation,
    requires_mist_rotation_heldout_feh,
    requires_mist_rotation_lowz,
    requires_mist_rotation_multifeh,
)

pytestmark = requires_mist_rotation


@pytest.fixture(scope="module")
def provider() -> MISTProvider:
    return MISTProvider()


def _raw_surface_n(vvcrit_dir: str, mass_tag: str) -> np.ndarray:
    """Surface nitrogen (n13+n14+n15, the provider's element-sum convention) for one
    raw `.track.eep`, read straight from disk — the ground truth the provider must
    reproduce at a grid point."""
    path = DATA_DIR / vvcrit_dir / "eeps" / f"{mass_tag}.track.eep"
    e = rmm.EEP(str(path), verbose=False).eeps
    return (
        np.asarray(e["surface_n14"], float)
        + np.asarray(e["surface_n13"], float)
        + np.asarray(e["surface_n15"], float)
    )


def _feh_code(feh: float) -> str:
    """0.0 -> 'p000', -0.75 -> 'm075', 0.5 -> 'p050' (MIST dir-name [Fe/H] code)."""
    return ("m" if feh < 0 else "p") + f"{round(abs(feh) * 100):03d}"


def _raw_track(feh: float, vvcrit: float, mass_tag: str = "00300M"):
    """Read one raw `.track.eep` for an explicit (feh, vvcrit) grid — test ground
    truth for the within-bucket [Fe/H] interpolation checks.

    Unlike `test_mist_provider._real_track`, this targets the rotation rate
    *explicitly* (`...vvcrit{vvcrit}`): with both vvcrit grids on disk a feh-only
    glob would silently return the non-rotating dir, so a rotating-axis test must
    name the rotating dir (as `_raw_surface_n` does)."""
    vv = f"{vvcrit:.1f}"
    path = DATA_DIR / f"feh_{_feh_code(feh)}_afe_p0_vvcrit{vv}" / "eeps" / f"{mass_tag}.track.eep"
    return rmm.EEP(str(path), verbose=False).eeps


def _provider_n_at_eep(states, target_eep: float) -> float:
    """Surface N of the track state whose EEP is nearest `target_eep`."""
    eeps = np.array([s.eep for s in states])
    k = int(np.argmin(np.abs(eeps - target_eep)))
    return states[k].metals_surf["N"]


def test_default_axis_is_purely_non_rotating(provider):
    """The default (0.0) axis must contain only non-rotating grids, and a separate
    rotating axis must exist — i.e. the two solar grids did NOT collide onto one
    degenerate [Fe/H] point. This is the structural form of the contamination fix."""
    provider._ensure_loaded()
    assert 0.0 in provider._axes and 0.4 in provider._axes
    assert provider._default_vvcrit == 0.0
    assert all(g.vvcrit == 0.0 for g in provider._axes[0.0].grids)
    assert all(g.vvcrit == 0.4 for g in provider._axes[0.4].grids)
    # the non-rotating axis still carries the full [Fe/H] span (uncollided)
    assert len(provider._axes[0.0].grids) >= 2


def test_default_track_reads_non_rotating_bucket_at_grid_point(provider):
    """A 3 M_sun solar track with rotation OFF reads the non-rotating grid. 3.0/0.0
    are exact grid points (no blend), so the match is tight.

    NOTE this is a "reads the right bucket" check, *not* the contamination gate: at
    feh=0.0 exactly, even the buggy [Fe/H]-only keying happened to land on the
    non-rotating grid (the duplicate-0.0 bracket resolves to the lower index, which
    sorts non-rotating-first). The query that actually discriminates the bug is the
    off-grid feh blend below."""
    states0 = provider.track(mass=3.0, feh=0.0, vvcrit=0.0)
    n_default = _provider_n_at_eep(states0, 551.0)

    raw_nonrot = _raw_surface_n("feh_p000_afe_p0_vvcrit0.0", "00300M")
    raw_rot = _raw_surface_n("feh_p000_afe_p0_vvcrit0.4", "00300M")
    n_raw_nonrot = float(raw_nonrot[550])   # EEP r+1 == 551 -> raw absolute row 550
    n_raw_rot = float(raw_rot[550])

    assert n_raw_rot > 1.5 * n_raw_nonrot, "sanity: rotation should enrich N here"
    assert n_default == pytest.approx(n_raw_nonrot, rel=1e-3)
    assert abs(n_default - n_raw_rot) > 0.3 * n_raw_rot


@requires_mist_heldout_feh   # also needs p050 (the grid the solar bucket blends toward)
def test_off_grid_feh_blend_uses_non_rotating_bucket(provider):
    """THE contamination gate — a test that FAILS on the old [Fe/H]-only keying.

    At an *off-grid* [Fe/H] the duplicate-0.0 bug bites: the old bracket for
    feh=0.25 spans `_fehs=[..,0.0,0.0,0.5]` indices 4 (the **rotating** solar grid,
    sorted second) and 5 (non-rotating 0.5) — so `track(3.0, 0.25)` would blend the
    *rotating* solar track into a nominally non-rotating request. The fixed keying
    partitions rotation into its own axis, so the 0.0 axis blends non-rotating 0.0
    with non-rotating 0.5.

    At fixed EEP the [Fe/H] blend is linear with weight 0.5 (0.25 between 0.0 and
    0.5), so the two hypotheses are distinct, ground-truth-free predictions:
      fixed: 0.5*(N_nonrot_solar + N_p050)
      buggy: 0.5*(N_rot_solar    + N_p050)
    The rotating solar N is ~2x the non-rotating, so these differ by ~20% here."""
    n_solar_nonrot = float(_raw_surface_n("feh_p000_afe_p0_vvcrit0.0", "00300M")[550])
    n_solar_rot = float(_raw_surface_n("feh_p000_afe_p0_vvcrit0.4", "00300M")[550])
    n_p050 = float(_raw_surface_n("feh_p050_afe_p0_vvcrit0.0", "00300M")[550])

    blend_fixed = 0.5 * (n_solar_nonrot + n_p050)
    blend_buggy = 0.5 * (n_solar_rot + n_p050)
    assert abs(blend_buggy - blend_fixed) > 0.1 * blend_fixed, "hypotheses must be distinct"

    n = _provider_n_at_eep(provider.track(mass=3.0, feh=0.25, vvcrit=0.0), 551.0)
    # the fixed (non-rotating) blend is what we must see — and emphatically NOT the buggy one
    assert n == pytest.approx(blend_fixed, rel=1e-3)
    assert abs(n - blend_fixed) < abs(n - blend_buggy)


def test_rotation_on_reads_the_rotating_grid(provider):
    """The mirror of the contamination test: with rotation ON, the 3 M_sun solar
    track must read the rotating grid."""
    states4 = provider.track(mass=3.0, feh=0.0, vvcrit=0.4)
    n_rot = _provider_n_at_eep(states4, 551.0)
    raw_rot = _raw_surface_n("feh_p000_afe_p0_vvcrit0.4", "00300M")
    assert n_rot == pytest.approx(float(raw_rot[550]), rel=1e-3)


def test_rotation_enriches_main_sequence_surface_nitrogen(provider):
    """The headline payoff: at the massive end, rotation raises *main-sequence*
    surface N (rotational mixing dredges CNO-processed material up during the MS —
    the Hunter-diagram signature we don't otherwise show until post-MS dredge-up)."""
    s0 = provider.track(mass=20.0, feh=0.0, vvcrit=0.0)
    s4 = provider.track(mass=20.0, feh=0.0, vvcrit=0.4)
    # mid/late MS (EEP ~430), where rotational mixing has surfaced CNO-processed
    # material but the star is still core-H burning (phase MS) — so this is genuine
    # MS enrichment, not post-MS dredge-up. Non-rotating surface N is still pristine.
    k0 = int(np.argmin(np.abs(np.array([s.eep for s in s0]) - 430.0)))
    k4 = int(np.argmin(np.abs(np.array([s.eep for s in s4]) - 430.0)))
    assert s0[k0].phase == "MS" and s4[k4].phase == "MS"
    n0 = s0[k0].metals_surf["N"]
    n4 = s4[k4].metals_surf["N"]
    assert n4 > 2.0 * n0, f"rotation should enrich MS surface N (got {n0:.2e} -> {n4:.2e})"


def test_rotation_inert_below_kraft_break(provider):
    """MIST ramps rotation in by mass: below the ~1.2 M_sun Kraft break the rotating
    track is *bit-identical* to the non-rotating one (low-mass stars magnetically
    brake, so a fixed initial spin is unphysical). The 1.0 M_sun track must be
    identical with rotation ON vs OFF — which is exactly why the Sun anchor can't
    police the contamination bug, and why the rotation toggle must be honest about
    being a no-op here (Chunk 2)."""
    s0 = provider.track(mass=1.0, feh=0.0, vvcrit=0.0)
    s4 = provider.track(mass=1.0, feh=0.0, vvcrit=0.4)
    assert len(s0) == len(s4)
    for a, b in zip(s0, s4):
        assert a.Teff_K == b.Teff_K
        assert a.L_lsun == b.L_lsun
        assert a.metals_surf["N"] == b.metals_surf["N"]
        assert a.Y_surf == b.Y_surf


def test_parameter_ranges_exposes_available_vvcrits(provider):
    """The frontend reads which rotation rates exist to decide whether to offer the
    toggle (≥2 ⇒ offer it)."""
    avail = provider.parameter_ranges()["vvcrit"]["available"]
    assert 0.0 in avail and 0.4 in avail


def test_vvcrit_snaps_to_nearest_bucket(provider):
    """Rotation is a discrete 2-point grid: an in-between or out-of-range request
    snaps to the nearest available bucket (never interpolates — §6)."""
    on = provider.track(mass=3.0, feh=0.0, vvcrit=0.4)
    # 0.3 is closer to 0.4 than 0.0 -> snaps to the rotating bucket
    snapped = provider.track(mass=3.0, feh=0.0, vvcrit=0.3)
    assert _provider_n_at_eep(snapped, 551.0) == _provider_n_at_eep(on, 551.0)
    # a wildly out-of-range value also snaps (no extrapolation, no error)
    far = provider.track(mass=3.0, feh=0.0, vvcrit=9.0)
    assert _provider_n_at_eep(far, 551.0) == _provider_n_at_eep(on, 551.0)


# --- the [Fe/H] axis *within* the rotating bucket (vvcrit=0.4) ----------------
# The rotation axis snaps between buckets, but [Fe/H] still interpolates *within* a
# bucket. test_mist_provider has lies-between + held-out feh tests for the
# non-rotating axis; these are their vvcrit=0.4 analogs, so the rotating axis's
# within-bucket [Fe/H] interpolation gets the same validation (an advisor-flagged gap
# after rotation Chunk 4 filled the rotating [Fe/H] span).


@requires_mist_rotation_multifeh
def test_feh_interpolation_lies_between_metallicities_rotating(provider):
    """The §6/§10 lies-between property, but *within the rotating bucket*: at a fixed
    EEP an interpolated [Fe/H] on the vvcrit=0.4 axis must lie between its bracketing
    rotating grids on the HR diagram — the analog of
    test_mist_provider.test_feh_interpolation_lies_between_metallicities.

    The [Fe/H] interpolation is shared blend-then-invert code (the `_Axis` just swaps
    which grids it holds), so this bound is structurally guaranteed on either axis;
    the point is that it holds with the *rotating* grids actually selected. But
    lies-between alone is a weak discriminator here: rotation's logL/Teff signature is
    far subtler than its surface-N one, so over most rows a contaminated *non-rotating*
    blend would still land inside the rotating bracket+slack (measured: only ~1/25 age
    samples diverge in logL, but ~16/25 in log Teff at the -1.0/-0.75 bracket). So we
    add the contamination-style check (cf. test_off_grid_feh_blend_uses_non_rotating_bucket):
    on the rows where the rotating and non-rotating blends genuinely diverge in log
    Teff, the interpolated point must sit closer to the *rotating* blend — proving the
    vvcrit=0.4 grids, not their non-rotating twins, drove the interpolation.

    Mass 3.0 (a grid point, so only [Fe/H] is interpolated) is above the ~1.2 M_sun
    Kraft break on purpose: at 1.0 M_sun the rotating track is bit-identical to the
    non-rotating one, so the whole test would silently degenerate to the non-rotating
    case.
    """
    provider._ensure_loaded()
    fehs = provider._axes[0.4].fehs               # the rotating axis's own [Fe/H] span
    f_lo, f_hi = float(fehs[0]), float(fehs[1])   # first rotating bracket
    f_mid = 0.5 * (f_lo + f_hi)
    rl, rh = _raw_track(f_lo, 0.4), _raw_track(f_hi, 0.4)   # rotating brackets
    nl, nh = _raw_track(f_lo, 0.0), _raw_track(f_hi, 0.0)   # their non-rotating twins

    lo, hi = provider.age_range(3.0, f_mid, vvcrit=0.4)
    discriminated = 0
    for frac in np.linspace(0.05, 0.95, 25):
        st = provider.state_at(3.0, f_mid, lo + frac * (hi - lo), vvcrit=0.4)
        row = int(round(st.eep)) - 1
        logL, logT = math.log10(st.L_lsun), math.log10(st.Teff_K)
        # 1) structural lies-between against the rotating bracket
        assert min(rl["log_L"][row], rh["log_L"][row]) - 0.03 <= logL <= max(rl["log_L"][row], rh["log_L"][row]) + 0.03
        assert min(rl["log_Teff"][row], rh["log_Teff"][row]) - 0.01 <= logT <= max(rl["log_Teff"][row], rh["log_Teff"][row]) + 0.01
        # 2) discrimination: where the buckets diverge, the interp tracks the rotating one
        rot_blend = 0.5 * (rl["log_Teff"][row] + rh["log_Teff"][row])
        nonrot_blend = 0.5 * (nl["log_Teff"][row] + nh["log_Teff"][row])
        if abs(rot_blend - nonrot_blend) > 0.01:
            assert abs(logT - rot_blend) < abs(logT - nonrot_blend)
            discriminated += 1
    # the discrimination clause must actually have fired (else lies-between is vacuous)
    assert discriminated >= 5    # measured 16


@requires_mist_rotation_heldout_feh
def test_feh_interpolation_tracks_held_out_grid_rotating():
    """Hold the *rotating* solar grid out: interpolate at [Fe/H]=0 / vvcrit=0.4 from
    only the rotating m050/p050 grids and check it reproduces the real *rotating* p000
    run — the analog of test_mist_provider.test_feh_interpolation_tracks_held_out_grid,
    and the test with teeth. Unlike lies-between (a structural convexity bound),
    accuracy against a held-out grid catches blend-weight, feh-mapping, and
    rotating-grid-specific drift.

    Mass 3.0 is above the Kraft break (so rotation genuinely bites — at 1.0 M_sun the
    rotating and non-rotating grids are identical and the test couldn't tell the axes
    apart). Tolerances are *measured on the rotating axis*, not copied from the
    non-rotating test: L median ~0.7%, Teff median ~1.8%. The larger Teff error than
    the non-rotating 1.0 M_sun case reflects the steeper 3.0 M_sun He-ignition
    morphology across a full 1.0-dex bracket (a few rows are much worse, so — like the
    non-rotating test — we assert on the median).

    The clause with teeth is the relative one: interpolating the *non-rotating*
    m050/p050 grids and comparing to the same rotating p000 ground truth gives ~2.6%
    median L-error (3.6x worse). A contamination bug that read the wrong axis would
    make the rotating and non-rotating paths *identical*, collapsing that ratio to 1 —
    so the `> 2x` assertion fails exactly when the axis selection is broken, a thing no
    absolute tolerance alone can police.
    """
    p = MISTProvider(fehs=(-0.5, 0.5))          # rotating solar grid deliberately excluded
    real = _raw_track(0.0, 0.4)                  # ground truth: the real rotating p000 3.0 track

    def _median_errs(vvcrit: float) -> tuple[float, float]:
        lo, hi = p.age_range(3.0, 0.0, vvcrit=vvcrit)
        L_errs, T_errs = [], []
        for frac in np.linspace(0.05, 0.95, 25):
            st = p.state_at(3.0, 0.0, lo + frac * (hi - lo), vvcrit=vvcrit)
            row = int(round(st.eep)) - 1
            L_real, T_real = 10 ** real["log_L"][row], 10 ** real["log_Teff"][row]
            L_errs.append(abs(st.L_lsun - L_real) / L_real)
            T_errs.append(abs(st.Teff_K - T_real) / T_real)
        return float(np.median(L_errs)), float(np.median(T_errs))

    L_med, T_med = _median_errs(0.4)
    assert L_med < 0.02     # measured 0.7%
    assert T_med < 0.03     # measured 1.8%

    # teeth: reading the non-rotating bucket misses the rotating truth by ~3.6x
    # (measured 2.6% vs 0.7%) — and a contamination bug would make these equal.
    L_med_nonrot, _ = _median_errs(0.0)
    assert L_med_nonrot > 2.0 * L_med


# --- Chunk 2: the data-derived rotation honesty gate (rotation_status) ---------

def test_rotation_threshold_is_data_derived_kraft_break(provider):
    """The rotation-onset mass is *derived* from the data (the first grid mass whose
    rotating track diverges from the non-rotating one), not hardcoded — and it lands
    at the ~1.2 M_sun Kraft break (convective→radiative envelope; magnetic braking
    shuts off so a fixed initial spin becomes physical)."""
    thr = provider._rotation_threshold(0.0)
    assert thr is not None
    assert 1.15 <= thr <= 1.35, f"expected the Kraft break near 1.2 M_sun, got {thr}"


def test_rotation_status_inert_below_threshold(provider):
    """At the Sun (1.0 M_sun) the rotating grid exists but rotation does nothing —
    the toggle must report has_grid=True, active=False (an honest no-op, not a dead
    control). This is the gate the frontend uses to grey the toggle with a note."""
    st = provider.rotation_status(1.0, 0.0)
    assert st["has_grid"] is True
    assert st["active"] is False
    assert st["threshold_msun"] is not None and st["threshold_msun"] > 1.0


def test_rotation_status_active_above_threshold(provider):
    """At 3 M_sun (above the Kraft break) toggling rotation changes the track, so the
    gate reports active=True."""
    st = provider.rotation_status(3.0, 0.0)
    assert st["has_grid"] is True
    assert st["active"] is True


def test_rotation_status_absent_where_no_grid(provider):
    """The rotating axis now spans the full fetched [Fe/H] axis (Chunk 4 added the
    remaining rotating metallicities), so the headline super-solar grid [Fe/H]=+0.5 is
    *present* — has_grid=True. Absence is honest only *beyond* the fetched axis: a
    metallicity past the rotating-grid span (here +0.75) has no rotating grid, so the
    toggle reports has_grid=False rather than silently snapping to one that exists."""
    assert provider.rotation_status(3.0, 0.5)["has_grid"] is True   # filled by Chunk 4
    st = provider.rotation_status(3.0, 0.75)
    assert st["has_grid"] is False
    assert st["active"] is False


@pytest.mark.parametrize("mass", [1.0, 1.1, 3.0, 8.0, 20.0])
def test_rotation_status_never_lies_about_the_track(provider, mass):
    """The honesty contract, tied to reality (the project's 'don't label a non-feature'
    rule): wherever the gate says active=False, the rotating and non-rotating tracks
    must be *bit-identical* (toggling truly does nothing); wherever it says active=True,
    they must actually differ. The gate is derived from this same divergence, so this
    pins that the derivation and the served tracks can never drift apart."""
    st = provider.rotation_status(mass, 0.0)
    s0 = provider.track(mass, 0.0, vvcrit=0.0)
    s4 = provider.track(mass, 0.0, vvcrit=0.4)
    max_dteff = max(abs(a.Teff_K - b.Teff_K) for a, b in zip(s0, s4))
    max_dn = max(abs(a.metals_surf["N"] - b.metals_surf["N"]) for a, b in zip(s0, s4))
    if st["active"]:
        assert max_dteff > 0.0 or max_dn > 0.0, "active=True but the tracks are identical"
    else:
        assert max_dteff == 0.0 and max_dn == 0.0, "active=False but the tracks differ"


@requires_mist_rotation_lowz
def test_rotation_status_works_at_low_z(provider):
    """Low-Z is where the headline CHE payoff lives, so the gate must work there too:
    the rotating m100 grid gives has_grid=True and a derived threshold at [Fe/H]=-1."""
    st = provider.rotation_status(3.0, -1.0)
    assert st["has_grid"] is True
    assert st["active"] is True
    assert st["threshold_msun"] is not None


# --- Chunk 3: surface rotation velocity (v_rot_kms) + the API wiring -----------

def test_rotation_velocity_surfaced_through_state(provider):
    """The Chunk-3 payoff: v_rot_kms is now a real StellarState field, not a stub.
    The non-rotating axis is honestly 0 km/s (the model isn't spinning); the rotating
    axis carries the real, large equatorial velocity at the massive end."""
    s0 = provider.track(20.0, 0.0, vvcrit=0.0)
    s4 = provider.track(20.0, 0.0, vvcrit=0.4)
    assert all(s.v_rot_kms == 0.0 for s in s0), "non-rotating grid must report 0 km/s"
    assert max(s.v_rot_kms for s in s4) > 100.0, "rotating massive star must spin fast"


def test_rotation_velocity_consistent_with_the_honesty_gate(provider):
    """Below the Kraft break MIST zeroes rotation entirely (not just the mixing), so
    v_rot_kms is 0 on BOTH grids at 1.0 M_sun — the readout never shows a spinning star
    whose track the gate calls a no-op. Above the break the rotating velocity is real."""
    s0 = provider.track(1.0, 0.0, vvcrit=0.0)
    s4 = provider.track(1.0, 0.0, vvcrit=0.4)
    assert max(s.v_rot_kms for s in s0) == 0.0
    assert max(s.v_rot_kms for s in s4) == 0.0           # inert below the break, velocity too
    s_active = provider.track(3.0, 0.0, vvcrit=0.4)
    assert max(s.v_rot_kms for s in s_active) > 0.0       # real spin above it


def test_api_track_vvcrit_param_selects_the_rotating_bucket():
    """The /track route threads vvcrit to the provider: the rotating bucket returns a
    different track (MS surface-N enrichment) than the default non-rotating one, and
    surfaces the real v_rot_kms — proving the axis reaches the API edge (§4)."""
    client = TestClient(app)
    base = client.get("/track", params={"mass": 20.0, "feh": 0.0}).json()
    rot = client.get("/track", params={"mass": 20.0, "feh": 0.0, "vvcrit": 0.4}).json()
    assert client.get("/track", params={"mass": 20.0, "feh": 0.0}).status_code == 200
    # same EEP shape, different physics
    assert len(base) == len(rot)
    k = len(base) // 3   # mid-MS-ish
    assert rot[k]["metals_surf"]["N"] > base[k]["metals_surf"]["N"]
    assert max(r["v_rot_kms"] for r in rot) > 100.0
    assert all(b["v_rot_kms"] == 0.0 for b in base)


def test_api_rotation_status_route():
    """The /rotation_status route exposes the honesty gate to the frontend, going
    through PROVIDER so it stays §3-clean. Shape + the three regimes."""
    client = TestClient(app)
    body = client.get("/rotation_status", params={"mass": 1.0, "feh": 0.0}).json()
    assert set(body) == {"has_grid", "threshold_msun", "active"}
    assert body["has_grid"] is True and body["active"] is False        # inert at the Sun
    assert client.get("/rotation_status", params={"mass": 20.0, "feh": 0.0}).json()["active"] is True
    # +0.5 is now covered (Chunk 4 filled the rotating axis); absence is beyond it (+0.75).
    assert client.get("/rotation_status", params={"mass": 3.0, "feh": 0.5}).json()["has_grid"] is True
    assert client.get("/rotation_status", params={"mass": 3.0, "feh": 0.75}).json()["has_grid"] is False


def test_massive_rotating_supergiant_classifies_sn_not_none(provider):
    """The core-collapse foreshadow must not vanish when rotation is enabled.

    A rotating massive solar track (35-42 M_sun, vvcrit=0.4) ends at core-helium
    burning (CHeB) as a bloated supergiant — it forms no WD and no WR, and its track
    simply terminates with NO row past the normal window. The endgame classifier used
    to split SN vs none on whether such a post-window row existed (`r0 <= r_last`),
    so these stars fell through to `type="none"` and the UI showed nothing — even
    though they core-collapse. Their non-rotating twins (which keep a phase-5 row
    past the window) were correctly SN, so the gateway was inconsistent across the
    rotation axis. The fix classifies by the evolved, massive end state instead, so
    the SN note is shown whether rotation is on or off."""
    for m in (35.0, 40.0):
        rot = provider.endgame(m, 0.0, 0.4)
        non = provider.endgame(m, 0.0, 0.0)
        assert rot.type == "SN", f"rotating {m} M_sun must warn of core collapse, got {rot.type}"
        assert non.type == "SN"                 # the non-rotating twin was always SN
        assert rot.states == []                 # SN is a dead-end note, nothing to render
        assert rot.mass_init_msun == m          # snapped to the real grid track
