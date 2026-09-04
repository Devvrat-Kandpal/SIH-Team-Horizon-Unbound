"""
tests/conftest.py — Project ARJUNA (SIH 26170)
Global pytest configuration ensuring canonical Backend resolution.
"""

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(ROOT_DIR / "Backend") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "Backend"))
