"""Tests for etl.data_run and the data-run workflow (D2-05 restored): only allow-listed steps, only data/ paths,
least privilege, never main or dev/*."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from etl.data_run import RequestError, execute, main, plan

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "data-run.yml"


def test_plan_builds_argv_for_each_allowed_command() -> None:
    assert plan({"steps": [
        {"command": "enrich", "package": "data/packages/x/2026/x-2026.1", "targets": "data/sources/x/t.json", "notes": "why"},
        {"command": "import_file", "config": "data/sources/x/c.toml", "file": "data/uploads/x/2026/l.pdf", "info": "data/sources/x/i.json",
         "country_aliases": "data/sources/x/c.json", "official_count": 5, "official_as_of": "2026-11-12", "accept": ["Q3"]},
        {"command": "build_index"},
        {"command": "validate", "package": "data/packages/x/2026/x-2026.1"},
    ]}) == [
        ("etl.enrich", ["--package", "data/packages/x/2026/x-2026.1", "--targets", "data/sources/x/t.json", "--notes", "why"]),
        ("etl.import_file", ["--config", "data/sources/x/c.toml", "--file", "data/uploads/x/2026/l.pdf", "--info", "data/sources/x/i.json",
                             "--country-aliases", "data/sources/x/c.json", "--official-count", "5", "--official-as-of", "2026-11-12", "--accept", "Q3"]),
        ("etl.build_index", []),
        ("etl.validate", ["data/packages/x/2026/x-2026.1"]),
    ]


@pytest.mark.parametrize("request_, message", [
    ({}, "steps"), ({"steps": []}, "steps"), ({"steps": [{"command": "shell", "run": "rm -rf /"}]}, "command must be one of"),
    ({"steps": [{"command": "build_index", "extra": 1}]}, "unknown key"),
    ({"steps": [{"command": "validate", "package": "../etc/passwd"}]}, "inside data/"),
    ({"steps": [{"command": "validate", "package": "/data/x"}]}, "inside data/"),
    ({"steps": [{"command": "validate", "package": "etl/validate.py"}]}, "inside data/"),
    ({"steps": [{"command": "validate", "package": "data/../.github/workflows"}]}, "inside data/"),
    ({"steps": [{"command": "validate", "package": "data"}]}, "inside data/"),
    ({"steps": [{"command": "import_file", "config": "data/a", "file": "data/b", "info": "data/c", "official_count": -1}]}, "official_count"),
    ({"steps": [{"command": "import_file", "config": "data/a", "file": "data/b", "info": "data/c", "accept": "Q3"}]}, "accept"),
    ({"steps": [{"command": "enrich", "package": "data/a", "targets": "data/b", "notes": ""}]}, "notes"),
    ({"steps": [{"command": "build_index"}] * 21}, "at most 20"),
    ({"steps": [{"command": "build_index"}], "other": 1}, "steps"),
])
def test_requests_that_are_not_allowed_run_nothing(request_, message) -> None:
    ran = []
    with pytest.raises(RequestError, match=message):
        execute(request_, runner=lambda m, a: ran.append(m) or (0, ""))
    assert ran == []


def test_the_first_failing_step_stops_the_run() -> None:
    calls = []

    def runner(module, argv):
        calls.append(module)
        return (1 if module == "etl.enrich" else 0), f"{module} output"

    report = execute({"steps": [{"command": "build_index"}, {"command": "enrich", "package": "data/p", "targets": "data/t"}, {"command": "build_index"}]}, runner=runner)
    assert calls == ["etl.build_index", "etl.enrich"] and not report["ok"]
    assert [(s["module"], s["exit_code"]) for s in report["steps"]] == [("etl.build_index", 0), ("etl.enrich", 1)]


def test_main_writes_the_report_even_for_a_refused_request(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "req.json").write_text(json.dumps({"steps": [{"command": "shell"}]}), encoding="utf-8")
    assert main(["req.json", "--report", "out/report.json"]) == 1
    report = json.loads((tmp_path / "out" / "report.json").read_text(encoding="utf-8"))
    assert report["ok"] is False and "command must be one of" in report["error"]


def test_main_runs_a_real_step(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    sample = ROOT / "data" / "samples" / "sample-fair" / "2026" / "sample-fair-2026.20261104T020000Z"
    target = tmp_path / "data" / "p"
    import shutil

    shutil.copytree(sample, target)
    (tmp_path / "req.json").write_text(json.dumps({"steps": [{"command": "validate", "package": "data/p"}]}), encoding="utf-8")
    assert main(["req.json", "--report", "r.json"]) == 0
    report = json.loads((tmp_path / "r.json").read_text(encoding="utf-8"))
    assert report["ok"] and report["steps"][0]["exit_code"] == 0 and "OK" in report["steps"][0]["output"]


# ------------------------------------------------------------------------------------- workflow (static)

TEXT = WORKFLOW.read_text(encoding="utf-8")


def test_workflow_triggers_only_on_data_run_branches() -> None:
    on = TEXT.split("\non:", 1)[1].split("\npermissions:", 1)[0]
    assert re.findall(r"^  (\w+):", on, re.M) == ["push"]
    assert re.findall(r'^      - "([^"]+)"', on, re.M) == ["data-run/**"]
    assert "pull_request_target" not in TEXT and "workflow_run" not in TEXT


def test_workflow_has_least_privilege_and_no_secrets() -> None:
    perms = TEXT.split("\npermissions:", 1)[1].split("\n\n", 1)[0]
    assert re.findall(r"^  ([\w-]+): (\w+)", perms, re.M) == [("contents", "write")]
    assert "secrets." not in TEXT and "pull-requests" not in TEXT
    assert set(re.findall(r"uses: ([\w./-]+)@", TEXT)) == {"actions/checkout", "actions/setup-python"}


def test_workflow_pushes_only_back_to_its_data_run_branch_and_avoids_loops() -> None:
    assert 'case "$BRANCH" in data-run/*) ;; *) echo "refusing to push to $BRANCH"; exit 1;; esac' in TEXT
    assert 'git push origin "HEAD:refs/heads/$BRANCH"' in TEXT and TEXT.count("git push") == 1
    assert "main" not in re.sub(r"#.*", "", TEXT).replace("python -m etl.data_run", "")
    assert "[data-run result]" in TEXT.split("if:", 1)[1].split("\n", 1)[0]
    assert "concurrency:" in TEXT and "cancel-in-progress: false" in TEXT
    assert "python -m etl.data_run data-run/request.json" in TEXT
