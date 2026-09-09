""""
tests/test_websocket_rbac.py — Project ARJUNA (SIH 26170)

Adversarial WebSocket Role-Based Access Control tests (P0-01).

Verifies the documented permission model is actually enforced on WebSocket
control commands:

    viewer       -> telemetry only (no mutations)
    qa_inspector -> telemetry / inspection (no mutations)
    operator     -> set_scenario / reset
    admin        -> set_scenario / reset

Each control attempt is made black-box over a real authenticated WebSocket and
the observable chamber scenario is inspected to confirm accept/deny behavior.
"""

import json
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


def _read_scenario(ws, max_frames: int = 6) -> str:
    """Reads telemetry frames until a scenario value is observed."""
    for _ in range(max_frames):
        data = ws.receive_json()
        sc = data.get("scenario")
        if sc:
            return str(sc).lower()
    return ""


def _force_nominal() -> None:
    """Uses the operator credential to guarantee a clean global state first."""
    client.post("/api/reset", headers={"X-API-Key": API_KEY})


READ_ONLY_ROLES = {
    "viewer": VIEWER_KEY,
    "qa_inspector": QA_KEY,
}


@pytest.mark.parametrize("role_name,key", list(READ_ONLY_ROLES.items()))
def test_read_only_role_cannot_set_scenario(role_name, key):
    """Viewer / QA must NOT be able to set_scenario over WebSocket."""
    _force_nominal()
    with client.websocket_connect(f"/ws?api_key={key}") as ws:
        _read_scenario(ws)
        ws.send_text(
            json.dumps({"action": "set_scenario", "scenario": "thermal_drift"})
        )
        for _ in range(6):
            data = ws.receive_json()
            scenario = str(data.get("scenario", "")).lower()
            assert scenario != "thermal_drift", (
                f"role '{role_name}' was able to set_scenario over WebSocket (RBAC violation)"
            )


@pytest.mark.parametrize("role_name,key", list(READ_ONLY_ROLES.items()))
def test_read_only_role_cannot_reset(role_name, key):
    """Viewer / QA must NOT be able to reset the chamber over WebSocket."""
    # Put the chamber into a non-nominal scenario via operator first.
    client.post(
        "/api/inject-fault",
        json={"event_type": "THERMAL_DRIFT"},
        headers={"X-API-Key": API_KEY},
    )
    with client.websocket_connect(f"/ws?api_key={key}") as ws:
        _read_scenario(ws)
        ws.send_text(json.dumps({"action": "reset"}))
        # Reset would move the shared chamber to nominal within a tick or two,
        # so a read-only role holding the chamber AWAY from nominal is the signal
        # that mutating reset was (correctly) denied.
        observed_nominal = False
        for _ in range(6):
            data = ws.receive_json()
            if str(data.get("scenario", "")).lower() == "nominal":
                observed_nominal = True
                break
        assert observed_nominal is False, (
            f"role '{role_name}' was able to issue reset over WebSocket (RBAC violation)"
        )


@pytest.mark.parametrize(
    "role_name,key", [("operator", API_KEY), ("admin", ADMIN_KEY)]
)
def test_privileged_role_can_set_scenario(role_name, key):
    """Operator / Admin must be able to set_scenario over WebSocket."""
    _force_nominal()
    with client.websocket_connect(f"/ws?api_key={key}") as ws:
        _read_scenario(ws)
        ws.send_text(
            json.dumps({"action": "set_scenario", "scenario": "thermal_drift"})
        )
        applied = False
        for _ in range(8):
            data = ws.receive_json()
            if str(data.get("scenario", "")).lower() == "thermal_drift":
                applied = True
                break
        assert applied, (
            f"role '{role_name}' set_scenario over WebSocket was not applied"
        )


@pytest.mark.parametrize(
    "role_name,key", [("operator", API_KEY), ("admin", ADMIN_KEY)]
)
def test_privileged_role_can_reset(role_name, key):
    """Operator / Admin must be able to reset the chamber over WebSocket."""
    client.post(
        "/api/inject-fault",
        json={"event_type": "ELECTRICAL_SPIKE"},
        headers={"X-API-Key": API_KEY},
    )
    with client.websocket_connect(f"/ws?api_key={key}") as ws:
        _read_scenario(ws)
        ws.send_text(json.dumps({"action": "reset"}))
        applied = False
        for _ in range(8):
            data = ws.receive_json()
            if str(data.get("scenario", "")).lower() == "nominal":
                applied = True
                break
        assert applied, (
            f"role '{role_name}' reset over WebSocket was not applied"
        )
