"""Module B tests: functional, numerical, nonlinear, robustness, leakage, regimes."""

import math
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "Backend"))
from Backend.module_b_forecaster import LinearBaselineForecaster, ModuleBForecaster, arrhenius_ratio


def feed(f, pts):
    r = None
    for t, y, tp in pts:
        r = f.update(t, y, temperature=tp)
    return r


def test_init_insufficient():
    f = ModuleBForecaster()
    r = f.update(0.0, 10.0, 125.0)
    assert r["n_observations"] == 1 and r["forecast_status"] == "INSUFFICIENT_DATA"


def test_horizon_168_linear():
    f = ModuleBForecaster()
    for t in range(0, 25):
        f.update(float(t), 10 + 0.45 * t, 125.0)
    r = f.update(25.0, 10 + 0.45 * 25, 125.0)
    assert abs(r["forecast_168h_uA"] - 85.6) < 3.0


def test_no_nan_inf_outputs():
    f = ModuleBForecaster()
    for bad in (float("nan"), float("inf"), float("-inf")):
        r = f.update(bad, 10.0, 125.0)
        assert math.isfinite(r["forecast_168h_uA"])
        r = f.update(1.0, bad, 125.0)
        assert math.isfinite(r["forecast_168h_uA"])


def test_no_leakage():
    f1 = ModuleBForecaster()
    f2 = ModuleBForecaster()
    obs = [(float(t), 10 + 0.3 * t, 125.0 + 0.1 * t) for t in range(0, 48)]
    for t, y, tp in obs:
        f1.update(t, y, temperature=tp)
        f2.update(t, y, temperature=tp)
    r1 = f1.update(48.0, 10 + 0.3 * 48, 129.0)
    r2 = f2.update(48.0, 10 + 0.3 * 48, 129.0)
    assert r1["forecast_168h_uA"] == r2["forecast_168h_uA"]
    f3 = ModuleBForecaster()
    for t, y, tp in obs:
        f3.update(t, y, temperature=tp)
    r3 = f3.update(48.0, 10 + 0.3 * 48, 200.0)
    assert isinstance(r3, dict) and math.isfinite(r3["forecast_168h_uA"])


def test_duplicate_reversed():
    f = ModuleBForecaster()
    for t in range(0, 12):
        f.update(float(t), 10 + 0.2 * t, 125.0)
    r = f.update(5.0, 12.0, 125.0)
    assert r["forecast_status"] in ("LOW_CONFIDENCE", "NONLINEAR_REGIME", "STABLE_FORECAST", "OOD")
    assert math.isfinite(r["forecast_168h_uA"])


def test_missing_const_temp():
    f = ModuleBForecaster()
    for t in range(0, 15):
        f.update(float(t), 10 + 0.2 * t, None)
    r = f.update(15.0, 13.0, None)
    assert math.isfinite(r["forecast_168h_uA"])
    g = ModuleBForecaster()
    for t in range(0, 15):
        g.update(float(t), 10 + 0.2 * t, 125.0)
    r2 = g.update(15.0, 13.0, 125.0)
    assert math.isfinite(r2["forecast_168h_uA"])


def test_temp_jump_safe():
    f = ModuleBForecaster()
    for t in range(0, 15):
        f.update(float(t), 10 + 0.2 * t, 125.0)
    r = f.update(15.0, 13.0, 160.0)
    assert math.isfinite(r["forecast_168h_uA"]) and f.last_method in (
        "linear",
        "physics",
        "sqrt",
        "log",
        "linear_fallback",
    )


def test_explosion_rejected():
    f = ModuleBForecaster()
    for t in range(0, 12):
        f.update(float(t), 10.0, 125.0)
    r = f.update(12.0, 500.0, 125.0)
    assert math.isfinite(r["forecast_168h_uA"]) and r["forecast_168h_uA"] <= 150.0


def test_arrhenius_chain():
    assert arrhenius_ratio(125.0) == 1.0
    assert arrhenius_ratio(150.0) > arrhenius_ratio(125.0) > arrhenius_ratio(25.0)
    f = ModuleBForecaster()
    for t in range(0, 15):
        T = 125.0 + 0.2 * t
        y = (10 + 0.45 * t) * arrhenius_ratio(T)
        f.update(float(t), y, T)
    th, ok = f.estimate_future_temp(168.0)
    assert math.isfinite(th) and isinstance(ok, bool)


def test_baseline_preserved():
    b = LinearBaselineForecaster()
    for t in range(0, 10):
        b.update(float(t), 10 + 0.45 * t)
    assert b.update(10.0, 14.5)["n_observations"] == 11
