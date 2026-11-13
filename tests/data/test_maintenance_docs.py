"""The maintenance manual (D4-06) stays true: what it names exists.

- every document in docs/data-platform/ is listed in its index, and every linked document exists;
- every repository path it mentions in backticks exists (placeholders like ``<exhibition_id>`` and globs are skipped,
  as are the conventional output locations that are created at run time);
- every ``python -m <module>`` it shows is a module with a ``main``; every Python name ``crawler.x.y`` / ``etl.x.y``
  it mentions exists.
"""
from __future__ import annotations

import importlib
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs" / "data-platform"
MANUAL = DOCS / "maintenance.md"
TEXT = MANUAL.read_text(encoding="utf-8")
# created by running the pipeline, not committed: the manual names them as conventions
RUNTIME_PATHS = {"data/raw", "data/packages", "data/index/datasets.json", "data/index/assessments.json", "data/registry/companies.json",
                 "data/history/companies.json", "data/registry"}
# owned by ai and kept on dev/ai-intelligence until phase integration (module-boundaries.md §4.2): named, not present here
OTHER_BRANCH_PATHS = {"tests/contract", "tests/contract/registry_check.py"}
PREFIXES = ("crawler/", "etl/", "data/", "tests/", "docs/", "schemas/", ".github/")


def test_every_data_platform_document_is_in_the_index() -> None:
    linked = set(re.findall(r"\]\(([a-z0-9-]+\.md)\)", TEXT))
    on_disk = {p.name for p in DOCS.glob("*.md")}
    assert on_disk - linked == set(), "add these documents to the index in maintenance.md §1"
    assert linked - on_disk == set(), "the index links documents that do not exist"


def _paths() -> list[str]:
    tokens = (t.rstrip("/") for t in re.findall(r"`([^`\s]+)`", TEXT))
    return sorted({t for t in tokens if t.startswith(PREFIXES) and not any(c in t for c in "<>*|")})


@pytest.mark.parametrize("path", _paths())
def test_every_mentioned_path_exists(path: str) -> None:
    if path in RUNTIME_PATHS:
        pytest.skip("created at run time")
    if path in OTHER_BRANCH_PATHS:
        pytest.skip("on dev/ai-intelligence")
    assert (ROOT / path).exists(), f"maintenance.md mentions {path}, which does not exist"


@pytest.mark.parametrize("module", sorted(set(re.findall(r"python -m ((?:etl|crawler|tests)\.[a-z_.]+)", TEXT))))
def test_every_command_module_has_a_main(module: str) -> None:
    assert callable(getattr(importlib.import_module(module), "main", None)), module


@pytest.mark.parametrize("name", sorted(set(re.findall(r"\b((?:crawler|etl)\.[a-z_]+\.[A-Za-z_]+)\b", TEXT))))
def test_every_mentioned_python_name_exists(name: str) -> None:
    module, attr = name.rsplit(".", 1)
    assert hasattr(importlib.import_module(module), attr), name


def test_the_manual_lists_every_command_line_module() -> None:
    clis = sorted(f"etl.{p.stem}" for p in (ROOT / "etl").glob("*.py") if re.search(r"^def main\(", p.read_text(encoding="utf-8"), re.M))
    for module in clis:
        assert re.search(rf"python -m {re.escape(module)}\b(?![._a-z])", TEXT), f"maintenance.md §3 does not show {module}"
