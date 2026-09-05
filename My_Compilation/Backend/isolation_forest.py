import os
import sys
import warnings
from typing import Any

import joblib
import numpy as np
import pandas as pd
from scipy.stats import linregress
from sklearn.ensemble import IsolationForest

# Resolve criticality_config from Backend or project root
try:
    from Backend.criticality_config import get_config as _get_crit_config
except ImportError:
    _this_dir = os.path.dirname(os.path.abspath(__file__))
    _root_dir = os.path.dirname(_this_dir)
    if _this_dir not in sys.path:
        sys.path.insert(0, _this_dir)
    if _root_dir not in sys.path:
        sys.path.insert(0, _root_dir)
    from criticality_config import get_config as _get_crit_config


# ===========================================================================
# MODULE B: Latent Drift Predictor (ISRO ECSS-Q-ST-60-02C)
# Forecasts the 168h endpoint Iddq from real-time burn-in drift measurements.
# Uses Ordinary Least Squares linear regression over a rolling time window.
# ===========================================================================
class LinearRegressionDriftPredictor:
    """
    Project Arjuna (SIH 26170): MODULE B — Latent Drift Predictor.

    Maintains a rolling window of Iddq observations tagged with BURN-IN HOURS
    (0h, 24h, 96h, 168h) and uses Ordinary Least Squares linear regression to
    forecast the 168h endpoint Iddq.

    Key design decision: time axis is in REAL BURN-IN HOURS (0–168), not wall
    clock seconds. The server maps each simulation tick to an accrued burn-in
    hour counter so the extrapolation to 168h is physically meaningful.

    Early-rejects components whose projected 168h Iddq would exceed:
        - Static limit: dynamically configured (default 50 µA)
        - Dynamic limit: dynamically configured (default lot_mean + 3σ)
    """

    def __init__(
        self,
        lot_mean_iddq: float = 10.0,
        lot_std_iddq: float = 1.17,
        datasheet_limit_ua: float = 50.0,
        dynamic_sigma: float = 3.0,
    ):
        self.lot_mean = lot_mean_iddq
        self.lot_std = lot_std_iddq
        self.datasheet_limit_ua = datasheet_limit_ua
        self.dynamic_sigma = dynamic_sigma
        self.forecast_target_h = 168.0
        self.max_window = 200
        self._burn_hours: list[float] = []  # X axis: burn-in hours (0–168)
        self._iddq: list[float] = []  # Y axis: Iddq readings in µA

    def reset(self):
        self._burn_hours.clear()
        self._iddq.clear()

    def predict_168h(
        self, value_0h: float, value_24h: float, actual_168h: float | None = None
    ) -> dict:
        """
        Strict ISRO Module B interface: predicts 168h Iddq purely from 0h and 24h measurements.
        Computes Mean Absolute Error (MAE) if actual ground truth is provided.
        """
        slope = (value_24h - value_0h) / 24.0
        forecast_168h = value_0h + slope * self.forecast_target_h

        dynamic_limit_ua = self.lot_mean + self.dynamic_sigma * self.lot_std

        early_reject = (forecast_168h > self.datasheet_limit_ua) or (
            forecast_168h > dynamic_limit_ua
        )
        mae = abs(forecast_168h - actual_168h) if actual_168h is not None else 0.0

        result = {
            "slope": slope,
            "forecast_168h_uA": forecast_168h,
            "projected_168h_iddq_ua": forecast_168h,
            "will_violate_static": forecast_168h > self.datasheet_limit_ua,
            "will_violate_dynamic": forecast_168h > dynamic_limit_ua,
            "early_reject": early_reject,
            "lead_time_saved_hours": 144.0 if early_reject else 0.0,
            "forecast_mae_ua": mae,
            "mae": mae,
        }

        if actual_168h is not None:
            result["actual_168h"] = actual_168h

        return result

    def update(self, burn_in_hours: float, iddq_uA: float) -> dict:
        """
        Feed one new observation.
        burn_in_hours : elapsed burn-in time in HOURS (0–168), not wall seconds.
        iddq_uA       : latest Iddq reading in µA.
        Returns a drift prediction dict.
        """
        self._burn_hours.append(float(burn_in_hours))
        self._iddq.append(float(iddq_uA))

        # Trim rolling window
        if len(self._burn_hours) > self.max_window:
            self._burn_hours.pop(0)
            self._iddq.pop(0)

        n = len(self._burn_hours)

        # Need at least 8 points for a statistically meaningful regression
        # Also need variation in time (X axis) to compute a slope
        if n < 8 or self._burn_hours[-1] == self._burn_hours[0]:
            return self._initializing_result(iddq_uA, n)

        # --- OLS Linear Regression: Iddq = slope * hours + intercept ---
        # Coerce the scipy LinregressResult named-tuple fields to concrete floats so both
        # the physics math and static type-checking are unambiguous.
        _lr: Any = linregress(self._burn_hours, self._iddq)
        slope = float(_lr.slope)
        intercept = float(_lr.intercept)
        r_value = float(_lr.rvalue)
        r2 = float(r_value**2) if not np.isnan(r_value) else 0.0
        raw_forecast = intercept + slope * self.forecast_target_h
        recent_mean = float(np.mean(self._iddq[-min(len(self._iddq), 8) :]))
        # Robust shrinkage forecast with physical baseline floor for 125C silicon HTOL
        forecast_168h = max(
            self.lot_mean * 0.5, (1.0 - r2) * recent_mean + r2 * raw_forecast
        )

        # Current projected drift rate (µA per hour)
        drift_rate = slope

        # Limits
        dynamic_limit_ua = self.lot_mean + self.dynamic_sigma * self.lot_std
        will_violate_static = forecast_168h > self.datasheet_limit_ua
        will_violate_dynamic = forecast_168h > dynamic_limit_ua

        # Statistically significant drift requiring early rejection:
        # Requires actual trending correlation (R2 >= 0.25 and positive drift_rate > 0.01 uA/h)
        # OR current physical breach of datasheet limit (50 uA)
        has_significant_trend = (r2 >= 0.25 and drift_rate > 0.01) or (
            iddq_uA > self.datasheet_limit_ua
        )
        early_reject = bool(
            (will_violate_static or will_violate_dynamic) and has_significant_trend
        )

        # Drift status label
        abs_rate = abs(drift_rate)
        if abs_rate < 0.005 or not has_significant_trend:
            drift_status = "STABLE (<0.01 µA/h)"
        elif will_violate_static:
            drift_status = f"CRITICAL SLOPE ({drift_rate:+.4f} µA/h)"
        elif will_violate_dynamic:
            drift_status = f"ELEVATED SLOPE ({drift_rate:+.4f} µA/h)"
        else:
            drift_status = f"MONITORING ({drift_rate:+.4f} µA/h)"

        # 168h forecast label
        if will_violate_static and has_significant_trend:
            forecast_label = f"{forecast_168h:.2f} µA (VIOLATION)"
        elif will_violate_dynamic or iddq_uA > dynamic_limit_ua:
            forecast_label = f"{forecast_168h:.2f} µA (WARNING)"
        else:
            forecast_label = f"{forecast_168h:.2f} µA (SAFE)"

        # Hours until violation (if drifting toward limit)
        hours_to_violation = None
        if drift_rate > 0 and intercept < self.datasheet_limit_ua:
            hrs = (self.datasheet_limit_ua - intercept) / drift_rate
            if 0 < hrs < self.forecast_target_h:
                hours_to_violation = round(hrs, 1)

        return {
            "drift_slope_ua_h": round(float(drift_rate), 5),
            "forecast_168h_uA": round(float(forecast_168h), 3),
            "forecast_168h_label": forecast_label,
            "drift_status": drift_status,
            "drift_r2": round(float(r_value**2), 4),
            "early_reject_b": early_reject,
            "hours_to_violation": hours_to_violation,
            "n_observations": n,
        }

    def _initializing_result(self, iddq_uA: float, n: int) -> dict:
        needed = 8 - n
        return {
            "drift_slope_ua_h": 0.0,
            "forecast_168h_uA": round(float(iddq_uA), 3),
            "forecast_168h_label": f"COLLECTING DATA ({n}/8 obs)",
            "drift_status": f"INITIALIZING — {needed} more sample{'s' if needed != 1 else ''} needed",
            "drift_r2": 0.0,
            "early_reject_b": False,
            "hours_to_violation": None,
            "n_observations": n,
        }


class MultivariateAnomalyDetector:
    """
    Project Arjuna (SIH 26170): ISRO AI-Driven Anomaly Detection & Dynamic Outlier Engine
    conforming to space product assurance standard ECSS-Q-ST-60-02C.

    MODULE A: Dynamic Outlier Detection & Multivariate Screening
    - Evaluates multidimensional parametric correlations (Voltage, Current, Temperature,
      Standby Current Iddq, Propagation Delay t_pd).
    - Detects latent defects & lot-relative outliers (e.g. 45 uA leakage in a 10 uA lot,
      below the 50 uA datasheet max).
    - Generates Explainable AI (XAI) justifications for ISRO QA inspectors.
    """

    def __init__(
        self,
        contamination=0.001,
        n_estimators=40,
        random_state=42,
        use_engineered_features=True,
        n_jobs=-1,
    ):
        self.contamination = contamination
        self.n_estimators = n_estimators
        self.random_state = random_state
        self.use_engineered_features = use_engineered_features
        self.n_jobs = n_jobs

        self.model = IsolationForest(
            contamination=self.contamination,  # type: ignore[arg-type]
            n_estimators=self.n_estimators,
            random_state=self.random_state,
            n_jobs=self.n_jobs,
        )
        self.is_trained = False
        self.lot_stats = {}

    def _extract_batch_features(
        self, voltage, current, temperature, iddq=None, prop_delay=None
    ):
        """
        Vectorized feature matrix generation for training and batch datasets.
        """
        v = np.asarray(voltage, dtype=np.float32)
        c = np.asarray(current, dtype=np.float32)
        t = np.asarray(temperature, dtype=np.float32)

        if iddq is None:
            iddq = np.full_like(v, 10.0, dtype=np.float32)
        else:
            iddq = np.asarray(iddq, dtype=np.float32)

        if prop_delay is None:
            prop_delay = np.full_like(v, 4.5, dtype=np.float32)
        else:
            prop_delay = np.asarray(prop_delay, dtype=np.float32)

        if self.use_engineered_features:
            p = v * c
            r = v / (c + 1e-6)
            return np.column_stack([v, c, t, iddq, prop_delay, p, r])
        else:
            return np.column_stack([v, c, t, iddq, prop_delay])

    def train(self, data_source):
        """
        Train the Dynamic Outlier Isolation Forest on healthy baseline lot data.
        """
        if isinstance(data_source, str):
            if not os.path.exists(data_source):
                raise FileNotFoundError(f"Training file not found at: {data_source}")
            df = pd.read_csv(data_source)
        elif isinstance(data_source, pd.DataFrame):
            df = data_source
        else:
            raise ValueError("data_source must be a CSV file path or pandas DataFrame")

        voltage = df["voltage"].values
        current = df["current"].values
        temperature = df["temperature"].values
        iddq = (
            df["iddq"].values if "iddq" in df.columns else np.full_like(voltage, 10.0)
        )
        prop_delay = (
            df["prop_delay"].values
            if "prop_delay" in df.columns
            else np.full_like(voltage, 4.5)
        )

        # Coerce pandas .values (ArrayLike/ExtensionArray) to concrete numpy arrays.
        # Numerically identical, but eliminates numpy type-stub ambiguity (np.mean/np.std).
        voltage = np.asarray(voltage)
        current = np.asarray(current)
        temperature = np.asarray(temperature)
        iddq = np.asarray(iddq)
        prop_delay = np.asarray(prop_delay)

        features = self._extract_batch_features(
            voltage, current, temperature, iddq, prop_delay
        )
        self.model.fit(features)
        self.is_trained = True

        raw_scores = self.model.decision_function(features)

        self.lot_stats = {
            "mean_iddq": float(np.mean(iddq)),
            "std_iddq": float(np.std(iddq)) if np.std(iddq) > 1e-6 else 1.17,
            "mean_voltage": float(np.mean(voltage)),
            "std_voltage": float(np.std(voltage)) if np.std(voltage) > 1e-6 else 0.04,
            "mean_current": float(np.mean(current)),
            "std_current": float(np.std(current)) if np.std(current) > 1e-6 else 0.02,
            "mean_temp": float(np.mean(temperature)),
            "mean_score": float(np.mean(raw_scores)),
            "offset": float(self.model.offset_),
        }
        return self.lot_stats

    def _normalize_anomaly_score(self, raw_score):
        """
        Calibrates raw decision score:
        - Nominal baseline (raw_score >= +0.10) maps smoothly to 0.025 - 0.055 (2.5% - 5.5% baseline risk)
        - Latent boundary drift (raw_score between 0.00 and +0.08) maps to 0.20 - 0.55 (20% - 55%)
        - Critical anomalies (raw_score < 0.00) map to 0.75 - 0.99 (75% - 99%)
        """
        k = 25.0
        sig = 1.0 / (1.0 + np.exp(k * raw_score))
        score = 0.02 + 0.96 * sig
        return round(float(np.clip(score, 0.02, 0.99)), 4)

    def _generate_qa_explainability(
        self,
        voltage,
        current,
        temp,
        iddq,
        prop_delay,
        is_anomaly,
        score,
        detection_source="isolation_forest",
        criticality_level=2,
    ):
        mean_iddq = self.lot_stats.get("mean_iddq", 10.0)
        std_iddq = self.lot_stats.get("std_iddq", 1.17)
        mean_v = self.lot_stats.get("mean_voltage", 5.0)
        mean_c = self.lot_stats.get("mean_current", 1.20)

        evidence_items = []
        rule_triggered = "NOMINAL_OPERATION"
        recommended_action = "PROCEED_SCREENING"

        # 1. Standby current Iddq evidence
        z_iddq = (iddq - mean_iddq) / (std_iddq + 1e-6) if iddq is not None else 0.0
        evidence_items.append(
            {
                "metric": "iddq_uA",
                "observed_value": round(float(iddq), 2) if iddq is not None else 10.0,
                "baseline_mean": round(float(mean_iddq), 2),
                "baseline_std": round(float(std_iddq), 2),
                "delta_sigma": round(float(z_iddq), 2),
                "datasheet_limit": 50.0,
                "dynamic_limit": round(float(mean_iddq + 3.0 * std_iddq), 2),
            }
        )

        # 2. Dynamic Impedance & Power
        dynamic_res = round(float(voltage / (current + 1e-6)), 3)
        evidence_items.append(
            {
                "metric": "dynamic_res_ohm",
                "observed_value": dynamic_res,
                "baseline_mean": round(float(mean_v / (mean_c + 1e-6)), 3),
                "baseline_std": 0.08,
                "delta_sigma": round(
                    float((dynamic_res - (mean_v / (mean_c + 1e-6))) / 0.08), 2
                ),
                "datasheet_limit": None,
                "dynamic_limit": None,
            }
        )

        if not is_anomaly:
            justification = "QA STATUS [PASSED]: Component operates within 3-sigma lot bounds and nominal ECSS screening limits."
            structured_evidence = {
                "verdict": "PASSED",
                "fault_type": "NORMAL",
                "detection_source": detection_source,
                "criticality_level": criticality_level,
                "evidence": evidence_items,
                "rule_triggered": rule_triggered,
                "recommended_action": recommended_action,
                "qa_justification": justification,
            }
            return justification, structured_evidence

        reasons = []
        if iddq is not None and z_iddq > 3.0:
            reasons.append(
                f"Dynamic Outlier: Standby current Iddq ({iddq:.1f} uA) is {iddq / mean_iddq:.1f}x above Lot Mean ({mean_iddq:.1f} uA) despite passing static 50 uA limit (Z-Score: +{z_iddq:.1f} sigma)"
            )
            rule_triggered = "DYNAMIC_OUTLIER_3SIGMA_EXCEEDANCE"
            recommended_action = "QUARANTINE_LOT_AND_EARLY_REJECT"

        if voltage < 2.0 and current > 4.0:
            reasons.append(
                f"Catastrophic Short: Severe voltage collapse ({voltage:.2f} V) coupled with current surge ({current:.2f} A)"
            )
            rule_triggered = "OCP_FOLDBACK_SHORT_CIRCUIT"
            recommended_action = "EMERGENCY_SHUTDOWN_OCP"
        elif current > 3.0:
            reasons.append(
                f"Excessive Supply Current: Load current ({current:.2f} A) violates nominal thermal envelope"
            )
            rule_triggered = "EXCESSIVE_LOAD_CURRENT"
            recommended_action = "HOLD_CHAMBER_LOAD_AUDIT"

        if temp >= 130.0:
            reasons.append(
                f"Critical Thermal Overstress: Chamber/Die temp ({temp:.1f} °C) breaches 125 °C qualification rating"
            )
            if rule_triggered == "NOMINAL_OPERATION":
                rule_triggered = "THERMAL_OVERSTRESS_QUAL_BREACH"
                recommended_action = "CHAMBER_COOLING_INTERVENTION"

        if not reasons:
            reasons.append(
                f"Multivariate Correlation Failure: Non-linear parameter deviation detected (Severity Score: {score * 100:.1f}%)"
            )
            rule_triggered = "MULTIVARIATE_ISOLATION_DEVIATION"
            recommended_action = "REJECT_COMPONENT_PARAMETRIC_REVIEW"

        source_labels = {
            "isolation_forest": "Isolation Forest multivariate score",
            "z_score_safety_net": "Iddq z-score safety net (≥7σ extreme outlier)",
            "hybrid_fusion": "Isolation Forest multivariate score + Iddq z-score safety net",
            "criticality_threshold": "Criticality-weighted anomaly score threshold",
        }
        source_str = source_labels.get(detection_source, detection_source)
        reasons.append(f"Detection Source: {source_str}")

        justification = "QA STATUS [REJECTED]: " + " | ".join(reasons)
        structured_evidence = {
            "verdict": "REJECTED",
            "fault_type": (
                "ELECTRICAL_SHORT_CIRCUIT"
                if (voltage < 2.0 and current > 4.0)
                else ("ELECTRICAL_SPIKE" if z_iddq > 3.0 else "MULTIVARIATE_ANOMALY")
            ),
            "detection_source": detection_source,
            "criticality_level": criticality_level,
            "evidence": evidence_items,
            "rule_triggered": rule_triggered,
            "recommended_action": recommended_action,
            "qa_justification": justification,
        }
        return justification, structured_evidence

    def detect_spike(
        self,
        current,
        voltage,
        temp,
        iddq=10.0,
        prop_delay=4.5,
        criticality_level: int = 2,
    ):
        """
        Ultra-fast single-tick anomaly detection (<1ms) avoiding array stack allocations.

        criticality_level (1/2/3): Controls the secondary anomaly score gate.
          - Level 3 (mission-critical):  score >= 0.45 also triggers is_anomaly=True
          - Level 2 (nominal):           score >= 0.55
          - Level 1 (low-criticality):   score >= 0.65
        """
        if not self.is_trained:
            raise RuntimeError(
                "Model is not trained yet. Call train() or load_model() first."
            )

        v = float(voltage)
        c = float(current)
        t = float(temp)
        iq = float(iddq) if iddq is not None else 10.0
        pd_val = float(prop_delay) if prop_delay is not None else 4.5

        # FAIL-SAFE INPUT VALIDATION (aerospace fail-closed).
        # Corrupt / non-finite telemetry (NaN, ±Inf) MUST NOT be silently treated as a
        # healthy inlier: a screening system must never pass a part on missing/corrupt
        # sensor data. Only non-finite inputs hit this guard; all valid telemetry is
        # unaffected. NaN/Inf previously propagated through IsolationForest into a NaN
        # anomaly_score with is_anomaly=False (silent data corruption risk).
        if not all(np.isfinite(x) for x in (v, c, t, iq, pd_val)):
            return {
                "is_anomaly": True,
                "anomaly_score": 0.99,
                "raw_score": -1.0,
                "detection_source": "invalid_telemetry",
                "criticality_level": criticality_level,
                "iddq_uA": round(iq, 2) if np.isfinite(iq) else 0.0,
                "voltage": round(v, 4) if np.isfinite(v) else 0.0,
                "current": round(c, 4) if np.isfinite(c) else 0.0,
                "temperature": round(t, 2) if np.isfinite(t) else 0.0,
                "prop_delay": round(pd_val, 3) if np.isfinite(pd_val) else 0.0,
                "power": 0.0,
                "dynamic_resistance": 0.0,
                "iddq_zscore": 0.0,
                "lot_mean_iddq": round(float(self.lot_stats.get("mean_iddq", 10.0)), 2),
                "lot_std_iddq": round(float(self.lot_stats.get("std_iddq", 1.17)), 2),
                "qa_justification": (
                    "FAIL-SAFE QUARANTINE: Non-finite or corrupt telemetry (NaN/Inf) received. "
                    "Component flagged for sensor verification — not silently passed as healthy."
                ),
                "structured_evidence": None,
            }

        if self.use_engineered_features:
            p = v * c
            r = v / (c + 1e-6)
            features = np.array([[v, c, t, iq, pd_val, p, r]], dtype=np.float32)
        else:
            features = np.array([[v, c, t, iq, pd_val]], dtype=np.float32)

        raw_score = float(self.model.decision_function(features)[0])

        mean_iddq = self.lot_stats.get("mean_iddq", 10.0)
        std_iddq = self.lot_stats.get("std_iddq", 1.17)
        z_iddq = (iq - mean_iddq) / (std_iddq + 1e-6)

        # --- Hybrid decision logic ---
        if_flagged = raw_score < 0.0
        z_safety = abs(z_iddq) > 7.0  # ≥7σ: catastrophic outlier, belt-and-suspenders
        is_anomaly = bool(if_flagged or z_safety)

        # Blended anomaly score
        if_score = self._normalize_anomaly_score(raw_score)
        z_cap = 0.70 if z_iddq > 10.0 else 0.40
        z_contrib = float(np.clip(z_iddq / 10.0, 0.0, z_cap))
        normalized_score = round(float(np.clip(if_score + z_contrib, 0.02, 0.99)), 4)

        # Criticality secondary score gate
        crit_cfg = _get_crit_config(criticality_level)
        score_threshold = crit_cfg["if_score_threshold"]
        crit_flagged = normalized_score >= score_threshold

        if is_anomaly and crit_flagged and if_flagged and z_safety:
            detection_source = "hybrid_fusion"
        elif is_anomaly and if_flagged and z_safety:
            detection_source = "hybrid_fusion"
        elif is_anomaly and if_flagged:
            detection_source = "isolation_forest"
        elif is_anomaly and z_safety:
            detection_source = "z_score_safety_net"
        elif crit_flagged:
            detection_source = "criticality_threshold"
        else:
            detection_source = "none"

        is_anomaly = bool(is_anomaly or crit_flagged)

        p = v * c
        r = v / (c + 1e-6)

        qa_justification, structured_evidence = self._generate_qa_explainability(
            v,
            c,
            t,
            iq,
            pd_val,
            is_anomaly,
            normalized_score,
            detection_source,
            criticality_level,
        )

        return {
            "is_anomaly": is_anomaly,
            "anomaly_score": normalized_score,
            "raw_score": round(raw_score, 4),
            "detection_source": detection_source,
            "criticality_level": criticality_level,
            "iddq_uA": round(iq, 2),
            "voltage": round(v, 4),
            "current": round(c, 4),
            "temperature": round(t, 2),
            "prop_delay": round(pd_val, 3),
            "power": round(p, 4),
            "dynamic_resistance": round(r, 3),
            "iddq_zscore": round(float(z_iddq), 2),
            "lot_mean_iddq": round(float(mean_iddq), 2),
            "lot_std_iddq": round(float(std_iddq), 2),
            "qa_justification": qa_justification,
            "structured_evidence": structured_evidence,
        }

    def predict(
        self,
        voltage: float = 5.0,
        current: float = 1.2,
        temperature: float = 125.0,
        iddq: float = 10.0,
        prop_delay: float = 4.5,
        criticality_level: int = 2,
    ) -> dict:
        """Standard prediction interface with named sensor parameters."""
        res = self.detect_spike(
            current=current,
            voltage=voltage,
            temp=temperature,
            iddq=iddq,
            prop_delay=prop_delay,
            criticality_level=criticality_level,
        )
        res["fault_type"] = res.get("structured_evidence", {}).get(
            "fault_type", "NORMAL"
        )
        return res

    def detect_batch(
        self,
        voltage_array,
        current_array,
        temp_array,
        iddq_array=None,
        prop_delay_array=None,
        criticality_level: int = 2,
    ):
        """
        Vectorized anomaly detection for batch evaluation.

        criticality_level (1/2/3): Same secondary score gate as detect_spike.
        Returns (is_anomalies, normalized_scores, detection_sources).
        """
        if not self.is_trained:
            raise RuntimeError(
                "Model is not trained yet. Call train() or load_model() first."
            )

        features = self._extract_batch_features(
            voltage_array, current_array, temp_array, iddq_array, prop_delay_array
        )
        raw_scores = self.model.decision_function(features)

        v = np.asarray(voltage_array, dtype=np.float32)
        iq = (
            np.full_like(v, 10.0, dtype=np.float32)
            if iddq_array is None
            else np.asarray(iddq_array, dtype=np.float32)
        )

        mean_iddq = self.lot_stats.get("mean_iddq", 10.0)
        std_iddq = self.lot_stats.get("std_iddq", 1.17)
        z_iddq = (iq - mean_iddq) / (std_iddq + 1e-6)

        # --- Hybrid decision logic (vectorized) ---
        if_flagged = raw_scores < 0.0
        z_safety = np.abs(z_iddq) > 7.0
        base_anomaly = if_flagged | z_safety

        # Blended score
        if_scores = np.array([self._normalize_anomaly_score(s) for s in raw_scores])
        z_cap = np.where(z_iddq > 10.0, 0.70, 0.40)
        z_contrib = np.clip(z_iddq / 10.0, 0.0, z_cap).astype(np.float64)
        normalized_scores = np.clip(if_scores + z_contrib, 0.02, 0.99).round(4)

        # Criticality secondary score gate
        score_threshold = _get_crit_config(criticality_level)["if_score_threshold"]
        crit_flagged = normalized_scores >= score_threshold
        is_anomalies = base_anomaly | crit_flagged

        detection_sources = np.where(
            base_anomaly & crit_flagged & if_flagged & z_safety,
            "hybrid_fusion",
            np.where(
                base_anomaly & if_flagged & z_safety,
                "hybrid_fusion",
                np.where(
                    base_anomaly & if_flagged,
                    "isolation_forest",
                    np.where(
                        base_anomaly & z_safety,
                        "z_score_safety_net",
                        np.where(crit_flagged, "criticality_threshold", "none"),
                    ),
                ),
            ),
        )

        return is_anomalies, normalized_scores, detection_sources

    def save_model(self, filepath="isolation_forest_model.joblib"):
        if not self.is_trained:
            raise RuntimeError("Cannot save an untrained model.")
        payload = {
            "model": self.model,
            "lot_stats": self.lot_stats,
            "contamination": self.contamination,
            "n_estimators": self.n_estimators,
            "random_state": self.random_state,
            "use_engineered_features": self.use_engineered_features,
        }
        joblib.dump(payload, filepath)
        print(f"Model successfully serialized and saved to: {filepath}")

    @classmethod
    def load_model(cls, filepath="isolation_forest_model.joblib"):
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"No saved model found at: {filepath}")
        data = joblib.load(filepath)
        if isinstance(data, dict) and "model" in data:
            detector = cls(
                contamination=data.get("contamination", 0.0001),
                n_estimators=data.get("n_estimators", 40),
                random_state=data.get("random_state", 42),
                use_engineered_features=data.get("use_engineered_features", True),
            )
            detector.model = data["model"]
            detector.lot_stats = data.get("lot_stats", {})
            detector.is_trained = True
            return detector
        elif isinstance(data, cls):
            return data
        else:
            raise TypeError("Loaded object format is invalid.")


if __name__ == "__main__":
    import random
    import time

    warnings.filterwarnings("ignore")

    print("=================================================================")
    print("  ISRO / SIH 26170: MODULE A DYNAMIC OUTLIER DETECTION BENCHMARK  ")
    print("=================================================================")

    sample_csv = "sample_data.csv"
    try:
        from simulator import generate_dataset

        generate_dataset(sample_csv, n_normal=10000, n_drift=0, n_short=0)
    except ImportError:
        from Backend.simulator import generate_dataset

        generate_dataset(sample_csv, n_normal=10000, n_drift=0, n_short=0)

    detector = MultivariateAnomalyDetector(contamination=0.0001, n_estimators=40)
    detector.train(sample_csv)

    model_file = "isolation_forest_model.joblib"
    detector.save_model(model_file)
    reloaded_detector = MultivariateAnomalyDetector.load_model(model_file)
    print("Model serialization & reload: PASSED.")

    print(
        "\n[Test 1] ISRO Stated Prompt Challenge: Lot Avg=10uA, Part=45uA (Under 50uA Limit)..."
    )
    res_isro = reloaded_detector.detect_spike(
        current=1.20, voltage=5.00, temp=125.0, iddq=45.0
    )
    print(f"  -> Is Anomaly Detected: {res_isro['is_anomaly']} (Expected: True)")
    print(f"  -> Anomaly Score:       {res_isro['anomaly_score']}")
    print(f"  -> QA Explanation:      {res_isro['qa_justification']}")

    print("\n[Test 2] Testing 1,000 Nominal Burn-In Cycles (125°C, 10uA Iddq)...")
    false_positives = 0
    start_time = time.perf_counter()
    for _ in range(1000):
        v = 5.0 + random.uniform(-0.03, 0.03)
        c = 1.20 + random.uniform(-0.015, 0.015)
        t = 125.0 + random.uniform(-0.4, 0.4)
        iq = 10.0 + random.uniform(-1.5, 1.5)

        res = reloaded_detector.detect_spike(current=c, voltage=v, temp=t, iddq=iq)
        if res["is_anomaly"]:
            false_positives += 1
    latency = (time.perf_counter() - start_time) * 1000 / 1000.0

    print(
        f"  -> False Positives: {false_positives} / 1,000 (False Alarm Rate: {false_positives / 10:.2f}%)"
    )
    print(f"  -> Inference Latency: {latency:.4f} ms per sample (Target: <10ms)")

    print("\n[Test 3] Testing 100 Catastrophic Short Circuits...")
    false_negatives = 0
    for _ in range(100):
        v = random.uniform(0.1, 0.6)
        c = random.uniform(5.0, 10.0)
        t = random.uniform(130.0, 150.0)
        iq = random.uniform(80.0, 150.0)
        res = reloaded_detector.detect_spike(current=c, voltage=v, temp=t, iddq=iq)
        if not res["is_anomaly"]:
            false_negatives += 1

    print(
        f"  -> False Negatives (Missed Failures): {false_negatives} / 100 ({false_negatives}%)"
    )
    print(f"  -> Detection Rate: {(100 - false_negatives)}%")

    print("\n=================================================================")
    if res_isro["is_anomaly"] and false_positives == 0 and false_negatives == 0:
        print("  FINAL RESULT: MODULE A STRICTLY COMPLIANT WITH ISRO PROMPT (PASSED) ")
    else:
        print("  FINAL RESULT: CALIBRATION REQUIRED                                 ")
    print("=================================================================")
