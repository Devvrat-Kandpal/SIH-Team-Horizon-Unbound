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