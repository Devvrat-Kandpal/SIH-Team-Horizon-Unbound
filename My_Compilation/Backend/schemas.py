"""
Backend/schemas.py — Project ARJUNA (SIH 26170)
Unified Pydantic data contracts for real-time telemetry, structured explainability (XAI),
system control requests, and operational status views conforming to ECSS-Q-ST-60-02C.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, List

from pydantic import BaseModel, Field, field_validator


class EvidenceItem(BaseModel):
    """Specific parametric evidence contributing to an anomaly determination."""

    metric: str = Field(..., description="Physical or statistical metric name (e.g. iddq_uA, dynamic_res_ohm)")
    observed_value: float = Field(..., description="Value measured in the current telemetry tick")
    baseline_mean: float = Field(..., description="Expected lot population mean (mu)")
    baseline_std: float = Field(1.17, description="Lot population standard deviation (sigma)")
    delta_sigma: float = Field(..., description="Standard deviation offset: (observed - mean) / std")
    datasheet_limit: float | None = Field(None, description="Absolute static datasheet maximum rating")
    dynamic_limit: float | None = Field(None, description="3-sigma lot dynamic screening limit (mu + 3*sigma)")


class StructuredEvidence(BaseModel):
    """Machine-readable Explainable AI (XAI) payload for aerospace QA inspection."""

    verdict: str = Field(..., description="'PASSED', 'REJECTED', 'WARNING', or 'INITIALIZING'")
    fault_type: str = Field("NORMAL", description="Classified fault signature")
    detection_source: str = Field(
        "none",
        description="Subsystem flagging the condition (e.g. isolation_forest, cusum, z_score_safety_net, hybrid_fusion)",
    )
    criticality_level: int = Field(
        2, ge=1, le=3, description="NASA EEE-INST-002 / ECSS criticality tier (1=low, 2=standard, 3=mission-critical)"
    )
    evidence: List[EvidenceItem] = Field(default_factory=list, description="Parametric metrics justifying the verdict")
    rule_triggered: str = Field("NOMINAL_OPERATION", description="Formal screening rule identifier")
    recommended_action: str = Field("PROCEED_SCREENING", description="Actionable aerospace QA recommendation")
    qa_justification: str = Field(..., description="Human-readable QA justification text")


class TelemetryFrame(BaseModel):
    """Canonical unified telemetry frame shared across Simulator, ML models, WebSocket, and Database."""

    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat(), description="ISO 8601 UTC timestamp")
    # Raw Physics Telemetry (MIL-STD-883 Static Steady-State Burn-In)
    voltage: float = Field(..., description="DC Supply rail voltage (Vdd) in Volts")
    current: float = Field(..., description="Total active load current in Amperes")
    temperature: float = Field(..., description="Die / Chamber temperature in degrees Celsius (125.0C baseline)")
    iddq_uA: float = Field(..., description="Quiescent standby leakage current (Iddq) in microamperes")
    prop_delay: float = Field(4.50, description="Gate propagation delay (t_pd) in nanoseconds")
    criticality_level: int = Field(2, ge=1, le=3, description="Active mission criticality tier (1, 2, or 3)")

    # MODULE A: Multivariate Isolation Forest & Physical Features
    power_w: float = Field(..., description="Instantaneous power dissipation (V * I) in Watts")
    dynamic_res_ohm: float = Field(..., description="Dynamic silicon load impedance (V / I) in Ohms")
    iddq_zscore: float = Field(0.0, description="Z-score deviation relative to lot mean: (iddq - mu) / sigma")
    is_anomaly: bool = Field(False, description="Primary anomaly classification flag")
    anomaly_score: float = Field(0.03, ge=0.0, le=1.0, description="Calibrated risk severity score (0.0 to 1.0)")
    raw_score: float = Field(
        0.18, description="Raw Isolation Forest decision function score (negative indicates outlier)"
    )
    detection_source: str = Field("none", description="Specific model layer triggering the flag")
    fault_type: str = Field(
        "NORMAL", description="'NORMAL', 'ELECTRICAL_SPIKE', 'THERMAL_DRIFT', 'ELECTRICAL_SHORT_CIRCUIT'"
    )
    lot_mean_iddq: float = Field(10.0, description="Trained lot mean standby current in uA")
    lot_std_iddq: float = Field(1.17, description="Trained lot standard deviation in uA")
    qa_justification: str = Field("QA STATUS [PASSED]", description="Human-readable QA statement")

    # MODULE B: 168h Latent Drift Predictor (OLS Regression)
    drift_slope_ua_h: float = Field(0.0, description="Iddq drift rate in uA per simulated burn-in hour")
    forecast_168h_uA: float = Field(10.0, description="Projected Iddq value at 168-hour qualification endpoint")
    forecast_168h_label: str = Field("COLLECTING DATA", description="168h endpoint qualification label")
    drift_status: str = Field("INITIALIZING", description="Drift assessment status text")
    drift_r2: float = Field(0.0, ge=0.0, le=1.0, description="OLS linear regression coefficient of determination")
    early_reject_b: bool = Field(False, description="Module B early rejection trigger flag")
    hours_to_violation: float | None = Field(None, description="Estimated burn-in hours until limit breach")
    n_observations: int = Field(0, description="Number of sequential burn-in data points in rolling window")

    # MODULE C: Stateful Tabular CUSUM Filter
    cusum_score: float = Field(0.0, description="Cumulative positive sum register (S+)")
    cusum_threshold: float = Field(5.0, description="Active decision threshold (h) based on criticality tier")
    cusum_drift_detected: bool = Field(False, description="CUSUM cumulative drift alarm flag")

    # Session & Simulation State
    scenario: str = Field("nominal", description="Active simulation scenario name")
    burn_in_hours: float = Field(0.0, description="Accrued virtual burn-in hours (0.0 to 168.0h)")
    system_status: str = Field("NOMINAL", description="'NOMINAL' or 'ANOMALY'")

    # Structured Explainability Object
    structured_evidence: StructuredEvidence | None = Field(
        None, description="Detailed structured evidence payload for QA audit"
    )


class FaultInjectionRequest(BaseModel):
    """Payload for fault injection endpoint."""

    event_type: str | None = Field(
        None, description="Fault scenario type (e.g. ELECTRICAL_SPIKE, THERMAL_DRIFT, ELECTRICAL_SHORT_CIRCUIT)"
    )
    fault_type: str | None = Field(None, description="Alias for event_type")

    @field_validator("event_type", "fault_type")
    @classmethod
    def clean_type_str(cls, v: str | None) -> str | None:
        if v is None:
            return None
        cleaned = str(v).strip().upper()
        if not cleaned:
            raise ValueError("Value cannot be blank")
        return cleaned

    def get_event_type(self) -> str:
        val = self.event_type or self.fault_type
        if not val:
            raise ValueError("Either event_type or fault_type is required")
        return val.upper()


class CriticalityUpdateRequest(BaseModel):
    """Payload for criticality tier update endpoint."""

    criticality_level: int = Field(
        ..., ge=1, le=3, description="Must be 1 (low), 2 (standard), or 3 (mission-critical)"
    )


class SystemStatusResponse(BaseModel):
    """System status and operational readiness view."""

    backend_status: str = "ONLINE"
    system_status: str = "NOMINAL"
    operational: bool = True
    active_fault: str | None = None
    inject_spike: bool = False
    inject_short: bool = False
    inject_drift: bool = False
    burn_in_hours: float = 0.0
    criticality_level: int = 2
    criticality_label: str = "STANDARD"
    model_loaded: bool = True
    persistence: dict[str, Any] = Field(default_factory=dict)
    security: dict[str, Any] = Field(default_factory=dict)


class TelemetryHistoryQuery(BaseModel):
    """Query parameters for historical telemetry retrieval."""

    limit: int = Field(100, ge=1, le=1000, description="Number of historical records to return")
    fault_type: str | None = Field(
        None, description="Filter by fault type: NORMAL, ELECTRICAL_SPIKE, THERMAL_DRIFT, ELECTRICAL_SHORT_CIRCUIT"
    )
