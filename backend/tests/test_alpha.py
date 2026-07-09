"""Validation for the α-enhanced (equivalent-Z) what-if overlay sibling (`alpha.py`, `/alpha`).

Phase 3 of docs/plans/tempered-lineage-inspiral.md. The feature exists to show the
α-enhanced-population effect: at fixed [Fe/H], boosting [α/Fe] raises the true total
metallicity Z (Salaris 1993 equivalent-Z), so at fixed mass the track is **cooler
(redder), slightly fainter, and longer-lived** than the scaled-solar baseline — the
**opposite sign** from the initial-He effect (Phase 2). These tests lock that MEASURED
physics (Gate 3) so a re-bake or a parser change that silently flattens or flips it fails
loudly.

The comparison is baseline-vs-enhanced, both self-run MESA, only the equivalent Z
differing — NEVER against the MIST spine (that would conflate the effect with the
MESA-vs-MIST systematic). So the sibling must not import PROVIDER; that isolation is
asserted here too.

Data-gated by `requires_alpha_data` — skips on a checkout without the offline MESA runs
(they're never committed; generate them per backend/docs/mesa_alpha_recipe.md).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from star_sim.api import app
from star_sim.alpha import alpha_available, alpha_overlay
from star_sim.state import StellarState

from .conftest import requires_alpha_data

client = TestClient(app)


# --- the data-availability honesty gate (UNGATED — must answer even with no data) ---
def test_alpha_status_route_always_answers() -> None:
    """/alpha_status is the frontend's toggle-visibility gate — it must be a plain 200 with a
    boolean whether or not the MESA runs are on disk (a fresh clone has none). This is the one
    test here that does NOT require the data, so the gate is exercised on every checkout."""
    resp = client.get("/alpha_status")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body.get("has_grid"), bool)
    assert body["has_grid"] == alpha_available()


# The masses the batch ships (backend/docs/mesa_alpha_recipe.md §0).
_GRID_MASSES = [1.0, 2.0, 6.0]


# --- Gate 3: the measured equivalent-Z physics -------------------------------
@requires_alpha_data
@pytest.mark.parametrize("mass", _GRID_MASSES)
def test_enhanced_is_cooler_fainter_longer_lived(mass: float) -> None:
    """The whole feature, per mass: the α-enhanced (higher equivalent-Z) ZAMS is cooler
    + fainter, and its main-sequence lifetime is longer — same inlist, only the
    equivalent total Z differs. This is the opposite sign from the He effect."""
    r = alpha_overlay(mass)
    base, enh = r["baseline"], r["enhanced"]

    # It really is the same star but for the equivalent Z: snapped to the exact grid
    # mass, and the enhanced member carries the higher initial metallicity.
    assert r["mass_snapped"] == mass
    assert enh["z_init"] > base["z_init"]
    assert enh["mh"] > base["mh"]

    assert enh["zams"]["teff_k"] < base["zams"]["teff_k"], "α-enhanced must be cooler at ZAMS"
    assert enh["zams"]["l_lsun"] < base["zams"]["l_lsun"], "α-enhanced must be fainter at ZAMS"
    assert enh["tau_ms_gyr"] > base["tau_ms_gyr"], "α-enhanced must be longer-lived"


@requires_alpha_data
def test_enhanced_z_and_derived_alpha_fe_match_the_recipe() -> None:
    """The pair is the scaled-solar vs. [α/Fe]≈+0.4 equivalent-Z range, and the served
    [α/Fe] is *derived* from the measured Z ratio (inverted Salaris), not hardcoded —
    so it must land near the +0.4 the recipe targeted."""
    r = alpha_overlay(1.0)
    # baseline ~ solar Z=0.0152; enhanced ~ 0.0152*1.9646 = 0.0299 (Salaris [α/Fe]=+0.4)
    assert r["baseline"]["z_init"] == pytest.approx(0.0152, abs=0.001)
    assert r["enhanced"]["z_init"] == pytest.approx(0.0299, abs=0.001)
    # the equivalent [M/H] of the enhanced run is ~ +0.29 (log10(1.9646))
    assert r["enhanced"]["mh"] == pytest.approx(0.293, abs=0.02)
    # the data-derived [α/Fe] recovers the targeted +0.4 (a real, sizeable enhancement)
    assert r["alpha_fe"] == pytest.approx(0.4, abs=0.03)
    assert r["alpha_fe"] > 0.2


# --- the track blocks are real §3 StellarStates ------------------------------
@requires_alpha_data
def test_states_are_valid_stellar_states() -> None:
    """Each track row round-trips into a StellarState with sane, on-MS-and-beyond values.
    The overlay consumers (HR) read these exactly like a /track payload."""
    r = alpha_overlay(2.0)
    for member in ("baseline", "enhanced"):
        states = r[member]["states"]
        assert len(states) >= 2
        for s in states:
            st = StellarState(**s)          # exact §3 shape — constructs or raises
            assert st.Teff_K > 0 and st.L_lsun > 0 and st.R_rsun > 0
            assert 0.0 <= st.Z_surf <= 1.0
        # the ZAMS scalars match the served track's first row (no drift)
        assert r[member]["zams"]["teff_k"] == pytest.approx(states[0]["Teff_K"])
        assert r[member]["zams"]["l_lsun"] == pytest.approx(states[0]["L_lsun"])


# --- snap-always honesty ------------------------------------------------------
@requires_alpha_data
def test_snap_is_honest_and_flagged() -> None:
    """Out-of-grid mass snaps to the nearest node and is flagged in-band (never 422'd),
    reporting the TRUE snapped mass — the /helium + /structure snap-always contract."""
    exact = alpha_overlay(6.0)
    assert exact["mass_snapped"] == 6.0 and exact["mass_snapped_far"] is False

    far = alpha_overlay(3.5)               # nearest grid node is 2.0 (|3.5-2|>0.25*2)
    assert far["mass_snapped"] == 2.0 and far["mass_snapped_far"] is True
    assert far["mass_requested"] == 3.5


# --- the route ----------------------------------------------------------------
@requires_alpha_data
def test_route_shape_and_422() -> None:
    resp = client.get("/alpha", params={"mass": 2.0})
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) >= {"mass_requested", "mass_snapped", "mass_snapped_far",
                         "alpha_fe", "baseline", "enhanced"}
    for member in ("baseline", "enhanced"):
        assert set(body[member]) >= {"z_init", "mh", "tau_ms_gyr", "zams", "states"}
        assert isinstance(body[member]["states"], list) and body[member]["states"]

    # 422 is reserved for structurally-invalid mass (the Query gt=0 bound).
    assert client.get("/alpha", params={"mass": 0}).status_code == 422
    assert client.get("/alpha", params={"mass": -1}).status_code == 422


# --- the §3 boundary: the sibling never routes through PROVIDER ---------------
@requires_alpha_data
def test_sibling_does_not_import_provider() -> None:
    """alpha.py emits StellarState directly (like helium.py/binary.py) — it must not reach
    the provider, or the honesty rule ("never vs. the MIST spine") is at risk. It reuses
    only the MESA parser's free helpers."""
    import ast

    import star_sim.alpha as alpha

    with open(alpha.__file__, "r", encoding="utf-8") as fh:
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
    # the only providers.mesa symbols it pulls are the free parsing helpers
    from_mesa = {
        n.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and (node.module or "").endswith("providers.mesa")
        for n in node.names
    }
    assert from_mesa <= {"_MesaTrack", "_build_track", "_state_from_track"}
    assert "MISTProvider" not in from_mesa
