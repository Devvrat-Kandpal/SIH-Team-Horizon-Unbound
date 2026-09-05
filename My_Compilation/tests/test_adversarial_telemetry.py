"""
tests/test_adversarial_telemetry.py — Project ARJUNA (SIH 26170)

Adversarial / malformed telemetry robustness suite (Doc-6 sect 17/18):
verifies that the runtime detection stack does NOT crash and produces
DEFINED, safe behavior when fed NaN, +/-Inf, negative, extreme, missing,
or corrupt telemetry — and that it does NOT silently pass a faulty reading
as a healthy inlier in a high-reliability screening pipeline.

Covers:
  Module A (detect_spike):  NaN / +/-Inf / negative / extreme / zero / missing
  Module B (drift predictor): insufficient obs, reset-during-run, flat slope
  Module C (CUSUM):          NaN / Inf / reset / sustained creep
"""

import math
import sys
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "Backend"))

from Backend.cusum_drift import DriftDetector
from Backend.isolation_forest import LinearRegressionDriftPredictor, MultivariateAnomalyDetector


@pytest.fixture(scope="module")
def trained_model():
    sample_csv = ROOT_DIR / "Model" / "sample_data.csv"
    detector = MultivariateAnomalyDetector(contamination=0.001, n_estimators=40, random_state=42)
    detector.train(str(sample_csv))
    return detector


# ============================================================================
# MODULE A — detect_spike malformed/edge inputs
# ============================================================================
def test_nan_iddq_fail_safe(trained_model):
    """NaN Iddq must be flagged FAIL-SAFE, never a silent healthy inlier."""
    res = trained_model.detect_spike(
        current=1.2, voltage=5.0, temp=125.0, iddq=float("nan"),
        prop_delay=4.5, criticality_level=2,
    )
    assert res["is_anomaly"] is True
    assert res["detection_source"] == "invalid_telemetry"
    assert math.isfinite(res["anomaly_score"])


def test_inf_iddq_fail_safe(trained_model):
    for bad in (float("inf"), float("-inf")):
        res = trained_model.detect_spike(
            current=1.2, voltage=5.0, temp=125.0, iddq=bad,
            prop_delay=4.5, criticality_level=2,
        )
        assert res["is_anomaly"] is True
        assert res["detection_source"] == "invalid_telemetry"


def test_nan_other_fields_fail_safe(trained_model):
    """Corrupt voltage/current/temperature must also fail-safe."""
    cases = {"voltage": float("nan"), "current": float("nan"), "temp": float("nan")}
    for field, bad in cases.items():
        kwargs = dict(current=1.2, voltage=5.0, temp=125.0, iddq=10.0, prop_delay=4.5, criticality_level=2)
        kwargs[field] = bad
        res = trained_model.detect_spike(**kwargs)
        assert res["is_anomaly"] is True, f"not fail-safe for {field}"
        assert res["detection_source"] == "invalid_telemetry"


def test_negative_iddq(trained_model):
    """Physically impossible negative Iddq is flagged (finite input -> normal path)."""
    res = trained_model.detect_spike(
        current=1.2, voltage=5.0, temp=125.0, iddq=-50.0,
        prop_delay=4.5, criticality_level=2,
    )
    assert res["is_anomaly"] is True


def test_extreme_iddq_999(trained_model):
    """999 uA extreme outlier must be flagged."""
    res = trained_model.detect_spike(
        current=1.2, voltage=5.0, temp=125.0, iddq=999.0,
        prop_delay=4.5, criticality_level=2,
    )
    assert res["is_anomaly"] is True


def test_zero_voltage_current_no_crash(trained_model):
    """Zero voltage/current must not crash; defined result returned."""
    res = trained_model.detect_spike(
        current=0.0, voltage=0.0, temp=125.0, iddq=10.0,
        prop_delay=4.5, criticality_level=2,
    )
    assert isinstance(res["is_anomaly"], bool)
    assert math.isfinite(res["anomaly_score"])


def test_normal_control(trained_model):
    """Control: valid nominal telemetry is a healthy inlier."""
    res = trained_model.detect_spike(
        current=1.2, voltage=5.0, temp=125.0, iddq=10.0,
        prop_delay=4.5, criticality_level=2,
    )
    assert res["is_anomaly"] is False
    assert res["detection_source"] == "none"


# ============================================================================
# MODULE B — drift predictor edge cases
# ============================================================================
def test_b_insufficient_observations():
    p = LinearRegressionDriftPredictor(lot_mean_iddq=10.0, lot_std_iddq=1.17)
    r = p.update(burn_in_hours=1.0, iddq_uA=10.2)
    assert r["n_observations"] == 1
    assert "INITIALIZING" in r["drift_status"]
    assert r["early_reject_b"] is False


def test_b_reset_during_run():
    p = LinearRegressionDriftPredictor(lot_mean_iddq=10.0, lot_std_iddq=1.17)
    p.update(burn_in_hours=1.0, iddq_uA=10.1)
    p.update(burn_in_hours=2.0, iddq_uA=10.2)
    p.reset()
    r = p.update(burn_in_hours=3.0, iddq_uA=10.3)
    assert r["n_observations"] == 1
    assert "INITIALIZING" in r["drift_status"]


def test_b_flat_slope():
    """Flat 0h==24h reading -> zero slope, forecast equals baseline, no early reject."""
    p = LinearRegressionDriftPredictor(lot_mean_iddq=10.0, lot_std_iddq=1.17)
    pred = p.predict_168h(value_0h=10.0, value_24h=10.0)
    assert pred["slope"] == 0.0
    assert pred["forecast_168h_uA"] == 10.0
    assert pred["early_reject"] is False


def test_b_negative_burn_time_no_crash():
    p = LinearRegressionDriftPredictor(lot_mean_iddq=10.0, lot_std_iddq=1.17)
    r = p.update(burn_in_hours=-5.0, iddq_uA=10.0)  # must not crash
    assert isinstance(r, dict)


# ============================================================================
# MODULE C — CUSUM edge cases
# ============================================================================
def test_cusum_nan_no_crash():
    d = DriftDetector(mean=10.0, std=1.17, criticality_level=2)
    flag = d.evaluate_drift(float("nan"))
    assert isinstance(flag, bool)


def test_cusum_inf_handled():
    d = DriftDetector(mean=10.0, std=1.17, criticality_level=2)
    flag = d.evaluate_drift(float("inf"))
    assert isinstance(flag, bool)


def test_cusum_reset_clears_state():
    d = DriftDetector(mean=10.0, std=1.17, criticality_level=2)
    for _ in range(30):
        d.evaluate_drift(11.0)  # accumulate
    d.reset()
    assert d.cusum == 0.0
    assert d.drift_detected is False


def test_cusum_sustained_creep_detects():
    d = DriftDetector(mean=10.0, std=1.17, criticality_level=2)
    detected = False
    iddq = 10.0
    for _ in range(60):
        iddq += 0.3
        if d.evaluate_drift(iddq):
            detected = True
            break
    assert detected is True
