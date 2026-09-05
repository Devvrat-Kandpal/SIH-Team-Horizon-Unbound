"""
tests/test_simulator_columns.py — Project ARJUNA (SIH 26170)

Guards the fragile wiring between simulator.py telemetry columns and
isolation_forest.py train(): the ML training MUST consume the real,
physically-derived Iddq channel rather than silently falling back to a
constant 10.0. Also verifies the thin compatibility wrappers on the
simulator exist and return/reset correctly.
"""

import math
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "Backend"))

from Backend import simulator as sim_mod
from Backend.isolation_forest import MultivariateAnomalyDetector


@pytest.fixture(scope="module")
def sample_df():
    csv_path = ROOT_DIR / "Model" / "sample_data.csv"
    if not csv_path.exists():
        pytest.skip("sample_data.csv not present")
    return pd.read_csv(csv_path)


def test_training_reads_real_iddq_not_constant(sample_df):
    """The canonical simulator column is 'iddq'; training must consume its
    real variance. If it fell back to a constant 10.0, std_iddq would be
    artificial and mean_iddq exactly 10.0."""
    assert "iddq" in sample_df.columns, "simulator must emit the iddq column"
    model = MultivariateAnomalyDetector()
    stats = model.train(sample_df)
    assert len(sample_df) > 0
    # Real Iddq spread — not a constant-10.0 fallback
    assert stats["std_iddq"] > 0.05, f"Iddq std too small: {stats['std_iddq']}"
    assert 5.0 < stats["mean_iddq"] < 15.0, f"Iddq mean implausible: {stats['mean_iddq']}"


def test_training_accepts_iddq_ua_alias(sample_df):
    """Robustness: if a dataset names the channel iddq_uA, training must still
    consume its real values instead of the silent 10.0 constant fallback."""
    renamed = sample_df.rename(columns={"iddq": "iddq_uA"})
    model = MultivariateAnomalyDetector()
    stats = model.train(renamed)
    assert stats["std_iddq"] > 0.05, "iddq_uA alias must be consumed, not the constant"
    assert math.isclose(stats["mean_iddq"], float(sample_df["iddq"].mean()), rel_tol=0.5)


def test_simulator_wrapper_functions_exist_and_work():
    """Thin compatibility wrappers must be importable and delegate correctly."""
    assert hasattr(sim_mod, "get_next_telemetry_frame")
    assert hasattr(sim_mod, "reset_simulator")
    sim_mod.reset_simulator()
    frame = sim_mod.get_next_telemetry_frame(mode="normal", seconds_elapsed=0)
    for key in ("voltage", "current", "temperature", "iddq", "prop_delay"):
        assert key in frame, f"missing {key} in wrapper frame"
    assert math.isfinite(float(frame["temperature"]))


# ============================================================================
# Simulator interface contract (anti-divergence guard)
# ============================================================================
# A teammate's local simulator rewrite diverged from this authoritative file
# (4-tuple step(), iddq_uA column, I_leak_base=0.05 reintroducing the 5000x
# leakage bug, INVERTED criticality convention). These tests lock the public
# contract so any divergent replacement fails CI loudly instead of silently
# breaking server.py, evaluate_model.py, and the whole test suite.

def test_simulator_interface_contract():
    """Locks the public API the rest of the system depends on."""
    sim = sim_mod.ComponentSimulator(criticality_level=2)
    sim.reset()

    # step() returns the 3-tuple (temperature, voltage, current) — the team's
    # divergent rewrite returned a 4-tuple, which breaks every caller.
    result = sim.step(dt=1.0, mode="normal")
    assert isinstance(result, tuple) and len(result) == 3, (
        "ComponentSimulator.step() must return a 3-tuple (t, v, i)"
    )

    # compute_iddq_and_prop_delay exists and returns a 2-tuple.
    t, v, i = result
    iq, pd_val = sim.compute_iddq_and_prop_delay(t, v, mode="normal")
    assert math.isfinite(iq) and math.isfinite(pd_val)

    # Public quantize + export_to_sqlite exist (tests/server reference them).
    assert hasattr(sim_mod, "quantize") or hasattr(sim, "quantize"), (
        "quantize() must remain available for ADC-quantization tests"
    )
    assert hasattr(sim_mod, "export_to_sqlite"), (
        "export_to_sqlite must remain available (used by the CLI/DB path)"
    )

    # Physics constants locked to the corrected values:
    #   I_leak_base = 10e-6 A (true DUT leakage — NOT the 0.05 A mis-scale bug)
    #   R_th = 16.667 °C/W (calibrated for 125 °C steady state)
    assert sim.I_leak_base == 10e-6, (
        f"I_leak_base must be 10e-6 A (true DUT leakage), got {sim.I_leak_base} — "
        "0.05 A is the known 5000x mis-scale bug"
    )
    assert abs(sim.R_th - 16.667) < 0.01, f"R_th must stay 16.667, got {sim.R_th}"


def test_simulator_criticality_convention_not_inverted():
    """The project-wide convention is Level 1 = LOW criticality, Level 3 =
    MISSION-CRITICAL (matching criticality_config, server, and the frontend).
    A divergent simulator docstring/code inverted this — lock the direction."""
    from Backend.criticality_config import CRITICALITY_CONFIG, get_config
    l1, l3 = get_config(1), get_config(3)
    # Mission-critical (L3) must have the TIGHTEST CUSUM threshold.
    assert l3["cusum_threshold"] < l1["cusum_threshold"], (
        "Level 3 (mission-critical) must have a tighter CUSUM threshold than Level 1"
    )
    assert l3["fault_label"] == "MISSION-CRITICAL"
    assert l1["fault_label"] == "LOW-CRITICALITY"
    # And the simulator must accept all three levels without reordering them.
    for lvl in (1, 2, 3):
        s = sim_mod.ComponentSimulator(criticality_level=lvl)
        assert s.criticality_level == lvl


def test_simulator_emits_iddq_column_canonical_name(sample_df):
    """The canonical generated-dataset column is 'iddq' (not 'iddq_uA').
    generate_dataset writes it; train() and tests consume it."""
    assert "iddq" in list(sample_df.columns)
    assert "prop_delay" in list(sample_df.columns), (
        "prop_delay is an inert modeled feature but must stay in the dataset"
    )