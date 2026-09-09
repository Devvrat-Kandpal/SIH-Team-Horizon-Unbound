"""
tests/test_unit.py — Project ARJUNA (SIH 26170)
Unit tests for core physical formulas, Arrhenius leakage acceleration,
12-bit ADC quantization, CUSUM accumulation, and OLS drift projection.
Designed with reference to ECSS-Q-ST-60-02C-era space product assurance concepts (prototype).
"""
import math
import sys
from pathlib import Path

import pytest

# Ensure Backend is accessible
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "Backend"))

from Backend.cusum_drift import DriftDetector
from Backend.isolation_forest import LinearRegressionDriftPredictor
from Backend.simulator import ComponentSimulator


def test_arrhenius_leakage_acceleration():
    """M-07 fix: test the ACTUAL implementation (_arrhenius_leakage) and the
    REAL activation energy constant (Ea_kB_KELVIN = 4000 K ~ 0.345 eV), not a
    re-derived equation with different constants."""
    from Backend.physics_constants import I_LEAK_BASE_A, Ea_kB_KELVIN

    sim = ComponentSimulator(criticality_level=2)

    T_ref_C = 25.0
    T_hot_C = 125.0
    leak_ref = sim._arrhenius_leakage(T_ref_C)
    leak_hot = sim._arrhenius_leakage(T_hot_C)

    # Direction invariant: higher temperature -> strictly higher leakage
    assert leak_hot > leak_ref > 0.0

    # Magnitude invariant: matches the implemented Ea constant (~29x for 4000 K)
    t0_k = T_ref_C + 273.15
    t_hot_k = T_hot_C + 273.15
    expected_ratio = math.exp(Ea_kB_KELVIN * (1.0 / t0_k - 1.0 / t_hot_k))
    assert math.isclose(
        leak_hot / leak_ref, expected_ratio, rel_tol=1e-9
    ), "Leakage ratio must match exp(Ea_kB * (1/T0 - 1/T)) with the code's Ea"

    # Implemented Ea corresponds to ~0.345 eV (4000 K), NOT the outdated 0.70 eV
    assert math.isclose(Ea_kB_KELVIN * 8.617333e-5, 0.345, rel_tol=0.01)
    # Documented acceleration between 25C and 125C is ~29x, NOT ">100x"
    assert 20.0 < expected_ratio < 40.0

    # Base magnitude (M-08): 10 uA at the 125 C reference temperature; the
    # 25 C value must be the Arrhenius-scaled base (~0.34 uA with Ea_kB=4000 K)
    leak_125 = sim._arrhenius_leakage(125.0)
    assert math.isclose(leak_125 * 1e6, I_LEAK_BASE_A * 1e6, rel_tol=0.5)
    assert math.isclose(
        leak_ref * 1e6, I_LEAK_BASE_A * 1e6 / expected_ratio, rel_tol=0.1
    )

    # Standby current at 125 C nominal burn-in stays well within datasheet limit
    telemetry_nominal = sim.step_telemetry(scenario="nominal")
    assert 5.0 <= telemetry_nominal["iddq_uA"] <= 20.0
    assert 120.0 <= telemetry_nominal["temperature"] <= 130.0


def test_timestep_convergence_destruction_time():
    """M-15: destruction-time event must converge as dt decreases."""
    sim_hi = ComponentSimulator(criticality_level=2)
    sim_lo = ComponentSimulator(criticality_level=2)

    def time_to_destroy(sim, dt):
        t_phys = 0.0
        # Cap at 400 simulated hours to bound the search
        max_steps = int(400 * 3600 / dt)
        for _ in range(max_steps):
            sim.step(dt=dt, mode="drift", drift_time=t_phys, drift_rate=0.005)
            t_phys += dt
            if sim.destroyed:
                return t_phys / 3600.0
        return None

    t_hi = time_to_destroy(sim_hi, dt=1.0)
    t_lo = time_to_destroy(sim_lo, dt=0.5)

    assert t_hi is not None, "DUT must destroy under drift at dt=1.0"
    assert t_lo is not None, "DUT must destroy under drift at dt=0.5"
    # Convergence: halving dt must change the destruction hour by < 15%
    assert abs(t_lo - t_hi) / t_hi < 0.15, (
        f"Destruction time not converged: dt=1.0 -> {t_hi:.2f} h, dt=0.5 -> {t_lo:.2f} h"
    )


def test_adc_quantization_resolution():
    """Validates 12-bit ADC step-size quantization across sensor ranges."""
    sim = ComponentSimulator(criticality_level=2)

    v_lsb = 10.0 / 4095.0
    t_lsb = 175.0 / 4095.0
    i_lsb = 15.0 / 4095.0

    t_raw = 125.123456
    t_quant = sim.quantize(t_raw, 175.0)
    assert abs(t_quant - t_raw) <= t_lsb

    v_raw = 5.012345
    v_quant = sim.quantize(v_raw, 10.0)
    assert abs(v_quant - v_raw) <= v_lsb

    i_raw = 1.234567
    i_quant = sim.quantize(i_raw, 15.0)
    assert abs(i_quant - i_raw) <= i_lsb


def test_cusum_mathematical_accumulation():
    """Validates Tabular CUSUM S+ formula: S_n^+ = max(0, S_{n-1}^+ + X_n - (mu + k))."""
    detector = DriftDetector(
        metric_name="Iddq", mean=10.0, std=1.0, criticality_level=2
    )

    # Under Level 2: k = 0.5, h = 5.0
    assert detector.allowance == 0.5
    assert detector.threshold == 5.0

    # 1. Readings below mu + k (<= 10.5) must not accumulate (S+ = 0)
    flag, s_plus = detector.update(10.2)
    assert s_plus == 0.0
    assert not flag

    # 2. Reading with delta > k accumulates: 11.5 - (10.0 + 0.5) = 1.0
    flag, s_plus = detector.update(11.5)
    assert pytest.approx(s_plus, 0.001) == 1.0
    assert not flag

    # 3. Second reading of 12.0: 1.0 + (12.0 - 10.5) = 2.5
    flag, s_plus = detector.update(12.0)
    assert pytest.approx(s_plus, 0.001) == 2.5
    assert not flag

    # 4. Sustained shift pushes s_plus past h (5.0) -> fires alarm
    for _ in range(5):
        flag, s_plus = detector.update(13.0)
    assert flag is True
    assert s_plus >= 5.0

    # 5. Reset clears register
    detector.reset()
    assert detector.s_plus == 0.0


def test_ols_drift_predictor_projection():
    """Validates Ordinary Least Squares linear extrapolation to 168h endpoint."""
    predictor = LinearRegressionDriftPredictor(
        lot_mean_iddq=10.0,
        lot_std_iddq=1.17,
        datasheet_limit_ua=50.0,
        dynamic_sigma=3.0,
    )

    # Nominal slow drift: 0h = 10.0 uA, 24h = 10.2 uA -> slope = 0.2 / 24 = 0.00833 uA/h
    # Forecast at 168h = 10.0 + 0.00833 * 168 = 11.4 uA (well within dynamic limit of 13.51 uA)
    res = predictor.predict_168h(value_0h=10.0, value_24h=10.2, actual_168h=11.4)

    assert pytest.approx(res["projected_168h_iddq_ua"], 0.05) == 11.4
    assert pytest.approx(res["forecast_mae_ua"], 0.05) == 0.0
    assert res["early_reject"] is False

    # Steep drift: 0h = 10.0 uA, 24h = 20.0 uA -> slope = 10.0 / 24 = 0.4167 uA/h
    # Forecast at 168h = 10.0 + 0.4167 * 168 = 80.0 uA -> exceeds 50 uA limit
    res_steep = predictor.predict_168h(value_0h=10.0, value_24h=20.0, actual_168h=78.5)
    assert res_steep["projected_168h_iddq_ua"] > 50.0
    assert res_steep["early_reject"] is True
    assert res_steep["lead_time_saved_hours"] == 144.0


def test_short_circuit_ocp_foldback():
    """Validates simulator Over-Current Protection (OCP) foldback behavior."""
    sim = ComponentSimulator(criticality_level=2)

    # Step short circuit scenario
    telemetry = sim.step_telemetry(scenario="electrical_short")

    # In short circuit, voltage collapses and current limits to ~8.0A OCP
    assert telemetry["voltage"] < 2.0
    assert telemetry["current"] > 5.0
    assert telemetry["status"] in ("ANOMALY", "WARNING")
