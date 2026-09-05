"""
tests/test_unit.py — Project ARJUNA (SIH 26170)
Unit tests for core physical formulas, Arrhenius leakage acceleration,
12-bit ADC quantization, CUSUM accumulation, and OLS drift projection.
Conforms to ECSS-Q-ST-60-02C Space Product Assurance.
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
    """Validates exponential Arrhenius leakage growth between 25°C and 125°C."""
    T0_K = 273.15 + 25.0  # 298.15 K
    T_hot_K = 273.15 + 125.0  # 398.15 K
    kB_eV = 8.617333e-5
    Ea = 0.70  # Silicon junction activation energy (eV)

    exponent = (Ea / kB_eV) * (1.0 / T0_K - 1.0 / T_hot_K)
    theoretical_acceleration_factor = math.exp(exponent)

    assert (
        theoretical_acceleration_factor > 100.0
    ), "HTOL 125°C must significantly accelerate silicon leakage"

    sim = ComponentSimulator(criticality_level=2)
    telemetry_nominal = sim.step_telemetry(scenario="nominal")

    # Standby current at 125°C nominal burn-in must remain well within datasheet limit (50 µA)
    assert 5.0 <= telemetry_nominal["iddq_uA"] <= 20.0
    assert 120.0 <= telemetry_nominal["temperature"] <= 130.0


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
