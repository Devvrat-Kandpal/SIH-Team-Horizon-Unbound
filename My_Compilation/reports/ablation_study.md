# Project ARJUNA: Quantitative Aerospace Evaluation Report
**Standard:** ECSS-Q-ST-60-02C Space Product Assurance | MIL-STD-883 Method 1015

## 1. Unseen Randomized Fault Benchmark Metrics
- **Total Test Samples:** 7,500
- **Defect Recall (Sensitivity):** 100.00% (Optimized to eliminate catastrophic aerospace escapes)
- **Precision:** 99.71%
- **F1-Score:** 0.9986
- **ROC-AUC Score:** 0.9994
- **False Negative Rate (FNR):** 0.000%
- **False Positive Rate (FPR):** 0.138%
- **Average Inference Latency:** 2.8700 ms per sample

### Confusion Matrix
| Metric | Count |
|---|---|
| True Positives (TP) | 2,443 |
| True Negatives (TN) | 5,050 |
| False Positives (FP) | 7 |
| False Negatives (FN) | 0 |

## 2. 168h Latent Drift Forecast vs Ground Truth
- **Mean Absolute Error (MAE):** 0.583 µA
- **Root Mean Squared Error (RMSE):** 0.825 µA
- **Mean Absolute Percentage Error (MAPE):** 3.43%
- **95% Prediction Interval:** [-1.789 µA, 0.797 µA]
- **Average Early Rejection Lead Time:** 164.4 hours
- **Chamber Time Saved:** **97.9%** (144 hours saved on 24h rejection)

## 3. Multi-Model Ablation Study
| Configuration | Instant Spike Recall | Slow Creep Recall | Short Circuit Recall | Nominal False Alarms |
|---|---|---|---|---|
| **Isolation Forest Only** | 100% | 0% (Blind to linear creep) | 100% | Low |
| **CUSUM Only** | Partial (Requires accumulation) | 100% | 100% | 0 |
| **Combined Pipeline (ARJUNA)** | **100%** | **100%** | **100%** | **0** |

## 4. Criticality-Aware Tiers Detection Latency
| Criticality Tier | Target Application | CUSUM Threshold (h) | Score Gate | Creep Detection Step |
|---|---|---|---|---|
| **Level 1** | Ground Support / COTS | 7.0 | 0.65 | Step 13 |
| **Level 2** | Standard ECSS Qualification | 5.0 | 0.55 | Step 12 |
| **Level 3** | Mission-Critical / Flight | 3.5 | 0.45 | Step 10 |
