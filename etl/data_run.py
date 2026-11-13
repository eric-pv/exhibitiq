"""Entry point of the data-run GitHub Actions workflow (D2-05, restored 2026-11-12 at Albert's request).

    python -m etl.data_run data-run/request.json [--report data-run/report.json]

The workflow (``.github/workflows/data-run.yml``) runs on a push to a ``data-run/**`` branch, in GitHub's runners
(which have normal DNS, unlike the cloud workspace), and commits what this command produced back to that branch.
A person or Claude Code then checks the result and opens a pull request to ``dev/data-platform``; the workflow never
writes ``main`` or any ``dev/*`` branch.

The request lists steps; **only the commands below are allowed** and every path must stay inside ``data/`` (so a
request can never run arbitrary code or touch code, workflows or other people's paths)::

    {"steps": [
      {"command": "enrich", "package": "data/packages/...", "targets": "data/sources/....json", "notes": "..."},
      {"command": "import_file", "config": "data/sources/....toml", "file": "data/uploads/...", "info": "data/sources/....json", ...},
      {"command": "build_index"},
      {"command": "validate", "package": "data/packages/..."}
    ]}

Steps run in order; the first failing step stops the run. The report (JSON) records each step's command, exit code
and output, so the result can be reviewed without the Actions log.
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

REPORT_VERSION = 1
MAX_OUTPUT = 20000


class RequestError(ValueError):
    """The request is not allowed or not well formed; nothing was run."""


def _data_path(value: Any, key: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        raise RequestError(f"{key} must be a path inside data/")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or path.parts[0] != "data" or len(path.parts) < 2:
        raise RequestError(f"{key} must be a path inside data/, got {value!r}")
    return value


def _text(value: Any, key: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 4000:
        raise RequestError(f"{key} must be non-empty text (at most 4000 characters)")
    return value


def _enrich(step: Mapping[str, Any]) -> list[str]:
    argv = ["--package", _data_path(step.get("package"), "package"), "--targets", _data_path(step.get("targets"), "targets")]
    if "notes" in step:
        argv += ["--notes", _text(step["notes"], "notes")]
    return argv


def _import_file(step: Mapping[str, Any]) -> list[str]:
    argv = ["--config", _data_path(step.get("config"), "config"), "--file", _data_path(step.get("file"), "file"), "--info", _data_path(step.get("info"), "info")]
    if "country_aliases" in step:
        argv += ["--country-aliases", _data_path(step["country_aliases"], "country_aliases")]
    if "official_count" in step:
        count = step["official_count"]
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise RequestError("official_count must be a non-negative integer")
        argv += ["--official-count", str(count)]
    for key, flag in (("official_as_of", "--official-as-of"), ("notes", "--notes")):
        if key in step:
            argv += [flag, _text(step[key], key)]
    if "accept" in step:
        if not isinstance(step["accept"], list) or not all(isinstance(c, str) for c in step["accept"]):
            raise RequestError("accept must be a list of quality codes")
        argv += ["--accept", *step["accept"]]
    return argv


def _validate(step: Mapping[str, Any]) -> list[str]:
    return [_data_path(step.get("package"), "package")]


def _no_args(step: Mapping[str, Any]) -> list[str]:
    return []


# command -> (allowed keys, argv builder, module whose main runs it)
COMMANDS: dict[str, tuple[frozenset[str], Callable[[Mapping[str, Any]], list[str]], str]] = {
    "enrich": (frozenset({"package", "targets", "notes"}), _enrich, "etl.enrich"),
    "import_file": (frozenset({"config", "file", "info", "country_aliases", "official_count", "official_as_of", "notes", "accept"}), _import_file, "etl.import_file"),
    "build_index": (frozenset(), _no_args, "etl.build_index"),
    "validate": (frozenset({"package"}), _validate, "etl.validate"),
}


def plan(request: Any) -> list[tuple[str, list[str]]]:
    """(module, argv) for every step. Raises ``RequestError`` before anything runs if any step is not allowed."""
    if not isinstance(request, dict) or set(request) != {"steps"} or not isinstance(request["steps"], list) or not request["steps"]:
        raise RequestError('the request must be {"steps": [...]} with at least one step')
    if len(request["steps"]) > 20:
        raise RequestError("at most 20 steps")
    planned = []
    for i, step in enumerate(request["steps"]):
        if not isinstance(step, dict) or step.get("command") not in COMMANDS:
            raise RequestError(f"steps[{i}]: command must be one of {', '.join(sorted(COMMANDS))}")
        allowed, build, module = COMMANDS[step["command"]]
        unknown = sorted(set(step) - allowed - {"command"})
        if unknown:
            raise RequestError(f"steps[{i}] ({step['command']}): unknown key(s) {', '.join(unknown)}")
        try:
            planned.append((module, build(step)))
        except RequestError as exc:
            raise RequestError(f"steps[{i}] ({step['command']}): {exc}") from None
    return planned


def _run(module: str, argv: list[str]) -> tuple[int, str]:
    import importlib

    main = importlib.import_module(module).main
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = main(argv)
        except SystemExit as exc:  # argparse errors
            code = exc.code if isinstance(exc.code, int) else 2
    text = out.getvalue() + (("\n[stderr]\n" + err.getvalue()) if err.getvalue() else "")
    return int(code or 0), text[-MAX_OUTPUT:]


def execute(request: Any, *, runner: Callable[[str, list[str]], tuple[int, str]] = _run) -> dict[str, Any]:
    steps = []
    ok = True
    for module, argv in plan(request):
        code, output = runner(module, argv)
        steps.append({"module": module, "argv": argv, "exit_code": code, "output": output})
        if code != 0:
            ok = False
            break
    return {"version": REPORT_VERSION, "ok": ok, "steps": steps}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m etl.data_run", description="Run an allow-listed data request (GitHub Actions data-run workflow).")
    parser.add_argument("request", type=Path)
    parser.add_argument("--report", type=Path, default=Path("data-run/report.json"))
    args = parser.parse_args(argv)
    try:
        request = json.loads(args.request.read_text(encoding="utf-8"))
        report = execute(request)
    except (OSError, ValueError) as exc:
        report = {"version": REPORT_VERSION, "ok": False, "error": str(exc), "steps": []}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "steps"} | {"steps": [(s["module"], s["exit_code"]) for s in report["steps"]]}, ensure_ascii=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
