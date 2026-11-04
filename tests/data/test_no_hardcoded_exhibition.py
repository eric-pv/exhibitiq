"""Guard for the V2.3 mandatory rule: no specific exhibition in core code.

Core code (``crawler/``, ``etl/``) must not depend on a specific exhibition's name.
Exhibition-specific differences belong in registration data, source configs or
adapters, never in core code. This is a coarse name check, not a proof; it
catches the obvious regression of hard-coding a real exhibition.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORE_DIRS = ("crawler", "etl")
# Names of real exhibitions that appeared in project discussions; extend as needed.
FORBIDDEN = re.compile(r"\b(mspo|tadte|eurosatory|dsei)\b", re.IGNORECASE)


def _core_python_files() -> list[Path]:
    return sorted(p for d in CORE_DIRS for p in (ROOT / d).rglob("*.py"))


def test_core_directories_have_python_files() -> None:
    assert _core_python_files(), "the guard would pass vacuously"


def test_core_code_names_no_specific_exhibition() -> None:
    hits = [
        f"{path.relative_to(ROOT)}:{number}: {line.strip()}"
        for path in _core_python_files()
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1)
        if FORBIDDEN.search(line)
    ]
    assert hits == []
