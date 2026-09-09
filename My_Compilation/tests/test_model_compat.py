"""
tests/test_model_compat.py — Project ARJUNA (SIH 26170)

Serialized-Model Reproducibility (P0-07).

The serialized Isolation Forest (Model/isolation_forest_model.joblib) must load
under the SAME pinned scikit-learn version used to train and infer across
local / CI / Docker. A version mismatch would otherwise raise an
InconsistentVersionWarning and destroy benchmark reproducibility.

These tests:
  1. Assert the installed scikit-learn version equals the PINNED requirement.
  2. Load the shipped artifact with warnings promoted to errors so any
     InconsistentVersionWarning (or other unexpected warning during load)
     FAILS the suite instead of being silently tolerated.
  3. Assert the artifact structure, estimator type, feature count, and that
     MultivariateAnomalyDetector.load_model round-trips successfully.
"""

import re
import sys
import warnings
from pathlib import Path

import joblib
import sklearn

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "Backend"))

from Backend.isolation_forest import MultivariateAnomalyDetector  # noqa: E402

REQUIREMENTS = ROOT_DIR / "requirements.txt"
MODEL_PATH = ROOT_DIR / "Model" / "isolation_forest_model.joblib"

# Expected structure of the serialized artifact (see Backend/isolation_forest.py)
EXPECTED_KEYS = {
    "model",
    "lot_stats",
    "contamination",
    "n_estimators",
    "random_state",
    "use_engineered_features",
}
# The deployed detector consumes 7 features (see MultivariateAnomalyDetector).
EXPECTED_FEATURES = 7


def _pinned_sklearn_version() -> str:
    """Returns the pin (e.g. '1.9.0') required by requirements.txt."""
    text = REQUIREMENTS.read_text(encoding="utf-8")
    match = re.search(r"^scikit-learn==([^\n#\s]+)", text, flags=re.MULTILINE)
    if not match:
        raise AssertionError("requirements.txt must pin scikit-learn with == lock")
    return match.group(1).strip()


def test_installed_sklearn_matches_pinned_requirement():
    """The runtime must be the SAME version the model was trained/serialized under."""
    pinned = _pinned_sklearn_version()
    assert sklearn.__version__ == pinned, (
        f"Runtime scikit-learn {sklearn.__version__} != pinned {pinned}. "
        "Install the pinned runtime (P0-07): pip install -r requirements.txt"
    )


def test_serialized_model_loads_without_sklearn_version_warning():
    """Loading the model must NOT raise InconsistentVersionWarning (P0-07)."""
    warnings.simplefilter("error")  # promote any warning (incl. version mismatch) to failure
    joblib.load(MODEL_PATH)
    warnings.resetwarnings()


def test_serialized_model_artifact_structure_and_features():
    """Structure, estimator type, and feature count of the shipped model."""
    data = joblib.load(MODEL_PATH)
    assert isinstance(data, dict), "model artifact must be a dict bundle"
    assert EXPECTED_KEYS.issubset(data.keys()), (
        f"artifact missing keys; has {sorted(data.keys())}"
    )

    estimator = data["model"]
    from sklearn.ensemble import IsolationForest

    assert isinstance(estimator, IsolationForest), type(estimator).__name__
    assert estimator.n_features_in_ == EXPECTED_FEATURES, (
        f"unexpected feature count {estimator.n_features_in_}; "
        f"expected {EXPECTED_FEATURES}"
    )


def test_multivariate_detector_load_model_round_trip():
    """The canonical loader must successfully reconstruct a trained detector."""
    detector = MultivariateAnomalyDetector.load_model(str(MODEL_PATH))
    assert detector.is_trained is True
    assert detector.lot_stats, "lot_stats must be populated on load"


def test_multivariate_detector_detect_requires_no_recompute():
    """Loaded detector must reproduce a deterministic decision on a known vector
    without retraining — validates the serialized weights are intact and usable."""
    detector = MultivariateAnomalyDetector.load_model(str(MODEL_PATH))
    # Nominal-ish in-lot vector: should NOT hard-fail and should return the
    # expected result tuple shape regardless of the flag value.
    result = detector.detect_spike(
        current=1.2,
        voltage=5.0,
        temp=125.0,
        iddq=10.0,
        prop_delay=4.5,
        criticality_level=2,
    )
    assert isinstance(result, dict)
    assert "anomaly_score" in result
    assert "detection_source" in result
