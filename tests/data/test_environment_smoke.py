"""Environment smoke test for P1-DATA-01 (Issue #6).

Checks only that the cloud Python environment is usable: Python version,
required packages, and that pyproject.toml / requirements.txt are consistent.
It does not define or check any ExhibitIQ data contract; the contract lives
in schemas/ only.
"""
from __future__ import annotations

import re
import sys
import tomllib
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MIN_PYTHON = (3, 11)


def _pinned_requirements() -> dict[str, str]:
    pins: dict[str, str] = {}
    for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = re.fullmatch(r"([A-Za-z0-9_.\-]+)==([A-Za-z0-9_.\-]+)", line)
        assert m, f"requirements.txt line is not an exact pin: {line!r}"
        pins[m.group(1).lower()] = m.group(2)
    return pins


def test_python_version_meets_minimum() -> None:
    assert sys.version_info[:2] >= MIN_PYTHON


def test_pyproject_requires_python_matches_test_minimum() -> None:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert data["project"]["requires-python"] == ">=3.11"
    assert data["tool"]["pytest"]["ini_options"]["testpaths"] == ["tests/data"]


def test_requirements_are_exact_pins_and_installed() -> None:
    pins = _pinned_requirements()
    assert {"jsonschema", "pytest"} <= pins.keys()
    for name, version in pins.items():
        assert metadata.version(name) == version, f"{name}: installed != pinned {version}"


def test_jsonschema_supports_draft_2020_12() -> None:
    # Generic library capability check only; no ExhibitIQ fields are defined here.
    from jsonschema import Draft202012Validator

    Draft202012Validator.check_schema({"type": "object"})
