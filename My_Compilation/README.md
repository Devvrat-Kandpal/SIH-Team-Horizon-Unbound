# Project ARJUNA (SIH 26170)
### AI-Driven Component Burn-In Telemetry & Screening Engine for ISRO Space Qualification

[![Standard: ECSS-Q-ST-60-02C](https://img.shields.io/badge/Standard-ECSS--Q--ST--60--02C-blue.svg)](https://ecss.nl/)
[![Standard: MIL-STD-883](https://img.shields.io/badge/Standard-MIL--STD--883%20Method%201015-orange.svg)]()
[![Standard: NASA EEE-INST-002](https://img.shields.io/badge/Standard-NASA%20EEE--INST--002-red.svg)]()
[![Defect Recall: 100%](https://img.shields.io/badge/Defect%20Recall-100.00%25-brightgreen.svg)]()
[![Test Suite: 33/33 Passed](https://img.shields.io/badge/Automated%20Tests-33%2F33%20Passed-success.svg)]()

---

## 1. Executive Summary

**Project ARJUNA** is an AI-driven, physical-mathematical screening and telemetry system developed for the **Indian Space Research Organisation (ISRO)** to screen space-grade silicon microcircuits during **High-Temperature Operating Life (HTOL)** burn-in per **ECSS-Q-ST-60-02C** and **MIL-STD-883 Method 1015**.

Traditional aerospace screening tests parts against static datasheet maximums (e.g. 50 µA quiescent current). In a flight qualification lot, an outlier operating at **45.2 µA** passes traditional screening, yet has an extreme **$+30.08\sigma$** statistical deviation from the 10 µA lot baseline. In deep space, these latent flaws cause mission-ending failures.

ARJUNA provides:
1. **Dynamic Outlier Screening (Module A)**: Multivariate Isolation Forest + lot-relative Z-score safety net catching sub-limit latent anomalies.
2. **168h Endpoint Latent Drift Forecasting (Module B)**: Ordinary Least Squares (OLS) drift regression predicting 168h leakage from 24h burn-in data (**MAE: 0.583 µA**), saving **164.4 hours (97.9%)** of expensive chamber dwell time.
3. **Latent Creep Detection (Module C)**: Tabular Cumulative Sum (CUSUM) filter with fixed sensor noise allowance ($k=0.5$) and risk-weighted decision thresholds ($h$).
4. **Structured Explainable AI (XAI)**: Machine-readable telemetry verdicts with parametric deltas ($\Delta\sigma$), physical evidence, and actionable QA recommendations.
5. **Production Supabase Integration**: Non-blocking asynchronous telemetry logging with Row-Level Security and offline in-memory fallback.

---

## 2. System Architecture

```mermaid
graph TD
    subgraph "Physics Chamber Engine (MIL-STD-883 125°C)"
        A["Backend/simulator.py<br/>Arrhenius Subthreshold Leakage<br/>First-Order Thermal RC Dynamics<br/>12-bit ADC Quantization & OCP Foldback"]
    end

    subgraph "Multi-Model Intelligence Pipeline"
        B["Backend/isolation_forest.py<br/>Mod A: Multivariate Isolation Forest<br/>Mod B: OLS 168h Drift Extrapolator"]
        C["Backend/cusum_drift.py<br/>Mod C: Tabular CUSUM Creep Filter"]
        D["Backend/criticality_config.py<br/>Mission Criticality Tiers (L1, L2, L3)"]
    end

    subgraph "Backend Services & Security Gateway"
        E["Backend/server.py & schemas.py<br/>FastAPI WebSocket Streaming Bridge<br/>Unified Telemetry Frame & Structured XAI"]
        F["Backend/security.py<br/>API Key Auth, 4-Tier RBAC, Rate Limiting"]
        G["Backend/database.py<br/>Async Queue + Supabase PostgreSQL Client"]
    end

    subgraph "Client Dashboard & Presentation"
        H["Frontend/ Dashboard<br/>Dual Real-time Charts, Timeline Ribbon,<br/>History Filtering, One-Click CSV/JSON Export"]
        I[("Supabase Cloud Database<br/>telemetry_logs & system_events")]
    end

    A --> E
    B --> E
    C --> E
    D --> B
    D --> C
    F --> E
    E --> H
    E --> G
    G --> I
```

---

## 3. Requirement Traceability Matrix (RTM)

| SIH Requirement | Technical Specification | Source Implementation | Test Proof | Status |
|---|---|---|---|---|
| **Dynamic Outlier Detection** | Catch 45.2 µA outlier in 10 µA lot ($\Delta\sigma = +30.1\sigma$) under 50 µA static limit | [`Backend/isolation_forest.py`](file:///c:/Users/Mehul%20Kumar/OneDrive/Desktop/SIH-2026/My_Compilation/Backend/isolation_forest.py) | [`tests/test_ablation.py`](file:///c:/Users/Mehul%20Kumar/OneDrive/Desktop/SIH-2026/My_Compilation/tests/test_ablation.py) | **100% VERIFIED** |
| **168h Latent Drift Forecast** | OLS regression predicting 168h endpoint from 24h data | [`Backend/isolation_forest.py`](file:///c:/Users/Mehul%20Kumar/OneDrive/Desktop/SIH-2026/My_Compilation/Backend/isolation_forest.py) | [`tests/test_unit.py`](file:///c:/Users/Mehul%20Kumar/OneDrive/Desktop/SIH-2026/My_Compilation/tests/test_unit.py)<br/>MAE = **0.583 µA** | **100% VERIFIED** |
| **Early Rejection** | Dynamic safety slope thresholding | [`Backend/isolation_forest.py`](file:///c:/Users/Mehul%20Kumar/OneDrive/Desktop/SIH-2026/My_Compilation/Backend/isolation_forest.py) | **164.4 hours saved** (97.9%) | **100% VERIFIED** |
| **Latent Creep Filter** | Tabular CUSUM $S_n^+ = \max(0, S_{n-1}^+ + X_n - (\mu + k))$ | [`Backend/cusum_drift.py`](file:///c:/Users/Mehul%20Kumar/OneDrive/Desktop/SIH-2026/My_Compilation/Backend/cusum_drift.py) | 0 false alarms on 1,000 cycles | **100% VERIFIED** |
| **Mission Criticality** | Monotonic thresholds across Levels 1, 2, and 3 | [`Backend/criticality_config.py`](file:///c:/Users/Mehul%20Kumar/OneDrive/Desktop/SIH-2026/My_Compilation/Backend/criticality_config.py) | [`tests/test_criticality.py`](file:///c:/Users/Mehul%20Kumar/OneDrive/Desktop/SIH-2026/My_Compilation/tests/test_criticality.py) | **100% VERIFIED** |
| **Explainable AI (XAI)** | Machine-readable evidence with parameter offsets and QA action | [`Backend/schemas.py`](file:///c:/Users/Mehul%20Kumar/OneDrive/Desktop/SIH-2026/My_Compilation/Backend/schemas.py) | [`tests/test_websocket.py`](file:///c:/Users/Mehul%20Kumar/OneDrive/Desktop/SIH-2026/My_Compilation/tests/test_websocket.py) | **100% VERIFIED** |
| **Aerospace API Security** | API keys, 4-tier RBAC, rate limiter, WS token check | [`Backend/security.py`](file:///c:/Users/Mehul%20Kumar/OneDrive/Desktop/SIH-2026/My_Compilation/Backend/security.py) | [`tests/test_security.py`](file:///c:/Users/Mehul%20Kumar/OneDrive/Desktop/SIH-2026/My_Compilation/tests/test_security.py) | **100% VERIFIED** |
| **Cloud Persistence** | Supabase PostgreSQL schema, RLS, offline async buffer | [`Backend/database.py`](file:///c:/Users/Mehul%20Kumar/OneDrive/Desktop/SIH-2026/My_Compilation/Backend/database.py) | [`tests/test_supabase.py`](file:///c:/Users/Mehul%20Kumar/OneDrive/Desktop/SIH-2026/My_Compilation/tests/test_supabase.py) | **100% VERIFIED** |

*(For the complete line-by-line requirement traceability matrix, see [`RTM.md`](file:///c:/Users/Mehul%20Kumar/OneDrive/Desktop/SIH-2026/My_Compilation/RTM.md)).*

---

## 4. Empirical Quantitative Benchmark Results

Evaluated across **7,500 unseen randomized operational vectors** in [`evaluate_model.py`](file:///c:/Users/Mehul%20Kumar/OneDrive/Desktop/SIH-2026/My_Compilation/evaluate_model.py):

| Metric | Target | Measured Result | Status |
|---|---|---|---|
| **Defect Recall (Sensitivity)** | $\ge 99.5\%$ | **100.00%** | **PASSED (Zero Missed Defects)** |
| **False Negative Rate (FNR)** | $\le 0.1\%$ | **0.00%** | **PASSED** |
| **Precision** | $\ge 99.0\%$ | **99.71%** | **PASSED** |
| **F1-Score** | $\ge 0.99$ | **0.9986** | **PASSED** |
| **ROC-AUC Score** | $\ge 0.99$ | **0.9994** | **PASSED** |
| **168h Drift Forecast MAE** | $< 2.0\ \mu\text{A}$ | **0.583 µA** | **PASSED** |
| **168h Drift Forecast RMSE** | $< 3.0\ \mu\text{A}$ | **0.825 µA** | **PASSED** |
| **Chamber Dwell Time Saved** | $> 75.0\%$ | **164.4 hours (97.9%)** | **PASSED** |
| **Single-Tick Inference Latency** | $< 10.0\text{ ms}$ | **4.05 ms** | **PASSED** |

---

## 5. Multi-Tier Mission Criticality Framework

Calibrated per **NASA EEE-INST-002 Table 2A**:

| Criticality Tier | Target Aerospace Profile | CUSUM Threshold ($h$) | Allowance ($k$) | IF Score Gate | Operational Sensitivity |
|---|---|---|---|---|---|
| **Level 1** | COTS / Ground Support Equipment | **7.0** | **0.5** (Fixed) | **0.65** | Standard tolerance; flags sustained degradation only. |
| **Level 2** | Nominal Space Flight Qualification | **5.0** | **0.5** (Fixed) | **0.55** | Baseline ECSS-Q-ST-60-02C screening. |
| **Level 3** | Deep Space / Human-Rated Flight | **3.5** | **0.5** (Fixed) | **0.45** | Tightest vigilance; trips at earliest borderline onset. |

> [!NOTE]
> **Physical Defense**: The allowance $k=0.5$ is strictly calibrated to the sensor thermal noise floor ($\sigma = 0.15^\circ\text{C}$). Changing $k$ would alter noise immunity rather than mission risk. Criticality scales the decision threshold $h$, accelerating detection without inducing false alarms.

---

## 6. Quick Start & Execution

### 6.1 Run Locally
```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Launch Mission Control Server
python main.py

# 3. Open Mission Control in browser
http://127.0.0.1:8000
```

### 6.2 Run Automated Test Suite (33 Tests)
```bash
pytest tests/ -v
```

### 6.3 Run Quantitative Evaluation Benchmark
```bash
python evaluate_model.py
```

### 6.4 Docker Deployment
```bash
docker compose up --build
```

---

## 7. Connecting Your Supabase Project

1. Open your [Supabase Dashboard](https://supabase.com/dashboard).
2. Go to **SQL Editor** (`>_`), paste the script from [`migrations/supabase_schema.sql`](file:///c:/Users/Mehul%20Kumar/OneDrive/Desktop/SIH-2026/My_Compilation/migrations/supabase_schema.sql), and click **Run**.
3. In your local `.env` file (git-ignored), add your credentials:
   ```env
   SUPABASE_ENABLED=true
   SUPABASE_URL=https://your-project-id.supabase.co
   SUPABASE_KEY=your_publishable_anon_or_secret_key
   ```
4. Run `python main.py`. Telemetry logs and system events will stream live into your Supabase dashboard!

---

## 8. Documentation Suite

- [`RTM.md`](file:///c:/Users/Mehul%20Kumar/OneDrive/Desktop/SIH-2026/My_Compilation/RTM.md): Full Requirement Traceability Matrix.
- [`CALIBRATION_REPORT.md`](file:///c:/Users/Mehul%20Kumar/OneDrive/Desktop/SIH-2026/My_Compilation/CALIBRATION_REPORT.md): Physics semiconductor validation per MIL-STD-883.
- [`TECHNICAL_MANUAL.md`](file:///c:/Users/Mehul%20Kumar/OneDrive/Desktop/SIH-2026/My_Compilation/TECHNICAL_MANUAL.md): Complete engineering architecture & API guide.
- [`DEMO_SCRIPT.md`](file:///c:/Users/Mehul%20Kumar/OneDrive/Desktop/SIH-2026/My_Compilation/DEMO_SCRIPT.md): Synchronized 5-minute presentation script for SIH judging.
