"""
tests/test_security.py — Project ARJUNA (SIH 26170)
Automated Security, Authentication, RBAC, and Rate-Limiting Test Suite.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from Backend.security import ADMIN_KEY, API_KEY, QA_KEY, VIEWER_KEY, resolve_role_from_key
from Backend.server import app


def test_production_fails_closed_with_default_keys():
    """In production, default dev keys must cause a hard startup failure (fail-closed)."""
    root = Path(__file__).resolve().parent.parent
    env = dict(os.environ)
    env["ENVIRONMENT"] = "production"
    # Ensure no override keys are set so the defaults are exercised.
    for k in ("ARJUNA_API_KEY", "ARJUNA_ADMIN_KEY", "ARJUNA_QA_KEY", "ARJUNA_VIEWER_KEY"):
        env.pop(k, None)
    proc = subprocess.run(
        [sys.executable, "-c", "import sys; sys.path.insert(0,'.'); sys.path.insert(0,'Backend'); import security"],
        cwd=str(root),
        env=env,
        capture_output=True,
        text=True,
    )
    assert proc.returncode != 0, "production with default keys must fail to import"
    assert "FATAL: Default hardcoded API keys" in (proc.stdout + proc.stderr)


def test_development_warns_not_fails_with_default_keys():
    """In development, default keys produce a warning but must not hard-fail."""
    root = Path(__file__).resolve().parent.parent
    env = dict(os.environ)
    env["ENVIRONMENT"] = "development"
    for k in ("ARJUNA_API_KEY", "ARJUNA_ADMIN_KEY", "ARJUNA_QA_KEY", "ARJUNA_VIEWER_KEY"):
        env.pop(k, None)
    proc = subprocess.run(
        [sys.executable, "-c", "import sys; sys.path.insert(0,'.'); sys.path.insert(0,'Backend'); import security; print('OK')"],
        cwd=str(root),
        env=env,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert "OK" in proc.stdout


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_public_endpoints_accessible_without_auth(client):
    """Verify read-only endpoints are accessible to public viewers."""
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/status").status_code == 200
    assert client.get("/api/history").status_code == 200
    assert client.get("/api/events").status_code == 200
    assert client.get("/api/criticality").status_code == 200


def test_role_resolution_hierarchy():
    """Verify RBAC role resolution from configured key tokens."""
    assert resolve_role_from_key(ADMIN_KEY) == "admin"
    assert resolve_role_from_key(API_KEY) == "operator"
    assert resolve_role_from_key(QA_KEY) == "qa_inspector"
    assert resolve_role_from_key(VIEWER_KEY) == "viewer"
    assert resolve_role_from_key("unrecognized_key_123") is None


def test_operator_endpoint_with_valid_api_key_header(client):
    """Verify operator endpoints succeed with valid X-API-Key."""
    headers = {"X-API-Key": API_KEY}
    resp = client.post(
        "/api/inject-fault", json={"event_type": "THERMAL_DRIFT"}, headers=headers
    )
    assert resp.status_code == 200
    assert resp.json()["scenario"] == "thermal_drift"

    reset_resp = client.post("/api/reset", headers=headers)
    assert reset_resp.status_code == 200


def test_operator_endpoint_with_valid_bearer_token(client):
    """Verify operator endpoints succeed with valid Authorization Bearer token."""
    headers = {"Authorization": f"Bearer {API_KEY}"}
    resp = client.post(
        "/api/set-criticality", json={"criticality_level": 3}, headers=headers
    )
    assert resp.status_code == 200
    assert resp.json()["criticality_level"] == 3


def test_operator_endpoint_with_invalid_key_rejected(client):
    """Verify invalid API keys receive HTTP 403 Forbidden."""
    headers = {"X-API-Key": "completely-invalid-secret-key"}
    resp = client.post(
        "/api/inject-fault", json={"event_type": "ELECTRICAL_SPIKE"}, headers=headers
    )
    assert resp.status_code == 403
    assert "Invalid credentials" in resp.json()["detail"]


def test_operator_endpoint_with_empty_key_rejected(client):
    """Verify empty/blank keys receive HTTP 401 Unauthorized."""
    headers = {"X-API-Key": ""}
    resp = client.post(
        "/api/inject-fault", json={"event_type": "ELECTRICAL_SPIKE"}, headers=headers
    )
    assert resp.status_code == 401


def test_cors_headers_configured(client):
    """Verify CORS middleware responds with correct headers on pre-flight."""
    headers = {
        "Origin": "http://127.0.0.1:8000",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "X-API-Key, Content-Type",
    }
    resp = client.options("/api/inject-fault", headers=headers)
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == "http://127.0.0.1:8000"


def test_websocket_handshake_security(client):
    """Verify WebSocket handshake enforces token authorization."""
    # Invalid token must be closed with code 1008
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect("/ws?token=invalid-key-attempt") as ws:
            ws.receive_json()
    assert exc.value.code == 1008

    # Valid token connects smoothly
    with client.websocket_connect(f"/ws?token={API_KEY}") as ws:
        frame = ws.receive_json()
        assert "voltage" in frame
