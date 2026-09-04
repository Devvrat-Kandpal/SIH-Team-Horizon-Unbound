"""
simulation/simulator.py — Canonical backward-compatibility shim.
Authoritative source code is relocated to Backend/simulator.py per canonical architecture.
"""
import sys
import os

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from Backend.simulator import *
from Backend.simulator import ComponentSimulator, configure_logging
