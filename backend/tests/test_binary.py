"""Validation for the binary-stripped-star sibling (`binary.py`, `/binary`).

The stripped star is the hot, He-rich core a close companion exposes by Case-B
Roche-lobe overflow — the ~70% binary WR/subdwarf channel (Götberg+2018). Like the
supernova / structure / spectra siblings it bypasses `PROVIDER` and emits a plain
`StellarState`, so the anchors here are:

  * the parse + snap honesty (a request lands on a TRUE grid node, never an
    interpolation — §6), and the committed table's internal validity;
  * **the visibility gate** — the discipline check that this is a *feature*: a stripped
    star must read visibly distinct from the MIST single-star of the SAME initial mass
    through the real runtime path, or there is nothing to show. It keys on **Teff and
    Y_surf only, never luminosity** — a stripped star is sub-luminous *for its Teff*, but
    because M_strip ≪ M_init it is a He-star of a different mass, so the L comparison
    flips sign across the grid (sub-luminous at 2 M☉, over-luminous at 18 M☉). Hotter +
    He-enriched are the robust discriminators;
  * the SED-consistency regression — the *entire basis for trusting the LLM-transcribed
    table*: table L vs the ground-truth SED-integrated L, Stefan-Boltzmann L(Teff,R) vs
    SED L, and logg vs (M_strip, R). Gated `requires_gotberg_data` (reads the gitignored
    SEDs); the parameter table itself is committed, so every other test always runs.
"""

from __future__ import annotations

import math
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from star_sim import binary as b
from star_sim.api import app
from star_sim.state import StellarState

from .conftest import requires_gotberg_data, requires_mist_data

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SED_GRID = _REPO_ROOT / "data" / "gotberg_stripped" / "grid_014"

# The three mid/high-grid nodes used for the visibility gate (He-rich surface; the
# low-mass end is still H-rich sdB-like, so it is not where the He headline lives).
_VISIBILITY_MASSES = [4.04, 9.0, 14.87]


# --- parse + committed-table validity (always run — data is committed) --------

def test_grid_parses_23_solar_models():
    models = b.available_models()
    solar = [m for m in models if abs(m.grid_z - 0.014) < 1e-9]
    assert len(solar) == 23
    assert all(2.0 <= m.m_init <= 18.17 for m in solar)


def test_grid_is_ordered_and_he_enriches_with_mass():
    """Down the grid the stripped stars get hotter, bigger, and more He-surfaced —
    the physical trend (heavier progenitor → deeper stripping → more exposed He)."""
    solar = sorted((m for m in b.available_models() if abs(m.grid_z - 0.014) < 1e-9),
                   key=lambda m: m.m_init)
    teffs = [m.teff_kK for m in solar]
    assert teffs == sorted(teffs)                       # monotone hotter
    # He surface fraction (raw table X_He) rises from ~0 (low mass, H-rich) to ~0.87.
    assert solar[0].x_he < 0.05 and solar[-1].x_he > 0.8


# --- snap honesty (never interpolate — §6) ------------------------------------

def test_snap_returns_a_true_grid_node():
    node_masses = {m.m_init for m in b.available_models() if abs(m.grid_z - 0.014) < 1e-9}
    # a request off any node snaps to the nearest real node, reported verbatim
    r = b.stripped_star(8.5, 0.0)
    assert r.m_init_msun in node_masses
    assert r.state.mass_init_msun == r.m_init_msun    # the state carries the snapped node
    # 8.5 is between 8.15 and 9.0 -> nearest is 8.15
    assert r.m_init_msun == 8.15


def test_snap_far_flags_out_of_range():
    lo, hi = b.eligible_mass_range(0.0)
    assert b.stripped_star(hi + 5.0, 0.0).mass_snapped_far is True    # above the grid
    assert b.stripped_star(lo - 0.5, 0.0).mass_snapped_far is True    # below the grid
    assert b.stripped_star(9.0, 0.0).mass_snapped_far is False        # in range
    # with only the solar bucket on disk, [Fe/H] off ~solar snaps to Z=0.014 and is flagged
    assert b.stripped_star(9.0, 0.5).feh_snapped_far is True
    assert b.stripped_star(9.0, 0.0).feh_snapped_far is False


def test_snap_reports_true_grid_z_as_feh():
    r = b.stripped_star(9.0, -0.8)
    assert r.grid_z == 0.014                          # only solar on disk -> snaps to it
    assert r.feh_snapped == pytest.approx(0.0, abs=1e-9)


# --- StellarState validity (composition closes; scalars sane) -----------------

def test_state_is_valid_stellar_state():
    for mass in [2.0, 4.04, 9.0, 14.87, 18.17]:
        s = b.stripped_star(mass, 0.0).state
        assert isinstance(s, StellarState)
        # mass fractions close at 1 (Z_surf = grid Z, X/Y renormalized to 1−Z)
        assert s.X_surf + s.Y_surf + s.Z_surf == pytest.approx(1.0, abs=1e-9)
        assert 0.0 <= s.X_surf <= 1.0 and 0.0 <= s.Y_surf <= 1.0
        assert s.Z_surf == pytest.approx(0.014, abs=1e-9)
        # hot, compact, luminous He-star: Teff tens of kK, high surface gravity
        assert 15_000.0 < s.Teff_K < 120_000.0
        assert 5.0 < s.logg < 6.0
        assert s.L_lsun > 1.0
        assert s.R_rsun < 1.0                          # compact (sub-R☉)
        assert s.phase == "stripped-envelope star"
        assert s.mdot_msun_yr is None                  # not in the verified 8-column table


def test_current_mass_rides_as_a_routing_scalar():
    """M_strip (current mass) has no home on StellarState (only mass_init) — it must come
    back as a scalar, and it is far below the progenitor mass (the envelope is gone)."""
    r = b.stripped_star(9.0, 0.0)
    assert r.m_strip_msun == pytest.approx(2.49, abs=1e-6)
    assert r.m_strip_msun < r.m_init_msun              # stripped: current ≪ initial
    assert not hasattr(r.state, "m_strip_msun")


# --- the visibility gate (the "is this a feature" discipline check) -----------

@requires_mist_data
def test_stripped_is_off_relation_vs_single_star():
    """Through the REAL runtime path: the stripped star is hotter AND He-enriched vs the
    MIST single-star of the same initial mass (its ZAMS). Keys on Teff + Y_surf only —
    NOT L (which flips sign across the grid; see the module docstring)."""
    from star_sim.api import PROVIDER

    for mass in _VISIBILITY_MASSES:
        stripped = b.stripped_star(mass, 0.0).state       # the shipped path, not inline
        lo, hi = PROVIDER.age_range(mass, 0.0)
        single_zams = PROVIDER.state_at(mass, 0.0, lo + 0.02 * (hi - lo))

        d_teff = stripped.Teff_K - single_zams.Teff_K
        d_y = stripped.Y_surf - single_zams.Y_surf
        assert d_teff > 5000.0, f"M={mass}: stripped not hotter (ΔTeff={d_teff:.0f})"
        assert d_y > 0.2, f"M={mass}: stripped surface not He-enriched (ΔY={d_y:.2f})"


# --- /binary route smoke ------------------------------------------------------

def test_route_payload_shape():
    c = TestClient(app)
    r = c.get("/binary", params={"mass": 9.0, "feh": 0.0})
    assert r.status_code == 200
    d = r.json()
    # the §3 StellarState under `state`, routing scalars flattened alongside
    assert set(d) >= {
        "state", "m_strip_msun", "m_init_msun", "grid_z", "feh_snapped",
        "mass_snapped_far", "feh_snapped_far", "mass_grid_min", "mass_grid_max",
    }
    assert set(d["state"]) >= {"Teff_K", "L_lsun", "R_rsun", "logg", "X_surf", "Y_surf", "Z_surf"}
    assert d["state"]["Teff_K"] == pytest.approx(65500.0)
    assert d["m_strip_msun"] == pytest.approx(2.49)


def test_route_snaps_far_in_band_not_422():
    c = TestClient(app)
    r = c.get("/binary", params={"mass": 25.0, "feh": 0.5})   # out of grid both axes
    assert r.status_code == 200                                 # snap-always, not 422
    d = r.json()
    assert d["mass_snapped_far"] is True and d["feh_snapped_far"] is True
    assert d["m_init_msun"] == pytest.approx(18.17)             # snapped to the top node


def test_route_422_on_invalid_mass():
    c = TestClient(app)
    assert c.get("/binary", params={"mass": -1.0}).status_code == 422
    assert c.get("/binary", params={"mass": 0.0}).status_code == 422


# --- path (b): the companion (two-star Algol co-evolution) --------------------

def test_companion_init_mass_is_the_grid_q():
    """The companion starts at M2_init = 0.8·M_init — the grid's fixed q (pure, no data)."""
    assert b.COMPANION_MASS_RATIO == 0.8
    assert b.companion_init_mass(9.0) == pytest.approx(7.2)
    assert b.companion_init_mass(18.17) == pytest.approx(14.536)


def test_pair_payload_assembles_donor_plus_companion():
    """`binary_pair_payload` keeps `binary.py` a pure sibling: it takes the companion
    StellarState (fetched by the route via PROVIDER) and only assembles the payload +
    the transfer scalars. The donor block is byte-identical to the /binary payload."""
    # a stand-in companion state (the assembler must not care where it came from)
    comp = StellarState(
        age_yr=3.0e7, eep=350.0, phase="MS", mass_init_msun=7.2, feh_init=0.0,
        L_lsun=2.0e3, Teff_K=20_000.0, R_rsun=3.7, logg=4.1,
        X_surf=0.70, Y_surf=0.28, Z_surf=0.02, X_core=0.3, Y_core=0.68, Z_core=0.02,
    )
    payload = b.binary_pair_payload(9.0, 0.0, comp, elapsed_age_yr=3.0e7)

    # donor block == /binary payload, verbatim
    assert payload["m_init_msun"] == pytest.approx(9.0)
    assert payload["m_strip_msun"] == pytest.approx(2.49)
    assert set(payload) >= set(b.stripped_star_payload(9.0, 0.0))

    c = payload["companion"]
    assert c["mass_msun"] == pytest.approx(7.2)                  # 0.8 × 9.0
    # both ratios are companion÷donor (one convention): starts 0.8 (< 1, companion lighter)…
    assert c["mass_ratio_init"] == pytest.approx(0.8)
    # …and the Algol REVERSAL is the same ratio crossing 1: M2 (7.2) / M_strip (2.49) = 2.89 > 1
    assert c["mass_ratio_final"] == pytest.approx(7.2 / 2.49)
    assert c["mass_ratio_final"] > 1.0
    assert c["elapsed_age_yr"] == pytest.approx(3.0e7)
    assert c["state"]["Teff_K"] == pytest.approx(20_000.0)       # the passed-in companion


def test_reversal_holds_across_the_whole_grid():
    """The mass-ratio reversal is robust — M_strip < M2_init at EVERY grid node — so the
    headline never rests on a fragile assumption (the accretor is always the heavier star
    after stripping, regardless of the companion's exact fate)."""
    solar = [m for m in b.available_models() if abs(m.grid_z - 0.014) < 1e-9]
    for m in solar:
        m2 = b.companion_init_mass(m.m_init)
        assert m.m_strip < m2, f"M_init={m.m_init}: M_strip {m.m_strip} !< M2_init {m2}"


@requires_mist_data
def test_pair_route_companion_is_a_sane_ms_star():
    """The path (b) measure-first gate, as a regression: through the REAL route the
    companion comes back a sane MAIN-SEQUENCE star (hotter than the Sun, cooler than the
    stripped donor, still burning H), and the donor is always the hotter, blue-left marker."""
    c = TestClient(app)
    for mass in [2.0, 9.0, 18.17]:
        r = c.get("/binary_pair", params={"mass": mass, "feh": 0.0})
        assert r.status_code == 200
        d = r.json()
        comp = d["companion"]
        cs = comp["state"]
        # the companion is a real MS star of the expected mass
        assert cs["phase"] in ("MS", "PMS")
        assert comp["mass_msun"] == pytest.approx(0.8 * d["m_init_msun"])
        assert cs["mass_init_msun"] == pytest.approx(0.8 * d["m_init_msun"], abs=1e-6)
        # the donor (stripped He-star) is ALWAYS hotter than the companion (blue-left)
        assert d["state"]["Teff_K"] > cs["Teff_K"]
        # a real elapsed age was used (the donor's MS lifetime — positive, sub-Hubble)
        assert 1.0e6 < comp["elapsed_age_yr"] < 2.0e10


def test_pair_route_snaps_far_in_band_not_422():
    """Snap-always like /binary: an out-of-grid request snaps + flags in-band; the
    companion is still assembled off the snapped donor node."""
    c = TestClient(app)
    r = c.get("/binary_pair", params={"mass": 25.0, "feh": 0.0})   # above the grid
    assert r.status_code == 200
    d = r.json()
    assert d["mass_snapped_far"] is True
    assert d["m_init_msun"] == pytest.approx(18.17)                 # snapped to the top node
    assert "companion" in d and d["companion"]["mass_msun"] == pytest.approx(0.8 * 18.17)


def test_pair_route_422_on_invalid_mass():
    c = TestClient(app)
    assert c.get("/binary_pair", params={"mass": -1.0}).status_code == 422
    assert c.get("/binary_pair", params={"mass": 0.0}).status_code == 422


# --- path (b) Chunk 3: the Roche-lobe / mass-transfer geometry ----------------

def test_pinit_column_parsed():
    """The 9th CSV column (initial orbital period) parses onto the model — the Roche
    geometry's only new input. Spot-check two nodes against the on-disk dir names."""
    solar = {m.m_init: m for m in b.available_models() if abs(m.grid_z - 0.014) < 1e-9}
    assert solar[5.45].p_init == pytest.approx(10.7)     # M1_5.45q0.8P10.7Z0.014
    assert solar[18.17].p_init == pytest.approx(31.7)    # M1_18.17q0.8P31.7Z0.014


def test_roche_snaps_and_reports_node():
    """`roche_geometry` snaps (Z, M_init) like `stripped_star` (state↔geometry
    consistency) and its donor mass IS the snapped node."""
    g = b.roche_geometry(5.4, 0.0)                        # snaps to 5.45
    assert g["m_donor_msun"] == pytest.approx(5.45)
    assert g["m_companion_msun"] == pytest.approx(0.8 * 5.45)
    assert g["period_init_d"] == pytest.approx(10.7)


def test_roche_donor_is_heavier_at_rlof():
    """The caption-owned reversal fact: AT RLOF the donor (M1) is the HEAVIER star
    overflowing onto the lighter companion — the OPPOSITE ordering to the post-strip
    state the other panels show (where the donor is the lighter object)."""
    for mass in [2.0, 9.0, 18.17]:
        g = b.roche_geometry(mass, 0.0)
        assert g["m_donor_msun"] > g["m_companion_msun"]
        assert g["q"] == pytest.approx(0.8)              # M2/M1 < 1


def test_roche_separation_from_kepler_is_sane():
    """Separation from Kepler's third law on the node's (M1, M2, P_init). The 5.45 M☉
    node (P=10.7 d, M_tot≈9.8) → a≈43–44 R☉ (an intermediate-mass Case-B system), and a
    longer period gives a wider orbit."""
    g = b.roche_geometry(5.45, 0.0)
    assert g["separation_rsun"] == pytest.approx(43.7, abs=1.5)
    assert g["separation_au"] == pytest.approx(g["separation_rsun"] / 215.032, rel=1e-9)
    # monotone: the 18.17 node (P=31.7 d) is a much wider system than the 2.0 node (P=5.6 d)
    assert (b.roche_geometry(18.17, 0.0)["separation_rsun"]
            > b.roche_geometry(2.0, 0.0)["separation_rsun"])


def test_roche_lagrange_points_ordered():
    """The three collinear Lagrange points are on their expected intervals: L3 behind the
    donor (x<0), L1 between the stars (0<x<1), L2 behind the companion (x>1)."""
    g = b.roche_geometry(9.0, 0.0)
    assert g["l3_x"] < 0.0 < g["l1_x"] < 1.0 < g["l2_x"]
    # for q<1 (donor heavier) L1 sits on the companion's side of the centre of mass
    assert g["l1_x"] > g["x_cm"]


def test_roche_lobes_kiss_at_l1_and_donor_lobe_is_bigger():
    """The two critical-equipotential lobes touch at L1 (the donor's rightmost point and
    the companion's leftmost point both land on L1), and the donor's lobe (heavier star)
    is the larger of the two — the figure-of-eight that IS the mass-transfer geometry."""
    g = b.roche_geometry(9.0, 0.0)
    l1 = g["l1_x"]
    dl, cl = g["donor_lobe"], g["companion_lobe"]
    # closed outlines
    assert dl[0] == dl[-1] and cl[0] == cl[-1]
    d_right = max(p[0] for p in dl)
    c_left = min(p[0] for p in cl)
    assert d_right == pytest.approx(l1, abs=0.01)         # donor cusp at L1
    assert c_left == pytest.approx(l1, abs=0.01)          # companion cusp at L1
    # donor lobe spans farther from its centre (heavier → bigger lobe)
    d_extent = max(p[0] for p in dl) - min(p[0] for p in dl)
    c_extent = max(p[0] for p in cl) - min(p[0] for p in cl)
    assert d_extent > c_extent
    # every lobe point is on the donor's side or straddling — none leaks deep into the
    # companion's well (the L1-tangent bug this construction guards against)
    assert all(p[0] <= l1 + 0.01 for p in dl)
    assert all(p[0] >= l1 - 0.01 for p in cl)


def test_roche_donor_fills_its_eggleton_lobe():
    """The donor's reported radius at RLOF is its volume-equivalent (Eggleton) Roche-lobe
    radius — it FILLS its lobe by construction — and it scales with the separation."""
    g = b.roche_geometry(5.45, 0.0)
    # Eggleton R_L/a for q_donor = M1/M2 = 1.25 is ≈0.40; ×a≈43.7 → ≈17 R☉
    assert g["donor_roche_radius_rsun"] == pytest.approx(17.4, abs=1.5)
    frac = g["donor_roche_radius_rsun"] / g["separation_rsun"]
    assert 0.3 < frac < 0.5                                # a sane Roche-lobe filling factor


# --- track_roche_geometry (path (b) Chunk 4b): the per-step engine a co-evolving ------
# binary track drives with its REAL q(t)/a(t), instead of roche_geometry's one fixed
# q=0.8 CSV node. A lightweight stand-in for `posydon.BinaryStep` — the function is duck-
# typed on three attributes, so a real POSYDON bake isn't needed to test the geometry math.

class _FakeStep:
    def __init__(self, m1, m2, a):
        self.m1_current_msun = m1
        self.m2_current_msun = m2
        self.separation_rsun = a


def test_track_roche_geometry_matches_single_node_engine():
    """At the SAME (q, m1, m2, a) as a real `roche_geometry` node, the per-step engine
    (lower angular resolution) lands on essentially the same L-points and lobe sizes —
    one geometry engine underneath both callers, not two divergent implementations."""
    node = b.roche_geometry(5.45, 0.0)     # q=0.8, the CSV path's full resolution
    step = _FakeStep(node["m_donor_msun"], node["m_companion_msun"], node["separation_rsun"])
    g = b.track_roche_geometry([step])[0]
    assert g["l1_x"] == pytest.approx(node["l1_x"], abs=1e-3)
    assert g["l2_x"] == pytest.approx(node["l2_x"], abs=1e-3)
    assert g["l3_x"] == pytest.approx(node["l3_x"], abs=1e-3)
    d_extent = max(p[0] for p in g["donor_lobe"]) - min(p[0] for p in g["donor_lobe"])
    node_d_extent = max(p[0] for p in node["donor_lobe"]) - min(p[0] for p in node["donor_lobe"])
    assert d_extent == pytest.approx(node_d_extent, abs=0.02)


def test_track_roche_geometry_donor_lobe_swaps_size_across_the_reversal():
    """The Algol reversal, seen in the lobes: donor at cx=0 / companion at cx=1 is fixed
    by IDENTITY (star_1/star_2), never by which currently masses more — so as q=m2/m1
    crosses 1, the lobe that's LARGER swaps from the donor to the companion, at the SAME
    fixed positions. This is the live payoff `roche_geometry`'s one fixed q=0.8 never shows."""
    pre = b.track_roche_geometry([_FakeStep(8.83, 5.30, 24.4)])[0]     # q≈0.6, donor heavier
    post = b.track_roche_geometry([_FakeStep(1.07, 5.94, 29.3)])[0]    # q≈5.55, companion heavier (the demo track's endpoint)

    def extent(lobe):
        return max(p[0] for p in lobe) - min(p[0] for p in lobe)

    assert extent(pre["donor_lobe"]) > extent(pre["companion_lobe"])
    assert extent(post["companion_lobe"]) > extent(post["donor_lobe"])
    # the outlines stay centred on the same fixed positions throughout (0 and 1) —
    # no point strays deep into the far star's well on either side of the reversal
    for g in (pre, post):
        l1 = g["l1_x"]
        assert all(p[0] <= l1 + 0.02 for p in g["donor_lobe"])
        assert all(p[0] >= l1 - 0.02 for p in g["companion_lobe"])


def test_track_roche_geometry_none_on_degenerate_step():
    """A step whose masses/separation can't form a geometry (defensive — shouldn't occur
    on the real bake, `binary_track` already truncates first) returns `None`, not a crash."""
    bad = [_FakeStep(0.0, 5.0, 10.0), _FakeStep(5.0, 5.0, 0.0), _FakeStep(5.0, -1.0, 10.0)]
    assert b.track_roche_geometry(bad) == [None, None, None]
    # a mix of good and bad steps preserves the good one's geometry at its own index
    mixed = b.track_roche_geometry([_FakeStep(0.0, 5.0, 10.0), _FakeStep(8.83, 5.3, 24.4)])
    assert mixed[0] is None
    assert mixed[1] is not None and mixed[1]["m_donor_msun"] == pytest.approx(8.83)


@requires_mist_data
def test_pair_route_carries_roche_and_companion_fits_its_lobe():
    """Through the real route: `/binary_pair` now carries the `roche` geometry block, and
    the modelled companion is COMPACT enough to sit well inside its Roche lobe at RLOF (it
    is a main-sequence star, not yet filling its lobe — only the donor overflows)."""
    c = TestClient(app)
    r = c.get("/binary_pair", params={"mass": 5.45, "feh": 0.0})
    assert r.status_code == 200
    d = r.json()
    g = d["roche"]
    assert set(g) >= {"q", "m_donor_msun", "m_companion_msun", "separation_rsun",
                      "l1_x", "l2_x", "l3_x", "donor_lobe", "companion_lobe", "stream"}
    # the companion's own Eggleton lobe radius (q_c = M2/M1 = 0.8) ≈ 0.36·a; its real
    # modelled radius must be well under that (it is an unbloated MS star)
    a = g["separation_rsun"]
    comp_r = d["companion"]["state"]["R_rsun"]
    assert comp_r < 0.36 * a                               # comfortably inside its lobe


# --- the SED-consistency regression (why we trust the transcribed table) ------

_KPC_CM = 3.0856775814913673e21
_LSUN_ERGS = 3.828e33
_TEFF_SUN = 5772.0
_LOGG_SUN = 4.438


def _sed_logL(model_dir: Path) -> float:
    """log10(L/L_sun) from a Götberg SED (flux at 1 kpc). λ-sorted (CMFGEN concatenates
    frequency bands → file order isn't monotone) and clipped at 5 µm (all real luminosity
    of these hot compact stars is blueward; the clip neutralizes the spurious >5 µm
    free-free tail in the 3.65 M☉ file)."""
    pts = set()
    for line in (model_dir / "SED.txt").read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        a, c = line.split()
        pts.add((float(a), float(c)))
    lam_flx = sorted(pts)
    fbol = 0.0
    for i in range(1, len(lam_flx)):
        lam, flx = lam_flx[i]
        if lam > 50_000.0:
            break
        fbol += 0.5 * (flx + lam_flx[i - 1][1]) * (lam - lam_flx[i - 1][0])
    return math.log10(4.0 * math.pi * _KPC_CM**2 * fbol / _LSUN_ERGS)


def _sed_dir_for(m_init: float) -> Path | None:
    for d in _SED_GRID.iterdir():
        mt = re.match(r"M1_([0-9.]+)q", d.name)
        if mt and abs(float(mt.group(1)) - m_init) < 1e-6:
            return d
    return None


@requires_gotberg_data
def test_table_matches_seds():
    """Every committed Z=0.014 row is self-consistent with its ground-truth SED — the
    check that makes the LLM-transcribed table trustworthy. Measured max |Δ| = 0.070 dex
    (table-L vs SED-L), 0.063 (SB vs SED-L), 0.017 (logg). The bounds are tightened to
    ~0.10 (L) / 0.05 (logg) — headroom over the measured maxima, but tight enough that a
    single-digit transcription slip in a row still trips it. Do not edit a table row
    without re-running this."""
    solar = [m for m in b.available_models() if abs(m.grid_z - 0.014) < 1e-9]
    checked = 0
    for m in solar:
        d = _sed_dir_for(m.m_init)
        assert d is not None, f"no SED dir for M_init={m.m_init}"
        sed_logL = _sed_logL(d)
        sb_logL = math.log10(m.r_eff**2 * (m.teff_kK * 1000.0 / _TEFF_SUN) ** 4)
        calc_logg = _LOGG_SUN + math.log10(m.m_strip) - 2.0 * math.log10(m.r_eff)
        assert abs(m.logL - sed_logL) < 0.10, f"M={m.m_init}: tblL vs sedL = {abs(m.logL - sed_logL):.3f}"
        assert abs(sb_logL - sed_logL) < 0.10, f"M={m.m_init}: SB(Teff,R) vs sedL = {abs(sb_logL - sed_logL):.3f}"
        assert abs(m.logg - calc_logg) < 0.05, f"M={m.m_init}: logg vs (Mstrip,R) = {abs(m.logg - calc_logg):.3f}"
        checked += 1
    assert checked == 23
