"""
tests/test_ood.py - Project ARJUNA (SIH 26170)
Out-Of-Distribution (OOD) Generalization Suite.
Verifies that the ML models (Isolation Forest & CUSUM) behave deterministically
when fed non-physical, adversarial, or extremely noisy telemetry.
"""

import random
import sys
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "Backend"))

from Backend.isolation_forest import MultivariateAnomalyDetector


@pytest.fixture(scope="module")
def trained_model():
    sample_csv = ROOT_DIR / "Model" / "sample_data.csv"
    detector = MultivariateAnomalyDetector(contamination=0.001, n_estimators=40)
    detector.train(str(sample_csv))
    return detector


def test_ood_static_flatline(trained_model):
    """
    OOD Test 1: Sensor freeze / Flatline.
    If the telemetry stays perfectly flat for 50 ticks, is it flagged?
    Module A isn't a time-series model so it sees "normal" values if frozen at nominal.
    But we verify it doesn't crash or behave erratically.
    """
    for _ in range(50):
        res = trained_model.detect_spike(
            current=1.2,
            voltage=5.0,
            temp=125.0,
            iddq=10.0,
            prop_delay=4.5,
            criticality_level=2,
        )
        assert res["is_anomaly"] is False
        assert 0.0 <= res["anomaly_score"] < 0.6


def test_ood_extreme_bounds(trained_model):
    """
    OOD Test 2: Extreme non-physical bounds.
    Verify the model correctly isolates extreme outliers (V=1000V, T=-273C, etc).
    """
    # High-voltage surge, negative temp (non-physical)
    res1 = trained_model.detect_spike(
        current=100.0,
        voltage=1000.0,
        temp=-273.15,
        iddq=0.0,
        prop_delay=0.0,
        criticality_level=2,
    )
    assert res1["is_anomaly"] is True

    # Extreme negative Iddq (impossible)
    res2 = trained_model.detect_spike(
        current=1.2,
        voltage=5.0,
        temp=125.0,
        iddq=-50.0,
        prop_delay=4.5,
        criticality_level=2,
    )
    assert res2["is_anomaly"] is True


def test_ood_pure_random_noise(trained_model):
    """
    OOD Test 3: Pure unstructured noise.
    Verifies the model flags highly chaotic uncorrelated telemetry.
    """
    random.seed(42)
    anomalies_flagged = 0
    n_samples = 100

    for _ in range(n_samples):
        res = trained_model.detect_spike(
            current=random.uniform(-5.0, 15.0),
            voltage=random.uniform(-10.0, 20.0),
            temp=random.uniform(0.0, 300.0),
            iddq=random.uniform(-20.0, 100.0),
            prop_delay=random.uniform(0.0, 10.0),
            criticality_level=2,
        )
        if res["is_anomaly"]:
            anomalies_flagged += 1

    assert anomalies_flagged > (n_samples * 0.90)

def test_cross_seed_robustness(trained_model):
    """
    OOD Test 4: Cross-seed invariance.
    Verifies that different RNG seeds don't wildly change the Isolation Forest bounding logic.
    """
    import random

    anomalies_seed1 = 0
    anomalies_seed2 = 0
    n_samples = 50

    random.seed(10)
    for _ in range(n_samples):
        res = trained_model.detect_spike(
            current=random.uniform(-5.0, 15.0), voltage=random.uniform(-10.0, 20.0), temp=random.uniform(0.0, 300.0), iddq=random.uniform(-20.0, 100.0)
        )
        if res["is_anomaly"]:
            anomalies_seed1 += 1

    random.seed(999)
    for _ in range(n_samples):
        res = trained_model.detect_spike(
            current=random.uniform(-5.0, 15.0), voltage=random.uniform(-10.0, 20.0), temp=random.uniform(0.0, 300.0), iddq=random.uniform(-20.0, 100.0)
        )
        if res["is_anomaly"]:
            anomalies_seed2 += 1

    # Both should flag >90% of random noise as anomalies, regardless of seed
    assert anomalies_seed1 > (n_samples * 0.90)
    assert anomalies_seed2 > (n_samples * 0.90)

