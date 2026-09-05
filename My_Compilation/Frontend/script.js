/**
 * Project Arjuna (SIH 26170): ISRO Aerospace Burn-In Mission Control Engine
 * Author: Member 1 (Frontend Developer & UI/UX Lead)
 * 
 * Specifically addresses ISRO Evaluation Metrics:
 * - Module A: Dynamic Outlier Detection (Lot Mean 10 uA vs Part 45 uA vs 50 uA Max)
 * - Module B: 168h Latent Drift Predictor (0h -> 24h -> 96h -> 168h intervals)
 * - Metric 3: Explainable AI (XAI) QA Inspector Justification Window
 */

document.addEventListener("DOMContentLoaded", () => {
    // =========================================================
    // 1. INTRO SCREEN TRANSITION (FAST & INTERACTIVE)
    // =========================================================
    const introScreen = document.getElementById("introScreen");
    const mainPage = document.getElementById("mainPage");
    const btnEnterDashboard = document.getElementById("btnEnterDashboard");
    let hasEntered = false;

    function enterDashboard() {
        if (hasEntered) return;
        hasEntered = true;
        if (introScreen) {
            introScreen.style.transition = "opacity 0.4s ease, transform 0.4s ease";
            introScreen.style.opacity = "0";
            introScreen.style.pointerEvents = "none";
            introScreen.style.transform = "scale(1.04)";
            setTimeout(() => {
                introScreen.style.display = "none";
            }, 400);
        }
        if (mainPage) {
            mainPage.style.display = "block";
            mainPage.style.opacity = "1";
            mainPage.classList.add("active");
            setTimeout(() => {
                if (telemetryChart) telemetryChart.resize();
            }, 450);
        }
    }

    if (btnEnterDashboard) {
        btnEnterDashboard.addEventListener("click", (e) => {
            e.stopPropagation();
            enterDashboard();
        });
    }
    if (introScreen) {
        introScreen.addEventListener("click", enterDashboard);
    }
    document.addEventListener("keydown", enterDashboard, { once: true });

    // Auto-enter in 1.6s
    setTimeout(enterDashboard, 1600);

    // =========================================================
    // 2. MISSION CLOCK & INTERVAL ADVANCEMENT
    // =========================================================
    let missionSeconds = 0;
    let burnInHours = 0; // Virtual hours: 0h -> 24h -> 96h -> 168h
    let pendingReset = false;
    const missionTimeEl = document.getElementById("missionTime");
    const intervalFillEl = document.getElementById("intervalFill");
    const stage0h = document.getElementById("stage0h");
    const stage24h = document.getElementById("stage24h");
    const stage96h = document.getElementById("stage96h");
    const stage168h = document.getElementById("stage168h");
    const earlyRejectTag = document.getElementById("earlyRejectTag");
    const earlyHoursSaved = document.getElementById("earlyHoursSaved");

    setInterval(() => {
        missionSeconds++;
        const hours = Math.floor(missionSeconds / 3600);
        const minutes = Math.floor((missionSeconds % 3600) / 60);
        const seconds = missionSeconds % 60;
        if (missionTimeEl) {
            missionTimeEl.textContent = 
                `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
        }
    }, 1000);

    function updateBurnInInterval(virtualHour, isRejected = false) {
        if (pendingReset) {
            virtualHour = 0;
            isRejected = false;
        }
        burnInHours = virtualHour;
        const progress = Math.min(100, (burnInHours / 168) * 100);
        if (intervalFillEl) {
            intervalFillEl.style.width = `${progress}%`;
        }

        [stage0h, stage24h, stage96h, stage168h].forEach(st => {
            if (st) st.className = "stageNode";
        });

        if (burnInHours >= 168) {
            if (stage168h) stage168h.className = isRejected ? "stageNode flagged" : "stageNode active";
        } else if (burnInHours >= 96) {
            if (stage96h) stage96h.className = isRejected ? "stageNode flagged" : "stageNode active";
        } else if (burnInHours >= 24) {
            if (stage24h) stage24h.className = isRejected ? "stageNode flagged" : "stageNode active";
        } else {
            if (stage0h) stage0h.className = "stageNode active";
        }

        if (isRejected) {
            if (earlyRejectTag) {
                earlyRejectTag.textContent = `EARLY REJECT AT ${burnInHours}h`;
                earlyRejectTag.className = "earlyRejectBadge reject";
            }
            const saved = Math.max(0, 168 - burnInHours);
            if (earlyHoursSaved) {
                earlyHoursSaved.innerHTML = `Chamber Time Saved: <strong style="color:#ef4444;">${saved} hrs (SAVED)</strong>`;
            }
        } else {
            if (earlyRejectTag) {
                earlyRejectTag.textContent = `SCREENING: ${burnInHours}h / 168h`;
                earlyRejectTag.className = "earlyRejectBadge";
            }
            if (earlyHoursSaved) {
                earlyHoursSaved.innerHTML = `Chamber Time Saved: <strong>0 hrs</strong>`;
            }
        }
    }

    // =========================================================
    // 3. MULTI-AXIS REAL-TIME CHART.JS SETUP
    // =========================================================
    const chartCanvas = document.getElementById("telemetryChart");
    const ctx = chartCanvas ? chartCanvas.getContext("2d") : null;
    const MAX_POINTS = 30;

    const telemetryChart = ctx && typeof Chart !== "undefined" ? new Chart(ctx, {
        type: "line",
        data: {
            labels: Array(MAX_POINTS).fill(""),
            datasets: [
                {
                    label: "Standby Current Iddq (µA)",
                    data: Array(MAX_POINTS).fill(10.0),
                    borderColor: "#38bdf8",
                    backgroundColor: "rgba(56, 189, 248, 0.1)",
                    borderWidth: 2.5,
                    pointRadius: 2,
                    tension: 0.3,
                    yAxisID: "y-iddq"
                },
                {
                    label: "Supply Voltage (V)",
                    data: Array(MAX_POINTS).fill(5.0),
                    borderColor: "#60a5fa",
                    backgroundColor: "rgba(96, 165, 250, 0.05)",
                    borderWidth: 2,
                    pointRadius: 1.5,
                    tension: 0.3,
                    yAxisID: "y-vi"
                },
                {
                    label: "Active Current (A)",
                    data: Array(MAX_POINTS).fill(1.2),
                    borderColor: "#f97316",
                    backgroundColor: "rgba(249, 115, 22, 0.05)",
                    borderWidth: 2,
                    pointRadius: 1.5,
                    tension: 0.3,
                    yAxisID: "y-vi"
                },
                {
                    label: "Chamber Temp (°C)",
                    data: Array(MAX_POINTS).fill(125.0),
                    borderColor: "#ef4444",
                    backgroundColor: "rgba(239, 68, 68, 0.05)",
                    borderWidth: 2,
                    pointRadius: 1.5,
                    tension: 0.3,
                    yAxisID: "y-temp"
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: { duration: 200 },
            scales: {
                x: {
                    grid: { color: "rgba(255, 255, 255, 0.04)" },
                    ticks: { color: "#64748b", font: { size: 9 } }
                },
                "y-iddq": {
                    type: "linear",
                    position: "left",
                    suggestedMin: 0,
                    suggestedMax: 60,
                    grid: { color: "rgba(255, 255, 255, 0.05)" },
                    ticks: {
                        color: "#38bdf8",
                        callback: (v) => v + " µA"
                    },
                    title: {
                        display: true,
                        text: "Iddq Standby (µA)",
                        color: "#38bdf8"
                    }
                },
                "y-vi": {
                    type: "linear",
                    position: "right",
                    suggestedMin: 0,
                    suggestedMax: 10,
                    grid: { drawOnChartArea: false },
                    ticks: {
                        color: "#f97316",
                        callback: (v) => v + " V/A"
                    },
                    title: {
                        display: true,
                        text: "Voltage / Active Current",
                        color: "#f97316"
                    }
                },
                "y-temp": {
                    type: "linear",
                    position: "right",
                    suggestedMin: 100,
                    suggestedMax: 150,
                    grid: { drawOnChartArea: false },
                    ticks: {
                        color: "#ef4444",
                        callback: (v) => v + " °C"
                    },
                    title: {
                        display: true,
                        text: "Temp (°C)",
                        color: "#ef4444"
                    }
                }
            },
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: "rgba(15, 23, 42, 0.95)",
                    borderColor: "rgba(56, 189, 248, 0.4)",
                    borderWidth: 1
                }
            }
        }
    }) : null;

    if (!telemetryChart && chartCanvas) {
        chartCanvas.setAttribute("aria-label", "Telemetry chart unavailable");
        console.warn("Chart.js was not available; telemetry cards remain active.");
    }

    window.addEventListener("resize", () => {
        if (telemetryChart) telemetryChart.resize();
    });

    // =========================================================
    // 4. UI UPDATE HANDLER & QA EXPLAINABILITY (MEMBER 3 DYNAMIC)
    // =========================================================
    const iddqValueEl = document.getElementById("iddqValue");
    const iddqBadgeEl = document.getElementById("iddqBadge");
    const voltageValueEl = document.getElementById("voltageValue");
    const voltageBadgeEl = document.getElementById("voltageBadge");
    const currentValueEl = document.getElementById("currentValue");
    const currentBadgeEl = document.getElementById("currentBadge");
    const tempValueEl = document.getElementById("tempValue");
    const tempBadgeEl = document.getElementById("tempBadge");
    const anomalyScoreValueEl = document.getElementById("anomalyScoreValue");
    const aiBadgeEl = document.getElementById("aiBadge");

    const qaVerdictBadge = document.getElementById("qaVerdictBadge");
    const qaJustificationText = document.getElementById("qaJustificationText");
    const ifStatusTextEl = document.getElementById("ifStatusText");
    const driftStatusTextEl = document.getElementById("driftStatusText");
    const forecast168hValue = document.getElementById("forecast168hValue");
    const cusumStatusTextEl = document.getElementById("cusumStatusText");
    const alertFeedEl = document.getElementById("alert-feed");
    const systemStatusTextEl = document.getElementById("systemStatusText");
    const footerStatusEl = document.getElementById("footerStatus");

    // Dynamic Member 3 Physics & Model Stats
    const lotMeanStatEl = document.getElementById("lotMeanStat");
    const lotStdStatEl = document.getElementById("lotStdStat");
    const zScoreStatEl = document.getElementById("zScoreStat");
    const rawScoreStatEl = document.getElementById("rawScoreStat");
    const powerStatEl = document.getElementById("powerStat");
    const resStatEl = document.getElementById("resStat");
    const pdStatEl = document.getElementById("pdStat");
    // Module B
    const driftSlopeStatEl = document.getElementById("driftSlopeStat");

    let lastAlertMode = "nominal";

    function updateDashboardUI(payload) {
        const iddq = Number(payload.iddq_uA !== undefined ? payload.iddq_uA : (payload.iddq !== undefined ? payload.iddq : 10.0));
        const v = Number(payload.voltage !== undefined ? payload.voltage : 5.0);
        const c = Number(payload.current !== undefined ? payload.current : 1.20);
        const t = Number(payload.temperature !== undefined ? payload.temperature : 125.0);
        const pd = Number(payload.prop_delay !== undefined ? payload.prop_delay : 4.50);
        const score = Number(payload.anomaly_score !== undefined ? payload.anomaly_score : 0.032);
        const rawScore = Number(payload.raw_score !== undefined ? payload.raw_score : 0.1824);
        const isAnomaly = Boolean(payload.is_anomaly);
        const justification = payload.qa_justification || "QA STATUS [PASSED]: Operating nominally within lot distribution.";
        const lotMean = Number(payload.lot_mean_iddq || 10.00);
        const lotStd = Number(payload.lot_std_iddq || 1.17);
        const zScore = Number(payload.iddq_zscore !== undefined ? payload.iddq_zscore : ((iddq - lotMean) / lotStd));
        const power = Number(payload.power_w !== undefined ? payload.power_w : (v * c));
        const dynamicRes = Number(payload.dynamic_res_ohm !== undefined ? payload.dynamic_res_ohm : (v / (c + 1e-6)));

        // Member 4 CUSUM metrics
        const cusumScore = Number(payload.cusum_score !== undefined ? payload.cusum_score : 0.0);
        const cusumDriftDetected = Boolean(payload.cusum_drift_detected);
        const cusumThr = Number(payload.cusum_threshold !== undefined ? payload.cusum_threshold : 5.0);

        // 1. Update Telemetry Cards
        if (iddqValueEl) iddqValueEl.textContent = iddq.toFixed(1);
        if (voltageValueEl) voltageValueEl.textContent = v.toFixed(2);
        if (currentValueEl) currentValueEl.textContent = c.toFixed(2);
        if (tempValueEl) tempValueEl.textContent = t.toFixed(1);
        if (anomalyScoreValueEl) anomalyScoreValueEl.textContent = (score * 100).toFixed(1) + "%";

        // 2. Iddq Dynamic Badge (Real calculation from Member 3 lot mean and z-score)
        if (iddqBadgeEl) {
            if (isAnomaly) {
                const ratio = (iddq / lotMean).toFixed(1);
                iddqBadgeEl.textContent = `${ratio}x LOT MEAN (Z: ${zScore >= 0 ? '+' : ''}${zScore.toFixed(1)}σ)`;
                iddqBadgeEl.className = "cardBadge critical";
            } else if (iddq > (lotMean + 3 * lotStd)) {
                iddqBadgeEl.textContent = `ELEVATED LEAKAGE (+${zScore.toFixed(1)}σ)`;
                iddqBadgeEl.className = "cardBadge warning";
            } else {
                iddqBadgeEl.textContent = `LOT AVG: ${lotMean.toFixed(1)} µA (±${lotStd.toFixed(1)}σ)`;
                iddqBadgeEl.className = "cardBadge";
            }
        }

        // 3. Dynamic Stats Rows (Real physics & ML values from Member 3)
        if (lotMeanStatEl) lotMeanStatEl.textContent = `${lotMean.toFixed(2)} µA`;
        if (lotStdStatEl) lotStdStatEl.textContent = `${lotStd.toFixed(2)} µA`;
        if (zScoreStatEl) {
            zScoreStatEl.textContent = `${zScore >= 0 ? '+' : ''}${zScore.toFixed(2)} σ`;
            zScoreStatEl.style.color = Math.abs(zScore) >= 3.0 ? '#ef4444' : '#10b981';
        }
        if (rawScoreStatEl) {
            rawScoreStatEl.textContent = `${rawScore >= 0 ? '+' : ''}${rawScore.toFixed(4)}`;
            rawScoreStatEl.className = rawScore < 0 ? 'text-red' : 'text-green';
        }
        if (powerStatEl) powerStatEl.textContent = `${power.toFixed(2)} W`;
        if (resStatEl) resStatEl.textContent = `${dynamicRes.toFixed(2)} Ω`;
        if (pdStatEl) pdStatEl.textContent = `${pd.toFixed(3)} ns`;

        // 3b. Module B Drift Predictor outputs (real-time from backend)
        const driftStatus   = payload.drift_status       || "INITIALIZING";
        const forecastLabel = payload.forecast_168h_label || "--";
        const driftSlope    = Number(payload.drift_slope_ua_h !== undefined ? payload.drift_slope_ua_h : 0.0);
        const earlyRejectB  = Boolean(payload.early_reject_b);

        if (driftStatusTextEl) {
            driftStatusTextEl.textContent = driftStatus;
            driftStatusTextEl.className = earlyRejectB ? "text-red" : "text-green";
        }
        if (forecast168hValue) {
            forecast168hValue.textContent = forecastLabel;
            forecast168hValue.className = earlyRejectB ? "text-red" : "text-green";
        }
        if (driftSlopeStatEl) {
            driftSlopeStatEl.textContent = `${driftSlope >= 0 ? '+' : ''}${driftSlope.toFixed(4)} µA/h`;
            driftSlopeStatEl.className = Math.abs(driftSlope) > 0.1 ? "text-red" : "text-green";
        }

        // 3c. Member 4 CUSUM outputs
        if (cusumStatusTextEl) {
            cusumStatusTextEl.textContent = `${cusumScore.toFixed(4)} (${cusumDriftDetected ? 'DRIFT ALARM' : 'NORMAL'})`;
            cusumStatusTextEl.className = cusumDriftDetected ? "text-red" : "text-green";
        }

        // 4. QA Inspector Box & AI FDIR (Coordinated between Modules A, B, and Member 4)
        if (isAnomaly) {
            if (qaVerdictBadge) {
                qaVerdictBadge.textContent = "LOT REJECTED";
                qaVerdictBadge.className = "qaBadge fail";
            }
            if (qaJustificationText) {
                qaJustificationText.textContent = justification;
                qaJustificationText.style.borderLeftColor = "#ef4444";
            }

            if (ifStatusTextEl) {
                ifStatusTextEl.textContent = "DYNAMIC OUTLIER FLAG";
                ifStatusTextEl.className = "text-red";
            }
            if (systemStatusTextEl) systemStatusTextEl.textContent = "FDIR: REJECTION ARMED";
            if (footerStatusEl) footerStatusEl.textContent = "REJECTION LOGGED - ECSS INTERVENTION";
            if (aiBadgeEl) {
                aiBadgeEl.className = "cardBadge critical";
                aiBadgeEl.textContent = "ANOMALY REJECT";
            }

            if (lastAlertMode !== "anomaly") {
                pushAlert("alert-red", `⚡ ${justification}`);
                lastAlertMode = "anomaly";
            }
        } else if (earlyRejectB) {
            if (qaVerdictBadge) {
                qaVerdictBadge.textContent = "EARLY REJECT";
                qaVerdictBadge.className = "qaBadge fail";
            }
            if (qaJustificationText) {
                qaJustificationText.textContent = `QA STATUS [EARLY REJECT]: Module B forecasting projects 168h Iddq will reach ${forecastLabel}, exceeding qualification safety slope.`;
                qaJustificationText.style.borderLeftColor = "#ef4444";
            }

            if (ifStatusTextEl) {
                ifStatusTextEl.textContent = "HEALTHY (INLIER)";
                ifStatusTextEl.className = "text-green";
            }
            if (systemStatusTextEl) systemStatusTextEl.textContent = "MODULE B: 168h VIOLATION FORECAST";
            if (footerStatusEl) footerStatusEl.textContent = "EARLY REJECTION ARMED - LATENT DRIFT DETECTED";
            if (aiBadgeEl) {
                aiBadgeEl.className = "cardBadge critical";
                aiBadgeEl.textContent = "LATENT DRIFT REJECT";
            }

            if (lastAlertMode !== "drift_reject") {
                pushAlert("alert-yellow", `⏳ MODULE B: 168h Iddq projected to reach ${forecastLabel} — early rejection armed.`);
                lastAlertMode = "drift_reject";
            }
        } else if (cusumDriftDetected) {
            if (qaVerdictBadge) {
                qaVerdictBadge.textContent = "DRIFT DETECTED";
                qaVerdictBadge.className = "qaBadge warning";
            }
            if (qaJustificationText) {
                qaJustificationText.textContent = `QA STATUS [DRIFT ALERT]: Module C Cumulative Sum (CUSUM) statistical filter flagged latent parametric creep (S+ = ${cusumScore.toFixed(4)} >= ${cusumThr.toFixed(1)} µA).`;
                qaJustificationText.style.borderLeftColor = "#f59e0b";
            }

            if (ifStatusTextEl) {
                ifStatusTextEl.textContent = "HEALTHY (INLIER)";
                ifStatusTextEl.className = "text-green";
            }
            if (systemStatusTextEl) systemStatusTextEl.textContent = "CUSUM DRIFT DETECTED";
            if (footerStatusEl) footerStatusEl.textContent = "CUSUM ALARM LOGGED - LATENT CREEP";
            if (aiBadgeEl) {
                aiBadgeEl.className = "cardBadge warning";
                aiBadgeEl.textContent = "MODULE C (CUSUM)";
            }

            if (lastAlertMode !== "cusum_drift") {
                pushAlert("alert-yellow", `📈 MODULE C CUSUM: Progressive time-series drift detected (S+ = ${cusumScore.toFixed(4)} >= ${cusumThr.toFixed(1)} µA).`);
                lastAlertMode = "cusum_drift";
            }
        } else {
            if (qaVerdictBadge) {
                qaVerdictBadge.textContent = "LOT PASSED";
                qaVerdictBadge.className = "qaBadge pass";
            }
            if (qaJustificationText) {
                qaJustificationText.textContent = justification;
                qaJustificationText.style.borderLeftColor = "#10b981";
            }

            if (ifStatusTextEl) {
                ifStatusTextEl.textContent = "HEALTHY (INLIER)";
                ifStatusTextEl.className = "text-green";
            }
            if (systemStatusTextEl) systemStatusTextEl.textContent = "DYNAMIC FDIR ACTIVE";
            if (footerStatusEl) footerStatusEl.textContent = "SYSTEM READY";
            if (aiBadgeEl) {
                aiBadgeEl.className = "cardBadge";
                aiBadgeEl.textContent = "MODULE A (ISOLATION)";
            }
            lastAlertMode = "nominal";
        }

        // 5. Update Chart
        if (telemetryChart) {
            const now = new Date().toLocaleTimeString().split(" ")[0];
            telemetryChart.data.labels.push(now);
            telemetryChart.data.labels.shift();

            telemetryChart.data.datasets[0].data.push(iddq);
            telemetryChart.data.datasets[0].data.shift();

            telemetryChart.data.datasets[1].data.push(v);
            telemetryChart.data.datasets[1].data.shift();

            telemetryChart.data.datasets[2].data.push(c);
            telemetryChart.data.datasets[2].data.shift();

            telemetryChart.data.datasets[3].data.push(t);
            telemetryChart.data.datasets[3].data.shift();

            telemetryChart.update("none");
        }
    }

    function pushAlert(typeClass, message) {
        const timeStr = `[${new Date().toLocaleTimeString()}]`;
        const card = document.createElement("div");
        card.className = `alertCard ${typeClass}`;

        const timeDiv = document.createElement("div");
        timeDiv.className = "alertTime";
        timeDiv.textContent = timeStr;

        const bodyDiv = document.createElement("div");
        bodyDiv.className = "alertBody";
        bodyDiv.textContent = message;

        card.appendChild(timeDiv);
        card.appendChild(bodyDiv);
        if (alertFeedEl) {
            alertFeedEl.insertBefore(card, alertFeedEl.firstChild);
            while (alertFeedEl.children.length > 12) {
                alertFeedEl.removeChild(alertFeedEl.lastChild);
            }
        }
    }

    // =========================================================
    // 5. WEBSOCKET CLIENT & HONEST ERROR HANDLING
    // =========================================================
    let ws = null;
    let isWsConnected = false;
    let reconnectTimer = null;
    let isPageUnloading = false;
    let currentScenario = "nominal";

    const wsStatusTextEl = document.getElementById("wsStatusText");
    const wsDotEl = document.getElementById("wsDot");

    function connectWebSocket() {
        if (isPageUnloading) return;
        try {
            const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
            const host = window.location.host || "127.0.0.1:8000";
            ws = new WebSocket(`${proto}//${host}/ws`);
            ws.onopen = () => {
                isWsConnected = true;
                if (wsStatusTextEl) wsStatusTextEl.textContent = "LIVE BACKEND CONNECTED";
                if (wsDotEl) wsDotEl.className = "statusDot green";
                pushAlert("alert-green", "Connected to FastAPI real-time burn-in telemetry stream.");
                syncTeamStatus();
                hydrateTeamHistory();
                if (typeof fetchAndSyncCriticality === "function") {
                    fetchAndSyncCriticality();
                }
                // Re-sync active scenario upon reconnect if not nominal
                if (currentScenario && currentScenario !== "nominal") {
                    sendWsAction("set_scenario", currentScenario);
                }
            };
            ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    updateDashboardUI(data);
                    if (typeof window._arjunaExtendedUpdate === "function") {
                        window._arjunaExtendedUpdate(data);
                    }
                    
                    // Task 2: Wire live burn_in_hours into progress bar
                    if (data.burn_in_hours !== undefined) {
                        const isRejected = Boolean(data.is_anomaly || data.early_reject_b || data.cusum_drift_detected);
                        updateBurnInInterval(data.burn_in_hours, isRejected);
                    }
                } catch (e) {
                    console.error("Invalid JSON:", e);
                }
            };
            ws.onclose = () => {
                if (isPageUnloading) return;
                if (isWsConnected) {
                    isWsConnected = false;
                    if (wsStatusTextEl) wsStatusTextEl.textContent = "⚠️ BACKEND OFFLINE — WAITING FOR CONNECTION";
                    if (wsDotEl) wsDotEl.className = "statusDot red";
                    pushAlert("alert-red", "⚠️ Backend WebSocket disconnected. Please start the server.");
                }
                reconnectTimer = setTimeout(connectWebSocket, 3000);
            };
            ws.onerror = () => {
                if (!isWsConnected) {
                    if (wsStatusTextEl) wsStatusTextEl.textContent = "⚠️ CONNECTION ERROR";
                    if (wsDotEl) wsDotEl.className = "statusDot red";
                }
            };
        } catch (e) {
            console.error("WebSocket init error:", e);
        }
    }

    window.addEventListener("beforeunload", () => {
        isPageUnloading = true;
        if (reconnectTimer) clearTimeout(reconnectTimer);
        if (ws) {
            ws.onclose = null;
            ws.close(1000, "Page unloaded");
        }
    });

    window.addEventListener("pagehide", () => {
        isPageUnloading = true;
        if (reconnectTimer) clearTimeout(reconnectTimer);
        if (ws) {
            ws.onclose = null;
            ws.close(1000, "Page hidden");
        }
    });

    connectWebSocket();

    // =========================================================
    // 6. SCENARIO CONTROL BUTTONS
    // =========================================================
    const activeScenarioLabel = document.getElementById("activeScenarioLabel");
    const btnNominal = document.getElementById("btn-nominal");
    const btnIsroOutlier = document.getElementById("btn-isro-outlier");
    const btnThermal = document.getElementById("btn-thermal");
    const btnShort = document.getElementById("btn-short");
    const btnReset = document.getElementById("btn-reset");

    function setActiveBtn(activeBtn) {
        [btnNominal, btnIsroOutlier, btnThermal, btnShort].forEach(b => b && b.classList.remove("active"));
        if (activeBtn) activeBtn.classList.add("active");
    }

    function sendWsAction(action, scenario = null) {
        if (action === "set_scenario" && scenario && scenario !== "nominal") {
            const eventType = {
                isro_outlier: "ELECTRICAL_SPIKE",
                thermal_drift: "THERMAL_DRIFT",
                electrical_short: "ELECTRICAL_SHORT_CIRCUIT",
            }[scenario];
            if (eventType) {
                fetch("/api/inject-fault", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ event_type: eventType }),
                }).catch(() => {});
            }
        } else if (action === "reset" || (action === "set_scenario" && scenario === "nominal")) {
            fetch("/api/reset", { method: "POST" }).catch(() => {});
        }
        if (ws && ws.readyState === WebSocket.OPEN) {
            const msg = { action: action };
            if (scenario) msg.scenario = scenario;
            ws.send(JSON.stringify(msg));
        }
    }

    async function hydrateTeamHistory() {
        try {
            const response = await fetch("/api/history?limit=30");
            if (!response.ok || !telemetryChart) return;
            const frames = await response.json();
            if (!Array.isArray(frames) || frames.length === 0) return;
            const recent = frames.slice(-30);
            telemetryChart.data.labels = recent.map((frame) => {
                const timestamp = frame.timestamp ? new Date(frame.timestamp) : new Date();
                return timestamp.toLocaleTimeString().split(" ")[0];
            });
            telemetryChart.data.datasets[0].data = recent.map((frame) => Number(frame.iddq_uA ?? frame.iddq ?? 10));
            telemetryChart.data.datasets[1].data = recent.map((frame) => Number(frame.voltage ?? 5));
            telemetryChart.data.datasets[2].data = recent.map((frame) => Number(frame.current ?? 1.2));
            telemetryChart.data.datasets[3].data = recent.map((frame) => Number(frame.temperature ?? 125));
            telemetryChart.update("none");
        } catch (error) {
            console.warn("Team history is unavailable; continuing with live telemetry.", error);
        }
    }

    async function syncTeamStatus() {
        try {
            const response = await fetch("/api/status");
            if (response.ok) await response.json();
        } catch (error) {
            console.warn("Team status is unavailable; continuing with live telemetry.", error);
        }
    }

    if (btnNominal) {
        btnNominal.addEventListener("click", () => {
            currentScenario = "nominal";
            setActiveBtn(btnNominal);
            activeScenarioLabel.textContent = "SCENARIO: NOMINAL LOT SCREENING";
            activeScenarioLabel.style.color = "#10b981";
            activeScenarioLabel.style.borderColor = "#10b981";
            updateBurnInInterval(0, false);
            pushAlert("alert-green", "🟢 Scenario changed: Nominal lot screening baseline restored (10 µA avg).");
            sendWsAction("set_scenario", "nominal");
        });
    }

    if (btnIsroOutlier) {
        btnIsroOutlier.addEventListener("click", () => {
            currentScenario = "isro_outlier";
            setActiveBtn(btnIsroOutlier);
            activeScenarioLabel.textContent = "SCENARIO: ISRO DYNAMIC OUTLIER (45 µA IN 10 µA LOT)";
            activeScenarioLabel.style.color = "#ef4444";
            activeScenarioLabel.style.borderColor = "#ef4444";
            pushAlert("alert-red", "🔴 Injected ISRO Dynamic Outlier: 45 µA part in 10 µA lot (under 50 µA max). Testing Module A.");
            sendWsAction("set_scenario", "isro_outlier");
        });
    }

    if (btnThermal) {
        btnThermal.addEventListener("click", () => {
            currentScenario = "thermal_drift";
            setActiveBtn(btnThermal);
            activeScenarioLabel.textContent = "SCENARIO: LATENT DRIFT (EARLY 24h REJECTION)";
            activeScenarioLabel.style.color = "#f59e0b";
            activeScenarioLabel.style.borderColor = "#f59e0b";
            pushAlert("alert-yellow", "🟡 Injected Latent Drift: 0h -> 24h tracking to predict 168h failure ahead of time.");
            sendWsAction("set_scenario", "thermal_drift");
        });
    }

    if (btnShort) {
        btnShort.addEventListener("click", () => {
            currentScenario = "electrical_short";
            setActiveBtn(btnShort);
            activeScenarioLabel.textContent = "SCENARIO: CATASTROPHIC SHORT CIRCUIT";
            activeScenarioLabel.style.color = "#e11d48";
            activeScenarioLabel.style.borderColor = "#e11d48";
            pushAlert("alert-red", "⚡ Injected Catastrophic Short: Testing multivariate voltage collapse.");
            sendWsAction("set_scenario", "electrical_short");
        });
    }

    if (btnReset) {
        btnReset.addEventListener("click", () => {
            currentScenario = "nominal";
            missionSeconds = 0;
            pendingReset = true;
            setActiveBtn(btnNominal);
            activeScenarioLabel.textContent = "SCENARIO: NOMINAL LOT SCREENING";
            activeScenarioLabel.style.color = "#38bdf8";
            activeScenarioLabel.style.borderColor = "#38bdf8";
            if (alertFeedEl) alertFeedEl.innerHTML = "";
            updateBurnInInterval(0, false);
            pushAlert("alert-green", "🔄 Chamber reset: 0h baseline restored.");
            sendWsAction("reset");
            setTimeout(() => {
                pendingReset = false;
            }, 1000);
        });
    }

    // =========================================================
    // 7. CRITICALITY LEVEL CONTROLS (REST API — not WebSocket)
    //    Backend is the source of truth. Frontend reads criticality
    //    from /api/criticality on connect and after each reconnect.
    // =========================================================
    const btnCrit1 = document.getElementById("btn-crit-1");
    const btnCrit2 = document.getElementById("btn-crit-2");
    const btnCrit3 = document.getElementById("btn-crit-3");
    const criticalityLabelEl = document.getElementById("criticalityLabel");
    const critCusumThresholdEl = document.getElementById("critCusumThreshold");
    const critIfGateEl = document.getElementById("critIfGate");
    const critFaultLabelEl = document.getElementById("critFaultLabel");

    const CRIT_META = {
        1: { label: "LEVEL 1 — LOW CRITICALITY",  color: "#10b981", btn: btnCrit1 },
        2: { label: "LEVEL 2 — STANDARD",          color: "#6366f1", btn: btnCrit2 },
        3: { label: "LEVEL 3 — MISSION CRITICAL",  color: "#ef4444", btn: btnCrit3 },
    };

    function setCriticalityUI(cfg) {
        // cfg = { criticality_level, label, description, cusum_threshold, if_score_threshold }
        const level = cfg.criticality_level;
        const meta  = CRIT_META[level];
        if (!meta) return;

        // Update selector buttons
        [btnCrit1, btnCrit2, btnCrit3].forEach(b => b && b.classList.remove("active"));
        if (meta.btn) meta.btn.classList.add("active");

        // Update label badge
        if (criticalityLabelEl) {
            criticalityLabelEl.textContent  = meta.label;
            criticalityLabelEl.style.borderColor = meta.color;
            criticalityLabelEl.style.color  = meta.color;
        }

        // Update threshold display
        if (critCusumThresholdEl) critCusumThresholdEl.textContent = cfg.cusum_threshold.toFixed(1);
        if (critIfGateEl)         critIfGateEl.textContent         = cfg.if_score_threshold.toFixed(2);
        if (critFaultLabelEl)     critFaultLabelEl.textContent     = cfg.label || "";
    }

    async function fetchAndSyncCriticality() {
        try {
            const resp = await fetch("/api/criticality");
            if (resp.ok) {
                const cfg = await resp.json();
                setCriticalityUI(cfg);
            }
        } catch (e) {
            console.warn("Could not fetch criticality level:", e);
        }
    }

    async function postCriticality(level) {
        try {
            const resp = await fetch("/api/set-criticality", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ criticality_level: level }),
            });
            if (resp.ok) {
                const cfg = await resp.json();
                setCriticalityUI(cfg);
                pushAlert("alert-green", `🎯 Criticality updated to Level ${level} (${cfg.label}). CUSUM h=${cfg.cusum_threshold}, IF gate=${cfg.if_score_threshold}.`);
            } else {
                const err = await resp.json().catch(() => ({}));
                pushAlert("alert-red", `❌ Criticality change rejected: ${err.error || resp.statusText}`);
            }
        } catch (e) {
            pushAlert("alert-red", `❌ Could not reach backend to set criticality: ${e.message}`);
        }
    }

    if (btnCrit1) btnCrit1.addEventListener("click", () => postCriticality(1));
    if (btnCrit2) btnCrit2.addEventListener("click", () => postCriticality(2));
    if (btnCrit3) btnCrit3.addEventListener("click", () => postCriticality(3));

    // Sync criticality from backend on page load and after each WebSocket reconnect
    fetchAndSyncCriticality();
    syncTeamStatus();
    hydrateTeamHistory();

    // =========================================================
    // 8. LIVE FAULT TYPE & DETECTION SOURCE DISPLAY
    //    Update the QA FDIR panel with fault_type and detection_source
    //    from each telemetry tick (fields added in server.py).
    // =========================================================
    // Extend updateDashboardUI to also reflect fault_type and detection_source.
    // We patch the function by wrapping around the existing logic that fires on each message.
    const _origUpdate = updateDashboardUI;
    window._arjunaExtendedUpdate = function(payload) {
        const faultType = payload.fault_type || "NORMAL";
        const detSource = payload.detection_source || "none";
        const cusumThr  = payload.cusum_threshold !== undefined ? payload.cusum_threshold : null;
        const critLevel = payload.criticality_level || 2;

        // Sync criticality threshold display from live telemetry
        if (cusumThr !== null && critCusumThresholdEl) {
            critCusumThresholdEl.textContent = cusumThr.toFixed(1);
        }

        // Update FDIR panel fault type row (append if not yet present)
        let faultTypeRow = document.getElementById("faultTypeRow");
        let detSourceRow = document.getElementById("detSourceRow");
        let critLevelRow = document.getElementById("critLevelRow");
        const fdirBox = document.querySelector(".fdirSummaryBox");
        if (fdirBox && !faultTypeRow) {
            faultTypeRow = document.createElement("div");
            faultTypeRow.className = "fdirStatusRow";
            faultTypeRow.style.cssText = "border-top: 1px solid rgba(239,68,68,0.3); margin-top: 6px; padding-top: 6px;";
            faultTypeRow.id = "faultTypeRow";
            faultTypeRow.innerHTML = `<span>Fault Classification:</span><strong id="faultTypeText" class="text-green">NORMAL</strong>`;
            fdirBox.appendChild(faultTypeRow);

            detSourceRow = document.createElement("div");
            detSourceRow.className = "fdirStatusRow";
            detSourceRow.id = "detSourceRow";
            detSourceRow.innerHTML = `<span>Detection Source:</span><strong id="detSourceText" class="text-green">—</strong>`;
            fdirBox.appendChild(detSourceRow);

            critLevelRow = document.createElement("div");
            critLevelRow.className = "fdirStatusRow";
            critLevelRow.id = "critLevelRow";
            critLevelRow.innerHTML = `<span>Criticality Level:</span><strong id="critLevelText" class="text-green">LEVEL 2</strong>`;
            fdirBox.appendChild(critLevelRow);
        }

        const faultTypeText = document.getElementById("faultTypeText");
        const detSourceText = document.getElementById("detSourceText");
        const critLevelText = document.getElementById("critLevelText");
        if (faultTypeText) {
            const isBad = faultType !== "NORMAL";
            faultTypeText.textContent = faultType;
            faultTypeText.className = isBad ? "text-red" : "text-green";
        }
        if (detSourceText) {
            const isAlert = detSource !== "none";
            detSourceText.textContent = detSource.replace(/_/g, " ").toUpperCase();
            detSourceText.className = isAlert ? "text-red" : "text-green";
        }
        if (critLevelText) {
            critLevelText.textContent = `LEVEL ${critLevel}`;
        }

        // Also update the CUSUM display to show the active threshold
        const cusumEl = document.getElementById("cusumStatusText");
        if (cusumEl && payload.cusum_score !== undefined) {
            const cusumScore = Number(payload.cusum_score);
            const cusumDetected = Boolean(payload.cusum_drift_detected);
            const thrStr = cusumThr !== null ? `/${cusumThr.toFixed(1)}` : "";
            cusumEl.textContent = `${cusumScore.toFixed(4)}${thrStr} (${cusumDetected ? "DRIFT ALARM" : "NORMAL"})`;
            cusumEl.className = cusumDetected ? "text-red" : "text-green";
        }

        // 9. STRUCTURED XAI EVIDENCE RENDERING
        const se = payload.structured_evidence;
        const xaiRule = document.getElementById("xaiRuleTriggered");
        const xaiSource = document.getElementById("xaiDetectionSource");
        const xaiDelta = document.getElementById("xaiParametricDelta");
        const xaiGate = document.getElementById("xaiDynamicGate");
        const recBadge = document.getElementById("recommendedActionBadge");
        if (se) {
            const isReject = se.verdict === "REJECTED";
            if (xaiRule) {
                xaiRule.textContent = se.rule_triggered || "NOMINAL_OPERATION";
                xaiRule.className = isReject ? "text-red" : "text-green";
            }
            if (xaiSource) {
                xaiSource.textContent = (se.detection_source || "none").replace(/_/g, " ").toUpperCase();
                xaiSource.className = isReject ? "text-red" : "text-cyan";
            }
            if (xaiDelta) {
                const zVal = Number(payload.iddq_zscore || 0.0);
                xaiDelta.textContent = `${zVal >= 0 ? '+' : ''}${zVal.toFixed(1)} σ (${Math.abs(zVal) >= 3 ? 'OUTLIER' : 'INLIER'})`;
                xaiDelta.className = Math.abs(zVal) >= 3 ? "text-red" : "text-green";
            }
            if (xaiGate) {
                const lotMean = Number(payload.lot_mean_iddq || 10.0);
                const lotStd = Number(payload.lot_std_iddq || 1.17);
                xaiGate.textContent = `${(lotMean + 3.0 * lotStd).toFixed(2)} µA`;
            }
            if (recBadge) {
                const act = se.recommended_action || "PROCEED_SCREENING";
                recBadge.textContent = `ACTION: ${act}`;
                recBadge.className = isReject ? "actionBadge reject" : "actionBadge pass";
            }
        }

        // Maintain in-memory session telemetry buffer for client-side export
        if (!window._telemetryBuffer) window._telemetryBuffer = [];
        window._telemetryBuffer.push(payload);
        if (window._telemetryBuffer.length > 1000) window._telemetryBuffer.shift();

        // Update Timeline Ribbon if new fault state detected
        if (payload.fault_type && payload.fault_type !== "NORMAL") {
            const ribbon = document.getElementById("timelineRibbon");
            if (ribbon && ribbon.lastChild && !ribbon.lastChild.textContent.includes(payload.fault_type)) {
                const node = document.createElement("div");
                node.className = payload.fault_type === "THERMAL_DRIFT" ? "timelineNode warning" : "timelineNode critical";
                const timeStr = (payload.timestamp || "").split("T")[1]?.slice(0, 8) || "LIVE";
                node.textContent = `[${timeStr}] ${payload.fault_type} (${payload.scenario})`;
                ribbon.appendChild(node);
                ribbon.scrollLeft = ribbon.scrollWidth;
            }
        }
    };

    // =========================================================
    // 10. TELEMETRY EXPORT (CSV & JSON) AND HISTORY QUERYING
    // =========================================================
    const btnExportCsv = document.getElementById("btnExportCsv");
    const btnExportJson = document.getElementById("btnExportJson");
    const btnFetchHistory = document.getElementById("btnFetchHistory");
    const faultFilterSelect = document.getElementById("faultFilterSelect");
    const historyCountBadge = document.getElementById("historyCountBadge");

    function downloadFile(content, fileName, contentType) {
        const a = document.createElement("a");
        const file = new Blob([content], { type: contentType });
        a.href = URL.createObjectURL(file);
        a.download = fileName;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(a.href);
    }

    if (btnExportCsv) {
        btnExportCsv.addEventListener("click", () => {
            const data = window._telemetryBuffer || [];
            if (!data.length) {
                pushAlert("alert-yellow", "No telemetry buffered in current session to export.");
                return;
            }
            const headers = [
                "timestamp", "voltage", "current", "temperature", "iddq_uA",
                "prop_delay", "anomaly_score", "is_anomaly", "fault_type",
                "criticality_level", "system_status"
            ];
            const rows = data.map(r => [
                r.timestamp || "",
                r.voltage ?? 5.0,
                r.current ?? 1.20,
                r.temperature ?? 125.0,
                r.iddq_uA ?? 10.0,
                r.prop_delay ?? 4.5,
                r.anomaly_score ?? 0.03,
                r.is_anomaly ? 1 : 0,
                r.fault_type || "NORMAL",
                r.criticality_level ?? 2,
                r.system_status || "NOMINAL"
            ].join(","));
            const csvContent = headers.join(",") + "\n" + rows.join("\n");
            const ts = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
            downloadFile(csvContent, `ARJUNA_Telemetry_${ts}.csv`, "text/csv;charset=utf-8;");
            pushAlert("alert-green", `📥 Successfully exported ${data.length} telemetry records to CSV.`);
        });
    }

    if (btnExportJson) {
        btnExportJson.addEventListener("click", () => {
            const data = window._telemetryBuffer || [];
            if (!data.length) {
                pushAlert("alert-yellow", "No telemetry buffered in current session to export.");
                return;
            }
            const jsonStr = JSON.stringify(data, null, 2);
            const ts = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
            downloadFile(jsonStr, `ARJUNA_Telemetry_${ts}.json`, "application/json");
            pushAlert("alert-green", `📦 Successfully exported ${data.length} telemetry records to JSON.`);
        });
    }

    if (btnFetchHistory && faultFilterSelect) {
        btnFetchHistory.addEventListener("click", async () => {
            const faultType = faultFilterSelect.value;
            try {
                const url = `/api/history?limit=100${faultType !== 'ALL' ? `&fault_type=${encodeURIComponent(faultType)}` : ''}`;
                const resp = await fetch(url);
                if (resp.ok) {
                    const records = await resp.json();
                    if (historyCountBadge) {
                        historyCountBadge.textContent = `Records Found: ${records.length}`;
                    }
                    pushAlert("alert-green", `🔍 Queried ${records.length} records matching filter: ${faultType}`);
                } else {
                    pushAlert("alert-red", `Failed to query history: ${resp.statusText}`);
                }
            } catch (e) {
                pushAlert("alert-red", `Error fetching history: ${e.message}`);
            }
        });
    }

});
