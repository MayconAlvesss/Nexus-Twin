"""
NexusTwin — API Integration Tests
=====================================
FastAPI TestClient-based integration tests that exercise each router endpoint.

These tests use TestClient (synchronous httpx client) which runs the full
ASGI stack in-process — no server needed. The database is overridden with
an in-memory SQLite test fixture so tests are fully isolated and fast.

Run:
    pytest tests/test_api_integration.py -v
"""

import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.dependencies import get_db
from database.twin_db import TwinDBManager

# ---------------------------------------------------------------------------
# Test DB fixture — in-memory SQLite, reset between test classes
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def test_db():
    """
    Create a fresh in-memory TwinDBManager for the test session.
    Using scope='module' so the DB accumulates state within a test class
    (which mirrors how the real app works: elements registered before compute).
    """
    import asyncio
    db = TwinDBManager(":memory:")
    asyncio.get_event_loop().run_until_complete(db.connect())
    yield db
    asyncio.get_event_loop().run_until_complete(db.disconnect())


@pytest.fixture(scope="module")
def client(test_db):
    """
    TestClient with the DB dependency overridden to use the in-memory fixture.
    The API key header is pre-set to the default dev key.
    """
    app.dependency_overrides[get_db] = lambda: test_db

    with TestClient(app, raise_server_exceptions=True) as c:
        c.headers.update({"X-NexusTwin-API-Key": "nexus-dev-key-change-me"})
        yield c

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Root health-check
# ---------------------------------------------------------------------------

def test_root_returns_online(client) -> None:
    """GET / must return 200 with status='NexusTwin Online'."""
    resp = client.get("/")
    assert resp.status_code == 200
    data = resp.json()
    assert "NexusTwin Online" in data["status"]


# ---------------------------------------------------------------------------
# Elements endpoint
# ---------------------------------------------------------------------------

class TestElementsEndpoint:

    def test_register_element_success(self, client) -> None:
        resp = client.post("/api/v1/elements", json={
            "element_id":     "TEST-COL-001",
            "name":           "Test Column 1",
            "element_type":   "COLUMN",
            "material_class": "concrete",
            "age_years":      5.0,
            "floor_level":    "L1",
        })
        assert resp.status_code == 201
        assert resp.json()["element_id"] == "TEST-COL-001"

    def test_register_invalid_element_type_fails(self, client) -> None:
        resp = client.post("/api/v1/elements", json={
            "element_id":     "TEST-BAD",
            "name":           "Bad Element",
            "element_type":   "INVALID_TYPE",
            "material_class": "concrete",
        })
        assert resp.status_code == 422

    def test_list_elements_returns_registered(self, client) -> None:
        resp = client.get("/api/v1/elements")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] >= 1
        ids = [e["element_id"] for e in data["elements"]]
        assert "TEST-COL-001" in ids

    def test_get_element_detail(self, client) -> None:
        resp = client.get("/api/v1/elements/TEST-COL-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["element"]["element_type"] == "COLUMN"
        assert data["element"]["material_class"] == "concrete"

    def test_get_missing_element_returns_404(self, client) -> None:
        resp = client.get("/api/v1/elements/DOES-NOT-EXIST")
        assert resp.status_code == 404

    def test_no_api_key_returns_401(self, client) -> None:
        resp = client.get(
            "/api/v1/elements",
            headers={"X-NexusTwin-API-Key": "wrong-key"}
        )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Structural Health endpoint
# ---------------------------------------------------------------------------

class TestHealthEndpoint:

    def test_compute_shi_healthy_element(self, client) -> None:
        """Healthy sensor readings should produce SHI ≥ 65 and HEALTHY status."""
        resp = client.post("/api/v1/health/compute", json={
            "element_id":           "TEST-COL-001",
            "strain_readings":      [100.0] * 30,
            "vibration_readings":   [1.0] * 30,
            "temperature_readings": [22.0] * 30,
            "miner_damage_ratio":   0.0,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["shi_score"] >= 65.0
        assert data["status"] == "HEALTHY"

    def test_compute_shi_unknown_element_returns_404(self, client) -> None:
        resp = client.post("/api/v1/health/compute", json={
            "element_id":           "NONEXISTENT",
            "strain_readings":      [100.0] * 10,
            "vibration_readings":   [1.0] * 10,
            "temperature_readings": [22.0] * 10,
        })
        assert resp.status_code == 404

    def test_shi_history_is_populated_after_compute(self, client) -> None:
        resp = client.get("/api/v1/health/TEST-COL-001/history?limit=10")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] >= 1   # we just computed above


# ---------------------------------------------------------------------------
# Fatigue endpoint
# ---------------------------------------------------------------------------

class TestFatigueEndpoint:

    def test_compute_fatigue_returns_safe(self, client) -> None:
        resp = client.post("/api/v1/fatigue/compute", json={
            "element_id":     "TEST-COL-001",
            "material_class": "concrete",
            "stress_blocks": [
                {"stress_range_mpa": 10.0, "cycle_count": 1000},
            ],
            "element_age_years": 5.0,
        })
        assert resp.status_code == 200
        data = resp.json()
        # Very low stress — should be SAFE
        assert data["status"] == "SAFE"
        assert data["damage_ratio"] >= 0.0
        assert 0.0 <= data["remaining_life_pct"] <= 100.0

    def test_compute_fatigue_zero_blocks(self, client) -> None:
        """Empty stress_blocks list should return D=0, SAFE."""
        resp = client.post("/api/v1/fatigue/compute", json={
            "element_id":     "TEST-COL-001",
            "material_class": "steel",
            "stress_blocks":  [],
        })
        assert resp.status_code == 200
        assert resp.json()["damage_ratio"] == 0.0


# ---------------------------------------------------------------------------
# Simulation endpoint (no auth required)
# ---------------------------------------------------------------------------

class TestSimulationEndpoint:

    def test_register_and_tick(self, client) -> None:
        # Register sensor suite
        resp = client.post("/api/v1/simulate/register?element_id=TEST-COL-001")
        assert resp.status_code == 200
        assert "strain" in resp.json()["sensors"]

        # Request one tick
        resp = client.post("/api/v1/simulate/tick?element_id=TEST-COL-001")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["readings"]) == 3   # strain + vibration + temperature

    def test_tick_unknown_element_returns_404(self, client) -> None:
        resp = client.post("/api/v1/simulate/tick?element_id=GHOST-ELEM")
        assert resp.status_code == 404
