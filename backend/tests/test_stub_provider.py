"""Sanity checks for the stub, wired from §10 of STAR_SIM_SPEC.md.

These double as a *contract* test: when `MISTProvider` replaces `StubProvider`,
the Sun anchor and the ZAMS-spread expectations should still hold (with tighter
tolerances), so keep them when you swap providers.
"""

from __future__ import annotations

import math

import pytest
from fastapi.testclient import TestClient

from star_sim.api import app
from star_sim.provider import ParameterOutOfRange, StellarStateProvider
from star_sim.providers import StubProvider

SUN_AGE_YR = 4.6e9


@pytest.fixture
def provider() -> StubProvider:
    return StubProvider()


def test_stub_satisfies_provider_protocol(provider):
    # runtime_checkable Protocol: structural conformance to the §3 boundary.
    assert isinstance(provider, StellarStateProvider)


def test_sun_anchor(provider):
    """1 M_sun, [Fe/H]=0 at ~4.6 Gyr renders the Sun (§10)."""
    st = provider.state_at(1.0, 0.0, SUN_AGE_YR)
    assert st.L_lsun == pytest.approx(1.0, rel=1e-6)
    assert st.Teff_K == pytest.approx(5772.0, abs=1.0)
    assert st.R_rsun == pytest.approx(1.0, rel=1e-6)
    assert st.logg == pytest.approx(4.438, abs=0.01)


def test_composition_sums_to_one(provider):
    st = provider.state_at(1.0, 0.0, SUN_AGE_YR)
    assert st.X_surf + st.Y_surf + st.Z_surf == pytest.approx(1.0, abs=1e-9)
    assert st.X_core + st.Y_core + st.Z_core == pytest.approx(1.0, abs=1e-9)


def test_zams_spread_is_dramatic(provider):
    """Across the mass range, L spans ~9 orders and Teff sweeps red->blue (§10)."""
    lo = provider.state_at(0.1, 0.0, 0.0)
    hi = provider.state_at(40.0, 0.0, 0.0)
    orders = math.log10(hi.L_lsun) - math.log10(lo.L_lsun)
    assert orders > 8.0
    assert lo.Teff_K < 3500.0   # cool red dwarf
    assert hi.Teff_K > 30000.0  # hot blue O star


def test_luminosity_monotonic_in_mass(provider):
    masses = [0.2, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0]
    lums = [provider.state_at(m, 0.0, 0.0).L_lsun for m in masses]
    assert lums == sorted(lums)


def test_core_hydrogen_depletes_with_age(provider):
    young = provider.state_at(1.0, 0.0, 0.0)
    old = provider.state_at(1.0, 0.0, young_max := provider.age_range(1.0, 0.0)[1])
    assert old.X_core < young.X_core
    assert old.eep > young.eep
    assert young_max > 0.0


def test_out_of_range_raises(provider):
    with pytest.raises(ParameterOutOfRange):
        provider.state_at(1000.0, 0.0, 0.0)
    with pytest.raises(ParameterOutOfRange):
        provider.state_at(1.0, 9.0, 0.0)


# --- API round-trip: payload is exactly the StellarState shape ---------------

EXPECTED_KEYS = {
    "age_yr", "eep", "phase", "mass_init_msun", "feh_init",
    "L_lsun", "Teff_K", "R_rsun", "logg",
    "X_surf", "Y_surf", "Z_surf", "X_core", "Y_core", "Z_core",
    "v_rot_kms", "activity",
}


def test_api_state_payload_is_stellarstate_shape():
    client = TestClient(app)
    resp = client.get("/state", params={"mass": 1.0, "feh": 0.0, "age": SUN_AGE_YR})
    assert resp.status_code == 200
    assert set(resp.json().keys()) == EXPECTED_KEYS


def test_api_out_of_range_is_422():
    client = TestClient(app)
    resp = client.get("/state", params={"mass": 999.0, "feh": 0.0, "age": 0.0})
    assert resp.status_code == 422


def test_api_health_and_ranges():
    client = TestClient(app)
    assert client.get("/health").json()["status"] == "ok"
    rng = client.get("/ranges").json()
    assert "mass_msun" in rng and "feh" in rng
