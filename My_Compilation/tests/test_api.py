"""
tests/test_api.py — Project ARJUNA (SIH 26170)
Exhaustive integration test suite for all FastAPI REST API routes.
Tests /api/health, /api/status, /api/history (with filtering), /api/events,
/api/inject-fault, /api/reset, /api/set-criticality, /api/lot-stats, and dashboard static files.
"""

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "Backend"))

from Backend.security import ADMIN_KEY, API_KEY
from Backend.server import app

AUTH_HEADERS = {"X-API-Key": API_KEY}
ADMIN_HEADERS = {"X-API-Key": ADMIN_KEY}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_api_health(client):
    """GET /api/health returns 200 OK with operational metadata."""
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert data["project"] == "ARJUNA-SIH-26170"
    assert "timestamp" in data


def test_api_status(client):
    """GET /api/status returns live system state and persistence status."""
    res = client.get("/api/status")
    assert res.status_code == 200
    data = res.json()
    assert "model_loaded" in data
    assert "criticality_level" in data
    assert "current_scenario" in data
    assert "persistence" in data


def test_api_lot_stats(client):
    """GET /api/lot-stats returns lot statistics from trained model."""
    res = client.get("/api/lot-stats")
    assert res.status_code == 200
    data = res.json()
    assert "mean_iddq" in data
    assert "std_iddq" in data
    assert data["mean_iddq"] > 0.0


def test_api_criticality_flow(client):
    """Validates GET /api/criticality and POST /api/set-criticality transition."""
    # 1. Check current criticality
    res = client.get("/api/criticality")
    assert res.status_code == 200
    initial = res.json()
    assert initial["criticality_level"] in (1, 2, 3)

    # 2. Update to Level 3 (Mission-Critical)
    res_update = client.post(
        "/api/set-criticality", json={"criticality_level": 3}, headers=AUTH_HEADERS
    )
    assert res_update.status_code == 200
    data = res_update.json()
    assert data["ok"] is True
    assert data["criticality_level"] == 3
    assert data["label"] == "MISSION-CRITICAL"
    assert data["cusum_threshold"] == 3.5

    # 3. Verify reflected in GET
    res_after = client.get("/api/criticality")
    assert res_after.json()["criticality_level"] == 3

    # 4. Reject invalid criticality level (e.g. 99)
    res_bad = client.post(
        "/api/set-criticality", json={"criticality_level": 99}, headers=AUTH_HEADERS
    )
    assert res_bad.status_code in (400, 422)

    # Reset back to Level 2
    client.post(
        "/api/set-criticality", json={"criticality_level": 2}, headers=AUTH_HEADERS
    )


def test_api_inject_fault_and_reset(client):
    """Validates POST /api/inject-fault and POST /api/reset."""
    # 1. Inject ELECTRICAL_SPIKE
    res_spike = client.post(
        "/api/inject-fault",
        json={"fault_type": "ELECTRICAL_SPIKE"},
        headers=AUTH_HEADERS,
    )
    assert res_spike.status_code == 200
    assert res_spike.json()["ok"] is True
    assert res_spike.json()["fault_type"] == "ELECTRICAL_SPIKE"

    # 2. Inject THERMAL_DRIFT
    res_drift = client.post(
        "/api/inject-fault", json={"event_type": "THERMAL_DRIFT"}, headers=AUTH_HEADERS
    )
    assert res_drift.status_code == 200
    assert res_drift.json()["ok"] is True

    # 3. Reject invalid fault type
    res_invalid = client.post(
        "/api/inject-fault",
        json={"fault_type": "UNKNOWN_ALIEN_RAY"},
        headers=AUTH_HEADERS,
    )
    assert res_invalid.status_code in (400, 422)

    # 4. Reset chamber simulation
    res_reset = client.post("/api/reset", headers=AUTH_HEADERS)
    assert res_reset.status_code == 200
    assert res_reset.json()["ok"] is True


def test_api_history_and_events(client):
    """Validates GET /api/history with fault_type filtering and GET /api/events."""
    # Fetch history
    res_hist = client.get("/api/history?limit=10")
    assert res_hist.status_code == 200
    data = res_hist.json()
    assert isinstance(data, list)

    # Test filtering by fault_type
    res_filtered = client.get("/api/history?fault_type=ELECTRICAL_SPIKE&limit=5")
    assert res_filtered.status_code == 200
    assert isinstance(res_filtered.json(), list)

    # Fetch events
    res_events = client.get("/api/events?limit=10")
    assert res_events.status_code == 200
    assert isinstance(res_events.json(), list)


def test_dashboard_static_assets(client):
    """Validates dashboard HTML and frontend static asset delivery."""
    res_html = client.get("/")
    assert res_html.status_code == 200
    assert "Project ARJUNA" in res_html.text or "ARJUNA" in res_html.text

    res_css = client.get("/styles.css")
    assert res_css.status_code == 200

    res_js = client.get("/script.js")
    assert res_js.status_code == 200
