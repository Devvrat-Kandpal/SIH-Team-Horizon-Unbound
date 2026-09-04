"""
criticality_config.py — Canonical backward-compatibility shim.
Authoritative source code is relocated to Backend/criticality_config.py per canonical architecture.
"""
import sys
import os

_root = os.path.dirname(os.path.abspath(__file__))
if _root not in sys.path:
    sys.path.insert(0, _root)

from Backend.criticality_config import *
from Backend.criticality_config import CRITICALITY_CONFIG, get_config
