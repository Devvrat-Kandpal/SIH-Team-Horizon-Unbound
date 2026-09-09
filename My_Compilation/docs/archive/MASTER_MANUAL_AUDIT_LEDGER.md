# PROJECT ARJUNA — FORENSIC AUDIT & CLAIMS LEDGER (HISTORICAL)
**SIH 26170 | Phase 0 Baseline Audit | Status: HISTORICAL REFERENCE ARTIFACT**

> [!NOTE]
> **HISTORICAL AUDIT ARTIFACT**: This document preserves the Phase 0 forensic claim ledger, evidence matrix, and baseline contradiction register.
> For the active master presentation manual, spoken demo scripts, and team Q&A battle bank, refer to the canonical [docs/MASTER_MANUAL.md](../MASTER_MANUAL.md).

> Evidence outranks wording. Current implementation outranks documentation.
> No statement stronger than its evidence.

## 0. PRE-AUDIT BASELINE (PHASE 0)
- HEAD: `c153716` (main). Working tree DIRTY (pre-existing, not caused by this audit):
  ~35 modified + 8 untracked files at audit start.
- Env: Win32, Python 3.14.4, numpy 2.4.6, pandas 2.3.3, scipy 1.17.0,
  scikit-learn 1.9.0, fastapi 0.136.0, pydantic 2.13.4, uvicorn 0.48.0,
  joblib 1.5.3, pytest 9.0.3, ruff 0.16.1.
- Repo: 183 files under My_Compilation (46 py, 11 md, 21 joblib/csv/db).
- Tests collected: **119 across 18 suites**. Result: **119 passed (100% green)**.
  The previous server/tests mismatch (E-CONTRADICTION-1 regarding /api/config and WS RBAC)
  has been resolved, and multi-client coherence tests added (`tests/test_multi_client_interference.py`).
- Module B files at HEAD: `Backend/isolation_forest.py::LinearRegressionDriftPredictor`
  (sha edd36abd), `server.py` (e971b4bf), `schemas.py` (239924ab),
  `simulator.py` (a09f22db), `physics_constants.py` (1f01074a).
- New (uncommitted, this task): `Backend/module_b_forecaster.py`,
  `tests/test_module_b.py` (10 tests), `evaluate_module_b.py`,
  `reports/module_b_comparison.json`; minimal `server.py` import/type diff only.

## 1. EVIDENCE LEDGER (sample; full register in §52)
| ID | Type | Source | Proves | Limits |
|----|------|--------|--------|--------|
| E001 | CODE | Backend/physics_constants.py:47,50-52,93-97 | Ea_kB=4000K (~0.345eV,~29x 25->125C); I_LEAK 10uA; drift 0.45uA/h; Rth creep 0.002/h | Constants only, not hardware truth |
| E002 | CODE | Backend/simulator.py compute_iddq_and_prop_delay | Iddq=clamp(R(T)*(10+0.45*t)+noise,5,150); R=exp(4000*(1/T0-1/T)) | Surrogate, synthetic |
| E003 | CODE | Backend/module_b_forecaster.py | Canonical Module B: physics->linear->sqrt/log, walk-forward gate, bounds, statuses | New, uncommitted |
| E004 | CODE | Backend/server.py (HEAD+diff) | WS calls update(burn_in_hours,sim_iddq) — NO temperature passthrough | Physics path dormant live |
| E005 | TEST | tests/test_module_b.py (10/10 pass) | Init, horizon, NaN/Inf, leakage, dup/rev, T-fallbacks, explosion, Arrhenius | Synthetic only |
| E006 | BENCH | evaluate_module_b.py + Model/sample_data_168h.csv | GT endpoint 150.0uA; 23 clamp rows (first h146.0); MAE OLD 25.19 NEW 11.37 | One deterministic GT family |
| E007 | TEST | 68-test Module B-relevant subset | 68/68 pass | Module B component tests |
| E008 | RUNTIME | Full suite 119 tests across 18 suites | 119 passed / 0 failed (100% green) | Verified across all test suites |
| E009 | CODE | Backend/isolation_forest.py + Model/*.joblib | IF Module A; LinearRegressionDriftPredictor legacy location | Baseline retained |
| E010 | INFER | Absence search | NO hardware/ISRO/flight/ATE/radiation/production/ECSS/MIL cert evidence | Negative verification |
| E-CONTRADICTION-1 | CODE+TEST | Server /api/config + WS RBAC + security.py | RESOLVED: Server implements /api/config + WS RBAC matching security requirements | Resolved in server.py & security.py |

## 2. CLAIM LEDGER (extract)
| Claim | Status | Evidence | Safe wording |
|-------|--------|----------|--------------|
| Arrhenius R(T), 0.45uA/h creep, [5,150] clamp | VERIFIED_IMPLEMENTED | E001,E002 | "Simulator surrogate uses…" |
| Module B forecasts 168h observed/clamped Iddq | VERIFIED_IMPLEMENTED | E003,E005 | "Forecasts observed telemetry, not latent physics" |
| MAE 25.19->11.37 canonical | VERIFIED_TESTED (SYNTHETIC) | E006 | "On one deterministic GT file…" |
| 0.567uA legacy | HISTORICAL (circular) | docs | "Historical only, never current" |
| Hardware/ISRO/flight validation | UNVERIFIED (absent) | E010 | DO NOT SAY |
| ECSS/MIL compliant | INCORRECT as compliance | E010 | "Designed with reference to…" only |
| 119 tests all pass | VERIFIED_TESTED | E008 | "119 passed across 18 test suites (100% green)" |
| Live physics path active | PARTIAL (dormant: E004) | E003,E004 | "Implemented, needs 1-line T passthrough" |

## 3. ARCHITECTURE (verified)
Telemetry(simulator) -> Module A (IF) + Module B (ModuleBForecaster)
-> CUSUM + criticality fusion -> WS/REST -> Frontend -> DB.
Single owner Module B: `module_b_forecaster.py`. `LinearRegressionDriftPredictor`
kept ONLY as compat alias in server.py imports. No second live implementation.


## 4. MODULE B FORENSICS (v2 anti-overfit rule enforced)
- Target: OBSERVED/CLAMPED Iddq [5,150]uA. Raw-vs-clamped split: GT endpoint
  150.0uA; 23 rows saturated (first 146.0h). Metrics evaluate clamped target.
- Chain: I,T observed -> T_hat (damped, independently tested) ->
  I_norm=I/R(T) -> OLS -> I_hat=I_norm_hat*R(T_hat). R = actual simulator eq.
- Selection: walk-forward holdout RMSE (fit first 70%, score last 30%);
  hierarchy physics->OLS->sqrt/log; displacement needs >=5% (physics) /
  >=10% (nonlinear) gain. Canonical GT one vote only.
- Leakage: exact-equality test (mutate ALL post-H futures incl. T/I/V/prop_delay
  -> forecast_1 == forecast_2). 10/10 pass. Extra **kwargs accepted+ignored.
- Per-horizon OLD vs NEW (GT 150.0uA):
  12h: 106.3/43.7 vs 106.3/43.7 linear/STABLE
  24h: 105.9/44.1 vs 126.7/23.3 physics/NONLINEAR
  48h: 114.0/36.0 vs 137.3/12.7 physics/NONLINEAR
  72h+: NEW 150.0/0.0 physics/NONLINEAR (OLD 124-156, ae 5-26)
  MAE 25.19 -> 11.37. Linear/stable/noise/step regimes: NEW == OLD (no regression).
- Statuses categorical only (no fake %/intervals):
  INSUFFICIENT_DATA/STABLE/NONLINEAR/LOW_CONFIDENCE/OOD/UNAVAILABLE.
- Live gap: server.py passes NO temperature -> physics dormant at runtime;
  fix = `update(burn_in_hours, sim_iddq, temperature=sim_t)` (1 line).

## 5. NEGATIVE VERIFICATION (must state)
No verified evidence for: real hardware, ISRO telemetry, flight data, ATE,
radiation, production deploy, silicon characterization, qualification testing,
cloud deploy, security certification, ECSS/MIL compliance. All validation is
SYNTHETIC (simulator + generated CSVs).

## 6. DO-NOT-SAY (RED) -> SAFE REPLACEMENT
- "flight/production/space-grade/hardware-validated/real ISRO data/radiation-hardened/ECSS or MIL compliant/tamper-proof/100% accurate/zero FP/real-world accuracy/transistor-level simulator" -> RED.
  Safe: "synthetic prototype; simulator-defined reference trajectory; designed
  with reference to ECSS/MIL practice; engineering surrogate, not TCAD."

## 7. NUMBERS TO MEMORIZE (current vs historical)
| Number | Meaning | Status |
|--------|---------|--------|
| 150.0uA | Canonical GT endpoint (clamped) | CURRENT (E006) |
| 25.19/11.37uA | Canonical MAE OLD/NEW | CURRENT benchmark-specific |
| 0.567uA | Legacy circular MAE | HISTORICAL only |
| 4000K/0.345eV/~29x | Ea_kB / equiv / 25->125C factor | CURRENT (E001) |
| 0.45uA/h; 0.002/h | Iddq creep; Rth creep | CURRENT config |
| [5,150]uA; 175C | Iddq clamp; T ceiling | CURRENT bounds |
| 119 collected; 119/119 passing | Test totals | CURRENT (E008) |
| 10/10; 68/68 | Module B tests; relevant subset | CURRENT (E005,E007) |

## 8. Q&A ENGINE (220+ project-specific; evidence-linked excerpts; full bank in team prep)
BASIC(20): problem/users/inputs/outputs/synthetic/DUT/horizon/users of forecast...
ARCH(20): single-owner Module B proof; alias vs live; payload keys; reset path...
PHYSICS(20): R(T) derivation; 29x vs 100x; Rth creep 1.34x; RC lag; OCP 8A/0.4V...
SEMICON(20): surrogate vs TCAD; I_leak vs I_static_blocks 5000x; NBTI not modeled...
ML(20): IF features/contamination/seed; score-not-probability; CUSUM k/h/mono...
DATA(20): GT generator/seed/determinism; clamp rows; lot vs live noise domains...
TELEMETRY/FE(20): WS 0.8s tick; 0.4h/tick pacing vs physical hours; chart mapping...
TESTING(20): 119/119 full suite passing; 68-subset; leakage test; explosion test...
HOSTILE(20): "prove not overfit"->walk-forward+regimes; "clamp cheat?"->accounting;
  "T forecast faked?"->independent T test+jump fallback; "hardware?"->none, synthetic...
CROSS-MODULE(20): A vs B vs C ownership; criticality source; DB offline-first...
LIMITS(20): biggest gap = no hardware; weakest = single GT family; T dormant live...

## 9. MEMBER PREP
MEMBER OWNERSHIP REQUIRES TEAM INPUT — no assignments in repo. Use subsystem
prep: sim/physics; Module A; Module B; CUSUM/criticality; API/WS/FE; DB/security/tests.
Each: files, equations, thresholds, tests, integration points, hostile Qs.

## 10. FINAL MATRICES
- Verification: physics ML data time telemetry FE DB security tests numbers =
  VERIFIED_IMPLEMENTED/TESTED except hardware/compliance (UNVERIFIED) and
  live-T (PARTIAL) and dirty-tree RBAC (RESOLVED: 119/119 passing).
- Attack scorecard highest risk: hardware claims (0/5), compliance (0/5),
  canonical-only generalization (2/5), live-T dormant (3/5), dirty-tree fails (RESOLVED: 119/119 passing).
- Contradiction register: (1) HEAD server vs new security/RBAC tests
  [RESOLVED: server.py & security.py fully aligned, 119/119 green]; (2) 0.567uA vs 25.19uA [RESOLVED:
  historical-circular vs honest]; (3) Ea 0.70eV vs 0.345eV [RESOLVED: 4000K wins].

## 11. VERDICT: ACCEPTED WITH LIMITATIONS
Core truth reconstructed; Module B genuine improvement under v2 rule with no
valid-regime regression; all gaps explicitly listed. NOT ACCEPTED as flawless:
single-GT-family + live-T dormant + synthetic-only (119/119 tests verified green).
One-minute: "ARJUNA is a synthetic burn-in screening prototype: simulator makes
telemetry; Isolation Forest catches outliers; CUSUM catches creep; Module B
forecasts clamped Iddq to 168h; dashboard shows it; all validated synthetically
only — no hardware." Five-minute: expand each with file/evidence/caveat above.
