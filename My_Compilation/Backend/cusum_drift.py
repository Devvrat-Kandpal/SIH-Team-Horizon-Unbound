"""
cusum_drift.py — Project ARJUNA (SIH 26170): Time-Series CUSUM Drift Detector
Author: Member 4 (Time-Series AI Specialist)

Implements the Tabular Cumulative Sum (CUSUM) statistical quality control algorithm
for detecting slow, latent thermal and parametric creep in space-grade electronics
during High-Temperature Operating Life (HTOL) screening per ECSS-Q-ST-60-02C.

Decision thresholds are mission-criticality-weighted via CRITICALITY_CONFIG:
  - Level 3 (mission-critical): tightest threshold → earliest alarm
  - Level 2 (nominal):          standard ECSS baseline
  - Level 1 (low-criticality):  widest threshold → only sustained drift fires alarm

The CUSUM accumulation formula, stateful register, and reset behavior are
unchanged regardless of criticality level. Only the decision threshold (h) varies.
"""

import os
import sys

# Resolve criticality_config from Backend or project root
try:
    from Backend.criticality_config import get_config
except ImportError:
    _this_dir = os.path.dirname(os.path.abspath(__file__))
    _root_dir = os.path.dirname(_this_dir)
    if _this_dir not in sys.path:
        sys.path.insert(0, _this_dir)
    if _root_dir not in sys.path:
        sys.path.insert(0, _root_dir)
    from criticality_config import get_config


class DriftDetector:
    """
    Stateful Cumulative Sum (CUSUM) anomaly detector for early degradation tracking.
    Formula: S_n^+ = max(0, S_{n-1}^+ + X_n - (mu + k))

    The decision threshold (h) is criticality-aware:
      - Level 1 (low):            h = 7.0  (most tolerant)
      - Level 2 (nominal/default): h = 5.0  (ECSS baseline)
      - Level 3 (mission-critical): h = 3.5  (tightest — earliest alarm)

    The allowance k is fixed at 0.5 across all levels — it is calibrated to the
    sensor noise floor (σ ≈ 0.15 °C), not to mission criticality.
    """

    def __init__(
        self,
        metric_name: str = "Iddq",
        mean: float = 10.0,
        std: float = 1.17,
        k: float = None,
        threshold: float = None,
        criticality_level: int = 2,
    ):
        self.metric_name = metric_name

        # Target nominal baseline
        self.mean = float(mean)

        # Expected nominal standard deviation (informational; not used in CUSUM formula)
        self.std = float(std)

        self.criticality_level = criticality_level
        cfg = get_config(criticality_level)

        # Sensitivity / reference parameter (allowance).
        # If caller explicitly passes k, use it; otherwise use config value.
        # k tracks the sensor noise floor — it should NOT change with criticality.
        self.k = float(k) if k is not None else float(cfg["cusum_k"])

        # Decision threshold (h) — criticality-weighted.
        # If caller explicitly passes threshold, use it; otherwise use config value.
        self.threshold = float(threshold) if threshold is not None else float(cfg["cusum_threshold"])

        # Stateful cumulative positive deviation
        self.cusum = 0.0

        # Detection latch
        self.drift_detected = False

    def update_criticality(self, criticality_level: int) -> None:
        """
        Updates the decision threshold to match a new criticality level.
        The CUSUM accumulator and alarm latch are NOT reset — call reset()
        separately if a full state clear is needed.

        Only the threshold (h) changes; k stays fixed (noise-floor calibrated).
        """
        cfg = get_config(criticality_level)
        self.criticality_level = criticality_level
        self.threshold = float(cfg["cusum_threshold"])
        # k intentionally not changed — it is a noise-floor constant, not a criticality parameter

    def evaluate_drift(self, sensor_value: float) -> bool:
        """
        Processes a single incoming sensor reading and updates the stateful CUSUM register.
        Returns True if accumulated drift exceeds the criticality-weighted safety threshold.
        """
        if self.drift_detected:
            return True

        # Positive CUSUM calculation
        self.cusum = max(0.0, self.cusum + float(sensor_value) - (self.mean + self.k))

        # Check detection threshold
        if self.cusum >= self.threshold:
            self.drift_detected = True
            return True

        return False

    def get_status(self) -> dict:
        """Returns the current state of the CUSUM detector for telemetry logging."""
        return {
            "metric": self.metric_name,
            "mean": self.mean,
            "k": self.k,
            "threshold": self.threshold,
            "criticality_level": self.criticality_level,
            "cusum": round(self.cusum, 4),
            "drift_detected": self.drift_detected,
        }

    @property
    def allowance(self) -> float:
        return self.k

    @property
    def s_plus(self) -> float:
        return self.cusum

    def update(self, sensor_value: float) -> tuple[bool, float]:
        """Convenience method returning (is_drift, current_cusum_s_plus)."""
        flag = self.evaluate_drift(sensor_value)
        return flag, self.cusum

    def reset(self) -> None:
        """Resets the stateful accumulator back to zero."""
        self.cusum = 0.0
        self.drift_detected = False


if __name__ == "__main__":
    import random

    print("==========================================================================")
    print("  PROJECT ARJUNA (SIH 26170): CUSUM DRIFT DETECTOR STANDALONE DEMO")
    print("==========================================================================")

    for level in [1, 2, 3]:
        print(f"\n--- Criticality Level {level} ---")
        detector = DriftDetector(metric_name="Iddq", mean=10.0, std=1.17, criticality_level=level)
        print(f"  CUSUM threshold (h) = {detector.threshold}, k = {detector.k}")

        print("  [Phase 1] 20 Normal Sensor Readings (±0.2 µA jitter)...")
        for step in range(1, 21):
            iddq = 10.0 + random.uniform(-0.2, 0.2)
            flag = detector.evaluate_drift(iddq)
            if flag:
                print(f"    FALSE ALARM at Step {step:02d}! (Should not happen)")
                break
        else:
            print(f"    No false alarms (CUSUM S+ = {detector.cusum:.4f})")

        print("  [Phase 2] Slow Latent Creep (+0.25 µA per step)...")
        iddq = 10.0
        for step in range(21, 60):
            iddq += 0.25 + random.uniform(-0.05, 0.05)
            flag = detector.evaluate_drift(iddq)
            if flag:
                print(
                    f"    --> CUSUM DRIFT ALARM at Step {step:02d} (S+ = {detector.cusum:.4f} >= {detector.threshold})"
                )
                break

    print("\n[SUCCESS] CUSUM Criticality Demo Complete.")
