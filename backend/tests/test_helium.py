"""Validation for the initial-helium (Y) what-if overlay sibling (`helium.py`, `/helium`).

Phase 2 of docs/plans/tempered-lineage-inspiral.md. The feature exists to show the
globular-cluster second-generation effect: at fixed mass/[Fe/H], a He-enhanced star
(Y≈0.40) is **hotter, brighter, and shorter-lived** than a primordial-Y one (Y≈0.27) —
the horizontal-branch "second-parameter" story. These tests lock that MEASURED physics
(Gate 2) so a re-bake or a parser change that silently flattens it fails loudly.

The comparison is baseline-vs-enhanced, both self-run MESA, only Y differing — NEVER
against the MIST spine (that would conflate the He effect with the MESA-vs-MIST
systematic). So the sibling must not import PROVIDER; that isolation is asserted here too.

Data-gated by `requires_helium_data` — skips on a checkout without the offline MESA
runs (they're never committed; generate them per backend/docs/mesa_helium_recipe.md).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from star_sim.api import app
from star_sim.helium import helium_available, helium_overlay
from star_sim.state import StellarState

from .conftest import requires_helium_data

client = TestClient(app)


# --- the data-availability honesty gate (UNGATED — must answer even with no data) ---
def test_helium_status_route_always_answers() -> None:
    """/helium_status is the frontend's toggle-visibility gate — it must be a plain 200 with a
    boolean whether or not the MESA runs are on disk (a fresh clone has none). This is the one
    test here that does NOT require the data, so the gate is exercised on every checkout."""
    resp = client.get("/helium_status")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body.get("has_grid"), bool)
    assert body["has_grid"] == helium_available()


# The masses the batch ships (backend/docs/mesa_helium_recipe.md §0).
_GRID_MASSES = [1.0, 2.0, 6.0]


# --- Gate 2: the measured second-parameter physics ---------------------------
@requires_helium_data
@pytest.mark.parametrize("mass", _GRID_MASSES)
def test_enhanced_is_bluer_brighter_shorter_lived(mass: float) -> None:
    """The whole feature, per mass: He-enhanced ZAMS is hotter + more luminous, and
    its main-sequence lifetime is shorter — same inlist, only initial Y differs."""
    r = helium_overlay(mass)
    base, enh = r["baseline"], r["enhanced"]

    # It really is the same star but for Y: the pair snapped to the exact grid mass,
    # and the enhanced member carries the higher initial helium.
    assert r["mass_snapped"] == mass
    assert enh["y_init"] > base["y_init"]

    assert enh["zams"]["teff_k"] > base["zams"]["teff_k"], "enhanced-Y must be bluer at ZAMS"
    assert enh["zams"]["l_lsun"] > base["zams"]["l_lsun"], "enhanced-Y must be brighter at ZAMS"
    assert enh["tau_ms_gyr"] < base["tau_ms_gyr"], "enhanced-Y must be shorter-lived"


@requires_helium_data
def test_enhanced_and_baseline_helium_are_the_observed_range() -> None:
    """The pair is the primordial vs. NGC 2808 range (not two indistinguishable runs)."""
    r = helium_overlay(1.0)
    assert r["baseline"]["y_init"] == pytest.approx(0.2704, abs=0.01)
    assert r["enhanced"]["y_init"] == pytest.approx(0.40, abs=0.01)
    # ΔY is the physics knob; a real, sizeable enhancement (the bluest-MS extreme).
    assert r["enhanced"]["y_init"] - r["baseline"]["y_init"] > 0.05


# --- the track blocks are real §3 StellarStates ------------------------------
@requires_helium_data
def test_states_are_valid_stellar_states() -> None:
    """Each track row round-trips into a StellarState with sane, on-MS-and-beyond values.
    The overlay consumers (HR/comp) read these exactly like a /track payload."""
    r = helium_overlay(2.0)
    for member in ("baseline", "enhanced"):
        states = r[member]["states"]
        assert len(states) >= 2
        for s in states:
            st = StellarState(**s)          # exact §3 shape — constructs or raises
            assert st.Teff_K > 0 and st.L_lsun > 0 and st.R_rsun > 0
            assert 0.0 <= st.Y_surf <= 1.0
        # the ZAMS scalars match the served track's first row (no drift)
        assert r[member]["zams"]["teff_k"] == pytest.approx(states[0]["Teff_K"])
        assert r[member]["zams"]["l_lsun"] == pytest.approx(states[0]["L_lsun"])


# --- snap-always honesty ------------------------------------------------------
@requires_helium_data
def test_snap_is_honest_and_flagged() -> None:
    """Out-of-grid mass snaps to the nearest node and is flagged in-band (never 422'd),
    reporting the TRUE snapped mass — the /structure + /binary snap-always contract."""
    exact = helium_overlay(6.0)
    assert exact["mass_snapped"] == 6.0 and exact["mass_snapped_far"] is False

    far = helium_overlay(3.5)               # nearest grid node is 2.0 (|3.5-2|>0.25*2)
    assert far["mass_snapped"] == 2.0 and far["mass_snapped_far"] is True
    assert far["mass_requested"] == 3.5


# --- the route ----------------------------------------------------------------
@requires_helium_data
def test_route_shape_and_422() -> None:
    resp = client.get("/helium", params={"mass": 2.0})
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) >= {"mass_requested", "mass_snapped", "mass_snapped_far",
                         "baseline", "enhanced"}
    for member in ("baseline", "enhanced"):
        assert set(body[member]) >= {"y_init", "tau_ms_gyr", "zams", "states"}
        assert isinstance(body[member]["states"], list) and body[member]["states"]

    # 422 is reserved for structurally-invalid mass (the Query gt=0 bound).
    assert client.get("/helium", params={"mass": 0}).status_code == 422
    assert client.get("/helium", params={"mass": -1}).status_code == 422


# --- the §3 boundary: the sibling never routes through PROVIDER ---------------
@requires_helium_data
def test_sibling_does_not_import_provider() -> None:
    """helium.py emits StellarState directly (like binary.py/structure.py) — it must
    not reach the provider, or the honesty rule ("never vs. the MIST spine") is at risk.
    It reuses only the MESA parser's free helpers."""
    import ast

    import star_sim.helium as helium

    with open(helium.__file__, "r", encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    imported = {
        (node.module or "")
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    # It reuses the MESA parser (a sibling helper) but never the provider entry point:
    # no `from .api import ...` (where PROVIDER lives) and no provider construction.
    assert "api" not in imported and "star_sim.api" not in imported
    assert not any("provider" == m.rsplit(".", 1)[-1] for m in imported)
    # the only providers.mesa symbols it pulls are the two free parsing helpers
    from_mesa = {
        n.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and (node.module or "").endswith("providers.mesa")
        for n in node.names
    }
    assert from_mesa <= {"_MesaTrack", "_build_track", "_state_from_track"}
    assert "MISTProvider" not in from_mesa
