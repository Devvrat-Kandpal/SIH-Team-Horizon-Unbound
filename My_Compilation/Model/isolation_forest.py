"""
Model/isolation_forest.py — Canonical backward-compatibility shim.
Authoritative source code is relocated to Backend/isolation_forest.py per canonical architecture.
"""
# ruff: noqa: E402, F403, F401, I001
# (intentional shim pattern: re-export the authoritative Backend implementation)

import sys
import os

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from Backend.isolation_forest import *
from Backend.isolation_forest import (
    MultivariateAnomalyDetector,
    LinearRegressionDriftPredictor,
)
