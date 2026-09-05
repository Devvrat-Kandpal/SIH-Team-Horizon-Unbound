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

import math
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

    # The allowance k = 0.5 µA is calibrated to the Iddq measurement domain (σ ≈ 1.17 µA).
    # k/σ ≈ 0.43. This places k in the sub-σ range effective for detecting small,
    # persistent latent shifts (δ ≈ 0.5–1.0σ) without excessive false alarms on nominal lots.
    # k does NOT change with criticality level — the threshold h carries the criticality burden.
    #
    # CALIBRATION-DOMAIN RESOLUTION (auto_baseline):
    # k = 0.5 µA with h = 3.5–7.0 assumes sensor noise σ ≈ 0.2 µA around the DUT's own
    # baseline. Raw population spread (σ ≈ 1.17 µA lot variation) referenced to a GLOBAL
    # mean would falsely accumulate (measured 92% flag rate — see
    # evaluate_model.benchmark_unclamped_nominal, iid mode). The fix is NOT re-deriving
    # k/h per domain but per-DUT auto-baseline calibration (auto_baseline=True): the
    # first `baseline_window` readings lock THIS component's own reference (robust
    # median), so CUSUM measures drift from the part itself — invariant to lot position.
    # This matches standard HTOL practice where each DUT is referenced to its own
    # t=0 characterization.
    """

    def __init__(
        self,
        metric_name: str = "Iddq",
        mean: float = 10.0,
        std: float = 1.17,
        k: float | None = None,
        threshold: float | None = None,
        criticality_level: int = 2,
        auto_baseline: bool = False,
        baseline_window: int = 15,
    ):
        self.metric_name = metric_name

        # Target nominal baseline. With auto_baseline=True this is only the
        # PRIOR estimate; the detector re-calibrates to the individual DUT's
        # own baseline from its first `baseline_window` readings (robust median).
        self.mean = float(mean)

        # Expected nominal standard deviation (informational; not used in CUSUM formula)
        self.std = float(std)

        self.criticality_level = criticality_level
        cfg = get_config(criticality_level)

        # Per-DUT auto-baseline state (standard HTOL practice: each component is
        # referenced to its OWN initial readings, not the population mean, so
        # natural lot-to-lot / part-to-part spread (σ ≈ 1.17 µA) cannot accumulate
        # as false drift. Drift is then measured relative to the part itself.)
        self.auto_baseline = bool(auto_baseline)
        self.baseline_window = max(1, int(baseline_window))
        self._baseline_samples: list[float] = []
        self._baseline_locked: bool = not auto_baseline
        self.baseline_prior: float = float(mean)

        # Sensitivity / reference parameter (allowance).
        # If caller explicitly passes k, use it; otherwise use config value.
        # k tracks the sensor noise floor — it should NOT change with criticality.
        self.k = float(k) if k is not None else float(cfg["cusum_k"])

        # Decision threshold (h) — criticality-weighted.
        # If caller explicitly passes threshold, use it; otherwise use config value.
        self.threshold = (
            float(threshold) if threshold is not None else float(cfg["cusum_threshold"])
        )

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

        With auto_baseline=True, the first `baseline_window` finite readings are used to
        re-calibrate the reference mean to THIS component's own baseline (robust median);
        during that learning phase no drift alarm is raised (INITIALIZING semantics,
        mirroring Module B's insufficient-observation behaviour).
        """
        if self.drift_detected:
            return True

        value = float(sensor_value)

        # Non-finite telemetry guard (defensive, single-impulse latch prevention):
        # a NaN/±Inf sample must never wedge the CUSUM accumulator into a permanent
        # alarm, nor silently poison S+ with NaN (which would make the statistic
        # NaN-forever and unrecoverable without an operator reset). Module A already
        # hard-flags invalid/non-finite telemetry as a quarantined anomaly; CUSUM's
        # role is persistent drift, so it simply ignores non-finite samples and
        # remains recoverable. Valid finite telemetry is unaffected.
        if not math.isfinite(value):
            return False

        # Per-DUT baseline learning phase (auto_baseline only)
        if not self._baseline_locked:
            if value == value and value not in (float("inf"), float("-inf")):
                self._baseline_samples.append(value)
            if len(self._baseline_samples) >= self.baseline_window:
                samples = sorted(self._baseline_samples)
                mid = len(samples) // 2
                self.mean = float(
                    samples[mid]
                    if len(samples) % 2
                    else 0.5 * (samples[mid - 1] + samples[mid])
                )
                self._baseline_locked = True
            # Learning phase: never alarm on calibration data (fail-safe: nominal)
            return False

        # Positive CUSUM calculation
        self.cusum = max(0.0, self.cusum + value - (self.mean + self.k))

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
            "auto_baseline": self.auto_baseline,
            "baseline_calibrated": self._baseline_locked,
            "baseline_samples_collected": len(self._baseline_samples),
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
        """Resets the stateful accumulator back to zero.

        With auto_baseline=True the baseline learning phase is also re-armed
        (the next DUT / next scenario re-calibrates from scratch); the prior
        population mean is restored as the interim reference.
        """
        self.cusum = 0.0
        self.drift_detected = False
        if self.auto_baseline:
            self._baseline_samples = []
            self._baseline_locked = False
            self.mean = self.baseline_prior


if __name__ == "__main__":
    import random

    print("==========================================================================")
    print("  PROJECT ARJUNA (SIH 26170): CUSUM DRIFT DETECTOR STANDALONE DEMO")
    print("==========================================================================")

    for level in [1, 2, 3]:
        print(f"\n--- Criticality Level {level} ---")
        detector = DriftDetector(
            metric_name="Iddq", mean=10.0, std=1.17, criticality_level=level
        )
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
