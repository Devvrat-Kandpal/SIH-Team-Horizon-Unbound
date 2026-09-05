import os
import pytest
import numpy as np
import random
from isolation_forest import MultivariateAnomalyDetector, LinearRegressionDriftPredictor

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SAMPLE_CSV = os.path.join(BASE_DIR, "sample_data.csv")
MODEL_PATH = os.path.join(BASE_DIR, "isolation_forest_model.joblib")

@pytest.fixture(scope="module")
def trained_detector():
    if not os.path.exists(SAMPLE_CSV):
        import generate_dummy_data
        generate_dummy_data.generate_healthy_data(SAMPLE_CSV, rows=5000)
    
    detector = MultivariateAnomalyDetector(contamination=0.0001, random_state=42)
    detector.train(SAMPLE_CSV)
    return detector

def test_training_and_serialization(trained_detector, tmp_path):
    temp_model_file = str(tmp_path / "temp_model.joblib")
    trained_detector.save_model(temp_model_file)
    assert os.path.exists(temp_model_file)
    
    reloaded = MultivariateAnomalyDetector.load_model(temp_model_file)
    assert reloaded.is_trained is True
    
    res_orig = trained_detector.detect_spike(current=1.20, voltage=5.00, temp=125.0, iddq=10.0)
    res_reload = reloaded.detect_spike(current=1.20, voltage=5.00, temp=125.0, iddq=10.0)
    assert res_orig["is_anomaly"] == res_reload["is_anomaly"]

def test_isro_dynamic_outlier_stated_problem(trained_detector):
    """
    Test the exact ISRO prompt example:
    Lot average Iddq is 10 uA, component shows 45 uA (below absolute datasheet limit of 50 uA).
    Must be caught as a Dynamic Outlier with QA justification.
    """
    res = trained_detector.detect_spike(current=1.20, voltage=5.00, temp=125.0, iddq=45.0)
    assert res["is_anomaly"] is True
    # Score threshold is > 0.60 under the blended IF+z formula (IF base + capped z-contribution).
    # The old 0.70 threshold was calibrated for the removed artificial boost (0.50 + z_iddq*0.05).
    assert res["anomaly_score"] > 0.60
    assert "Dynamic Outlier" in res["qa_justification"]
    assert "Iddq" in res["qa_justification"]
    assert "detection_source" in res
    assert res["detection_source"] in ("isolation_forest", "hybrid_fusion", "z_score_safety_net")

def test_nominal_sensor_jitter(trained_detector):
    """Verify that harmless sensor jitter at 125°C never triggers false alarms."""
    for _ in range(500):
        v = 4.98 + random.uniform(-0.03, 0.03)
        c = 1.20 + random.uniform(-0.015, 0.015)
        t = 125.6 + random.uniform(-0.4, 0.4)
        iq = 10.0 + random.uniform(-1.2, 1.2)
        
        res = trained_detector.detect_spike(current=c, voltage=v, temp=t, iddq=iq)
        assert res["is_anomaly"] is False
        assert res["anomaly_score"] < 0.35
        assert "QA STATUS [PASSED]" in res["qa_justification"]

def test_sudden_micro_short(trained_detector):
    """Verify that severe electrical shorts are 100% caught."""
    for _ in range(50):
        v = random.uniform(0.1, 0.6)
        c = random.uniform(5.0, 10.0)
        t = random.uniform(130.0, 150.0)
        iq = random.uniform(80.0, 150.0)
        
        res = trained_detector.detect_spike(current=c, voltage=v, temp=t, iddq=iq)
        assert res["is_anomaly"] is True
        assert res["anomaly_score"] > 0.70
        assert "QA STATUS [REJECTED]" in res["qa_justification"]

def test_inference_latency(trained_detector):
    """Verify sub-25ms real-time execution constraint."""
    import time
    for _ in range(10):
        trained_detector.detect_spike(current=1.20, voltage=5.00, temp=125.0, iddq=10.0)
    start = time.perf_counter()
    for _ in range(100):
        trained_detector.detect_spike(current=1.20, voltage=5.00, temp=125.0, iddq=10.0)
    elapsed_ms = (time.perf_counter() - start) * 1000 / 100
    assert elapsed_ms < 25.0

# ===========================================================================
# MODULE B UNIT TESTS: Linear Regression Drift Predictor
# ===========================================================================

def test_module_b_initialising_phase():
    """Module B returns an initialising result when fewer than 8 observations collected."""
    predictor = LinearRegressionDriftPredictor(lot_mean_iddq=10.0, lot_std_iddq=1.17)
    for i in range(5):
        result = predictor.update(burn_in_hours=float(i), iddq_uA=10.0 + i * 0.1)
    assert result["n_observations"] == 5
    assert result["early_reject_b"] is False
    assert "INITIALIZING" in result["drift_status"]

def test_module_b_nominal_stable_forecast():
    """
    Module B correctly forecasts a stable component (flat Iddq ~10 µA)
    as SAFE at the 168h endpoint.
    """
    random.seed(42)
    predictor = LinearRegressionDriftPredictor(lot_mean_iddq=10.0, lot_std_iddq=1.17)
    # Feed 20 nominal observations at various burn-in hours
    for i in range(20):
        iddq = 10.0 + random.uniform(-0.3, 0.3)   # flat jitter around 10 µA
        result = predictor.update(burn_in_hours=float(i) * 8.0, iddq_uA=iddq)

    assert result["n_observations"] == 20
    assert result["early_reject_b"] is False
    assert "(SAFE)" in result["forecast_168h_label"]
    # 168h forecast should stay close to nominal lot mean
    assert 5.0 < result["forecast_168h_uA"] < 25.0

def test_module_b_thermal_drift_violation_early_reject():
    """
    Module B must flag early rejection when thermal drift will push
    Iddq above 50 µA by 168h (the ISRO Module B core requirement).
    Iddq rises at 0.45 µA/h: starting from 10 µA → ~85 µA at 168h.
    """
    predictor = LinearRegressionDriftPredictor(lot_mean_iddq=10.0, lot_std_iddq=1.17)
    DRIFT_RATE = 0.45  # µA per hour, matches server thermal_drift scenario

    for i in range(30):
        burn_h = float(i) * 3.0           # 0h, 3h, 6h ... 87h
        iddq   = 10.0 + DRIFT_RATE * burn_h + random.gauss(0, 0.05)
        result = predictor.update(burn_in_hours=burn_h, iddq_uA=iddq)

    # After 30 observations of clear upward drift, must predict violation
    assert result["early_reject_b"] is True
    assert result["forecast_168h_uA"] > 50.0
    assert "(VIOLATION)" in result["forecast_168h_label"]
    # Slope must be positive and significant
    assert result["drift_slope_ua_h"] > 0.10

def test_module_b_reset_clears_state():
    """Module B reset() must clear all observations so the next scenario starts fresh."""
    predictor = LinearRegressionDriftPredictor(lot_mean_iddq=10.0, lot_std_iddq=1.17)
    for i in range(20):
        predictor.update(burn_in_hours=float(i), iddq_uA=45.0)   # fill with outlier values

    predictor.reset()
    result = predictor.update(burn_in_hours=0.0, iddq_uA=10.0)

    assert result["n_observations"] == 1
    assert result["early_reject_b"] is False
    assert "INITIALIZING" in result["drift_status"]

def test_module_b_predict_168h_interface():
    """Verify predict_168h ISRO Module B interface and MAE computation."""
    predictor = LinearRegressionDriftPredictor(lot_mean_iddq=10.0, lot_std_iddq=1.17, datasheet_limit_ua=50.0, dynamic_sigma=3.0)
    
    # 0h = 10.0, 24h = 10.5 -> slope = 0.5/24, forecast_168h = 10.0 + (0.5/24)*168 = 13.5 uA
    res = predictor.predict_168h(value_0h=10.0, value_24h=10.5, actual_168h=13.2)
    assert round(res["forecast_168h_uA"], 2) == 13.50
    assert res["will_violate_static"] is False
    assert "mae" in res
    assert round(res["mae"], 2) == 0.30

def test_module_b_parameterized_limits():
    """Verify parameterized limits in LinearRegressionDriftPredictor."""
    custom_predictor = LinearRegressionDriftPredictor(
        lot_mean_iddq=20.0,
        lot_std_iddq=2.5,
        datasheet_limit_ua=75.0,
        dynamic_sigma=2.0
    )
    # Dynamic limit = 20.0 + 2.0 * 2.5 = 25.0
    res = custom_predictor.predict_168h(value_0h=20.0, value_24h=21.0)
    # slope = 1.0/24, forecast_168h = 20 + 7 = 27.0
    assert res["forecast_168h_uA"] == 27.0
    assert res["will_violate_static"] is False  # 27 < 75
    assert res["will_violate_dynamic"] is True  # 27 > 25

def test_detect_batch_and_spike_parity(trained_detector):
    """Verify that detect_batch and detect_spike produce consistent anomaly classifications."""
    v_test = [5.00, 5.00, 0.40, 5.00]
    c_test = [1.20, 1.20, 8.00, 1.20]
    t_test = [125.0, 125.0, 140.0, 125.0]
    iq_test = [10.0, 45.0, 90.0, 9.8]
    pd_test = [4.5, 4.6, 9.5, 4.5]
    
    is_anomalies_batch, scores_batch, det_sources_batch = trained_detector.detect_batch(
        v_test, c_test, t_test, iq_test, pd_test
    )

    assert len(det_sources_batch) == len(v_test), "detection_sources length must match input length"
    
    for i in range(len(v_test)):
        res_spike = trained_detector.detect_spike(
            current=c_test[i], voltage=v_test[i], temp=t_test[i],
            iddq=iq_test[i], prop_delay=pd_test[i]
        )
        assert bool(is_anomalies_batch[i]) == bool(res_spike["is_anomaly"]), f"Mismatch at index {i}"
        assert abs(scores_batch[i] - res_spike["anomaly_score"]) < 0.05, f"Score mismatch at index {i}"
        assert "detection_source" in res_spike, "detect_spike must return detection_source field"

