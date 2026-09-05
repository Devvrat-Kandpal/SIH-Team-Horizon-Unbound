# Project ARJUNA (SIH 26170): 5-Minute Scripted SIH Presentation Guide

**Target Audience**: Smart India Hackathon Judging Panel / ISRO Technical Evaluators  
**Goal**: Deliver an undeniable, high-impact demonstration showcasing 100% problem alignment, physics rigor, real-time AI explainability, and multi-model superiority in exactly 5 minutes.

---

## Team Role Distribution (per **Updated** SIH 26170 Execution Plan — 6 Members)

| Member | Updated PDF Role | Demo Role | Owns in Q&A |
|---|---|---|---|
| **Member 6** | Testing, Validation & Demo Engineer | Opening, closing, benchmark proof | Test suite (62), ground truth integrity, benchmark honesty, overall architecture |
| **Member 3** | Multivariate ML Engineer | Module A: 45 µA outlier + XAI evidence | Isolation Forest, +30.1σ math, OOD benchmark, "is it learning the simulator?" |
| **Member 4** | Time-Series AI Specialist | Module B/C: drift forecast + criticality tiers | CUSUM (k/h, auto-baseline fix), OLS MAE, 168h lead time, "why two interfaces?" |
| **Member 2** | Hardware Simulation & Data Engineer | Physics: short circuit, OCP foldback, thermal model | Arrhenius, thermal RC, units, leakage scale, "is the physics real?" |
| **Member 5** | Database + API + Integration Lead | Architecture: WebSocket/REST, Supabase, security | API/WS design, RBAC, RLS, "how does real ATE data enter?" |
| **Member 1** | Frontend Developer & UI/UX Lead | Dashboard operator: drives all clicks, XAI card tour | Frontend truthfulness, benchmark-data labeling, charts, fallback behavior |

**Stage rules:** One speaker at a time; Member 1 drives the dashboard while speaking only in their slot. Handoff phrase = state the time cue ("Next, the AI behind it — Member 3").

---

## Presentation Roadmap at a Glance

| Time | Segment | Presenter | Primary Visual / Action | Key Speaking Point |
|---|---|---|---|---|
| **0:00 – 0:30** | The Challenge & Context | **M6 Testing/Validation** | Mission Control Dashboard (Nominal 125°C) | Why traditional static screening fails space missions. |
| **0:30 – 1:15** | The 45 µA Latent Outlier | **M3 ML** | Click "Inject Electrical Spike" | Passing static 50 µA but caught at $+30.1\sigma$ by Module A. |
| **1:15 – 1:50** | Structured XAI Evidence | **M1 Frontend** | Structured Evidence Card tour | Explainability for space QA inspectors — no black boxes. |
| **1:50 – 2:50** | 168h Drift Forecast, CUSUM & Criticality | **M4 Time-Series** | "Inject Thermal Drift" → Level 2 → 3 toggle | Saving ~165 hours (98%) of chamber time; risk-weighted thresholds. |
| **2:50 – 3:30** | Catastrophic Short & Physics | **M2 Simulation** | "Inject Short Circuit" | Multivariate voltage collapse, OCP foldback — physics-grounded. |
| **3:30 – 4:10** | Architecture, Persistence & Security | **M5 Integration** | History table, Export CSV | Supabase streaming, RBAC, offline fallback, hardware-agnostic ingestion. |
| **4:10 – 4:40** | Quantitative Proof | **M6 Testing/Validation** | `reports/evaluation_report.json` + threshold tables | 62 automated tests, honest synthetic-domain metrics, OOD disclosure. |
| **4:40 – 5:00** | Close | **M6 Testing/Validation** | Back to live nominal dashboard | One-line impact statement; invite questions. |

---

## Detailed Step-by-Step Script

### Minute 0:00 – 0:30: Context & Challenge — **Member 6 (Testing, Validation & Demo Engineer)**
- **Action**: Open Mission Control (`http://localhost:8000`). Point to the live dual charts streaming nominal steady-state telemetry ($5.0\text{V}$, $1.2\text{A}$, $125.0^\circ\text{C}$, $I_{DDQ} = 10.0\ \mu\text{A}$).
- **Member 6 (Testing, Validation & Demo Engineer)**:
  > *"Respected Judges, qualification of space-grade electronic components under ECSS-Q-ST-60-02C and MIL-STD-883 requires 168 hours of continuous 125°C burn-in. Today, aerospace facilities rely on static datasheet limits. If a component is rated for 50 µA, any chip drawing 49 µA passes. But in deep space, latent defects that operate near the threshold inevitably cause catastrophic in-flight failure. Project ARJUNA solves this with dynamic, lot-relative, multi-model AI screening."*

---

### Minute 0:30 – 1:15: The 45 µA ISRO Latent Outlier — **Member 2 (ML Engineer)**
- **Action**: Click the **"Inject Spike (45µA)"** button. Watch the live chart spike to 45.2 µA.
- **Member 3 (Multivariate ML Engineer)**:
  > *"Notice what just happened. The quiescent current jumped to 45.2 µA. In a standard screening facility, this component would be stamped 'QUALIFIED' because it is strictly below the 50 µA datasheet limit. But watch ARJUNA's response: the status instantaneously turns red: REJECTED.  
  > ARJUNA's Module A evaluates this reading not against an absolute limit, but against the trained population lot. In a lot with a 10 µA mean and 1.17 µA standard deviation, 45.2 µA represents a plus thirty standard deviation anomaly. It is rejected immediately at the 24-hour checkpoint."*

---

### Minute 1:15 – 1:50: Structured Explainable AI (XAI) — **Member 1 (Frontend Lead)**
- **Action**: Scroll to the **"Structured XAI Evidence Card"** on the dashboard. Point out the parameter deltas, dynamic limit, and QA action.
- **Member 1 (Frontend Lead)**:
  > *"In mission-critical aerospace applications, black-box AI is unacceptable. ARJUNA does not return arbitrary confidence scores. It delivers structured, machine-readable engineering evidence:  
  > 1. Observed sensor value: 45.2 µA.  
  > 2. Population baseline: 10.0 µA.  
  > 3. Statistical deviation: +30.08 sigma.  
  > 4. Dynamic screening limit: 13.51 µA.  
  > 5. Actionable QA recommendation: 'QUARANTINE_LOT_AND_EARLY_REJECT'.  
  > This provides complete regulatory auditability for ISRO quality assurance engineers."*

> **DESIGN NOTE (multi-client):** All connected dashboards share one *single* virtual burn-in
> chamber state (scenario, burn-in clock, criticality). This is intentional — every observer
> sees the same chamber, so a fault injection or criticality change is globally coherent.
> It is not a per-user-session simulator.

---

### Minute 1:50 – 2:50 (Part A): Latent Drift Forecasting & Chamber Savings — **Member 4 (Time-Series AI)**
- **Action**: Click **"Reset Chamber"**, then click **"Inject Thermal Drift"**. Show the creeping leakage current slope on the charts and the 168h forecast pill.
- **Member 4 (Time-Series AI Specialist)**:
  > *"Next is the most costly challenge in aerospace manufacturing: latent parametric creep. A component might appear healthy at hour 10, but its subthreshold leakage current is slowly degrading.  
  > Watch Module B in action: our Ordinary Least Squares drift predictor computes the degradation trajectory in virtual burn-in hours. By hour 24, ARJUNA accurately forecasts that by hour 168, this component will reach 78 µA, severely violating space standards.  
  > We trigger Early Rejection at hour 24. That saves 144 hours of chamber operational time per component—a 97.9% reduction in burn-in chamber energy, throughput bottleneck, and facility costs."*

---

### Minute 1:50 – 2:50 (Part B): Mission Criticality Tiers & Statistical Defense — **Member 4 (Time-Series AI)**
- **Action**: Click the **Criticality Selector** and toggle from **Level 2 (Standard)** to **Level 3 (Mission-Critical)**.
- **Member 4 (Time-Series AI Specialist)**:
  > *"ARJUNA adheres to NASA EEE-INST-002 tiered mission criticality:  
  > - Level 1 for COTS and Ground Support ($h=7.0$).  
  > - Level 2 for Standard Flight Qualification ($h=5.0$).  
  > - Level 3 for Deep Space and Human-Rated Missions ($h=3.5$).  
  > When we switch to Level 3, the decision threshold tightens immediately. Notice that our CUSUM noise allowance parameter k remains fixed at 0.5 across all levels. Why? Because CUSUM operates on Iddq, and k = 0.5 µA is calibrated to the Iddq measurement domain (σ ≈ 1.17 µA, k/σ ≈ 0.43) — tuned to catch small persistent latent shifts without false alarms on nominal lots. Varying k would alter that noise allowance; varying h safely accelerates detection latency for flight-critical hardware. And one engineering detail judges often probe: each component's CUSUM reference is auto-calibrated to its own first 15 readings (per-DUT baseline), so natural lot spread can never accumulate as false drift — measured 0 false trips on 60 unclamped healthy parts."*

---

### Minute 2:50 – 3:30: Catastrophic Failure & OCP Foldback — **Member 2 (Simulation Engineer)**
- **Action**: Click **"Inject Short Circuit"**. Show the voltage rail instantly collapsing from 5.0V to 0.4V and load current jumping to 8.0A.
- **Member 2 (Hardware Simulation & Data Engineer)**:
  > *"Under catastrophic gate oxide failure, the component shorts. ARJUNA accurately models power supply Over-Current Protection foldback: current clamps at 8.0 Amps, voltage collapses to 0.4 Volts, and dynamic impedance drops to zero. Module A classifies the multivariate collapse within 4 milliseconds."*

---

### Minute 3:30 – 4:10: Persistence, Security & Export — **Member 5 (Integration Lead)**
- **Action**: Show the **History Table**, select the **"Filter: ELECTRICAL_SPIKE"** dropdown, and click **"Export CSV"**.
- **Member 5 (Database + API + Integration Lead)**:
  > *"Every telemetry frame is streamed asynchronously to our production Supabase PostgreSQL cloud database, backed by Row-Level Security and offline fallback queues. Mutating endpoints are protected by 4-tier Role-Based Access Control and rate limiters. Operators can filter historical faults and export full CSV logs with a single click."*

---

### Minute 4:10 – 5:00: Empirical Proof & Closing — **Member 6 (Testing, Validation & Demo Engineer)**
- **Action**: Open `reports/evaluation_report.json` or display the benchmark summary table.
- **Member 6 (Testing, Validation & Demo Engineer)**:
  > *"To prove ARJUNA is not just a hackathon demo, we evaluated 7,500 unseen randomized operational vectors (all metrics are measured on the validated synthetic simulation domain, not real hardware):  
  > - Defect Recall: 100.00% with zero missed defects within this simulator — per-segment: 100% instantaneous outliers, 100% creep, 100% shorts.  
  > - 168h Drift Forecast Error (in-domain linear drift): Mean Absolute Error of 0.567 µA; MAE rises honestly to 1.4–9.4 µA under non-linear OOD regimes, which Module C CUSUM compensates for.  
  > - Inference Latency: 2.85 milliseconds per tick.  
  > Project ARJUNA is fully tested with 62 passing automated tests (unit, API, WebSocket, security/RBAC, Supabase persistence, criticality, OOD generalization, threshold sensitivity, and adversarial telemetry), containerized with Docker, and completely traceable to ECSS-Q-ST-60-02C. Thank you, and we are ready for your questions."*

---

## 5-Minute Q&A Ownership Playbook (who answers what)

**Rule:** The addressed member answers first; M6 backs up anything about tests/numbers. Nobody else jumps in.

| # | Likely Judge Question | Owner | 15-second answer anchor |
|---|---|---|---|
| 1 | Where does ground truth come from? | **M6** | `evaluate_model.py` — physical thresholds only (3σ lot-relative + 127°C); label bias removed; OOD regimes use independent generators |
| 2 | Is the model just learning the simulator? | **M3** | OOD benchmark: OLS MAE degrades 1.4→9.4 µA on non-linear regimes (measured); CUSUM compensates without linearity assumptions |
| 3 | Why is CUSUM k = 0.5? | **M4** | k/σ ≈ 0.43 sub-σ allowance on Iddq domain; h carries criticality weighting; per-DUT auto-baseline makes it lot-position invariant |
| 4 | What if noise/lot spread is different on real hardware? | **M4** | Auto-baseline re-calibrates per part; k/h re-derived from measured σ — that's a config change, not a redesign |
| 5 | Why two Module B interfaces? | **M4** | `predict_168h` = ECSS 24h gate-check; `update()` = continuous rolling monitor; both share the same static+dynamic rejection semantics |
| 6 | Is the physics real? 50 mA vs 10 µA leakage? | **M2** | Rescaled: I_leak_base = 10 µA true DUT leakage (matches Iddq spec & legacy reference); Arrhenius Ea=0.70 eV; thermal RC R_th=16.667°C/W |
| 7 | Time scaling: 168h in 5 minutes? | **M2** | Documented DEMO_ACCELERATION_FACTOR=10× on the thermal state only; Module B's regression axis uses real hours — no scientific distortion |
| 8 | Zero false positives — real or clamped? | **M6** | Measured: Module A 0% FP unclamped; CUSUM 0/60 with auto-baseline; 3σ gate sees statistically expected ~0.17% tail — all in the report |
| 9 | NaN / corrupted telemetry? | **M6** | Dedicated adversarial suite: NaN/Inf/negative/999µA/missing — fail-safe handling, 62 tests green |
| 10 | Can anonymous clients write to your DB? | **M5** | RLS migration restricts INSERT to authenticated/service_role; 4-tier RBAC + rate limiter on API; WS handshake token |
| 11 | How does real ATE/SMU data enter? | **M5** | Hardware-agnostic WS/REST JSON schema; swap `ComponentSimulator` for a serial/ATE adapter — one integration point |
| 12 | Two judges using two tabs? | **M1** | Intentional single-DUT shared chamber — one virtual test bench, globally coherent state; documented design note |
| 13 | Is the anomaly score a probability? | **M3** | No — a severity index (sigmoid-scaled IF decision function); documented in `detect_spike`; no uncalibrated probability claims |
| 14 | What's NOT validated? | **M6** | Honest: synthetic domain only; radiation/TID/SEE out of scope; real hardware qualification needs representative ATE telemetry |

**Fallback answers if a question lands outside the table:** M6 takes it, says "good question — here's where that lives in the code," and opens the relevant file. Never guess.

---

## Contingency & Fallback Protocol

- **If cloud database is offline**: The backend automatically falls back to the in-memory deque and SQLite buffer with zero interruptions. Show the green *"In-Memory Fallback Active"* status pill.
- **If judges ask for code proof**: Open `RTM.md` to show the complete traceability table mapping every requirement to test lines.
- **If judges ask for automated test execution**: Run `pytest tests/ -v` directly in terminal to display all 62 green passing tests.

