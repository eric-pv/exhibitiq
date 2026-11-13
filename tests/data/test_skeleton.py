"""Skeleton checks for P1-DATA-02 (Issue #11).

Verifies the crawler/ and etl/ packages are importable and that no parallel
data contract exists outside schemas/. It tests structure only, not behavior.
"""
from __future__ import annotations

import importlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache"}


@pytest.mark.parametrize("name", ["crawler", "etl"])
def test_package_is_importable_and_documented(name: str) -> None:
    module = importlib.import_module(name)
    assert module.__doc__ and "owner: data" in module.__doc__
    assert (ROOT / name / "__init__.py").is_file()


def _schema_files_outside_schemas_dir() -> list[str]:
    found = []
    for path in ROOT.rglob("*.schema.json"):
        rel = path.relative_to(ROOT)
        if SKIP_DIRS & set(rel.parts):
            continue
        if rel.parts[0] != "schemas":
            found.append(rel.as_posix())
    return sorted(found)


def test_no_schema_files_outside_schemas_dir() -> None:
    """schemas/ is the only data contract; no parallel copies elsewhere."""
    assert _schema_files_outside_schemas_dir() == []


def test_schemas_dir_is_present_for_the_validator_to_load() -> None:
    assert (ROOT / "schemas" / "v1" / "VERSION").is_file()
