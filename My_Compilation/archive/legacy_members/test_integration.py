import pytest
import asyncio
import json
from fastapi.testclient import TestClient
from Backend.server import app, get_or_train_model

@pytest.fixture(scope="module")
def client():
    get_or_train_model()
    with TestClient(app) as c:
        yield c

def test_api_health_endpoint(client):
    """Verify backend health and model loading."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["model_loaded"] is True
    assert "mean_iddq" in data["lot_stats"]


def test_team_compatible_control_and_history_api(client):
    response = client.post("/api/inject-fault", json={"event_type": "THERMAL_DRIFT"})
    assert response.status_code == 200
    assert response.json()["scenario"] == "thermal_drift"

    status = client.get("/api/status")
    assert status.status_code == 200
    assert status.json()["inject_drift"] is True
    assert "persistence" in status.json()

    invalid = client.post("/api/inject-fault", json={"event_type": "UNKNOWN"})
    assert invalid.status_code == 400
    assert client.post("/api/inject-fault", json={"event_type": 123}).status_code == 422
    assert client.post("/api/inject-fault", json=[]).status_code == 422

    reset = client.post("/api/reset")
    assert reset.status_code == 200
    assert client.get("/api/status").json()["inject_drift"] is False
    assert client.get("/api/history?limit=5").status_code == 200


def test_team_compatible_websocket_alias(client):
    with client.websocket_connect("/ws/telemetry") as websocket:
        data = websocket.receive_json()
        assert data["scenario"] == "nominal"
        assert "criticality_level" in data


def test_criticality_api_is_strict_and_persistent(client):
    response = client.post("/api/set-criticality", json={"criticality_level": 3})
    assert response.status_code == 200
    assert response.json()["criticality_level"] == 3
    assert client.get("/api/criticality").json()["criticality_level"] == 3

    for invalid_body in (None, [], {}, {"criticality_level": True}, {"criticality_level": 1.0}, {"criticality_level": 4}):
        response = client.post("/api/set-criticality", json=invalid_body)
        assert response.status_code == 422

    assert client.post("/api/set-criticality", json={"criticality_level": 2}).status_code == 200

def test_dashboard_static_serving(client):
    """Verify Member 1 frontend dashboard is served at root."""
    response = client.get("/")
    assert response.status_code == 200
    assert "PROJECT ARJUNA" in response.text
    assert "telemetryChart" in response.text

def test_websocket_realtime_stream_and_ml_scoring(client):
    """Verify WebSocket streams live data scored in real time by Member 3."""
    with client.websocket_connect("/ws") as websocket:
        # Receive first nominal telemetry packet
        data = websocket.receive_json()
        assert "voltage" in data
        assert "current" in data
        assert "temperature" in data
        assert "iddq_uA" in data
        assert "is_anomaly" in data
        assert "anomaly_score" in data
        assert "qa_justification" in data
        
        # Nominal baseline check
        assert data["is_anomaly"] is False
        assert data["anomaly_score"] < 0.30
        assert "QA STATUS [PASSED]" in data["qa_justification"]

def test_websocket_module_b_fields_present(client):
    """
    Verify WebSocket payload includes all Module B drift predictor fields
    (ISRO requirement: 168h Latent Drift Predictor).
    """
    with client.websocket_connect("/ws") as websocket:
        # Collect several packets to allow drift predictor to initialise
        for _ in range(10):
            data = websocket.receive_json()

        # All Module B fields must be present
        assert "drift_slope_ua_h"    in data, "Missing drift_slope_ua_h"
        assert "forecast_168h_uA"    in data, "Missing forecast_168h_uA"
        assert "forecast_168h_label" in data, "Missing forecast_168h_label"
        assert "drift_status"        in data, "Missing drift_status"
        assert "drift_r2"            in data, "Missing drift_r2"
        assert "early_reject_b"      in data, "Missing early_reject_b"
        assert "n_observations"      in data, "Missing n_observations"
        assert "burn_in_hours"       in data, "Missing burn_in_hours"

        # Types must be correct
        assert isinstance(data["drift_slope_ua_h"],    float)
        assert isinstance(data["forecast_168h_uA"],    float)
        assert isinstance(data["forecast_168h_label"], str)
        assert isinstance(data["drift_status"],        str)
        assert isinstance(data["early_reject_b"],      bool)
        assert isinstance(data["n_observations"],      int)

        # After 10 observations the predictor should have data
        assert data["n_observations"] >= 1
        assert data["forecast_168h_uA"] > 0

def test_websocket_scenario_injection_isro_outlier(client):
    """
    Verify sending scenario command over WebSocket triggers Member 3's 
    ISRO dynamic outlier evaluation (45 uA part in 10 uA lot).
    """
    with client.websocket_connect("/ws") as websocket:
        # 1. Send scenario trigger
        websocket.send_text(json.dumps({
            "action": "set_scenario",
            "scenario": "isro_outlier"
        }))
        
        # 2. Wait for next broadcast tick
        received_anomaly = False
        for _ in range(3):
            data = websocket.receive_json()
            if data["scenario"] == "isro_outlier":
                assert data["is_anomaly"] is True
                assert data["anomaly_score"] > 0.70
                assert data["iddq_uA"] > 40.0
                assert data["fault_type"] == "ELECTRICAL_SPIKE"
                assert "Dynamic Outlier" in data["qa_justification"]
                received_anomaly = True
                break
                
        assert received_anomaly is True

def test_websocket_scenario_short_circuit(client):
    """Verify Member 3 catches electrical short circuit injected from UI."""
    with client.websocket_connect("/ws") as websocket:
        websocket.send_text(json.dumps({
            "action": "set_scenario",
            "scenario": "electrical_short"
        }))
        
        received_short = False
        for _ in range(3):
            data = websocket.receive_json()
            if data["scenario"] == "electrical_short":
                assert data["is_anomaly"] is True
                assert data["voltage"] < 1.0
                assert data["current"] > 5.0
                assert data["fault_type"] == "ELECTRICAL_SHORT_CIRCUIT"
                received_short = True
                break
                
        assert received_short is True

def test_member2_physics_and_criticality_integration(client):
    """Verify Member 2 ComponentSimulator physics and NASA EEE-INST-002 criticality are streamed."""
    with client.websocket_connect("/ws") as websocket:
        data = websocket.receive_json()
        assert "criticality_level" in data
        assert data["criticality_level"] in [1, 2, 3]
        # Verify physical ranges computed by Member 2 simulator at 125°C steady-state
        assert 120.0 <= data["temperature"] <= 130.0
        assert 4.80 <= data["voltage"] <= 5.10
        assert 1.10 <= data["current"] <= 1.40

def test_member4_cusum_drift_integration(client):
    """Verify Member 4 CUSUM DriftDetector evaluates thermal creep over WebSocket stream."""
    with client.websocket_connect("/ws") as websocket:
        # 1. Nominal check
        data = websocket.receive_json()
        assert "cusum_score" in data
        assert "cusum_drift_detected" in data
        assert isinstance(data["cusum_score"], float)
        assert data["cusum_drift_detected"] is False

        # 2. Trigger thermal drift scenario
        websocket.send_text(json.dumps({
            "action": "set_scenario",
            "scenario": "thermal_drift"
        }))

        # Receive packets during drift
        for _ in range(5):
            data = websocket.receive_json()
            assert "cusum_score" in data
            assert "cusum_drift_detected" in data

def test_websocket_scenario_reset(client):
    """Verify reset action restores nominal baseline and clears scenario."""
    with client.websocket_connect("/ws") as websocket:
        # First set an anomaly scenario
        websocket.send_text(json.dumps({
            "action": "set_scenario",
            "scenario": "isro_outlier"
        }))
        for _ in range(3):
            data = websocket.receive_json()
            if data["scenario"] == "isro_outlier":
                break

        # Now send reset
        websocket.send_text(json.dumps({
            "action": "reset"
        }))
        for _ in range(3):
            data = websocket.receive_json()
            if data["scenario"] == "nominal":
                assert data["is_anomaly"] is False
                assert data["burn_in_hours"] <= 1.0
                break



