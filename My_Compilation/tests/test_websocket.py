"""
tests/test_websocket.py — Project ARJUNA (SIH 26170)
Comprehensive WebSocket streaming, handshake security, and telemetry frame verification.
Tests /ws and /ws/telemetry with authenticated handshakes and invalid token rejection.
"""

import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "Backend"))

from Backend.security import API_KEY, VIEWER_KEY
from Backend.server import app

client = TestClient(app)


def test_websocket_unauthorized_rejection():
    """Validates that WebSocket handshake with an invalid key is rejected with code 1008."""
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/ws?api_key=completely_bogus_token") as ws:
            ws.receive_json()
    assert exc_info.value.code == 1008


def test_websocket_authorized_connection_and_frame_schema():
    """Validates successful WebSocket connection and TelemetryFrame + StructuredEvidence schema."""
    with client.websocket_connect(f"/ws?api_key={API_KEY}") as ws:
        # Receive first telemetry frame
        data = ws.receive_json()
        assert isinstance(data, dict)

        # Validate mandatory telemetry fields
        assert "voltage" in data
        assert "current" in data
        assert "temperature" in data
        assert "iddq_uA" in data
        assert "anomaly_score" in data
        assert "is_anomaly" in data
        assert "fault_type" in data
        assert "criticality_level" in data
        assert "system_status" in data
        assert "burn_in_hours" in data

        # Validate Structured XAI Evidence
        assert "structured_evidence" in data
        xai = data["structured_evidence"]
        assert "verdict" in xai
        assert "evidence" in xai
        assert isinstance(xai["evidence"], list)
        assert "qa_justification" in xai
        assert "recommended_action" in xai


def test_websocket_telemetry_alias_route():
    """Validates that /ws/telemetry functions identically to /ws."""
    with client.websocket_connect(f"/ws/telemetry?token={VIEWER_KEY}") as ws:
        data = ws.receive_json()
        assert "iddq_uA" in data
        assert "structured_evidence" in data


def test_websocket_interactive_commands():
    """Validates sending interactive commands (set_scenario, reset) over WebSocket."""
    with client.websocket_connect(f"/ws?api_key={API_KEY}") as ws:
        # 1. Read initial frame
        f1 = ws.receive_json()
        assert f1 is not None

        # 2. Trigger thermal drift scenario via WebSocket message
        ws.send_text(json.dumps({"action": "set_scenario", "scenario": "thermal_drift"}))

        # 3. Read subsequent frames to verify scenario transition
        f2 = ws.receive_json()
        assert f2["scenario"] == "thermal_drift" or "thermal" in str(f2.get("scenario", "")).lower()

        # 4. Send reset command
        ws.send_text(json.dumps({"action": "reset"}))
        f3 = ws.receive_json()
        assert f3["scenario"] == "nominal"
