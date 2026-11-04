"""Command line entry point for runs started by GitHub Actions or by hand (D2-05).

    python -m crawler.cli run --source NAME [--out data/raw] [--max-requests N] [--resume RUN_DIR]
    python -m crawler.cli scheduled

``run`` loads ``<sources-dir>/NAME.toml`` (default ``crawler/sources``), runs it with the adapter the config
names, stores the evidence with ``RunStore`` and prints ``key=value`` lines (also suitable for
``$GITHUB_OUTPUT``): ``status``, ``run_dir``, ``crawl_run_id``, ``snapshots``, ``errors``, ``pending``.

Input is treated as untrusted (workflow inputs come from people): ``NAME`` must be a plain file stem, the
config must live inside the sources directory, and ``--resume`` must be a run directory under ``--out``.

Exit codes: ``0`` the run was recorded, whatever its status (a failed or blocked source is data, see the
printed ``status``); ``2`` the request itself was invalid (bad name, bad config, unknown adapter, nothing to
resume), nothing was run or written.

``scheduled`` prints the JSON list of source names in ``crawler/schedule.toml`` (the sources a schedule runs).
There is no network access outside ``run``.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tomllib
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, TextIO

import crawler.file_import  # noqa: F401  (registers the built-in "file-import" adapter)
from crawler.adapters import AdapterRegistry, default_registry, resolve_adapter
from crawler.fetch import Fetcher, UrllibFetcher
from crawler.models import Request
from crawler.resume import ResumeError, plan_resume
from crawler.runner import RunOptions, run_source
from crawler.source_config import ConfigError, load_source_config
from crawler.store import RunStore, StoreError, verify_run

DEFAULT_SOURCES_DIR = Path("crawler/sources")
DEFAULT_SCHEDULE = Path("crawler/schedule.toml")
DEFAULT_OUT = Path("data/raw")
_NAME = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
_RUN_ID = re.compile(r"^run_[0-7][0-9A-HJKMNP-TV-Z]{25}$")
MAX_REQUESTS_LIMIT = 5000


class UsageError(Exception):
    pass


def source_path(name: str, sources_dir: Path) -> Path:
    if not _NAME.fullmatch(name) or len(name) > 64:
        raise UsageError(f"source name {name!r} must be lowercase letters, digits and hyphens")
    path = sources_dir / f"{name}.toml"
    if not path.is_file():
        raise UsageError(f"no source config {path}")
    if path.resolve().parent != sources_dir.resolve():
        raise UsageError("the source config must be inside the sources directory")
    return path


def scheduled_sources(schedule: Path) -> list[str]:
    if not schedule.is_file():
        return []
    try:
        data = tomllib.loads(schedule.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise UsageError(f"cannot read {schedule}: {exc}") from None
    names = data.get("sources", [])
    if set(data) - {"sources"} or not isinstance(names, list) or not all(isinstance(n, str) and _NAME.fullmatch(n) for n in names) or len(set(names)) != len(names):
        raise UsageError(f"{schedule}: expected `sources = [\"name\", ...]` with unique lowercase names")
    return list(names)


def run_command(args: argparse.Namespace, fetcher: Fetcher, adapters: AdapterRegistry, out: TextIO) -> int:
    if not 1 <= args.max_requests <= MAX_REQUESTS_LIMIT:
        raise UsageError(f"--max-requests must be between 1 and {MAX_REQUESTS_LIMIT}")
    sources_dir, root = Path(args.sources_dir), Path(args.out)
    path = source_path(args.source, sources_dir)
    config = load_source_config(path)
    if config.name != args.source:
        raise UsageError(f"the config's name {config.name!r} must equal its file name {args.source!r}")
    adapter = resolve_adapter(config, adapters)
    run_options = RunOptions(
        max_requests=args.max_requests,
        trigger=args.trigger,
        code_commit=os.environ.get("GITHUB_SHA") if re.fullmatch(r"[0-9a-f]{40}", os.environ.get("GITHUB_SHA", "")) else None,
        github_run_url=_github_run_url(),
    )
    start: list[Request] | None = None
    if args.resume:
        resume_dir = Path(args.resume)
        if _RUN_ID.fullmatch(args.resume):  # a bare run id: find its directory under --out
            found = sorted(root.glob(f"*/*/{args.resume}")) if root.is_dir() else []
            if len(found) != 1:
                raise UsageError(f"expected exactly one run directory named {args.resume} under {root}, found {len(found)}")
            resume_dir = found[0]
        if resume_dir.resolve().parent.parent.parent != root.resolve():
            raise UsageError("--resume must be a run directory under --out")
        plan = plan_resume(resume_dir, config)
        run_options = RunOptions(**{**run_options.__dict__, "resumes": plan.crawl_run_id})
        start = [Request(url) for url in plan.urls]
    store = RunStore(root, config)
    result = run_source(config, adapter, fetcher, options=run_options, sink=store, start_requests=start)
    run_dir = store.finalize(result)
    problems = verify_run(run_dir)
    if problems:
        raise StoreError("stored run failed verification: " + "; ".join(problems))
    for key, value in (
        ("status", result.status), ("run_dir", run_dir.as_posix()), ("crawl_run_id", result.crawl_run["crawl_run_id"]),
        ("snapshots", len(result.snapshots)), ("errors", len(result.errors)), ("pending", len(result.pending)),
    ):
        print(f"{key}={value}", file=out)
    return 0


def _github_run_url() -> str | None:
    server, repo, run_id = (os.environ.get(k, "") for k in ("GITHUB_SERVER_URL", "GITHUB_REPOSITORY", "GITHUB_RUN_ID"))
    if server.startswith("https://") and re.fullmatch(r"[\w.-]+/[\w.-]+", repo) and run_id.isdigit():
        return f"{server}/{repo}/actions/runs/{run_id}"
    return None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m crawler.cli", description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="run one source config and store the evidence")
    run.add_argument("--source", required=True, help="source config name (file stem in the sources directory)")
    run.add_argument("--sources-dir", default=str(DEFAULT_SOURCES_DIR))
    run.add_argument("--out", default=str(DEFAULT_OUT))
    run.add_argument("--max-requests", type=int, default=500)
    run.add_argument("--resume", help="an earlier run (its directory under --out, or just its run_… id): fetch only its pending / temporarily failed URLs")
    run.add_argument("--trigger", choices=("manual", "schedule", "import", "other"), default="manual")
    sched = sub.add_parser("scheduled", help="print the sources a scheduled run covers, as JSON")
    sched.add_argument("--schedule", default=str(DEFAULT_SCHEDULE))
    return parser


def main(argv: Sequence[str] | None = None, *, fetcher: Fetcher | None = None, adapters: AdapterRegistry | None = None, out: TextIO | None = None, err: TextIO | None = None) -> int:
    out, err = out or sys.stdout, err or sys.stderr
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as exc:
        return int(exc.code) if isinstance(exc.code, int) else 2
    try:
        if args.command == "scheduled":
            print(json.dumps(scheduled_sources(Path(args.schedule))), file=out)
            return 0
        return run_command(args, fetcher or UrllibFetcher(), adapters or default_registry, out)
    except (UsageError, ConfigError, ResumeError, StoreError) as exc:
        print(f"error: {exc}", file=err)
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
