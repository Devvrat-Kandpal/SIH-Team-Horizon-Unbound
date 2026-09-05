import pytest
import random
from cusum_drift import DriftDetector

def test_cusum_nominal_stability():
    """Verify zero false positives over 500 normal temperature jitter readings."""
    random.seed(42)
    detector = DriftDetector(mean=125.0, std=0.5, k=0.1, threshold=3.0)
    for _ in range(500):
        temp = 125.0 + random.uniform(-0.3, 0.3)
        is_drift = detector.evaluate_drift(temp)
        assert is_drift is False
        assert detector.cusum < 3.0

def test_cusum_slow_drift_detection():
    """Verify CUSUM detects gradual thermal creep (+0.15°C/step) within 25 steps."""
    detector = DriftDetector(mean=125.0, std=0.5, k=0.1, threshold=3.0)
    detected = False
    temp = 125.0
    for step in range(1, 30):
        temp += 0.15
        if detector.evaluate_drift(temp):
            detected = True
            break
    assert detected is True
    assert detector.drift_detected is True

def test_cusum_reset_behavior():
    """Verify reset() clears cumulative accumulator and alarm latch."""
    detector = DriftDetector(mean=125.0, std=0.5, k=0.1, threshold=3.0)
    for _ in range(20):
        detector.evaluate_drift(130.0) # trigger alarm
    assert detector.drift_detected is True
    
    detector.reset()
    assert detector.cusum == 0.0
    assert detector.drift_detected is False
    assert detector.evaluate_drift(125.0) is False

def test_cusum_status_dict():
    """Verify get_status() returns proper telemetry metadata dictionary."""
    detector = DriftDetector(mean=125.0, std=0.5, k=0.1, threshold=3.0)
    status = detector.get_status()
    assert status['mean'] == 125.0
    assert status['threshold'] == 3.0
    assert 'cusum' in status
    assert status['drift_detected'] is False
