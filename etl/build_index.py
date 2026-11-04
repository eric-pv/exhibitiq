"""Command line: build and write the dataset index the Dashboard reads (D2-12).

    python -m etl.build_index [--packages data/packages] [--out data/index/datasets.json]
                              [--assessments data/index/assessments.json] [--runs-dir data/raw] [--locator-prefix data/packages]

``assessments.json`` is ``{exhibition_id: {name, method, status, assessed_at, report_path, notes}}``, written by people after
a source assessment (see source-assessment-process.md). ``--runs-dir`` (a ``crawler.store`` directory) is scanned for runs
whose acquisition did not become part of any package, so failures show up in the index. Exit codes: 0 written, 2 invalid
input or an invalid index (nothing written).
"""
from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from etl.dataset_index import build_index, write_index


def load_assessments(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"cannot read assessments {path}: {exc}") from None
    if not isinstance(data, dict) or not all(isinstance(v, dict) for v in data.values()):
        raise ValueError(f"{path}: expected an object of objects keyed by exhibition_id")
    return data


def load_runs(runs_dir: Path) -> list[dict[str, Any]]:
    """Every ``crawl_run.json`` under a ``crawler.store`` directory (``<root>/<exhibition>/<edition>/<run>/``)."""
    runs = []
    for path in sorted(runs_dir.glob("*/*/run_*/crawl_run.json")) if runs_dir.is_dir() else []:
        try:
            runs.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError) as exc:
            raise ValueError(f"cannot read {path}: {exc}") from None
    return runs


def main(argv: Sequence[str] | None = None, *, now: datetime | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m etl.build_index", description="Build data/index/datasets.json from data packages.")
    parser.add_argument("--packages", default="data/packages")
    parser.add_argument("--out", default="data/index/datasets.json")
    parser.add_argument("--assessments", default="data/index/assessments.json")
    parser.add_argument("--runs-dir", default="data/raw")
    parser.add_argument("--locator-prefix", default="data/packages")
    args = parser.parse_args(argv)
    try:
        packages = Path(args.packages)
        index = build_index(
            packages, generated_at=now or datetime.now(timezone.utc), generator={"name": "exhibitiq-etl", "version": "1.0.0"},
            assessments=load_assessments(Path(args.assessments)), extra_runs=_unpackaged_runs(Path(args.runs_dir), packages), locator_prefix=args.locator_prefix,
        )
        write_index(index, args.out, packages_root=packages)
    except (ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    editions = sum(len(e["editions"]) for e in index["exhibitions"])
    print(f"wrote {args.out}: {len(index['exhibitions'])} exhibition(s), {editions} edition(s), {len(index['notices'])} notice(s)")
    return 0


def _unpackaged_runs(runs_dir: Path, packages: Path) -> list[dict[str, Any]]:
    """Runs from the evidence store that no package lists, so their outcome (often a failure) is not lost."""
    in_packages: set[str] = set()
    for manifest in packages.glob("*/*/*/manifest.json") if packages.is_dir() else []:
        try:
            in_packages.update(json.loads(manifest.read_text(encoding="utf-8")).get("crawl_run_ids", []))
        except (OSError, ValueError):
            continue
    return [r for r in load_runs(runs_dir) if r.get("crawl_run_id") not in in_packages]


if __name__ == "__main__":
    sys.exit(main())
