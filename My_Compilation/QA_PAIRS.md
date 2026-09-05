# Project ARJUNA (SIH 26170): Comprehensive 6-Member Q&A & Defense Guide

**Target Event**: Smart India Hackathon (SIH 26170) Grand Finale  
**Domain**: Indian Space Research Organisation (ISRO) / Space-Grade Microcircuit Qualification  
**Format**: 5-Minute Live Prototype Demonstration + 5-Minute Technical Jury Q&A  

---

## PART 1: Master Project Fact Sheet & Foundational Knowledge
*(Every single team member must understand this section before the presentation)*

### 1.1 The Problem Statement (SIH 26170)
During satellite manufacturing, microcircuits undergo **High-Temperature Operating Life (HTOL)** burn-in testing to accelerate latent silicon defects and eliminate infant mortality:
- **Standards Governed**: **ECSS-Q-ST-60-02C** (European Space Agency) and **MIL-STD-883 Method 1015** (Aerospace Military Standard).
- **Test Conditions**: 168 continuous hours at **125°C** under electrical bias.
- **The Core Flaw in Current Practice**: Facilities use **static datasheet limits**. If a chip has a datasheet maximum quiescent current ($I_{DDQ}$) of **50.0 µA**, any chip drawing **49.0 µA** is stamped "QUALIFIED" and shipped for satellite assembly.
- **The Space Hazard**: In a clean wafer lot where nominal chips draw **10.0 µA** ($\sigma = 1.17\ \mu\text{A}$), a chip drawing **45.2 µA** is a **$+30.08\sigma$ statistical outlier**. While within the static datasheet boundary, it possesses latent gate-oxide thinning, subthreshold channel leakage, or packaging contamination. In deep space, thermal cycling and total ionizing dose (TID) cause this latent defect to turn into a mission-critical catastrophic failure.
- **The Economic Bottleneck**: Space qualification chambers run 24/7 for 168 hours per lot. Defective parts that begin slowly creeping at hour 15 still consume the full 168 hours of thermal chamber dwell time, electricity, liquid nitrogen, and test floor capacity before being rejected at the end of the test.

---

### 1.2 The Project ARJUNA Solution
Project ARJUNA is an **AI-driven dynamic burn-in telemetry and screening engine**:
1. **Module A (Multivariate Outlier Screening)**: Employs an **Isolation Forest** paired with a lot-relative statistical $3\sigma$ gate to catch anomalous parts like the **45.2 µA outlier** at the first checkpoint, rejecting them despite passing static thresholds.
2. **Module B (168-Hour Endpoint Drift Forecasting)**: Uses an **Ordinary Least Squares (OLS)** linear trend model evaluated at hour 24. It predicts the expected leakage current at hour 168 (**MAE = 0.567 µA**). If the trajectory breaches dynamic safety boundaries, it executes **Early Rejection**, saving **144 to 165.2 hours (up to 98.3%)** of expensive chamber time.
3. **Module C (Latent Parametric Creep Detection)**: A stateful **Tabular Cumulative Sum (CUSUM)** filter that accumulates micro-shifts in leakage. Features a fixed noise allowance ($k=0.5\ \mu\text{A}$) and a per-DUT auto-baseline over its first 15 readings, making it invariant to healthy lot spread (0 false trips on 1,000 nominal cycles).
4. **Mission Criticality Architecture**: Complies with **NASA EEE-INST-002** with tiered decision intervals:
   - **Level 1 (COTS / Ground Support)**: $h = 7.0$ (relaxed tolerance)
   - **Level 2 (Standard Flight Qualification)**: $h = 5.0$ (baseline flight)
   - **Level 3 (Deep Space / Human Rated)**: $h = 3.5$ (ultra-sensitive early trip)
5. **Structured Explainable AI (XAI)**: Replaces black-box scores with an auditable engineering verdict showing observed sensor values, lot mean, standard deviation distance ($\Delta\sigma$), dynamic limit, and actionable QA recommendations (`QUARANTINE_LOT_AND_EARLY_REJECT`).
6. **Enterprise Architecture & Security**: Real-time async FastAPI WebSocket streaming, SQLite local buffer, production Supabase PostgreSQL cloud logging with Row-Level Security (RLS), 4-tier Role-Based Access Control (RBAC), rate-limiting, and one-click CSV export.

---

### 1.3 Key Figures & Numbers to Memorize
- **Burn-In Standard**: 168 hours, 125°C (ECSS-Q-ST-60-02C & MIL-STD-883 Method 1015)
- **Nominal DUT Values**: $V_{DD} = 5.0\text{V}$, $I_{load} = 1.2\text{A}$, $T = 125.0^\circ\text{C}$, $I_{DDQ} = 10.0\ \mu\text{A}$ ($\sigma \approx 1.17\ \mu\text{A}$)
- **Latent Outlier Spike**: $45.2\ \mu\text{A}$ (passes static 50.0 µA limit; rejected at $+30.08\sigma$)
- **CUSUM Slack**: $k = 0.5\ \mu\text{A}$ ($k/\sigma \approx 0.43$)
- **Decision Thresholds ($h$)**: Level 1 = $7.0$, Level 2 = $5.0$, Level 3 = $3.5$
- **Early Rejection Savings**: Rejection at hour 24 saves $144\text{ hours}$ ($85.7\%$ chamber dwell time)
- **Defect Recall**: $100.00\%$ (zero missed defects on 7,500 evaluated synthetic vectors)
- **In-Domain Drift Forecast MAE**: $0.567\ \mu\text{A}$ ($0.583\ \mu\text{A}$ in the preserved Phase-0 baseline run)
- **Inference Latency**: $2.85\text{ ms}$ per telemetry frame
- **Automated Test Suite**: 62 automated unit, API, WebSocket, security, and physics tests passing (100% green)

---

## PART 2: Member-Wise Detailed Q&A Breakdown

---

### MEMBER 1: Frontend Developer & UI/UX Lead
**Execution Plan Role**: What the judges see in the browser. Responsible for `index.html`, `styles.css`, `script.js`, `chart_v4.js`, Mission Control dark mode theme, real-time Chart.js dual-axis plots, FDIR alert feed, and driving the live dashboard during the pitch.

#### Key Concepts M1 Must Know:
- How Chart.js handles sliding window streaming without memory leaks.
- How the WebSocket client connects, listens, and reconnects automatically.
- Why all browser tabs display the **same single virtual burn-in chamber** (coherent test bench architecture).
- The 5 fields in the Structured XAI Evidence Card.

#### Q&A for Member 1:

**Q1: How does your frontend handle streaming high-frequency data without freezing or lagging the browser?**  
*Answer:*  
"We use Chart.js with a sliding FIFO window capped at 50 data points. On every WebSocket message, we push the new telemetry tuple and pop the oldest entry before calling `chart.update('none')`. Using `'none'` disables expensive cubic spline animations and executes an instantaneous canvas draw, keeping rendering time below 3 milliseconds and maintaining a smooth 60 FPS."

**Q2: What happens if two judges open the URL on two different laptops or browser tabs? Do they see different simulations?**  
*Answer:*  
"They see the exact same chamber state. This is an intentional design choice reflecting a real physical burn-in test bench: there is one Device Under Test (DUT) inside the environmental chamber. The backend maintains a single source of truth for chamber clock, scenario, and criticality, broadcasting identical synchronized telemetry to all connected client dashboards."

**Q3: Walk us through the Structured XAI Evidence Card. Why is this better than showing an AI probability score?**  
*Answer:*  
"In space qualification, quality assurance inspectors cannot act on a black-box percentage like '98% anomalous'. Our XAI Card displays 5 deterministic physical metrics:
1. Observed value (e.g., 45.2 µA),
2. Lot baseline mean (10.0 µA),
3. Statistical distance in lot standard deviations (+30.08 sigma),
4. Dynamic screening limit (13.51 µA),
5. An actionable engineering directive (`QUARANTINE_LOT_AND_EARLY_REJECT`).
This gives ISRO engineers an immediate, auditable trail compliant with quality protocols."

**Q4: How does the dashboard update when the user changes the Mission Criticality tier?**  
*Answer:*  
"When the operator selects Level 1, 2, or 3 from the dropdown, the frontend sends an HTTP `POST` to `/api/criticality` with the operator API key. The backend updates the chamber's $h$ decision threshold and dynamic screening multiplier, and the very next WebSocket broadcast reflects the new tier and updates the dynamic limit pills on the UI."

**Q5: How does your frontend handle network drops or WebSocket disconnections?**  
*Answer:*  
"The frontend implements an exponential backoff auto-reconnect loop. If the WebSocket disconnects, the UI displays a yellow 'Reconnecting' status pill and attempts reconnection every 2 seconds. In addition, historical data can still be browsed and exported via the REST API."

**Q6: What technologies were used to build the user interface and why?**  
*Answer:*  
"We used pure modern vanilla JavaScript, HTML5, and CSS3 alongside Chart.js. We avoided heavy frontend frameworks like React or Angular to ensure zero build-step overhead, sub-millisecond DOM update latency, and direct hardware-grade simplicity suitable for mission control displays."

---

### MEMBER 2: Hardware Simulation & Data Engineer
**Execution Plan Role**: What generates virtual chamber telemetry. Responsible for `Backend/simulator.py`, physical baseline logic, thermal equations, sensor noise injection, catastrophic failure models, and synthetic dataset generation.

#### Key Concepts M2 Must Know:
- The **Arrhenius Equation** governing thermal acceleration of subthreshold leakage.
- First-order **Thermal RC network** differential equations ($R_{th} = 16.667^\circ\text{C/W}$, $\tau \approx 30\text{s}$).
- Power supply **Over-Current Protection (OCP) foldback** ($I_{clamp} = 8.0\text{A}, V_{collapse} = 0.4\text{V}$).
- Sensor noise models (Gaussian jitter + 12-bit ADC quantization).
- Virtual burn-in clock vs demo acceleration factor ($10\times$ on thermal dynamics, real hours on regression).

#### Q&A for Member 2:

**Q1: Is your simulation physically accurate, or is it just generating random numbers?**  
*Answer:*  
"It is strictly grounded in semiconductor physics. Nominal subthreshold leakage is governed by the Arrhenius relation:
$$I_{leak}(T) = I_0 \cdot \exp\left(-\frac{E_a}{k_B} \left(\frac{1}{T} - \frac{1}{T_{ref}}\right)\right)$$
where $E_a = 0.70\text{ eV}$ represents the silicon bandgap activation energy, $k_B$ is Boltzmann's constant, and $T_{ref} = 298.15\text{ K}$ (25°C). Junction temperature follows a first-order thermal RC differential equation driven by ambient chamber temperature (125°C) and internal $I^2 R$ Joule heating with thermal resistance $R_{th} = 16.67^\circ\text{C/W}$."

**Q2: What happens physically inside the chip during the 'Short Circuit' scenario?**  
*Answer:*  
"The short circuit simulates gate-oxide dielectric breakdown. When the insulating oxide punctures, impedance collapses towards zero. In real automated test benches, the power supply cannot deliver infinite current—it hits its Over-Current Protection (OCP) foldback limit. Our simulator accurately clamps current at 8.0 Amps and folds rail voltage down to 0.4 Volts, reflecting real bench hardware behavior."

**Q3: Why is quiescent current ($I_{DDQ}$) measured in microamps (10 µA) while operating current is in Amps (1.2 A)?**  
*Answer:*  
"Operating current ($I_{load} \approx 1.2\text{A}$) powers active CMOS switching and core logic. Quiescent current ($I_{DDQ} \approx 10.0\ \mu\text{A}$) is the static leakage current drawn when clock inputs are halted. In space microcircuits, $I_{DDQ}$ is the most sensitive early-warning indicator of oxide defects, crystal dislocations, and ESD damage, which is why MIL-STD-883 places special emphasis on quiescent leakage screening."

**Q4: How did you simulate real-world sensor inaccuracies?**  
*Answer:*  
"We apply zero-mean Gaussian white noise ($\sigma_{noise} = 0.05\text{V}, 0.02\text{A}, 0.2^\circ\text{C}, 0.15\ \mu\text{A}$) combined with a simulated 12-bit Analog-to-Digital Converter (ADC) quantization step function. This proves our AI filters operate robustly against real instrumentation noise rather than sanitized mathematical data."

**Q5: How does your burn-in clock work? How can a 168-hour test run during a 5-minute hackathon demo?**  
*Answer:*  
"We distinguish between virtual simulation time and demonstration wall-clock time. In our demo mode, each tick advances virtual burn-in time while applying an acceleration factor of $10\times$ to the thermal state. Crucially, Module B's regression math operates on the actual simulated burn-in hour timestamps, so the physics and regression metrics remain mathematically undistorted."

**Q6: What training and benchmark datasets did you generate?**  
*Answer:*  
"We generated `sample_data.csv` and `sample_data_168h.csv`, containing over 10,000 nominal steady-state operational vectors and 1,000 failure vectors spanning thermal runaway, electrical shorts, and slow subthreshold parametric creep across full 168-hour lifecycles."

---

### MEMBER 3: Multivariate ML Engineer
**Execution Plan Role**: Sudden anomaly intelligence. Responsible for `Backend/isolation_forest.py`, Isolation Forest training, statistical Z-score distance, anomaly score scaling, and detecting the 45.2 µA latent outlier.

#### Key Concepts M3 Must Know:
- How **Isolation Forest** isolates anomalies via recursive random partitioning ($O(n \log n)$ complexity).
- Why Isolation Forest was chosen over Autoencoders or One-Class SVM.
- The mathematics of the **45.2 µA outlier** ($+30.08\sigma$ deviation from $\mu = 10.0\ \mu\text{A}$).
- Anomaly score calibration (sigmoid scaling into a $0.0\text{ to }1.0$ severity index).
- Out-of-Distribution (OOD) generalization.

#### Q&A for Member 3:

**Q1: Why did you choose Isolation Forest instead of a Deep Learning Autoencoder or One-Class SVM?**  
*Answer:*  
"Isolation Forest has three distinct engineering advantages for real-time aerospace screening:
1. **Inference Latency**: It runs in $2.85\text{ ms}$, whereas Deep Autoencoders require tensor overhead and GPU acceleration.
2. **Deterministic Partitioning**: Anomalies have shorter path lengths in recursive tree splits because they are few and different, making them mathematically isolatable with fewer cuts.
3. **Interpretability**: Combined with our statistical lot distribution, it allows us to quantify exactly which feature drove the isolation without black-box latent space ambiguity."

**Q2: Explain the math behind catching the 45.2 µA outlier.**  
*Answer:*  
"Our training lot baseline has a mean quiescent current $\mu = 10.0\ \mu\text{A}$ and standard deviation $\sigma = 1.17\ \mu\text{A}$.  
When an electrical defect draws $45.2\ \mu\text{A}$, the statistical Z-score distance is:
$$Z = \frac{x - \mu}{\sigma} = \frac{45.2 - 10.0}{1.17} = +30.08\sigma$$
Even though $45.2\ \mu\text{A}$ is strictly below the legacy static datasheet threshold of $50.0\ \mu\text{A}$, our dual-layer Module A evaluates it against both the Isolation Forest anomaly threshold and our dynamic lot-relative $3\sigma$ safety boundary ($10.0 + 3 \times 1.17 = 13.51\ \mu\text{A}$), triggering an immediate rejection."

**Q3: How is the raw Isolation Forest output converted into your dashboard's anomaly score?**  
*Answer:*  
"The raw scikit-learn `decision_function()` outputs values centered around 0.0 (negative for outliers, positive for inliers). We map this through a calibrated sigmoid transformation to yield an intuitive severity index between $0.0$ (nominal) and $1.0$ (extreme critical defect). This is documented as a severity index, not an uncalibrated probability."

**Q4: What was your contamination factor and how did you tune it?**  
*Answer:*  
"We configured the contamination parameter at $0.01$ ($1\%$). This aligns with aerospace manufacturing quality targets, where lot defect rates are low, preventing the model from fitting sensor noise while maintaining sharp sensitivity to genuine outliers."

**Q5: Is your model merely memorizing the simulator's output? How do you prove it generalizes?**  
*Answer:*  
"We conducted out-of-distribution (OOD) ablation testing using independent randomized noise seeds, non-linear degradation profiles, and multi-variable coupling that the Isolation Forest was never trained on. In our evaluation report, Module A maintained 100% defect recall across all test sets, proving it learns physical boundary distributions rather than simulator artifacts."

**Q6: What features are fed into Module A?**  
*Answer:*  
"Module A processes a 4-dimensional operational vector: Rail Voltage ($V$), Load Current ($I$), Chamber Temperature ($T$), and Quiescent Current ($I_{DDQ}$). This multivariate coupling allows it to catch combined anomalies—such as a subtle temperature rise coupled with an impedance dip—even if individual parameters are within broad boundaries."

---

### MEMBER 4: Time-Series AI Specialist
**Execution Plan Role**: Slow degradation intelligence. Responsible for `Backend/cusum_drift.py`, Tabular CUSUM algorithm, per-DUT auto-baseline calibration, OLS 168h trajectory forecast, and NASA EEE-INST-002 criticality tiers.

#### Key Concepts M4 Must Know:
- The **Tabular CUSUM** formulas ($S_n^+ = \max(0, S_{n-1}^+ + X_n - (\mu + k))$).
- Why $k = 0.5\ \mu\text{A}$ is fixed while $h$ changes with criticality.
- The **Per-DUT Auto-Baseline** (first 15 readings) eliminating false positives from lot spread.
- The **Ordinary Least Squares (OLS)** slope formula and how 24h data forecasts hour 168.
- Economic impact: Saving 144 to 165.2 hours ($98.3\%$) of burn-in chamber time.

#### Q&A for Member 4:

**Q1: Explain the CUSUM equations and why you chose Cumulative Sum over a simple moving average.**  
*Answer:*  
"A moving average is sluggish and lags behind small persistent shifts. Cumulative Sum (CUSUM) integrates the cumulative deviation from a reference mean over time:
$$S_n^+ = \max\left(0, S_{n-1}^+ + X_n - (\mu + k)\right)$$
$$S_n^- = \max\left(0, S_{n-1}^- - X_n + (\mu - k)\right)$$
$X_n$ is the current reading, $\mu$ is the target baseline, $k$ is the reference allowance (slack), and $h$ is the decision threshold. As soon as $S_n^+ \ge h$, a drift alarm triggers. This detects subtle sub-microamp creeping trends hours before any static threshold is violated."

**Q2: Why is the slack parameter $k = 0.5$ constant across all three criticality levels?**  
*Answer:*  
"$k$ represents the noise allowance in the physical measurement domain. Because our quiescent current has a natural sensor noise standard deviation $\sigma \approx 1.17\ \mu\text{A}$, setting $k = 0.5\ \mu\text{A}$ sets $k/\sigma \approx 0.43$, which is the optimal statistical filter for half-sigma latent shifts. Varying $k$ would alter our measurement noise tolerance; instead, we adjust the decision interval $h$ ($7.0 \to 5.0 \to 3.5$) to tighten detection speed for mission-critical tiers without distorting sensor physics."

**Q3: What is the 'Per-DUT Auto-Baseline' and why is it critical?**  
*Answer:*  
"Every silicon die has slight harmless manufacturing lot variance—one chip might idle at 9.2 µA while another idles at 10.8 µA. If CUSUM used a fixed global 10.0 µA reference, the 10.8 µA chip would falsely accumulate drift and trip an alarm. Our algorithm auto-calibrates each chip's baseline $\mu$ using its own first 15 stable readings. This makes CUSUM invariant to healthy part-to-part variance, yielding zero false trips across 1,000 test cycles."

**Q4: How does the Ordinary Least Squares (OLS) 168h forecast work?**  
*Answer:*  
"Module B fits a linear regression line $I(t) = m \cdot t + c$ over the initial 24 hours of burn-in telemetry:
$$m = \frac{N \sum (t \cdot I) - \sum t \sum I}{N \sum t^2 - (\sum t)^2}$$
We evaluate this model at $t = 168\text{ hours}$. If the projected endpoint exceeds our dynamic safety threshold, or if the slope $m$ indicates rapid creep, we issue an **Early Rejection** verdict at hour 24."

**Q5: How do you justify claiming '144 hours of chamber savings'?**  
*Answer:*  
"A full qualification run requires 168 hours. If a defective component begins creeping early, traditional protocols keep running the chamber until hour 168. By reliably diagnosing failure at hour 24:
$$168\text{ hours} - 24\text{ hours} = 144\text{ hours saved}$$
That represents an 85.7% saving on that specific test run, and under accelerated thermal creep tests up to 98.3% operational dwell time saved, drastically reducing chamber power and liquid nitrogen costs."

**Q6: What are the two interfaces in your Module B code and why do both exist?**  
*Answer:*  
"We provide `predict_168h(history)` and `update(val, hour)`. `predict_168h` acts as the formal ECSS 24-hour gate-check milestone, computing the full trajectory slope. `update` provides a continuous streaming rolling monitor for live dashboard updates. Both share the exact same underlying dynamic rejection logic."

---

### MEMBER 5: Database + API + Integration Lead
**Execution Plan Role**: Everything that bridges and stores data. Responsible for `Backend/server.py`, `database.py`, `security.py`, FastAPI async event loop, WebSocket broadcasting, SQLite local buffer, Supabase cloud sync, RBAC, and telemetry export.

#### Key Concepts M5 Must Know:
- How FastAPI's async event loop handles WebSocket clients without blocking AI compute.
- The dual storage architecture: Local SQLite/in-memory buffer + Supabase cloud PostgreSQL.
- **Row-Level Security (RLS)** in Supabase preventing unauthorized data tampering.
- The 4-tier **Role-Based Access Control (RBAC)** model (`Viewer`, `Operator`, `QA_Lead`, `Admin`).
- How real-world Automated Test Equipment (ATE) like Advantest or Teradyne connects to ARJUNA.

#### Q&A for Member 5:

**Q1: How does your backend handle high-frequency WebSocket data without blocking?**  
*Answer:*  
"FastAPI runs on an asynchronous `asyncio` event loop powered by Uvicorn. The telemetry generation and model inference loop runs non-blockingly, broadcasting JSON payloads to all connected WebSocket clients via `asyncio.gather`. Database writes are dispatched asynchronously in background tasks, ensuring database latency never stalls real-time telemetry streaming."

**Q2: What happens if the internet goes down or the Supabase cloud database is unreachable?**  
*Answer:*  
"We built an automatic offline fallback system. Telemetry frames are always buffered in an in-memory double-ended queue (`deque`) and a local SQLite database (`burn_in.db`). If a cloud write fails, the system logs a warning, switches to the local buffer, and continues streaming to the dashboard without dropping a single frame."

**Q3: How is your database secured against unauthorized modifications?**  
*Answer:*  
"Our Supabase PostgreSQL database implements **Row-Level Security (RLS)**. Anonymous users only have read permissions on historical logs. All mutating write operations (`INSERT`, `UPDATE`, `DELETE`) require authenticated API keys or the backend `service_role` secret key. Furthermore, the REST API implements 4-tier Role-Based Access Control:
1. `Viewer` (read-only dashboard access),
2. `Operator` (start/pause chamber scenarios),
3. `QA_Lead` (modify criticality and quarantine lots),
4. `Admin` (full system configuration)."

**Q4: How does real Automated Test Equipment (ATE) or a Source Measure Unit (SMU) integrate with ARJUNA?**  
*Answer:*  
"Our system is completely hardware-agnostic. The ingestion layer expects a standardized JSON schema containing timestamp, voltage, current, temperature, and quiescent current. To interface with an industry ATE bench—such as a Keithley 2400 SMU or Teradyne tester—we simply replace the simulated telemetry generator with a lightweight serial/GPIB/SCPI socket driver that feeds the existing API pipeline."

**Q5: How is rate limiting implemented to prevent Denial of Service (DoS) attacks on the chamber server?**  
*Answer:*  
"In `Backend/security.py`, we implemented a token-bucket rate limiter for REST endpoints and scenario controls. If an unauthorized script attempts to spam scenario toggles or hammer the API, the system responds with HTTP `429 Too Many Requests`, safeguarding chamber stability."

**Q6: How does the CSV Export feature work?**  
*Answer:*  
"The frontend provides a one-click 'Export CSV' button that queries `/api/history` with optional scenario filters. The backend streams the filtered SQLite/in-memory records as a standardized MIME `text/csv` download containing complete timestamps, sensor readings, and AI decision flags for external auditing."

---

### MEMBER 6: Testing, Validation & Demo Engineer
**Execution Plan Role**: Proof that the entire prototype works seamlessly. Responsible for opening and closing the presentation, the 62-test automated suite, quantitative benchmark verification, MIL-STD/ECSS compliance verification, and benchmark honesty.

#### Key Concepts M6 Must Know:
- The structure and coverage of the **62 automated tests** (`pytest tests/ -v`).
- The quantitative benchmark results: **100% Defect Recall**, **0.567 µA MAE**, **2.85 ms Latency**.
- Benchmark honesty: Disclosing that metrics are evaluated on the validated synthetic domain, not real physical silicon.
- Out-of-Distribution (OOD) test findings: How OLS MAE degrades to $1.4\text{--}9.4\ \mu\text{A}$ on non-linear drift, and how Module C compensates.
- The Adversarial Telemetry test suite (handling `NaN`, `Inf`, negative voltage, missing keys).

#### Q&A for Member 6:

**Q1: How do we know your 100% defect recall isn't faked or overfitted?**  
*Answer:*  
"In `evaluate_model.py`, ground truth is defined strictly by physical failure criteria—temperatures exceeding 127°C, shorts where voltage collapses below 1.0V, or lot-relative deviations exceeding $3\sigma$ ($>13.51\ \mu\text{A}$)—completely independent of model inference labels. We evaluated 7,500 unseen randomized operational vectors across three independent failure regimes, and the multi-model architecture caught every single physical defect."

**Q2: What is your automated test suite composition?**  
*Answer:*  
"We have 62 automated tests passing across 8 distinct test suites:
- `test_unit.py`: Mathematical verification of Isolation Forest, CUSUM, and OLS regression.
- `test_api.py`: Verification of FastAPI REST endpoints and payload validation.
- `test_websocket.py`: Verification of async streaming, client handshakes, and XAI structure.
- `test_security.py`: Verification of API keys, 4-tier RBAC permissions, and rate limiters.
- `test_criticality.py`: Verification of monotonic threshold tightening across Levels 1, 2, and 3.
- `test_supabase.py`: Verification of cloud persistence, RLS, and offline queue fallback.
- `test_ablation.py`: Verification of out-of-distribution drift and multi-model superiority.
- `test_adversarial_telemetry.py`: Verification of fail-safe handling against corrupted data (`NaN`, `Inf`, missing keys)."

**Q3: What are the exact quantitative metrics measured by your benchmark harness?**  
*Answer:*  
"Across 7,500 unseen operational vectors:
- **Defect Recall (Sensitivity)**: $100.00\%$ (Zero missed defects)
- **False Negative Rate**: $0.00\%$
- **Precision**: $99.71\%$
- **F1-Score**: $0.9986$
- **ROC-AUC**: $0.9993$
- **In-Domain 168h Drift Forecast MAE**: $0.567\ \mu\text{A}$
- **Per-Tick Inference Latency**: $2.85\text{ ms}$"

**Q4: What happens if a corrupted sensor packet arrives with `NaN`, infinity, or negative voltage?**  
*Answer:*  
"We designed a dedicated adversarial telemetry suite. Telemetry payloads with `NaN`, `Inf`, negative rail voltages, or missing fields are caught at the Pydantic schema validation layer. The system tags the frame as `CORRUPTED_TELEMETRY`, logs an FDIR alert, and fails safe without crashing the backend or model inference pipeline."

**Q5: What are the honest limitations of your current evaluation?**  
*Answer:*  
"We are completely transparent: all metrics are evaluated on our validated physical-mathematical simulation domain, not physical silicon inside a cleanroom chamber. Radiation effects like Single Event Upsets (SEU) and Total Ionizing Dose (TID) are currently out of scope. Hardware deployment requires connecting to an actual ATE test bench to record real silicon noise distributions."

**Q6: What is the single biggest technical innovation of Project ARJUNA?**  
*Answer:*  
"Replacing static datasheet screening with **lot-relative multi-model AI screening**. By evaluating components relative to their peer population lot and forecasting degradation trajectories at hour 24, ARJUNA eliminates both latent orbital mission failures and weeks of wasted burn-in chamber operations."

---

## PART 3: Cross-Cutting & Common Questions (Every Member Must Know)

### Q1: What is Project ARJUNA in one sentence?
**Answer**:  
"Project ARJUNA is an AI-powered telemetry and dynamic screening engine that protects space missions by catching latent semiconductor defects during burn-in testing that pass traditional static datasheet limits."

### Q2: What is burn-in testing and why does ISRO do it?
**Answer**:  
"Burn-in testing is a process where newly manufactured silicon microcircuits are operated at elevated temperatures (125°C) and voltages for 168 continuous hours to accelerate latent defects and weed out infant mortality before components are launched into space."

### Q3: Why do traditional static limits fail?
**Answer**:  
"Static limits are designed as a coarse, one-size-fits-all maximum (e.g. 50 µA). However, in high-reliability space qualification lots, a healthy component draws only 10 µA. A flawed component drawing 45 µA passes static inspection despite being a $+30\sigma$ statistical anomaly. In orbit, space radiation and thermal cycles cause this latent defect to expand into complete circuit failure."

### Q4: How do the three AI modules (A, B, and C) complement each other?
**Answer**:  
- **Module A (Isolation Forest)** handles *sudden, multivariate anomalies* (electrical spikes, catastrophic shorts).
- **Module B (OLS Regression)** handles *long-term trajectory forecasting* (predicting the hour-168 state at hour 24).
- **Module C (CUSUM Filter)** handles *slow, subtle parametric creep* that is too gradual for an instantaneous outlier detector to notice.  
Together, they provide 360-degree anomaly coverage across both instantaneous and temporal failure modes.

### Q5: How does ARJUNA comply with NASA and ECSS standards?
**Answer**:  
- **ECSS-Q-ST-60-02C & MIL-STD-883 Method 1015**: Strictly models the 168-hour, 125°C High-Temperature Operating Life test regime.
- **NASA EEE-INST-002**: Direct implementation of tiered mission criticality levels (Level 1 COTS, Level 2 Standard Flight, Level 3 Deep Space) with dynamically scaled decision intervals ($h$).

### Q6: If a judge asks: "Has this been tested on real hardware?", what do we say?
**Answer**:  
*"Our algorithmic validation is currently demonstrated on a rigorous physical-mathematical simulation engine modeling Arrhenius leakage, thermal RC equations, and 12-bit ADC quantization. The software architecture is 100% hardware-ready: its REST and WebSocket interfaces allow an ISRO facility to plug in real ATE or SMU serial streams with zero modifications to the AI or backend pipeline."*

---

## PART 4: The 5-Minute Stage Execution Cheat-Sheet

| Timestamp | Segment Title | Presenter | Physical Action on Screen | Key Spoken Takeaway |
|---|---|---|---|---|
| **0:00 – 0:30** | The Space Qualification Problem | **Member 6** | Show live nominal dashboard (5V, 1.2A, 125°C, 10µA) | Why static screening (50µA) misses latent outliers in space-grade lots. |
| **0:30 – 1:15** | The 45 µA Latent Outlier | **Member 3** | Member 1 clicks **"Inject Spike (45µA)"** | Passes static 50µA limit, but rejected at $+30.1\sigma$ by Module A. |
| **1:15 – 1:50** | Explainable AI (XAI) Evidence | **Member 1** | Scroll down to Structured XAI Evidence Card | Auditable engineering facts: observed, mean, $\Delta\sigma$, dynamic limit, QA directive. |
| **1:50 – 2:50** | 168h Drift Forecast & Criticality | **Member 4** | Click **"Reset"**, click **"Inject Thermal Drift"**, toggle to **Level 3** | Saves 144h chamber time (85.7%); NASA EEE-INST-002 tiered $h$ thresholds. |
| **2:50 – 3:30** | Catastrophic Failure & OCP | **Member 2** | Member 1 clicks **"Inject Short Circuit"** | Voltage collapses to 0.4V, current clamps at 8.0A (OCP foldback physics). |
| **3:30 – 4:10** | Cloud Sync, Security & Export | **Member 5** | Filter history table and click **"Export CSV"** | Supabase streaming, RLS security, 4-tier RBAC, offline resilience. |
| **4:10 – 5:00** | Quantitative Benchmark Proof | **Member 6** | Show `evaluation_report.json` benchmark table | 100% recall, 0.567 µA MAE, 2.85ms latency, 62 automated tests green. |

---

## PART 5: Q&A Handoff & Emergency Fallback Rules

1. **The Direct Address Rule**: If a judge asks a question belonging to a specific module, the designated member takes a step forward and begins speaking within 2 seconds.
2. **The 20-Second Rule**: Keep answers punchy and anchor them with concrete engineering terms ($+30.1\sigma$, $k=0.5$, Arrhenius $E_a=0.70\text{ eV}$, 62 tests). Never ramble.
3. **The Backup Anchor**: Member 6 serves as the primary backup. If a question is ambiguous or spans multiple modules, Member 6 opens with the system context, then hands off to the specialist ("Member 4 implemented the exact CUSUM math for this").
4. **The Code Proof Fallback**: If a judge expresses skepticism about any claim, Member 1 immediately opens the relevant code file or runs `pytest tests/ -v` in the terminal to show green tests. Never argue with judges—show the code.
