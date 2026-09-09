"""Module B OLD-vs-NEW comparison (v2 hard rule).

Run from repo root:  python My_Compilation/evaluate_module_b.py
Writes: My_Compilation/reports/module_b_comparison.json
"""
import json
import math
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / "Backend"))

from Backend.module_b_forecaster import LinearBaselineForecaster, ModuleBForecaster  # noqa: E402
from Backend.simulator import write_ground_truth_168h_csv  # noqa: E402

GT = BASE / "Model" / "sample_data_168h.csv"
if not GT.exists():
    write_ground_truth_168h_csv(str(GT))

import pandas as pd  # noqa: E402

df = pd.read_csv(GT)
true_end = float(df["iddq"].iloc[-1])
HORIZ = [12, 24, 48, 72, 96, 120, 144]


def run(cls) -> dict:
    from typing import Any

    rows: dict = {}
    for h in HORIZ:
        sub = df[df["burn_in_hours"] <= h + 1e-9]
        f = cls()
        r: dict[str, Any] | None = None
        for _, row in sub.iterrows():
            kw = {"temperature": float(row["temperature"])} if cls is ModuleBForecaster else {}
            r = f.update(float(row["burn_in_hours"]), float(row["iddq"]), **kw)
        assert r is not None, f"no observations at or before horizon {h}h"
        fc = float(r["forecast_168h_uA"])
        err = fc - true_end
        rows[h] = {
            "fc": round(fc, 2),
            "ae": round(abs(err), 2),
            "signed_err": round(err, 2),
            "method": r.get("forecast_method", "baseline"),
            "status": r.get("forecast_status", r.get("drift_status")),
            "invalid": 0 if math.isfinite(fc) else 1,
            "explosive": 1 if (not math.isfinite(fc) or abs(fc) > 1e4) else 0,
            "fallback": 1 if r.get("fallback_used") else 0,
        }
    return rows


t0 = time.perf_counter()
old = run(LinearBaselineForecaster)
t1 = time.perf_counter()
new = run(ModuleBForecaster)
t2 = time.perf_counter()
mae_old = sum(v["ae"] for v in old.values()) / len(old)
mae_new = sum(v["ae"] for v in new.values()) / len(new)
print(f"GT endpoint (observed/clamped target): {true_end:.1f} uA | file: {GT.name}")
nclamp = int((df["iddq"] >= 149.99).sum())
first = float(df[df["iddq"] >= 149.99]["burn_in_hours"].iloc[0]) if nclamp else -1.0
print(f"clamp rows >=149.99: {nclamp} (first h {first:.1f})")
print("H | OLD fc/ae | NEW fc/ae/method/status")
for h in HORIZ:
    print(
        f"{h} | {old[h]['fc']:.1f}/{old[h]['ae']:.1f} | "
        f"{new[h]['fc']:.1f}/{new[h]['ae']:.1f}/{new[h]['method']}/{new[h]['status']}"
    )
print(f"MAE OLD {mae_old:.2f} NEW {mae_new:.2f} | t_old {t1 - t0:.3f}s t_new {t2 - t1:.3f}s")
print("env: Python 3.14.4 numpy 2.4.6 pandas 2.3.3 sklearn 1.9.0 scipy 1.17.0 | GT deterministic")
out = {"true_endpoint": true_end, "clamp_rows": nclamp, "old": old, "new": new}
Path(BASE / "reports" / "module_b_comparison.json").write_text(json.dumps(out, indent=2))
print("saved reports/module_b_comparison.json")
