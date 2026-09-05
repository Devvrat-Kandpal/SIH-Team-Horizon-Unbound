"""
tests/test_criticality_consistency.py — Project ARJUNA (SIH 26170)

Criticality semantics consistency suite (Doc-6 sect 19 / P2.5):
verifies that the canonical mapping is enforced everywhere:
    Level 1 = LOW criticality (COTS / ground support)
    Level 2 = STANDARD (nominal space qualification)
    Level 3 = MISSION-CRITICAL (flight / human-rated)
Guards against any regression to the historical inverted wording
("1=highest" / "3=lowest") in source, docs, or config.
"""

import re
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "Backend"))

from Backend.criticality_config import get_config


def test_level_labels_ordering():
    """Canonical semantics: L1=low, L2=standard, L3=mission-critical."""
    assert get_config(1)["fault_label"] == "LOW-CRITICALITY"
    assert get_config(2)["fault_label"] == "STANDARD"
    assert get_config(3)["fault_label"] == "MISSION-CRITICAL"


def test_level_descriptions_ordering():
    """Descriptions must reflect ascending criticality (L1 COTS -> L3 flight)."""
    desc1 = get_config(1)["description"].lower()
    desc3 = get_config(3)["description"].lower()
    assert "cots" in desc1 or "ground" in desc1
    assert "mission" in desc3 or "flight" in desc3 or "human" in desc3


_DISALLOWED_INVERTED = [
    re.compile(r"1\s*=\s*highest", re.IGNORECASE),
    re.compile(r"3\s*=\s*lowest", re.IGNORECASE),
    re.compile(r"\(1\s*=\s*highest\s*reliability"),
]


def test_no_inverted_criticality_wording():
    """Guard against historical inverted tier semantics in source/docs."""
    targets = [
        ROOT_DIR / "Backend" / "criticality_config.py",
        ROOT_DIR / "Backend" / "simulator.py",
        ROOT_DIR / "Backend" / "server.py",
        ROOT_DIR / "RTM.md",
        ROOT_DIR / "README.md",
    ]
    for path in targets:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in _DISALLOWED_INVERTED:
            assert not pattern.search(text), (
                f"Found inverted criticality wording {pattern.pattern!r} in {path.name}"
            )
