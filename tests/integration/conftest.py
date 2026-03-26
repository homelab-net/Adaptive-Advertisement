"""
Integration test bootstrap — adds all service source directories to sys.path.
Services have unique top-level package names so there are no import conflicts.
"""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]

for _svc in (
    "shared",
    "input-cv",
    "audience-state",
    "player",
    "decision-optimizer",
    "creative",
    "supervisor",
):
    _p = str(_ROOT / "services" / _svc)
    if _p not in sys.path:
        sys.path.insert(0, _p)
