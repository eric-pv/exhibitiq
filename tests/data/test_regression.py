"""Regression suite of the data-engineering modules (D3-08).

1. Every module's output on fixed synthetic inputs equals the reviewed expected file in ``tests/data/regression/``
   byte for byte (see ``tests/data/regression_outputs.py``; regenerate with
   ``python -m tests.data.regression_outputs --write`` only for an intended change, and review the diff).
2. The outputs do not depend on the working directory, the temporary directory or repeated runs.
3. Every module under ``crawler/`` and ``etl/`` is imported by at least one test, and every command line starts.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

from tests.data import regression_outputs as ro

ROOT = Path(__file__).resolve().parents[2]
TESTS = Path(__file__).resolve().parent
CLIS = ["etl.validate", "etl.report", "etl.build_index", "etl.catalog", "etl.integrity", "etl.import_file", "etl.enrich", "tests.data.regression_outputs"]


@pytest.mark.parametrize("name", list(ro.OUTPUTS))
def test_output_equals_the_expected_file(name: str) -> None:
    path = ro.expected_path(name)
    assert path.is_file(), f"missing {path}; run: python -m tests.data.regression_outputs --write"
    expected = path.read_text(encoding="utf-8")
    actual = ro.compute(name)
    assert actual == expected, f"{name} changed. If intended: python -m tests.data.regression_outputs --write, then review the diff"


def test_expected_files_are_exactly_the_outputs() -> None:
    assert sorted(p.stem for p in ro.EXPECTED_DIR.glob("*.json")) == sorted(ro.OUTPUTS)


def test_expected_files_contain_no_machine_paths_and_only_synthetic_data() -> None:
    for path in ro.EXPECTED_DIR.glob("*.json"):
        text = path.read_text(encoding="utf-8")
        assert str(ROOT) not in text and "/tmp/" not in text, path.name
        origins = set(re.findall(r'"data_origin": "([a-z_]+)"', text))
        assert origins <= {"synthetic"}, (path.name, origins)


def test_outputs_do_not_depend_on_the_working_directory(tmp_path: Path) -> None:
    script = "from tests.data import regression_outputs as ro; import sys; sys.stdout.write(ro.compute('pipeline') + ro.compute('catalog'))"
    run = subprocess.run([sys.executable, "-c", script], cwd=tmp_path, env={"PYTHONPATH": str(ROOT), "PATH": ""}, capture_output=True, text=True, timeout=300)
    assert run.returncode == 0, run.stderr
    assert run.stdout == ro.compute("pipeline") + ro.compute("catalog")


def test_compare_command_reports_a_difference(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    for name in ro.OUTPUTS:
        (tmp_path / f"{name}.json").write_text(ro.expected_path(name).read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(ro, "EXPECTED_DIR", tmp_path)
    assert ro.main([]) == 0
    (tmp_path / "history.json").write_text("{}\n", encoding="utf-8")
    assert ro.main([]) == 1 and "history" in capsys.readouterr().err
    assert ro.main(["--write"]) == 0 and ro.main([]) == 0


def _modules(package: str) -> list[str]:
    return sorted(f"{package}.{p.stem}" for p in (ROOT / package).glob("*.py") if p.stem != "__init__")


@pytest.mark.parametrize("module", _modules("crawler") + _modules("etl"))
def test_every_module_is_imported_by_a_test(module: str) -> None:
    package, name = module.split(".")
    pattern = re.compile(rf"(from {package}\.{name} import|import {package}\.{name}\b|from {package} import [^\n]*\b{name}\b|\"{package}\.{name}\")")
    users = [p.name for p in TESTS.glob("*.py") if pattern.search(p.read_text(encoding="utf-8"))]
    assert users, f"{module} is not imported by any test in tests/data/"


@pytest.mark.parametrize("module", CLIS)
def test_every_command_line_starts(module: str) -> None:
    run = subprocess.run([sys.executable, "-m", module, "--help"], cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert run.returncode == 0 and "usage:" in run.stdout, run.stderr
