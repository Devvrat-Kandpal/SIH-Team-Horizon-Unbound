"""
Backend/criticality_config.py — Project ARJUNA (SIH 26170)
Centralized mission-criticality-weighted threshold configuration.

Convention:
    Level 1 = lower criticality (COTS / ground-support applications)
    Level 2 = nominal / standard space qualification baseline
    Level 3 = highest / mission-critical (flight hardware, human-rated missions)

Threshold derivation (from simulator.py physics):
  - Temperature sensor noise: σ = 0.15 °C (Gaussian, simulator.py)
  - Iddq (normal mode) noise: σ ≈ 1.15 µA (simulator.py)
  - ADC: 12-bit, T_max = 175 °C → LSB ≈ 0.043 °C (dominated by Gaussian noise)

CUSUM parameters:
  - k (allowance): fixed at 0.5 across all levels.
      Rationale: CUSUM operates on Iddq (µA). k = 0.5 µA is calibrated to the
      Iddq measurement domain (σ ≈ 1.17 µA); k/σ ≈ 0.43 — a sub-σ allowance
      tuned to detect small persistent latent shifts (δ ≈ 0.5–1.0σ) without
      excessive false alarms on nominal lots. k does NOT change with
      criticality — only the decision threshold (h) changes.
  - h (threshold): varies with criticality level (see table below).
      Level 3 (h=3.5): fires after ~7 consecutive elevated readings — earliest alarm.
      Level 2 (h=5.0): fires after ~10 consecutive elevated readings — baseline.
      Level 1 (h=7.0): fires after ~14 consecutive elevated readings — most tolerant.

Isolation Forest score thresholds:
  - Normal telemetry at 125°C produces anomaly_score ≈ 0.025–0.08 (measured).
  - The gap between normal ceiling (0.08) and Level 3 gate (0.45) is ~5.6×.
  - Level 1: 0.65
  - Level 2: 0.55
  - Level 3: 0.45
"""

from typing import Any, Dict

CRITICALITY_CONFIG: Dict[int, Dict[str, Any]] = {
    1: {
        "cusum_threshold": 7.0,
        "cusum_k": 0.5,
        "if_score_threshold": 0.65,
        "fault_label": "LOW-CRITICALITY",
        "description": "COTS / ground-support — standard tolerance",
    },
    2: {
        "cusum_threshold": 5.0,
        "cusum_k": 0.5,
        "if_score_threshold": 0.55,
        "fault_label": "STANDARD",
        "description": "Nominal space qualification — ECSS-Q-ST-60-02C baseline",
    },
    3: {
        "cusum_threshold": 3.5,
        "cusum_k": 0.5,
        "if_score_threshold": 0.45,
        "fault_label": "MISSION-CRITICAL",
        "description": "Flight hardware / human-rated missions — tightest tolerance",
    },
}


def get_config(criticality_level: int) -> Dict[str, Any]:
    """
    Returns the threshold configuration for the given criticality level.
    Raises ValueError for invalid levels (not 1, 2, or 3).
    """
    if criticality_level not in CRITICALITY_CONFIG:
        raise ValueError(
            f"Invalid criticality_level={criticality_level!r}. "
            f"Must be one of: 1 (low), 2 (nominal), 3 (mission-critical)."
        )
    return CRITICALITY_CONFIG[criticality_level]
