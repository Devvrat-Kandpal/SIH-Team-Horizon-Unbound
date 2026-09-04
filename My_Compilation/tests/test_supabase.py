"""
tests/test_supabase.py — Project ARJUNA (SIH 26170)
Automated tests for Supabase Schema Alignment, Payload Formatting, Filtering, and Outage Fallback.
"""

from Backend.database import TelemetryStore, telemetry_store


def test_telemetry_payload_schema_compliance():
    """Verify that formatted payload strictly matches migrations/supabase_schema.sql."""
    raw_frame = {
        "timestamp": "2026-03-30T00:00:01.000Z",
        "voltage": 4.982,
        "current": 1.205,
        "temperature": 125.3,
        "iddq_uA": 45.2,
        "prop_delay": 4.52,
        "anomaly_score": 0.892,
        "is_anomaly": True,
        "cusum_drift_detected": False,
        "fault_type": "ELECTRICAL_SPIKE",
        "criticality_level": 3,
        "system_status": "ANOMALY",
    }

    formatted = TelemetryStore._format_telemetry_payload(raw_frame)

    # Exact column names must match SQL schema
    expected_cols = {
        "timestamp",
        "voltage",
        "current",
        "temperature",
        "iddq_uA",
        "prop_delay",
        "anomaly_score",
        "isolation_anomaly",
        "drift_anomaly",
        "fault_type",
        "criticality_level",
        "system_status",
    }
    assert set(formatted.keys()) == expected_cols
    assert formatted["voltage"] == 4.982
    assert formatted["iddq_uA"] == 45.2
    assert formatted["criticality_level"] == 3
    assert formatted["isolation_anomaly"] is True
    assert formatted["drift_anomaly"] is False
    assert formatted["fault_type"] == "ELECTRICAL_SPIKE"


def test_telemetry_store_offline_in_memory_persistence():
    """Verify offline fallback records telemetry and events without database connection."""
    store = TelemetryStore(history_limit=100)
    store.client = None  # Explicit offline mode
    store.http_client = None  # Explicit offline mode

    test_frame_1 = {
        "timestamp": "2026-03-30T00:00:01Z",
        "voltage": 5.0,
        "current": 1.2,
        "temperature": 125.0,
        "iddq_uA": 10.0,
        "fault_type": "NORMAL",
    }
    test_frame_2 = {
        "timestamp": "2026-03-30T00:00:02Z",
        "voltage": 5.0,
        "current": 1.2,
        "temperature": 125.0,
        "iddq_uA": 45.0,
        "fault_type": "ELECTRICAL_SPIKE",
    }

    store.record_telemetry(test_frame_1)
    store.record_telemetry(test_frame_2)
    store.record_event("INJECTION", "HIGH", "Spike injected", criticality_level=2)

    # Recent retrieval without filter
    recent_all = store.recent(limit=10)
    assert len(recent_all) == 2
    assert recent_all[0]["iddq_uA"] == 45.0  # Most recent first

    # Recent retrieval with fault_type filter
    spikes_only = store.recent(limit=10, fault_type="ELECTRICAL_SPIKE")
    assert len(spikes_only) == 1
    assert spikes_only[0]["fault_type"] == "ELECTRICAL_SPIKE"

    nominal_only = store.recent(limit=10, fault_type="NORMAL")
    assert len(nominal_only) == 1
    assert nominal_only[0]["fault_type"] == "NORMAL"

    # Events retrieval
    events = store.recent_events(limit=10)
    assert len(events) == 1
    assert events[0]["event_type"] == "INJECTION"


def test_telemetry_store_status_reporting():
    """Verify telemetry store provides comprehensive persistence status."""
    status = telemetry_store.get_status()
    assert "supabase_enabled" in status
    assert "supabase_available" in status
    assert "in_memory_records" in status
    assert "total_telemetry_logged" in status
