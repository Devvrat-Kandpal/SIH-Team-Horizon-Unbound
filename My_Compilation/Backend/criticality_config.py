"""
Backend/criticality_config.py — Project ARJUNA (SIH 26170)
Centralized mission-criticality-weighted threshold configuration.

Convention:
    Level 1 = lower criticality (COTS / ground-support applications)
    Level 2 = nominal / standard space qualification baseline
    Level 3 = highest / mission-critical (flight hardware, human-rated missions)

Threshold derivation (from simulator.py physics):
  - Temperature sensor noise: σ = 0.15 °C (Gaussian, simulator.py)
  - Iddq (normal mode) lot-jitter: σ ≈ 1.15 µA (simulator.py compute_iddq_and_prop_delay:
      `10.0 * thermal_ratio + random.gauss(0, 1.15)`) — this is the per-reading LOT
      spread the simulator prints into generated CSVs (measured 1.17 µA on sample_data).
  - ADC: 12-bit, T_max = 175 °C → LSB ≈ 0.043 °C (dominated by Gaussian noise)

CUSUM parameters:
  - k (allowance): fixed at 0.5 across all levels.
      k/σ relative to the simulator LOT-JITTER domain (σ ≈ 1.15 µA) is ≈ 0.43 — a
      sub-σ allowance per the classic CUSUM design convention (δ ≈ 0.5–1.0σ shifts).

  IMPORTANT — two noise domains, keep them distinct:
    (a) Lot-jitter domain (σ ≈ 1.15 µA): the cross-component spread printed into
        generated CSVs / used for training. A CUSUM referenced to a GLOBAL mean on
        this domain false-alarms (measured ~36%–79% of ticks for k=0.5 across levels).
        This is why the detector uses per-DUT AUTO-BASELINE: each component is
        referenced to its OWN first 15 readings (robust median), so lot position is
        cancelled out and this cross-component spread is NOT interpreted as drift.
    (b) Live per-tick sensor domain (σ ≈ 0.15 µA): the server's real-time nominal Iddq
        (`server.py`: 10.0 * thermal_ratio + gauss(0, 0.15), clamped [9, 11.5]). This is
        what the DEPLOYED CUSUM actually consumes after auto-baseline. Here k=0.5 is
        conservative (k/σ ≈ 3.3). Verified by Monte Carlo on 200 parts × 1000 ticks:
        0 false alarms at every level; detection latency for a +0.05 µA/tick creep was
        L3≈29, L2≈31, L1≈34 ticks.
  - h (threshold): varies with criticality level (see table below).
      For a sustained +1.0 µA elevation (δ=1.0), each tick advances S+ by (δ - k) = 0.5,
      so the alarm fires after h/0.5 ticks:
      Level 3 (h=3.5): ~7 consecutive elevated readings — earliest alarm.
      Level 2 (h=5.0): ~10 consecutive elevated readings — baseline.
      Level 1 (h=7.0): ~14 consecutive elevated readings — most tolerant.
  - The exact per-level latency on the LIVE low-noise domain for small creep was measured
    (≈29/31/34 ticks for +0.05 µA/tick) — see the Monte Carlo note above.

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
