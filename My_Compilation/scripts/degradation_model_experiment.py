"""scripts/degradation_model_experiment.py — Project ARJUNA (SIH 26170)

Phase 3.3 bounded experiment (master-prompt §24): compare the DEFAULT linear
degradation surrogate (Model A) against the DISABLED accumulated-Arrhenius
candidate (Model B) over a 168 h drift trajectory.

MEASURE-ONLY. The model switch is patched in-memory on Backend.simulator and
restored in a finally block; the on-disk default in physics_constants.py is
never modified. Outputs: reports/degradation_model_comparison.{md,json}.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import Backend.simulator as sim  # noqa: E402
from Backend.cusum_drift import DriftDetector  # noqa: E402
from Backend.module_b_forecaster import LinearBaselineForecaster  # noqa: E402
from Backend.physics_constants import (  # noqa: E402
    R_TH_C_PER_W,
    R_TH_DRIFT_RATE_PER_H,
)

CHECKPOINTS = (24, 48, 96, 168)


def run_model(model_name: str) -> dict:
    """Runs one 168 h drift trajectory under the given degradation model."""
    sim.DEGRADATION_MODEL = model_name
    component = sim.ComponentSimulator()
    cusum = DriftDetector(
        metric_name="Iddq",
        mean=10.0,
        std=1.17,
        criticality_level=2,
        auto_baseline=True,
        baseline_window=15,
    )
    forecaster = LinearBaselineForecaster()

    hourly = []  # (burn_in_h, temperature, iddq, degradation_state)
    cusum_first_alarm_h = None
    for h in range(1, 169):
        drift_time_s = h * 3600.0
        t, v, i = component.step(dt=1.0, mode="drift", drift_time=drift_time_s)
        iddq, _pd = component.compute_iddq_and_prop_delay(
            t, v, mode="drift", drift_time=drift_time_s
        )
        hourly.append((float(h), float(t), float(iddq), float(component.degradation)))

        is_drift, _score = cusum.update(iddq)
        if is_drift and cusum_first_alarm_h is None:
            cusum_first_alarm_h = h
        forecaster.update(float(h), float(iddq))

    traj = {h: (t, q, d) for h, t, q, d in hourly}
    t168, q168, _d168 = traj[168]
    checkpoints = {}
    for h in CHECKPOINTS:
        t_h, q_h, d_h = traj[h]
        if model_name == "accumulated_arrhenius":
            # Arrhenius path: r_effective = R_th * D, with D recorded in-loop at
            # this checkpoint (the linear path never touches the D variable).
            r_eff = R_TH_C_PER_W * d_h
        else:
            r_eff = R_TH_C_PER_W * (1.0 + R_TH_DRIFT_RATE_PER_H * h)
        checkpoints[h] = {
            "temperature_c": round(t_h, 2),
            "iddq_uA": round(q_h, 2),
            "rth_effective_c_per_w": round(r_eff, 4),
        }

    fc168 = forecaster.update(168.0, q168)
    return {
        "model": model_name,
        "final_degradation_state": round(float(component.degradation), 4),
        "destroyed": bool(component.destroyed),
        "checkpoints": checkpoints,
        "endpoint": {"temperature_c": round(t168, 2), "iddq_uA": round(q168, 2)},
        "cusum_first_alarm_h": cusum_first_alarm_h,
        "module_b_forecast_168h_uA": fc168["forecast_168h_uA"],
        "module_b_error_vs_true_uA": round(fc168["forecast_168h_uA"] - q168, 2),
        "module_b_hours_to_violation": fc168["hours_to_violation"],
        "module_b_r2": fc168["drift_r2"],
    }


def main() -> int:
    results = {}
    try:
        results["model_a_linear"] = run_model("linear")
        results["model_b_arrhenius"] = run_model("accumulated_arrhenius")
    finally:
        sim.DEGRADATION_MODEL = "linear"  # restore the shipped default

    a, b = results["model_a_linear"], results["model_b_arrhenius"]
    lines = [
        "# Degradation Model Comparison — Linear (A) vs Accumulated-Arrhenius (B)",
        "",
        "Phase 3.3 bounded experiment (measure-only). Model switch applied",
        "in-memory and restored; the shipped default (`linear`) is unchanged.",
        "",
        "| Metric | A: linear (DEFAULT) | B: accumulated_arrhenius (candidate) |",
        "|---|---|---|",
        f"| Final degradation state | {a['final_degradation_state']} | {b['final_degradation_state']} |",
        f"| Destroyed by 168 h | {a['destroyed']} | {b['destroyed']} |",
    ]
    for h in CHECKPOINTS:
        ca, cb = a["checkpoints"][h], b["checkpoints"][h]
        lines.append(f"| T @ {h} h [C] | {ca['temperature_c']} | {cb['temperature_c']} |")
        lines.append(f"| Iddq @ {h} h [uA] | {ca['iddq_uA']} | {cb['iddq_uA']} |")
        lines.append(
            f"| Rth_eff @ {h} h [C/W] | {ca['rth_effective_c_per_w']} | {cb['rth_effective_c_per_w']} |"
        )
    lines += [
        f"| CUSUM first alarm [h] | {a['cusum_first_alarm_h']} | {b['cusum_first_alarm_h']} |",
        f"| Module B 168h forecast [uA] | {a['module_b_forecast_168h_uA']} | {b['module_b_forecast_168h_uA']} |",
        f"| Module B error vs true endpoint [uA] | {a['module_b_error_vs_true_uA']} | {b['module_b_error_vs_true_uA']} |",
        f"| Module B hours-to-violation | {a['module_b_hours_to_violation']} | {b['module_b_hours_to_violation']} |",
        f"| Module B R^2 | {a['module_b_r2']} | {b['module_b_r2']} |",
        "",
        "## Interpretation",
        "",
        "- NOTE: Model A's 'final degradation state' shows 1.0 because the",
        "  linear path computes r_effective analytically (1 + 0.002h) and never",
        "  touches the D state variable; its effective D(168h) = 1.336 by design.",
        "- Model B is temperature-activated (positive feedback): as junction T",
        "  rises, D accelerates, so its trajectory is expected to exceed the",
        "  linear surrogate's. Any divergence quantifies the calibration risk",
        "  documented in SL-3/SL-4 of docs/SCIENTIFIC_LIMITATIONS.md.",
        "- Detection/forecast differences measure downstream sensitivity to the",
        "  degradation law — evidence for the judge question 'why linear?'.",
        "- This experiment does NOT validate either model physically",
        "  (SIMULATED / ASSUMED classification; see SCIENTIFIC_LIMITATIONS.md).",
        "",
    ]
    out_md = ROOT / "reports" / "degradation_model_comparison.md"
    out_json = ROOT / "reports" / "degradation_model_comparison.json"
    out_md.write_text("\n".join(lines), encoding="utf-8")
    out_json.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"WROTE {out_md.name} and {out_json.name}")
    print(f"Model A endpoint: T={a['endpoint']['temperature_c']} C, "
          f"Iddq={a['endpoint']['iddq_uA']} uA, D={a['final_degradation_state']}")
    print(f"Model B endpoint: T={b['endpoint']['temperature_c']} C, "
          f"Iddq={b['endpoint']['iddq_uA']} uA, D={b['final_degradation_state']}, "
          f"destroyed={b['destroyed']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
