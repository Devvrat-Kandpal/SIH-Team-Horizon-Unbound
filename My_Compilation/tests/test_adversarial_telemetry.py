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
import random
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


# ============================================================================
# Per-DUT auto-baseline (CUSUM calibration-domain fix)
# ============================================================================
def test_cusum_autobaseline_high_baseline_part_no_false_trip():
    """A healthy part whose own baseline sits at 11.4 uA (within natural lot
    spread) must NOT false-trip when auto-baselined to its own readings."""
    d = DriftDetector(mean=10.0, std=1.17, criticality_level=2, auto_baseline=True, baseline_window=15)
    random.seed(7)
    tripped = False
    for _ in range(60):
        if d.evaluate_drift(11.4 + random.gauss(0, 0.2)):
            tripped = True
            break
    assert not tripped, "Auto-baselined healthy part at 11.4 uA must not false-trip"
    assert d._baseline_locked, "Baseline must have calibrated after the learning window"
    assert 11.0 < d.mean < 11.8, f"Reference must lock near the part's own baseline, got {d.mean}"


def test_cusum_autobaseline_detects_drift_from_own_baseline():
    """Drift is measured relative to the part's OWN baseline, not the lot mean:
    a part baselined at 11.4 uA that creeps upward must still be caught."""
    d = DriftDetector(mean=10.0, std=1.17, criticality_level=2, auto_baseline=True, baseline_window=15)
    random.seed(7)
    for _ in range(15):
        d.evaluate_drift(11.4 + random.gauss(0, 0.2))
    detected = False
    iddq = 11.4
    for _ in range(200):
        iddq += 0.15
        if d.evaluate_drift(iddq):
            detected = True
            break
    assert detected, "Creep from the part's own baseline must be detected"


def test_cusum_autobaseline_learning_phase_never_alarms():
    """During the baseline learning window the detector must stay silent,
    even when fed outlier-ish calibration values."""
    d = DriftDetector(mean=10.0, std=1.17, criticality_level=2, auto_baseline=True, baseline_window=15)
    for v in (12.0, 11.9, 12.1, 11.8, 12.0, 11.9, 12.0, 12.2, 11.9, 12.0, 12.1, 11.9, 12.0, 12.0, 12.1):
        assert d.evaluate_drift(v) is False, "Learning phase must not alarm"


def test_cusum_autobaseline_reset_re_arms_learning():
    """reset() must re-arm the baseline learning phase for the next DUT."""
    d = DriftDetector(mean=10.0, std=1.17, criticality_level=2, auto_baseline=True, baseline_window=5)
    for _ in range(10):
        d.evaluate_drift(11.0)
    assert d._baseline_locked
    d.reset()
    assert not d._baseline_locked
    assert d.mean == 10.0, "reset must restore the prior population mean"
    assert not d.evaluate_drift(11.0), "re-armed learning phase must not alarm"


def test_cusum_legacy_mode_unchanged():
    """Default (auto_baseline=False) must keep the historical global-reference
    behaviour: accumulation against the fixed mean from tick one."""
    d = DriftDetector(mean=10.0, std=1.17, criticality_level=2)
    # 10.0 == mean, so S+ stays clamped at 0
    assert d.evaluate_drift(10.0) is False
    assert d.cusum == 0.0
    # One large spike immediately accumulates (no learning window)
    d.evaluate_drift(15.0)
    assert d.cusum > 0.0, "Legacy mode must accumulate from the first tick"


def test_cusum_live_noise_domain_no_false_alarm():
    """Deployed calibration check (Monte-Carlo, fixed seed):
    On the LIVE server per-tick Iddq noise domain (σ ≈ 0.15 µA, per-DUT auto-baseline),
    k=0.5 must NOT false-alarm on healthy parts at ANY criticality level.

    This guards the two-domain distinction documented in criticality_config.py:
    lot-jitter σ≈1.15 (cross-component spread, cancelled by auto-baseline) vs the
    live per-tick σ≈0.15 the deployed CUSUM actually consumes."""
    random.seed(123)
    for level in (1, 2, 3):
        false_trips = 0
        for _ in range(120):  # parts
            baseline = 10.0 + random.gauss(0, 1.15)  # unclamped lot position
            d = DriftDetector(
                mean=10.0, std=1.15, criticality_level=level,
                auto_baseline=True, baseline_window=15,
            )
            for _tick in range(500):
                # live server per-tick noise domain
                if d.evaluate_drift(baseline + random.gauss(0, 0.15)):
                    false_trips += 1
                    break
        assert false_trips == 0, (
            f"Level {level}: {false_trips}/120 healthy live-domain parts false-tripped"
        )


def test_cusum_nonfinite_does_not_latch():
    """A single NaN/Inf sample must NOT permanently wedge CUSUM into alarm
    (single-impulse latch prevention): the detector ignores non-finite samples,
    stays recoverable, and still detects genuine creep afterward."""
    d = DriftDetector(mean=10.0, std=1.17, criticality_level=2)
    assert d.evaluate_drift(float("nan")) is False
    assert d._baseline_locked  # non-auto-baseline detector always has a locked reference
    d2 = DriftDetector(mean=10.0, std=1.17, criticality_level=2, auto_baseline=True, baseline_window=5)
    for _ in range(5):
        d2.evaluate_drift(10.0)
    assert d2._baseline_locked
    # Inject a corrupt infinity, then confirm the accumulator is not wedged
    assert d2.evaluate_drift(float("inf")) is False
    assert math.isnan(d2.cusum) is False
    # Genuine sustained creep must still be detected after the glitch
    detected = False
    iddq = 10.0
    for _ in range(200):
        iddq += 0.15
        if d2.evaluate_drift(iddq):
            detected = True
            break
    assert detected, "CUSUM must still detect creep after a non-finite glitch"
