"""Regression outputs of the data-engineering modules (D3-08).

Runs every module end to end on fixed, synthetic inputs and returns its outputs as canonical JSON text, so that
``tests/data/test_regression.py`` can compare them byte for byte with the expected files in ``tests/data/regression/``.
A change in any module's behaviour (records, hashes, ordering, wording of notices) shows up as a diff of those files.

Inputs: the committed synthetic samples (``data/samples/``) and the CSV import pipeline of ``tests/data/test_assemble.py``
(fixed clock, fixed random source). Absolute paths are replaced by ``<repo>`` and ``<tmp>`` so the outputs do not depend on
where the repository or the temporary directory is.

When a change is intended, regenerate the expected files and review the diff in the PR::

    python -m tests.data.regression_outputs --write
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from collections.abc import Callable
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SAMPLES = ROOT / "data" / "samples"
EXPECTED_DIR = Path(__file__).resolve().parent / "regression"
FAIR = SAMPLES / "sample-fair" / "2026"
V1 = FAIR / "sample-fair-2026.20261104T010000Z"
V2 = FAIR / "sample-fair-2026.20261104T020000Z"
GENERATED_AT = datetime(2026, 11, 9, 0, 0, tzinfo=timezone.utc)
SCREENING_RULES = {  # chosen so that every label occurs on the sample: include, excluded, review, unscreened
    "name": "regression",
    "rules": [
        {"id": "optics-cyber", "field": "categories_as_listed", "op": "contains_any", "outcome": "include", "terms": ["optics", "cyber"]},
        {"id": "vehicles", "field": "categories_as_listed", "op": "contains_any", "outcome": "exclude", "terms": ["vehicles"]},
        {"id": "booth-b08", "field": "booth", "op": "equals_any", "outcome": "review", "terms": ["B-08"]},
    ],
}

def _text(value: Any, tmp: Path) -> str:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=1, allow_nan=False) + "\n"
    for path, label in ((tmp.resolve(), "<tmp>"), (tmp, "<tmp>"), (ROOT, "<repo>")):
        text = text.replace(path.as_posix(), label)
    return text


def _package_digest(directory: Path) -> dict[str, Any]:
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    return {k: manifest[k] for k in ("dataset_id", "content_hash", "files", "record_counts", "completeness_status", "schema_version")}


def _samples(tmp: Path) -> Any:
    import importlib.util  # noqa: PLC0415

    spec = importlib.util.spec_from_file_location("build_samples", SAMPLES / "build_samples.py")
    build_samples = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(build_samples)
    built = build_samples.build_all(tmp / "samples")
    return {"packages": [_package_digest(Path(p)) for p in sorted(built, key=lambda p: Path(p).name)]}


def _pipeline(tmp: Path) -> Any:
    from etl.assemble import OfficialCount, assemble_package  # noqa: PLC0415
    from tests.data.crawl_testkit import fixed_rand  # noqa: PLC0415
    from tests.data.test_assemble import pipeline  # noqa: PLC0415

    fixed_rand.counter = 0  # the test kit's id source is a process-wide counter: start from 0 so ids do not depend on earlier calls
    work = tmp / "pipeline"
    work.mkdir()
    kwargs = pipeline(work)
    package = assemble_package(work / "packages", **kwargs)
    # the same records with an official count the listing does not reach: completeness "partial"
    partial = assemble_package(work / "partial", **kwargs, official_count=OfficialCount(5, kwargs["sources"][0]["source_id"], date(2026, 11, 1)))
    return {"package": _package_digest(Path(package.path)), "partial": _package_digest(Path(partial.path)) | {"completeness": partial.manifest["completeness"]}}


def _validate(tmp: Path) -> Any:
    from etl.validate import validate_package  # noqa: PLC0415

    return {p.name: validate_package(p).to_dict() for p in sorted(SAMPLES.glob("*/*/*/"), key=lambda p: p.name)}


def _index(tmp: Path) -> Any:
    from etl.dataset_index import build_index, validate_index  # noqa: PLC0415

    index = build_index(SAMPLES, generated_at=GENERATED_AT, generator={"name": "exhibitiq-etl", "version": "1.0.0"}, locator_prefix="data/samples")
    problems = validate_index(index, packages_root=SAMPLES)
    if problems:
        raise AssertionError(f"index of the samples is invalid: {problems}")
    return index


def _history(tmp: Path) -> Any:
    from etl.history import build_history, latest_package_dirs  # noqa: PLC0415

    return build_history(latest_package_dirs(SAMPLES)).to_dict()


def _report(tmp: Path) -> Any:
    from etl.report import build_report  # noqa: PLC0415

    return {p.name: build_report(p) for p in sorted(SAMPLES.glob("*/*/*/"), key=lambda p: p.name)}


def _screening(tmp: Path) -> Any:
    from etl.screening import parse_rules, screen_package  # noqa: PLC0415

    return screen_package(V2, parse_rules(SCREENING_RULES))


def _catalog(tmp: Path) -> Any:
    from etl.catalog import diff_packages, edition_timeline, search_companies  # noqa: PLC0415

    return {
        "search_all": search_companies(SAMPLES),
        "search_alias": search_companies(SAMPLES, "SynOptics"),
        "timeline": edition_timeline(SAMPLES, "sample-fair", 2026),
        "diff": diff_packages(V1, V2),
    }


OUTPUTS: dict[str, Callable[[Path], Any]] = {
    "samples": _samples,
    "pipeline": _pipeline,
    "validate": _validate,
    "dataset_index": _index,
    "history": _history,
    "report": _report,
    "screening": _screening,
    "catalog": _catalog,
}


def compute(name: str) -> str:
    with tempfile.TemporaryDirectory(prefix="exhibitiq-regression-") as temp:
        tmp = Path(temp)
        return _text(OUTPUTS[name](tmp), tmp)


def expected_path(name: str) -> Path:
    return EXPECTED_DIR / f"{name}.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m tests.data.regression_outputs", description="Compare or rewrite the D3-08 regression outputs.")
    parser.add_argument("--write", action="store_true", help="rewrite tests/data/regression/*.json from the current code")
    args = parser.parse_args(argv)
    differ = []
    for name in OUTPUTS:
        text = compute(name)
        path = expected_path(name)
        if args.write:
            EXPECTED_DIR.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8", newline="\n")
            print(f"wrote {path}")
        elif not path.is_file() or path.read_text(encoding="utf-8") != text:
            differ.append(name)
    if differ:
        print("differ from the expected files: " + ", ".join(differ), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
