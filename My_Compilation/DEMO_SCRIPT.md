# Project ARJUNA (SIH 26170): 5-Minute Scripted SIH Presentation Guide

**Target Audience**: Smart India Hackathon Judging Panel / ISRO Technical Evaluators  
**Goal**: Deliver an undeniable, high-impact demonstration showcasing 100% problem alignment, physics rigor, real-time AI explainability, and multi-model superiority in exactly 5 minutes.

---

## Presentation Roadmap at a Glance

| Time | Segment | Primary Visual / Action | Key Speaking Point |
|---|---|---|---|
| **0:00 – 0:30** | The Challenge & Context | Mission Control Dashboard (Nominal 125°C) | Why traditional static screening fails space missions. |
| **0:30 – 1:30** | The 45 µA Latent Outlier | Click "Inject Electrical Spike" | Passing static 50 µA but caught at $+30.1\sigma$ by Module A. |
| **1:30 – 2:15** | Structured XAI Evidence | Open Structured Evidence Card | Explainability for space QA inspectors. |
| **2:15 – 3:15** | 168h Drift Forecast & Savings | Click "Inject Thermal Drift" | Saving 164.4 hours (97.9%) of expensive burn-in chamber time. |
| **3:15 – 3:55** | Mission Criticality & Latency | Switch Level 2 $\rightarrow$ Level 3 | Statistical defense of risk-weighted thresholds ($k=0.5$). |
| **3:55 – 4:25** | Catastrophic Short Circuit | Click "Inject Short Circuit" | Multi-sensor voltage collapse and OCP foldback. |
| **4:25 – 4:45** | Cloud Persistence & Security | Table view & Export CSV | Production Supabase streaming & API security. |
| **4:45 – 5:00** | Quantitative Proof & Close | Show `reports/ablation_study.md` | 100% recall, 0 false negatives, 0.583 µA MAE. |

---

## Detailed Step-by-Step Script

### Minute 0:00 – 0:30: Context & Challenge
- **Action**: Open Mission Control (`http://localhost:8000`). Point to the live dual charts streaming nominal steady-state telemetry ($5.0\text{V}$, $1.2\text{A}$, $125.0^\circ\text{C}$, $I_{DDQ} = 10.0\ \mu\text{A}$).
- **Presenter 1 (Lead)**:
  > *"Respected Judges, qualification of space-grade electronic components under ECSS-Q-ST-60-02C and MIL-STD-883 requires 168 hours of continuous 125°C burn-in. Today, aerospace facilities rely on static datasheet limits. If a component is rated for 50 µA, any chip drawing 49 µA passes. But in deep space, latent defects that operate near the threshold inevitably cause catastrophic in-flight failure. Project ARJUNA solves this with dynamic, lot-relative, multi-model AI screening."*

---

### Minute 0:30 – 1:30: The 45 µA ISRO Latent Outlier
- **Action**: Click the **"Inject Spike (45µA)"** button. Watch the live chart spike to 45.2 µA.
- **Presenter 2 (AI Lead)**:
  > *"Notice what just happened. The quiescent current jumped to 45.2 µA. In a standard screening facility, this component would be stamped 'QUALIFIED' because it is strictly below the 50 µA datasheet limit. But watch ARJUNA's response: the status instantaneously turns red: REJECTED.  
  > ARJUNA's Module A evaluates this reading not against an absolute limit, but against the trained population lot. In a lot with a 10 µA mean and 1.17 µA standard deviation, 45.2 µA represents a plus thirty standard deviation anomaly. It is rejected immediately at the 24-hour checkpoint."*

---

### Minute 1:30 – 2:15: Structured Explainable AI (XAI)
- **Action**: Scroll to the **"Structured XAI Evidence Card"** on the dashboard. Point out the parameter deltas, dynamic limit, and QA action.
- **Presenter 2 (AI Lead)**:
  > *"In mission-critical aerospace applications, black-box AI is unacceptable. ARJUNA does not return arbitrary confidence scores. It delivers structured, machine-readable engineering evidence:  
  > 1. Observed sensor value: 45.2 µA.  
  > 2. Population baseline: 10.0 µA.  
  > 3. Statistical deviation: +30.08 sigma.  
  > 4. Dynamic screening limit: 13.51 µA.  
  > 5. Actionable QA recommendation: 'QUARANTINE_LOT_AND_EARLY_REJECT'.  
  > This provides complete regulatory auditability for ISRO quality assurance engineers."*

---

### Minute 2:15 – 3:15: Latent Drift Forecasting & 164-Hour Chamber Savings
- **Action**: Click **"Reset Chamber"**, then click **"Inject Thermal Drift"**. Show the creeping leakage current slope on the charts and the 168h forecast pill.
- **Presenter 1 (Lead)**:
  > *"Next is the most costly challenge in aerospace manufacturing: latent parametric creep. A component might appear healthy at hour 10, but its subthreshold leakage current is slowly degrading.  
  > Watch Module B in action: our Ordinary Least Squares drift predictor computes the degradation trajectory in virtual burn-in hours. By hour 24, ARJUNA accurately forecasts that by hour 168, this component will reach 78 µA, severely violating space standards.  
  > We trigger Early Rejection at hour 24. That saves 144 hours of chamber operational time per component—a 97.9% reduction in burn-in chamber energy, throughput bottleneck, and facility costs."*

---

### Minute 3:15 – 3:55: Mission Criticality Tiers & Statistical Defense
- **Action**: Click the **Criticality Selector** and toggle from **Level 2 (Standard)** to **Level 3 (Mission-Critical)**.
- **Presenter 3 (Systems Lead)**:
  > *"ARJUNA adheres to NASA EEE-INST-002 tiered mission criticality:  
  > - Level 1 for COTS and Ground Support ($h=7.0$).  
  > - Level 2 for Standard Flight Qualification ($h=5.0$).  
  > - Level 3 for Deep Space and Human-Rated Missions ($h=3.5$).  
  > When we switch to Level 3, the decision threshold tightens immediately. Notice that our CUSUM noise allowance parameter k remains fixed at 0.5 across all levels. Why? Because k is calibrated to the physical sensor noise floor (0.15°C). Varying k would cause false alarms on normal noise; varying h safely accelerates detection latency for flight-critical hardware."*

---

### Minute 3:55 – 4:25: Catastrophic Failure & OCP Foldback
- **Action**: Click **"Inject Short Circuit"**. Show the voltage rail instantly collapsing from 5.0V to 0.4V and load current jumping to 8.0A.
- **Presenter 3 (Systems Lead)**:
  > *"Under catastrophic gate oxide failure, the component shorts. ARJUNA accurately models power supply Over-Current Protection foldback: current clamps at 8.0 Amps, voltage collapses to 0.4 Volts, and dynamic impedance drops to zero. Module A classifies the multivariate collapse within 4 milliseconds."*

---

### Minute 4:25 – 4:45: Persistence, Security & Export
- **Action**: Show the **History Table**, select the **"Filter: ELECTRICAL_SPIKE"** dropdown, and click **"Export CSV"**.
- **Presenter 1 (Lead)**:
  > *"Every telemetry frame is streamed asynchronously to our production Supabase PostgreSQL cloud database, backed by Row-Level Security and offline fallback queues. Mutating endpoints are protected by 4-tier Role-Based Access Control and rate limiters. Operators can filter historical faults and export full CSV logs with a single click."*

---

### Minute 4:45 – 5:00: Empirical Proof & Closing
- **Action**: Open `reports/evaluation_report.json` or display the benchmark summary table.
- **Presenter 1 (Lead)**:
  > *"To prove ARJUNA is not just a hackathon demo, we evaluated 7,500 unseen randomized operational vectors:  
  > - Defect Recall: Exactly 100.00% with ZERO missed defects.  
  > - 168h Drift Forecast Error: Mean Absolute Error of just 0.583 µA.  
  > - Inference Latency: 4 milliseconds per tick.  
  > Project ARJUNA is fully tested with 33 passing automated test suites, containerized with Docker, and completely traceable to ECSS-Q-ST-60-02C. Thank you, and we are ready for your questions."*

---

## Contingency & Fallback Protocol

- **If cloud database is offline**: The backend automatically falls back to the in-memory deque and SQLite buffer with zero interruptions. Show the green *"In-Memory Fallback Active"* status pill.
- **If judges ask for code proof**: Open `RTM.md` to show the complete traceability table mapping every requirement to test lines.
- **If judges ask for automated test execution**: Run `pytest tests/ -v` directly in terminal to display all 33 green passing tests in 13 seconds.

