# ARJUNA: EXTENDED Q&A BATTLE BANK (SIH 26170)

This document contains an exhaustive list of potential questions from judges, covering everything from fundamental physics to system architecture, machine learning theory, edge cases, and business impact. 

---

## 1. GENERAL & PROBLEM STATEMENT (Owner: M6 & All)

**Q: What exactly is Burn-In Testing?**
A: Burn-in is a stress test where semiconductor components are operated at extreme temperatures (usually 125°C) and elevated voltages for an extended period (typically 168 hours). The goal is to accelerate the aging process to trigger latent defects (infant mortality) before the component is deployed.

**Q: Why 168 hours? Why not 24 hours?**
A: 168 hours (exactly one week) is mathematically derived from the Arrhenius equation for thermal acceleration. It ensures that components surviving this period have crossed the 'infant mortality' phase of the bathtub reliability curve, giving a high statistical confidence of long-term survival in space (10-15 years).

**Q: Why do traditional static limits fail in space qualification?**
A: Static limits (e.g., max 50 µA leakage) account for worst-case manufacturing variance across all acceptable lots. However, in a high-quality lot where the mean is 10 µA, a part drawing 45 µA passes the 50 µA test but is statistically broken (+30 sigma deviation). In space, thermal cycling will rapidly degrade this already-weakened part.

**Q: What is I_DDQ and why is it so important?**
A: I_DDQ (Quiescent Drain Current) is the leakage current drawn by a CMOS circuit when it is powered on but the clock is halted (not switching). Elevated I_DDQ is the most sensitive early warning sign of gate oxide defects, internal shorts, or contamination, which is why it is the primary focus of our anomaly detection.

**Q: Who are the target users of ARJUNA?**
A: Quality Assurance (QA) engineers and test operators at ISRO's SAC (Space Applications Centre), URSC (U R Rao Satellite Centre), and certified aerospace foundries performing component-level environmental stress screening (ESS).

**Q: How does ARJUNA save money?**
A: By forecasting failure trajectories at hour 24 and executing Early Rejection, we free up the thermal chamber for the remaining 144 hours. This increases facility throughput, saves massive amounts of electricity and liquid nitrogen (used for thermal regulation), and prevents downstream integration of flawed chips.

---

## 2. STANDARDS & COMPLIANCE (Owner: M4 & M6)

**Q: What is ECSS-Q-ST-60-02C?**
A: It is the European Cooperation for Space Standardization standard for space-grade ASIC and IC qualification. It strictly mandates the burn-in conditions (125°C, 168h) and screening gates we model.

**Q: What is MIL-STD-883 Method 1015?**
A: The US Military Standard for microcircuits. Method 1015 specifically defines the procedures for High-Temperature Operating Life (HTOL) tests, including steady-state life and power/temperature requirements.

**Q: What is NASA EEE-INST-002?**
A: The NASA standard for selecting and qualifying EEE (Electrical, Electronic, and Electromechanical) parts. It defines three criticality levels. We mapped these to our system: Level 1 (COTS), Level 2 (Standard Flight), and Level 3 (Deep Space/Mission Critical).

**Q: How do you prove your software complies with these standards?**
A: Our physical simulator enforces the 125°C / 168h requirements (ECSS/MIL-STD). Our anomaly detection limits adapt to the NASA EEE-INST-002 criticality tiers by tightening the CUSUM decision interval (h parameter).

---

## 3. PHYSICS & HARDWARE SIMULATION (Owner: M2)

**Q: What is the Arrhenius Equation and how do you use it?**
A: I_leak(T) = I_0 * exp(-(E_a / k_B) * ((1/T) - (1/T_ref))). It models how thermal energy accelerates chemical and physical degradation. We use it to dynamically compute subthreshold leakage current based on the chamber temperature.

**Q: What activation energy (E_a) did you use and why?**
A: We used E_a = 0.70 eV, which is the standard accepted activation energy for silicon CMOS defect mechanisms (like electromigration and oxide breakdown) in reliability physics.

**Q: How does your thermal RC network work?**
A: We model the chip's temperature using a first-order differential equation: dT/dt = (T_ambient - T_chip) / tau + (V * I) * R_th. We use a thermal resistance (R_th) of 16.67 °C/W.

**Q: Explain Over-Current Protection (OCP) foldback.**
A: When a chip shorts, resistance drops to near zero. Real power supplies cannot provide infinite current. They 'fold back' the voltage to maintain a maximum clamped current (e.g., 8.0A). Our simulator accurately collapses the rail voltage to 0.4V when a short occurs, instead of predicting impossible currents.

**Q: What is 12-bit ADC Quantization?**
A: Real sensors don't give continuous infinite-precision floats. They convert analog signals to digital bits. A 12-bit ADC has 4096 discrete steps. We simulate this quantization noise to ensure our ML models don't overfit to mathematically smooth data.

**Q: Is your 'virtual time' scaling physically sound?**
A: Yes. We accelerate the *thermal state dynamics* (RC time constant) by 10x for demo purposes so it settles faster, but the *ML regression algorithms (Module B)* strictly use the real elapsed burn-in hours. We do not warp time for the AI.

---

## 4. MODULE A: ISOLATION FOREST & ML (Owner: M3)

**Q: Why not use a Neural Network / Autoencoder?**
A: Three reasons: 1) Latency (we need sub-4ms per tick; NNs require tensor overhead), 2) Explainability (NNs have opaque latent spaces; IF provides clear path-length anomaly scores), and 3) Compute (IF runs on basic edge CPUs without a GPU).

**Q: How exactly does Isolation Forest work?**
A: It builds an ensemble of random Decision Trees. Instead of splitting to classify, it splits to isolate. Anomalies are 'few and different,' so they get isolated very quickly (closer to the root of the tree). The average path length across all trees determines the anomaly score.

**Q: How do you handle multivariate data?**
A: The Isolation Forest naturally handles multivariate data (Voltage, Current, Temp, I_DDQ) by selecting a random feature and a random split value at each node. If a drop in voltage is only anomalous *because* current spiked, the tree captures this correlation organically.

**Q: What is the 'Contamination' parameter and what is yours?**
A: It is the expected proportion of outliers in the dataset. We set it to 0.01 (1%), which aligns with aerospace manufacturing defect rates. Setting it too high causes false positives; too low misses latent defects.

**Q: How did you convert the Isolation Forest output to a 0-1 score?**
A: We take the raw decision_function output (which ranges roughly from -0.5 to 0.5) and pass it through a calibrated Sigmoid function: 1 / (1 + exp(scaling_factor * raw_score)).

**Q: What happens if the lot is entirely bad? Will Isolation Forest miss it?**
A: Isolation Forest assumes anomalies are a minority. If a whole lot is bad, it might fail to detect it. *However*, we mitigate this with a dual-layer approach: our system also checks absolute hard-coded boundaries and lot-relative 3-sigma thresholds.

---

## 5. MODULE B/C: CUSUM, OLS, CRITICALITY (Owner: M4)

**Q: What is OLS (Ordinary Least Squares)?**
A: It's a linear regression method that finds the line of best fit by minimizing the sum of the squares of the vertical deviations. We use it at hour 24 to find the slope of degradation and project the I_DDQ value at hour 168.

**Q: What if the degradation is non-linear?**
A: OLS assumes linearity. If degradation is exponential, OLS will under-predict the 168h mark. *This is exactly why we have Module C (CUSUM).* CUSUM doesn't care about linearity; it accumulates any persistent shift and will catch the exponential curve as soon as it diverges from the baseline.

**Q: Explain Tabular CUSUM math.**
A: S_positive = max(0, previous_S_positive + current_value - target_mean - slack_k). It essentially says: 'Only accumulate error if the current value exceeds the mean by more than the allowed slack (k).'

**Q: Why is k = 0.5 µA?**
A: k is the slack/noise allowance. Our sensor noise standard deviation (sigma) is ~1.17 µA. In statistical process control, k is optimally chosen as half the expected shift. k=0.5 provides a k/sigma ratio of ~0.43, perfectly tuned to ignore normal Gaussian sensor jitter while catching real micro-shifts.

**Q: How do the criticality levels (h) work?**
A: h is the decision interval. If the accumulated error (S_positive) exceeds h, we trigger an alarm.
- Level 1 (COTS): h = 7.0 (Allows more drift before alarming)
- Level 2 (Standard): h = 5.0
- Level 3 (Deep Space): h = 3.5 (Highly sensitive, trips early)

**Q: Explain the Auto-Baseline feature.**
A: Normal chips vary slightly (e.g., one rests at 9.5 µA, another at 10.5 µA). If we used a hardcoded 10.0 µA target, the 10.5 µA chip would constantly accumulate false CUSUM error. Auto-baseline takes the average of the first 15 readings of *that specific chip* and uses it as the target mean, making the algorithm immune to natural lot variance.

---

## 6. BACKEND, API, DB & SECURITY (Owner: M5)

**Q: Why FastAPI instead of Flask or Django?**
A: FastAPI is natively asynchronous (built on Starlette and ASGI). This is mandatory for our system because we must stream high-frequency WebSocket data to the frontend without blocking the AI inference loop. Flask is synchronous/WSGI and would bottleneck.

**Q: How does the async WebSocket streaming work?**
A: We maintain a global list of connected active WebSocket clients. In the main simulation loop (running via asyncio.sleep), we generate the telemetry, run AI inference, serialize to JSON, and use asyncio.gather to concurrently broadcast the payload to all clients.

**Q: Why do you have two databases (SQLite + Supabase)?**
A: Resilience. SQLite is our local, in-memory/disk buffer ensuring zero data loss and ultra-low latency writing. Supabase (PostgreSQL) is the cloud historian for cross-facility access. If internet drops, SQLite buffers the data until connection is restored.

**Q: What is Row-Level Security (RLS) in Supabase?**
A: RLS enforces policies at the database engine level. We programmed it so that unauthenticated users can only SELECT (read) telemetry, but only the service_role or authenticated admins can INSERT or UPDATE records.

**Q: Explain your 4-tier RBAC.**
A: 1) Viewer (Read-only UI), 2) Operator (Can start/stop simulations), 3) QA Lead (Can change criticality and approve early rejections), 4) Admin (Full access). API endpoints check the provided JWT token against these roles before executing.

**Q: How do you prevent API abuse?**
A: We implemented a Token Bucket Rate Limiter. If an IP hits an endpoint more than X times per minute, the API returns a 429 Too Many Requests status, preventing DoS attacks on the chamber backend.

---

## 7. FRONTEND, UI & DATA VIS (Owner: M1)

**Q: Why Vanilla JS and HTML/CSS instead of React?**
A: For a mission control dashboard updating at 60 FPS, React's Virtual DOM diffing overhead can introduce micro-stutters. Vanilla JS allows direct DOM manipulation and zero build-step overhead, ensuring hardware-grade performance.

**Q: How does Chart.js handle streaming without crashing?**
A: We limit the arrays to a 50-point sliding window (FIFO). When a new point arrives, we push() to the end and shift() the first element off. We call chart.update('none') to bypass expensive animations.

**Q: How do you achieve the Dark Mode Aerospace look?**
A: We use CSS variables for a high-contrast palette (deep space blacks, neon greens/reds), monospaced fonts (Courier/Roboto Mono) for aligning shifting numbers, and CSS Grid/Flexbox for responsive layout.

**Q: Explain the UI's connection resilience.**
A: If the WebSocket connection closes, the JS onclose event triggers a recursive setTimeout loop (exponential backoff). It updates the UI status pill to yellow 'Reconnecting...' and tries to rebuild the WebSocket object until successful.

**Q: How is the XAI card updated?**
A: The WebSocket payload includes an xai_evidence JSON object. The frontend intercepts this, queries the DOM by ID, and injects the observed, mean, sigma_distance, and qa_action directly into the HTML spans.

---

## 8. TESTING, BENCHMARKS & EDGE CASES (Owner: M6)

**Q: What exactly do the 70 Pytest tests cover?**
A: - **Unit Tests**: Math logic (OLS calculation, CUSUM updates).
- **Integration Tests**: FastAPI endpoints, DB write speeds.
- **WebSocket Tests**: Simulating client handshakes and async payloads.
- **Security Tests**: Forcing invalid API keys, hitting rate limiters.
- **Physics Tests**: Ensuring T doesn't drop below ambient, testing foldback logic.

**Q: What is Out-of-Distribution (OOD) testing?**
A: Testing the AI on data distributions it was *never* trained on. We injected non-linear exponential drift and extreme noise. Isolation Forest maintained 100% recall, while OLS MAE degraded from 0.5 µA to 9.4 µA (which we honestly disclose).

**Q: What is Adversarial Telemetry?**
A: We send corrupted JSON payloads (e.g., voltage: NaN, current: Infinity, temperature: -9999) to the backend. Our Pydantic schemas catch this, reject the frame, and fail safe without crashing the Python process.

**Q: You claim 100% Defect Recall. Isn't 100% usually a sign of overfitting?**
A: In standard classification, yes. But here, ground truth is determined by rigid physical laws (e.g., short circuit = V < 1.0V). Because the failures are mechanically deterministic and mathematically distinct, 100% recall on the synthetic domain is expected. We clearly state this is synthetic domain performance, not real-world ATE performance.

**Q: How is Latency measured?**
A: We use time.perf_counter() before and after the combined Module A/B/C inference block. The average across 10,000 runs is 2.85 milliseconds.

---

## 9. ARCHITECTURE & ALTERNATIVE CHOICES (Owners: All)

**Q: Why not use cloud AI (AWS SageMaker / Google Vertex)?**
A: Space qualification facilities are often air-gapped for security (ITAR/EAR regulations). The system must be capable of running entirely on-premise on edge servers. Cloud latency (50-100ms) is also too slow for millisecond-level short-circuit detection.

**Q: How would you deploy this to ISRO's actual facilities?**
A: We would Dockerize the application. ISRO's Automated Test Equipment (ATE) generates SCPI/LXI data over ethernet. We would write a lightweight Python adapter to translate SCPI into our standardized JSON telemetry payload and push it to the FastAPI ingestion endpoint.

**Q: What happens if the database grows too large over a 168-hour test?**
A: At 1 tick per second, 168 hours is ~600,000 rows per DUT. PostgreSQL handles millions of rows easily. We would implement database partitioning by test lot and use time-series database optimizations (like TimescaleDB extension for Postgres) for long-term storage.

**Q: Why didn't you use a time-series database like InfluxDB?**
A: PostgreSQL (via Supabase) offers relational data integrity (linking test runs to specific operator IDs and hardware serial numbers) combined with Row-Level Security. InfluxDB is great for metrics, but lacks the complex RBAC and relational constraints needed for audited aerospace QA.

