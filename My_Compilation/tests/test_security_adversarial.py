"""
tests/test_security_adversarial.py — Project ARJUNA (SIH 26170)

Adversarial security verification suite:
- Remote host spoofing attacks (Host, Origin, Referer) attempting local bypass
- Fail-closed configuration tests (ARJUNA_ENV=production)
- Full REST RBAC matrix (viewer, qa_inspector, operator, admin)
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "Backend"))

from Backend.security import ADMIN_KEY, API_KEY, QA_KEY, VIEWER_KEY
from Backend.server import app

client = TestClient(app)


def test_remote_client_spoofed_host_cannot_bypass_auth():
    """A remote IP sending Host: localhost must NOT receive local development bypass."""
    remote_client = TestClient(app, client=("198.51.100.45", 54321))
    resp = remote_client.post(
        "/api/reset",
        headers={"Host": "localhost:8000"},
    )
    # Must be 401 Unauthorized (missing credentials), NOT 200
    assert resp.status_code == 401, (
        f"Remote client with spoofed Host obtained local bypass: status={resp.status_code}"
    )


def test_remote_client_spoofed_origin_cannot_bypass_auth():
    """A remote IP sending Origin: http://localhost:8000 must NOT receive local bypass."""
    remote_client = TestClient(app, client=("203.0.113.88", 43210))
    resp = remote_client.post(
        "/api/inject-fault",
        json={"event_type": "THERMAL_DRIFT"},
        headers={"Origin": "http://localhost:8000"},
    )
    assert resp.status_code == 401, (
        f"Remote client with spoofed Origin obtained local bypass: status={resp.status_code}"
    )


def test_arjuna_env_production_fails_closed_with_default_keys():
    """ARJUNA_ENV=production with default keys must hard-fail at import time."""
    env = dict(os.environ)
    env["ARJUNA_ENV"] = "production"
    for k in ("ARJUNA_API_KEY", "ARJUNA_ADMIN_KEY", "ARJUNA_QA_KEY", "ARJUNA_VIEWER_KEY"):
        env.pop(k, None)
    proc = subprocess.run(
        [sys.executable, "-c", "import sys; sys.path.insert(0,'.'); sys.path.insert(0,'Backend'); import security"],
        cwd=str(ROOT_DIR),
        env=env,
        capture_output=True,
        text=True,
    )
    assert proc.returncode != 0
    assert "FATAL: Default hardcoded API keys" in (proc.stdout + proc.stderr)


def test_arjuna_env_production_fails_closed_when_security_disabled():
    """ARJUNA_ENV=production with SECURITY_ENABLED=false must hard-fail."""
    env = dict(os.environ)
    env["ARJUNA_ENV"] = "production"
    env["SECURITY_ENABLED"] = "false"
    env["ARJUNA_API_KEY"] = "prod-x-strong-key-01"
    env["ARJUNA_ADMIN_KEY"] = "prod-x-strong-key-02"
    env["ARJUNA_QA_KEY"] = "prod-x-strong-key-03"
    env["ARJUNA_VIEWER_KEY"] = "prod-x-strong-key-04"
    proc = subprocess.run(
        [sys.executable, "-c", "import sys; sys.path.insert(0,'.'); sys.path.insert(0,'Backend'); import security"],
        cwd=str(ROOT_DIR),
        env=env,
        capture_output=True,
        text=True,
    )
    assert proc.returncode != 0
    assert "SECURITY_ENABLED=false is not permitted" in (proc.stdout + proc.stderr)


def test_production_fails_closed_with_empty_keys():
    """ARJUNA_ENV=production with blank/empty keys must hard-fail."""
    env = dict(os.environ)
    env["ARJUNA_ENV"] = "production"
    env["SECURITY_ENABLED"] = "true"
    env["ARJUNA_API_KEY"] = "   "
    env["ARJUNA_ADMIN_KEY"] = "prod-x-strong-key-02"
    env["ARJUNA_QA_KEY"] = "prod-x-strong-key-03"
    env["ARJUNA_VIEWER_KEY"] = "prod-x-strong-key-04"
    proc = subprocess.run(
        [sys.executable, "-c", "import sys; sys.path.insert(0,'.'); sys.path.insert(0,'Backend'); import security"],
        cwd=str(ROOT_DIR),
        env=env,
        capture_output=True,
        text=True,
    )
    assert proc.returncode != 0
    assert "FATAL: Default hardcoded API keys" in (proc.stdout + proc.stderr)


# ==============================================================================
# REST RBAC MATRIX VERIFICATION (viewer, qa_inspector, operator, admin)
# ==============================================================================

@pytest.mark.parametrize("read_only_key", [VIEWER_KEY, QA_KEY])
def test_read_only_roles_cannot_mutate_rest_endpoints(read_only_key):
    """Viewer and QA Inspector roles MUST NOT be able to mutate chamber state via REST."""
    headers = {"X-API-Key": read_only_key}

    # 1. Inject fault
    r1 = client.post("/api/inject-fault", json={"event_type": "THERMAL_DRIFT"}, headers=headers)
    assert r1.status_code == 403, f"Read-only role was able to inject fault: {r1.status_code}"

    # 2. Reset
    r2 = client.post("/api/reset", headers=headers)
    assert r2.status_code == 403, f"Read-only role was able to reset chamber: {r2.status_code}"

    # 3. Set criticality
    r3 = client.post("/api/set-criticality", json={"criticality_level": 3}, headers=headers)
    assert r3.status_code == 403, f"Read-only role was able to set criticality: {r3.status_code}"


@pytest.mark.parametrize("privileged_key", [API_KEY, ADMIN_KEY])
def test_privileged_roles_can_mutate_rest_endpoints(privileged_key):
    """Operator and Admin roles CAN mutate chamber state via REST."""
    headers = {"X-API-Key": privileged_key}

    # 1. Inject fault
    r1 = client.post("/api/inject-fault", json={"event_type": "THERMAL_DRIFT"}, headers=headers)
    assert r1.status_code == 200

    # 2. Set criticality
    r2 = client.post("/api/set-criticality", json={"criticality_level": 2}, headers=headers)
    assert r2.status_code == 200

    # 3. Reset
    r3 = client.post("/api/reset", headers=headers)
    assert r3.status_code == 200

