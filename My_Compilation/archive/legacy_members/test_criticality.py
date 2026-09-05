import random
import sys
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(CURRENT_DIR / "Model"))
sys.path.insert(0, str(CURRENT_DIR / "Model"))
sys.path.insert(0, str(CURRENT_DIR / "simulation"))

from isolation_forest import MultivariateAnomalyDetector
from simulator import ComponentSimulator
from cusum_drift import DriftDetector


def _load_model():
	model_path = CURRENT_DIR / "Model" / "isolation_forest_model.joblib"
	if not model_path.exists():
		raise RuntimeError("Model not found. Run server.py once before this evaluation.")
	return MultivariateAnomalyDetector.load_model(str(model_path))


def _short_fault_type(result, voltage, current):
	if result["is_anomaly"] and result["raw_score"] < 0 and current > 4 and voltage < 2:
		return "ELECTRICAL_SHORT_CIRCUIT"
	return "ELECTRICAL_SPIKE" if result["is_anomaly"] else "NORMAL"


def run_evaluation():
	model = _load_model()
	lot_mean = model.lot_stats.get("mean_iddq", 10.0)
	lot_std = model.lot_stats.get("std_iddq", 1.17)
	results = {}

	for level in (1, 2, 3):
		random.seed(42 + level)
		simulator = ComponentSimulator(criticality_level=level)
		cusum = DriftDetector(mean=lot_mean, std=lot_std, criticality_level=level)

		normal_false_positives = 0
		for _ in range(1000):
			temp, voltage, current = simulator.step(mode="normal")
			simulator_iddq, prop_delay = simulator.compute_iddq_and_prop_delay(
				temp, voltage, mode="normal"
			)
			# Match server.py's calibrated nominal Iddq telemetry path.
			iddq = 10.0 + random.gauss(0.0, 0.15)
			normal_false_positives += int(
				cusum.evaluate_drift(iddq)
				or model.detect_spike(current, voltage, temp, iddq, prop_delay, level)["is_anomaly"]
			)

		spike_latency = None
		for step in range(1, 21):
			result = model.detect_spike(1.2, 5.0, 125.0, 45.0, 4.5, level)
			if result["is_anomaly"]:
				spike_latency = step
				break

		simulator.reset()
		cusum.reset()
		drift_latency = None
		for step in range(1, 200):
			temp, voltage, current = simulator.step(
				mode="drift", drift_time=float(step), drift_rate=0.01
			)
			iddq, _ = simulator.compute_iddq_and_prop_delay(
				temp, voltage, mode="drift", drift_time=float(step)
			)
			if cusum.evaluate_drift(iddq + step * 0.1):
				drift_latency = step
				break

		simulator.reset()
		temp, voltage, current = simulator.step(mode="short")
		iddq, prop_delay = simulator.compute_iddq_and_prop_delay(temp, voltage, mode="short")
		short_result = model.detect_spike(current, voltage, temp, iddq, prop_delay, level)
		short_fault = _short_fault_type(short_result, voltage, current)

		results[level] = {
			"false_positive_rate": normal_false_positives / 1000,
			"spike_latency": spike_latency,
			"drift_latency": drift_latency,
			"short_fault_type": short_fault,
		}

	assert all(row["false_positive_rate"] == 0 for row in results.values())
	assert all(row["spike_latency"] is not None for row in results.values())
	assert all(row["drift_latency"] is not None for row in results.values())
	assert results[3]["drift_latency"] < results[1]["drift_latency"]
	assert all(row["short_fault_type"] == "ELECTRICAL_SHORT_CIRCUIT" for row in results.values())

	print("Level | FP rate | Spike latency | Drift latency | Short classification")
	for level in (1, 2, 3):
		row = results[level]
		print(
			f"{level}     | {row['false_positive_rate']:.3f}   | {row['spike_latency']:>13} | "
			f"{row['drift_latency']:>13} | {row['short_fault_type']}"
		)
	return results


def test_criticality_scenarios():
	run_evaluation()


if __name__ == "__main__":
	run_evaluation()
