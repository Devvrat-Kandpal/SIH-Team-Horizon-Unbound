"""
tests/test_criticality.py — Project ARJUNA (SIH 26170)
Statistical defense and latency verification for Multi-Tier Mission Criticality (Levels 1, 2, 3).
Conforms to ECSS-Q-ST-60-02C Space Product Assurance & MIL-STD-883.
"""

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "Backend"))

from Backend.criticality_config import get_config
from Backend.cusum_drift import DriftDetector


def test_criticality_config_structure_and_monotonicity():
    """Validates that criticality thresholds tighten monotonically from Level 1 to Level 3."""
    cfg1 = get_config(1)
    cfg2 = get_config(2)
    cfg3 = get_config(3)

    # 1. CUSUM decision threshold h must strictly decrease (tighter tolerance)
    assert cfg1["cusum_threshold"] > cfg2["cusum_threshold"] > cfg3["cusum_threshold"]
    assert cfg1["cusum_threshold"] == 7.0
    assert cfg2["cusum_threshold"] == 5.0
    assert cfg3["cusum_threshold"] == 3.5

    # 2. CUSUM allowance k must remain fixed at 0.5 (calibrated to physical noise floor)
    assert cfg1["cusum_k"] == cfg2["cusum_k"] == cfg3["cusum_k"] == 0.5

    # 3. Isolation Forest score threshold must strictly decrease (tighter sensitivity)
    assert cfg1["if_score_threshold"] > cfg2["if_score_threshold"] > cfg3["if_score_threshold"]
    assert cfg1["if_score_threshold"] == 0.65
    assert cfg2["if_score_threshold"] == 0.55
    assert cfg3["if_score_threshold"] == 0.45


def test_invalid_criticality_level_raises_error():
    """Validates that querying invalid levels (e.g. 0 or 4) raises ValueError."""
    with pytest.raises(ValueError):
        get_config(0)
    with pytest.raises(ValueError):
        get_config(4)


def test_criticality_detection_latency_ranking():
    """
    Empirical proof: When exposed to an identical subtle drift trajectory,
    Level 3 trips earlier than Level 2, and Level 2 trips earlier than Level 1.
    """
    d1 = DriftDetector(metric_name="Iddq", mean=10.0, std=1.0, criticality_level=1)
    d2 = DriftDetector(metric_name="Iddq", mean=10.0, std=1.0, criticality_level=2)
    d3 = DriftDetector(metric_name="Iddq", mean=10.0, std=1.0, criticality_level=3)

    trip_tick_1 = None
    trip_tick_2 = None
    trip_tick_3 = None

    # Slowly ramping leakage current: 10.0 -> 14.0 uA
    for tick in range(1, 40):
        current_val = 10.0 + 0.15 * tick

        flag1, _ = d1.update(current_val)
        flag2, _ = d2.update(current_val)
        flag3, _ = d3.update(current_val)

        if flag1 and trip_tick_1 is None:
            trip_tick_1 = tick
        if flag2 and trip_tick_2 is None:
            trip_tick_2 = tick
        if flag3 and trip_tick_3 is None:
            trip_tick_3 = tick

    assert trip_tick_3 is not None, "Level 3 must detect drift"
    assert trip_tick_2 is not None, "Level 2 must detect drift"
    assert trip_tick_1 is not None, "Level 1 must detect drift"

    # Strict latency hierarchy: Latency(L3) < Latency(L2) < Latency(L1)
    assert trip_tick_3 < trip_tick_2 < trip_tick_1, (
        f"Expected trip order L3 < L2 < L1, got L3={trip_tick_3}, L2={trip_tick_2}, L1={trip_tick_1}"
    )


def test_criticality_zero_false_positives_on_nominal_cycles():
    """
    Validates statistical stability: 1,000 nominal Gaussian cycles
    produce exactly zero false alarms across all three criticality levels.
    """
    np.random.seed(42)
    nominal_readings = np.random.normal(loc=10.0, scale=0.15, size=1000)

    for level in [1, 2, 3]:
        detector = DriftDetector(metric_name="Iddq", mean=10.0, std=0.15, criticality_level=level)
        false_alarms = 0
        for val in nominal_readings:
            flag, _ = detector.update(val)
            if flag:
                false_alarms += 1
        assert false_alarms == 0, f"Criticality Level {level} had {false_alarms} false alarms on nominal noise"
