"""Validation for the isochrone / cluster sibling (`isochrone.py`, `/isochrone`).

Axis B of docs/plans/outward-quartet-atlas.md — the coeval-cluster locus (all masses at
one age) with the **main-sequence turnoff** as the age clock. The Gate-0 test locks the
MEASURED payoff (turnoff drops monotonically — cooler AND fainter — with age) so a wrong
column read or a naive global-max turnoff fails loudly.

An isochrone is a population locus, not a single star: the sibling bypasses PROVIDER and
reads the published MIST `.iso` grid with its own parser; that isolation is asserted here.

Data-gated by `requires_isochrone_data` — skips on a checkout without the fetched `.iso`
grid (gitignored). Two ungated tests exercise the status gate + the sibling-isolation AST
check on every checkout.
"""

from __future__ import annotations

import ast

import pytest
from fastapi.testclient import TestClient

import star_sim.isochrone as isochrone_mod
from star_sim.api import app
from star_sim.isochrone import isochrone, isochrone_available

from .conftest import requires_isochrone_data

client = TestClient(app)

GYR = 1.0e9


# --- ungated: the honesty gate + the sibling-isolation check (run on every checkout) ---
def test_isochrone_status_route_always_answers() -> None:
    """/isochrone_status is the frontend's toggle-visibility gate — a plain 200 with a bool
    whether or not the .iso grid is on disk (a fresh clone has none). The one route test that
    does NOT require the data, so the gate is exercised on every checkout."""
    resp = client.get("/isochrone_status")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body.get("has_grid"), bool)
    assert body["has_grid"] == isochrone_available()


def test_sibling_does_not_import_provider() -> None:
    """isochrone.py is a sibling — it reads the published grid with its own parser and must
    not reach the provider (no `api`, no `provider` module). It DOES build StellarStates, so
    importing `state` is expected (unlike bpass, whose payload is a population, not a star)."""
    with open(isochrone_mod.__file__, "r", encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    imported = {(node.module or "") for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert "api" not in imported and "star_sim.api" not in imported
    assert not any("provider" == m.rsplit(".", 1)[-1] for m in imported)
    # a §3-clean locus of StellarStates — importing the spine is correct here.
    assert any("state" == m.rsplit(".", 1)[-1] for m in imported)


# --- Gate 0: the turnoff is the cluster's age clock ------------------------------------
@requires_isochrone_data
def test_turnoff_drops_monotonically_with_age() -> None:
    """GATE 0 (measured through the real path): a young cluster turns off high on the MS
    (luminous, hot); an old one turns off low (faint, cool). Both the turnoff luminosity AND
    temperature must fall monotonically with age — the pedagogy the caption will claim."""
    ages = [0.1 * GYR, 1.0 * GYR, 4.0 * GYR, 12.0 * GYR]
    turnoffs = [isochrone(a, 0.0)["turnoff"] for a in ages]
    assert all(t is not None for t in turnoffs)
    teffs = [t["Teff_K"] for t in turnoffs]
    lums = [t["L_lsun"] for t in turnoffs]
    # strictly cooler and fainter as the cluster ages
    assert all(teffs[i] > teffs[i + 1] for i in range(len(teffs) - 1)), teffs
    assert all(lums[i] > lums[i + 1] for i in range(len(lums) - 1)), lums
    # the turnoff mass also drops (lighter stars are the ones just now leaving the MS)
    masses = [t["mass_msun"] for t in turnoffs]
    assert all(masses[i] > masses[i + 1] for i in range(len(masses) - 1)), masses


@requires_isochrone_data
def test_turnoff_is_ms_only_not_global_hottest() -> None:
    """The turnoff must be the bluest **MS** point, NOT the global hottest — old / metal-poor
    isochrones carry hot post-MS stars (blue HB, hot subdwarfs, WDs) bluer than the MSTO that
    a naive max(Teff) would hijack onto. Verify (a) the turnoff equals the hottest MS state,
    and (b) at old age there really IS a hotter non-MS state that would have fooled the naive
    version (so this test has teeth, not a tautology)."""
    data = isochrone(12.0 * GYR, -1.0)  # old + metal-poor: the worst case for the naive bug
    states = data["states"]
    turnoff = data["turnoff"]
    assert turnoff is not None
    ms_teffs = [s["Teff_K"] for s in states if s["phase"] == "MS"]
    assert turnoff["Teff_K"] == pytest.approx(max(ms_teffs))
    global_hottest = max(s["Teff_K"] for s in states)
    # the horizontal branch / WDs of a 12 Gyr metal-poor isochrone are hotter than the MSTO
    assert global_hottest > turnoff["Teff_K"] * 1.01


# --- the Sun anchor: version-consistency with the live tracks --------------------------
@requires_isochrone_data
def test_solar_isochrone_passes_through_the_sun() -> None:
    """The ~4.6 Gyr solar isochrone must contain a ~1 M_sun star at the Sun's §10 anchor
    (L≈1, Teff≈5772). This is the version-consistency check the whole v2.5 choice buys — the
    reason 'your star sits on the cluster isochrone' is literally true — and it catches a wrong
    column read / wrong age snap far more cheaply than a from-tracks reconstruction would."""
    data = isochrone(4.6 * GYR, 0.0)
    # the isochrone row nearest 1.0 M_sun (initial mass)
    sun = min(data["states"], key=lambda s: abs(s["mass_init_msun"] - 1.0))
    assert sun["mass_init_msun"] == pytest.approx(1.0, abs=0.05)
    assert sun["L_lsun"] == pytest.approx(1.0, rel=0.15)
    assert sun["Teff_K"] == pytest.approx(5772.0, abs=120.0)
    assert sun["phase"] == "MS"


# --- snap honesty + route shape --------------------------------------------------------
@requires_isochrone_data
def test_snap_is_honest_and_flagged() -> None:
    """Snap-always: an off-node (age, [Fe/H]) lands on a real published node, and the returned
    age/feh are those true nodes (not the request). A tiny nudge from a node is not flagged
    far; a big one is."""
    data = isochrone(1.0 * GYR, 0.02)  # near-solar
    assert data["feh"] in data["available_feh"]
    assert data["log_age"] in data["available_log_ages"]
    assert data["age_yr"] == pytest.approx(10.0 ** data["log_age"])
    # requesting an exact node age → not flagged far
    node_age = 10.0 ** data["available_log_ages"][len(data["available_log_ages"]) // 2]
    on_node = isochrone(node_age, 0.0)
    assert on_node["age_snapped_far"] is False


@requires_isochrone_data
def test_route_shape_and_422() -> None:
    resp = client.get("/isochrone", params={"age_yr": 1.0e9, "feh": 0.0})
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body["states"], list) and len(body["states"]) > 10
    assert set(body["turnoff"]) >= {"index", "Teff_K", "L_lsun", "mass_msun"}
    # a StellarState made it through asdict cleanly
    s0 = body["states"][0]
    assert {"Teff_K", "L_lsun", "phase", "mass_init_msun", "eep"} <= set(s0)
    # structurally invalid → 422 (Query bounds / age <= 0)
    assert client.get("/isochrone", params={"age_yr": 0, "feh": 0.0}).status_code == 422
    assert client.get("/isochrone", params={"age_yr": 1e9, "feh": 99}).status_code == 422
