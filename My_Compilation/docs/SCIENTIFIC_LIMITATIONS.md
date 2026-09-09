# Project ARJUNA — Scientific Limitations Register (Authoritative)

**Status**: SINGLE AUTHORITATIVE DOCUMENT for all scientific/modeling limitations.
Every claim in the README, MASTER_MANUAL, RTM, and the presentation must be
consistent with this register. Last synchronized: 2026-09-09.

Classification vocabulary (use these exact labels):
`IMPLEMENTED` / `VERIFIED` / `BENCHMARKED` / `SIMULATED` / `ASSUMED` /
`APPROXIMATED` / `EMPIRICAL` / `DEMONSTRATION MODEL` / `PLANNED` /
`FUTURE HARDWARE VALIDATION`.

---

## SL-1 — Simulation-only physics (blanket)

| | |
|---|---|
| Classification | SIMULATED |
| Statement | All telemetry is produced by `Backend/simulator.py` (a software physics surrogate). No hardware, ATE, or real component data was used. |
| Consequence | No claim of hardware validation, ISRO/ECSS qualification, flight qualification, or production readiness is supportable. |
| Evidence | `ComponentSimulator` docstring ("Prototype / simulation-only"); RTM rows marked `AUTOMATED TESTS PASS (local/synthetic)`. |

## SL-2 — Thermal model is a bulk-package approximation

| | |
|---|---|
| Classification | APPROXIMATED |
| Statement | One lumped RC node (`dT/dt = (P − (T−T_amb)/R_th)/C_th`, R_th = 16.667 °C/W, C_th = 1.5 J/°C) models the **average package temperature**. There is NO junction/hotspot model, no spatial gradient, and no separate junction-to-case vs case-to-ambient resistance. |
| Consequence | After a short, the modeled package *cools* because OCP foldback collapses delivered power (6 W → ~3.3 W, verified live). A real die could still develop localized hotspots. Do not present post-short temperature as junction temperature. |
| Verified behavior | Steady-state residual vs analytical `T_ss = T_amb + P·R_th`: mean 0.07 °C over 30 independent 600-step runs (runtime verification, 2026-09-09). |

## SL-3 — Degradation model is a linear engineering surrogate

| | |
|---|---|
| Classification | DEMONSTRATION MODEL / ASSUMED |
| Statement | Default drift: `R_th,eff = R_th · (1 + 0.002 · burn_in_h)` and `Iddq creep = (10 + 0.45·h) µA · Arrhenius(T)`. Both are hours-based linear placeholders, NOT validated semiconductor aging laws. Real mechanisms (NBTI, EM, TDDB) follow sub-linear power-law kinetics (t^n, n ≈ 0.25–0.5) — deliberately NOT implemented in the default model. |
| Parameters | `R_TH_DRIFT_RATE_PER_H = 0.002`, `IDDQ_DRIFT_RATE_UA_PER_H = 0.45` — engineering assumptions chosen so the 168 h trajectory stays survivable (< 175 °C ceiling). Not empirically calibrated. |
| Evidence | Comment block in `simulator.py::step`; constants in `Backend/physics_constants.py`; OOD suite quantifies Module B behavior when linearity is violated (`tests/test_ood.py`). |

## SL-4 — Arrhenius degradation candidate (disabled) reuses leakage Ea

| | |
|---|---|
| Classification | ASSUMED / PLANNED |
| Statement | The candidate model (`DEGRADATION_MODEL = "accumulated_arrhenius"`) uses `dD/dt = A₀·exp(−Ea,kB/T_K)` with `DEGRAD_ARRHENIUS_EA_KB = Ea_kB_KELVIN` (4000 K). **The degradation activation energy is ASSUMED equal to the leakage activation energy — no empirical basis.** |
| Calibration | `A₀ = 1.286e-2 s⁻¹` is endpoint-calibrated only: reproduces the linear model's D(168 h) = 1.336 at constant 125 °C. Temperature feedback means trajectories diverge above 125 °C. |
| Status | DISABLED by default; requires full downstream re-validation before becoming default (`physics_constants.py` caution block). Judge answer: "we implemented the candidate and gated it off; the linear surrogate remains default pending calibration data." |

## SL-5 — Verified Arrhenius leakage vs unverified degradation kinetics

| | |
|---|---|
| Classification | VERIFIED (leakage) / NOT VERIFIED (degradation kinetics) |
| Statement | The leakage Arrhenius relation is VERIFIED: Ea/kB = 4000 K (≈0.345 eV), measured 25→125 °C acceleration = 29.1× (runtime check 2026-09-09). This verification covers ONLY the leakage equation. It does NOT validate the degradation trajectory, its coefficient, or its (assumed) activation energy. |
| Judge-facing rule | Never let a correct leakage curve be presented as evidence that the aging model is physically correct. |

## SL-6 — Short-mode Iddq signature is empirical

| | |
|---|---|
| Classification | EMPIRICAL (synthetic) / DEMONSTRATION MODEL |
| Statement | In `electrical_short` mode, Iddq ~ U(85, 130) µA and prop-delay ~ U(9, 11) ns. These are documented empirical fault signatures (audit M-17), NOT physics-derived and NOT from hardware measurement. |
| Evidence | `simulator.py::compute_iddq_and_prop_delay`, short-mode branch. |

## SL-7 — Two noise domains (intentional, documented)

| | |
|---|---|
| Classification | DEMONSTRATION MODEL |
| Statement | Training CSVs carry lot-domain noise (σ ≈ 1.15–1.17 µA die spread); the live server applies sensor noise (σ ≈ 0.15 µA Iddq, 0.15 °C T, 0.01 V V, 0.005 A I) plus a nominal clamp [9.0, 11.5] µA. The clamp is a pre-screened healthy-channel bound; CUSUM compensates with per-DUT auto-baseline. |
| Evidence | `physics_constants.py` header (M-09/M-10); `evaluate_model.benchmark_unclamped_nominal` measures unclamped FP behavior rather than hiding it. |

## SL-8 — Module B scope of validity

| | |
|---|---|
| Classification | BENCHMARKED (in-domain) / SIMULATED |
| Defensible claim | "Module B accurately forecasts **this simulator's modeled degradation trajectory** under the tested conditions" — honest non-circular 168 h MAE 25.06 µA (RMSE 30.14 µA); circular legacy MAE 0.567 µA retained for comparison only, labeled `[circular]`. |
| Unsupported claim | "Module B accurately predicts actual spacecraft semiconductor degradation." Not supported — the trajectory is synthetic and OOD performance is quantified but imperfect. |
| Evidence | `reports/eval_final_output.txt` (Phase 2a HONEST vs 2b LEGACY), `tests/test_ood.py`. |

## SL-9 — Single shared chamber (multi-client)

| | |
|---|---|
| Classification | ACCEPTABLE INTENTIONAL BEHAVIOR (verified) |
| Statement | All connected clients observe ONE virtual DUT. WS- and REST-originated scenario/reset controls propagate globally via the generation counter (fixed 2026-09-09; previously WS controls were per-connection). Per-session isolation is a documented future enhancement. |
| Evidence | `tests/test_multi_client_interference.py` (3 tests); `server.py` header comment. |

---

## Approved demo language

✅ "Physics-grounded, real-time hybrid statistical/ML burn-in screening prototype operating within a defined simulation/benchmark domain."
✅ "Calibrated to a 125 °C steady-state design point (MIL-STD-883-aligned scenario, not a certified standard)."
✅ "Validated within simulation; hardware validation is future work."

❌ "Simulates real semiconductor degradation" → say "applies a documented degradation surrogate".
❌ "Hardware-validated / flight-qualified / ECSS-certified / production-ready".
❌ "Measures junction temperature" → say "models average package temperature".
❌ "Accurately predicts real semiconductor aging" (Module B) → use SL-8 wording.

