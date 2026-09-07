"""
tests/conftest.py — Project ARJUNA (SIH 26170)
Global pytest configuration ensuring canonical Backend resolution and a HERMETIC
(offline) test environment.

Hermeticity (audit F06): the repo ships a development `.env` with
SUPABASE_ENABLED=true and live credentials. Without this guard, any test that
constructs a Backend TelemetryStore would open real HTTPS connections to the
configured Supabase endpoint (observed during baseline testing), making the test
suite non-reproducible and slow, and risking writes to a live database. We
therefore force offline persistence for the whole test suite unless a developer
explicitly opts in with ARJUNA_TEST_LIVE_DB=1. load_dotenv() in Backend/database.py
does not override an already-set environment variable, so this guard is effective.
"""

import os
import sys
from pathlib import Path

# Opt-in live-database testing is explicit and off by default.
if os.environ.get("ARJUNA_TEST_LIVE_DB") != "1":
    os.environ.setdefault("SUPABASE_ENABLED", "false")

ROOT_DIR = Path(__file__).resolve().parent.parent

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(ROOT_DIR / "Backend") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "Backend"))
