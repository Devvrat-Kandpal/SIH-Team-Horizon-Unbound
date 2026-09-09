"""
tests/test_multi_client_interference.py — Project ARJUNA (SIH 26170)

Multi-client (concurrent WebSocket) state-coherence tests.

These tests DOCUMENT AND QUANTIFY the intentional single-chamber architecture:
Backend/server.py (header comment) states that all connected clients observe the
SAME simulated chamber — fault injections, resets, and criticality changes are
globally coherent by design. Per-session isolation is explicitly NOT implemented.

Therefore the expected behavior is:
  1. A scenario change by client B is OBSERVED by client A (shared state, coherent).
  2. A reset by client A is OBSERVED by client B (shared state, coherent).
  3. Concurrent clients never crash the server, never receive torn/invalid frames,
     and the chamber returns cleanly to nominal afterwards (no state leakage).

If per-session isolation is implemented in the future, tests 1 and 2 MUST be
revisited — they assert the documented shared-state semantics, not a bug.
"""

import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "Backend"))

from Backend.security import API_KEY
from Backend.server import app

client = TestClient(app)

VALID_FRAME_KEYS = {"voltage", "temperature", "current", "iddq_uA", "scenario"}


def _force_nominal() -> None:
    client.post("/api/reset", headers={"X-API-Key": API_KEY})


def _read_scenario(ws, max_frames: int = 6) -> str:
    for _ in range(max_frames):
        data = ws.receive_json()
        sc = data.get("scenario")
        if sc:
            return str(sc).lower()
    return ""


def _assert_valid_frame(frame: dict) -> None:
    """No torn frames: every broadcast frame must carry the core telemetry keys."""
    missing = VALID_FRAME_KEYS - frame.keys()
    assert not missing, f"torn/invalid broadcast frame; missing keys: {missing}"


def test_scenario_change_by_second_client_is_observed_by_first():
    """Client A connects; client B sets thermal_drift; client A observes the drift.

    This asserts the DOCUMENTED shared-chamber semantics (server.py header):
    one virtual chamber, globally coherent for every connected client.
    """
    _force_nominal()
    with client.websocket_connect(f"/ws?api_key={API_KEY}") as ws_a, \
         client.websocket_connect(f"/ws?api_key={API_KEY}") as ws_b:
        _read_scenario(ws_a)
        _read_scenario(ws_b)

        ws_b.send_text(
            json.dumps({"action": "set_scenario", "scenario": "thermal_drift"})
        )

        # Client A (which issued nothing) must observe the drift within a few frames.
        observed = False
        for _ in range(8):
            frame = ws_a.receive_json()
            _assert_valid_frame(frame)
            if str(frame.get("scenario", "")).lower() == "thermal_drift":
                observed = True
                break
        assert observed, (
            "client A did not observe client B's scenario change — shared-chamber "
            "coherence (documented design) is broken"
        )


def test_reset_by_first_client_is_observed_by_second():
    """Client A triggers reset while the chamber is in drift; client B observes nominal."""
    client.post(
        "/api/inject-fault",
        json={"event_type": "THERMAL_DRIFT"},
        headers={"X-API-Key": API_KEY},
    )
    with client.websocket_connect(f"/ws?api_key={API_KEY}") as ws_a, \
         client.websocket_connect(f"/ws?api_key={API_KEY}") as ws_b:
        _read_scenario(ws_a)
        _read_scenario(ws_b)

        ws_a.send_text(json.dumps({"action": "reset"}))

        observed = False
        for _ in range(8):
            frame = ws_b.receive_json()
            _assert_valid_frame(frame)
            if str(frame.get("scenario", "")).lower() == "nominal":
                observed = True
                break
        assert observed, (
            "client B did not observe client A's reset — reset propagation is broken"
        )


def test_concurrent_clients_return_to_clean_nominal_after_cycle():
    """After a fault + reset cycle with two clients connected, the chamber returns
    to nominal and keeps streaming valid frames — no state leakage across cycles."""
    _force_nominal()
    with client.websocket_connect(f"/ws?api_key={API_KEY}") as ws_a, \
         client.websocket_connect(f"/ws?api_key={API_KEY}") as ws_b:
        client.post(
            "/api/inject-fault",
            json={"event_type": "ELECTRICAL_SHORT"},
            headers={"X-API-Key": API_KEY},
        )
        # Drain a few frames during the fault on both clients.
        for _ in range(3):
            _assert_valid_frame(ws_a.receive_json())
            _assert_valid_frame(ws_b.receive_json())

        client.post("/api/reset", headers={"X-API-Key": API_KEY})

        back_nominal = False
        for _ in range(10):
            frame = ws_b.receive_json()
            _assert_valid_frame(frame)
            if str(frame.get("scenario", "")).lower() == "nominal":
                back_nominal = True
                break
        assert back_nominal, "chamber did not return to nominal after reset cycle"

        # Post-reset frames must remain valid on the other client too.
        for _ in range(2):
            _assert_valid_frame(ws_a.receive_json())
