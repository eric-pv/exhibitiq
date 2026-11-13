"""Tests for the data-package validator (D1-05).

Positive vector: the contract's example package (synthetic). Negative vectors:
for every rule R1-R11, a package built to violate that rule. Each case states the
EXACT set of rules expected, so a case proves the targeted rule fires and that
nothing else fires by accident (integrity fields are recomputed after each edit).
"""
from __future__ import annotations

import copy
import json
import socket
import subprocess
import sys
from pathlib import Path
from typing import Callable

import pytest

from etl.jsonl import canonical_line
from etl.package import DATA_FILES, MANIFEST_FILE, RECORD_SETS, compute_integrity, read_package, write_manifest
from etl.schema_registry import SchemaSet
from etl.validate import Report, main, validate_package

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "schemas" / "v1" / "examples" / "package"
CHANGE_EXAMPLE = ROOT / "schemas" / "v1" / "examples" / "change.example.json"

SRC1 = "src_01JCS000000000000000000001"
SRC_UNKNOWN = "src_01JCS000000000000000000009"
CO_UNKNOWN = "co_01JCC000000000000000000009"
RUN_UNKNOWN = "run_01JCR000000000000000000009"
PREVIOUS_DATASET = "example-expo-2026.20261101T000000Z"

Model = dict
Edit = Callable[[Model], None]


def load_model() -> Model:
    pkg = read_package(EXAMPLE)
    model: Model = {"manifest": copy.deepcopy(pkg.manifest), "exhibition": [pkg.exhibition], "edition": [pkg.edition]}
    for short in RECORD_SETS:
        model[short] = copy.deepcopy(pkg.records[short])
    return model


def build(
    tmp_path: Path,
    *,
    edit: Edit | None = None,
    raw: Callable[[dict[str, bytes]], None] | None = None,
    manifest_post: Callable[[dict], None] | None = None,
    tamper: Callable[[dict[str, bytes]], None] | None = None,
    sort: bool = True,
) -> Path:
    """Write a package from the example, apply edits, recompute integrity, return its directory.

    ``edit`` changes the model; ``raw`` changes file bytes before integrity is recomputed;
    ``manifest_post`` changes the manifest after integrity; ``tamper`` changes file bytes after.
    """
    model = load_model()
    if edit:
        edit(model)
    out = tmp_path / "pkg"
    out.mkdir()
    files: dict[str, bytes] = {
        "exhibition.json": "".join(canonical_line(r) for r in model["exhibition"]).encode("utf-8"),
        "edition.json": "".join(canonical_line(r) for r in model["edition"]).encode("utf-8"),
    }
    for short, (name, key) in RECORD_SETS.items():
        rows = sorted(model[short], key=lambda r: r[key].encode("utf-8")) if sort else model[short]
        files[name] = "".join(canonical_line(r) for r in rows).encode("utf-8")
    if raw:
        raw(files)
    for name, data in files.items():
        (out / name).write_bytes(data)
    manifest = model["manifest"]
    try:
        manifest.update(compute_integrity(out))
    except ValueError:
        pass  # e.g. a file without a final newline: leave the manifest stale on purpose
    if manifest_post:
        manifest_post(manifest)
    write_manifest(out / MANIFEST_FILE, manifest)
    if tamper:
        files = {name: (out / name).read_bytes() for name in DATA_FILES}
        tamper(files)
        for name, data in files.items():
            (out / name).write_bytes(data)
    return out


def rules_of(report: Report) -> set[str]:
    return report.rules()


# --------------------------------------------------------------------------- positive


def test_example_package_has_no_findings() -> None:
    report = validate_package(EXAMPLE)
    assert report.ok and report.findings == [], report.text()
    assert report.schema_version == (ROOT / "schemas" / "v1" / "VERSION").read_text(encoding="utf-8").strip()


def test_rebuilt_example_has_no_findings(tmp_path: Path) -> None:
    report = validate_package(build(tmp_path))
    assert report.ok, report.text()


def test_removed_participation_with_matching_count_is_valid(tmp_path: Path) -> None:
    def edit(m: Model) -> None:
        m["participations"][1]["listing_status"] = "removed"
        m["manifest"]["completeness"]["collected_participation_count"] = 1

    assert validate_package(build(tmp_path, edit=edit)).ok


def test_package_with_changes_for_a_later_dataset_is_valid(tmp_path: Path) -> None:
    def edit(m: Model) -> None:
        change = json.loads(CHANGE_EXAMPLE.read_text(encoding="utf-8"))
        change.update(dataset_id=m["manifest"]["dataset_id"], previous_dataset_id=PREVIOUS_DATASET, source_ids=[SRC1])
        m["manifest"]["previous_dataset_id"] = PREVIOUS_DATASET
        m["changes"] = [change]

    report = validate_package(build(tmp_path, edit=edit))
    assert report.ok, report.text()


@pytest.mark.parametrize("version", SchemaSet().accepted)
def test_every_accepted_schema_version_is_valid(tmp_path: Path, version: str) -> None:
    """R3 follows schemas/v1/COMPATIBILITY.json: older accepted drafts stay valid without rewriting."""
    report = validate_package(build(tmp_path, edit=lambda m: m["manifest"].update(schema_version=version)))
    assert report.ok, report.text()


# --------------------------------------------------------------------------- R1


@pytest.mark.parametrize("name", [MANIFEST_FILE, *DATA_FILES])
def test_r1_each_missing_file_is_reported(tmp_path: Path, name: str) -> None:
    out = build(tmp_path)
    (out / name).unlink()
    report = validate_package(out)
    assert rules_of(report) == {"R1"}
    assert [f.file for f in report.findings] == [name]


# --------------------------------------------------------------- R2-R11: edit-based cases

CASES: list[tuple[str, Edit, set[str]]] = []


def case(label: str, expected: set[str]):
    def register(fn: Edit) -> Edit:
        CASES.append((label, fn, expected))
        return fn

    return register


# R2 / R3
@case("R2 manifest lacks a required field", {"R2"})
def _(m):
    del m["manifest"]["producer"]


@case("R2 manifest has an unknown field", {"R2"})
def _(m):
    m["manifest"]["surprise"] = 1


@case("R3 schema_version differs from VERSION (the const also fails R2)", {"R2", "R3"})
def _(m):
    m["manifest"]["schema_version"] = "1.0.0-draft.2"


# R4
@case("R4 company lacks a required field", {"R4"})
def _(m):
    del m["companies"][0]["name"]


@case("R4 company has an undefined field", {"R4"})
def _(m):
    m["companies"][0]["undefined_field"] = "x"


@case("R4 participation lacks a required field", {"R4"})
def _(m):
    del m["participations"][0]["participation_type"]


@case("R4 exhibition.json has two records", {"R4"})
def _(m):
    m["exhibition"].append(copy.deepcopy(m["exhibition"][0]))


@case("R4 edition.json is empty", {"R4"})
def _(m):
    m["edition"].clear()


@case("R4 exhibition.json lacks a required field", {"R4"})
def _(m):
    del m["exhibition"][0]["name"]


@case("R4 edition.json lacks a required field", {"R4"})
def _(m):
    del m["edition"][0]["verification_status"]


@case("R4 source lacks the url that a non-manual source needs", {"R4"})
def _(m):
    del m["sources"][0]["url"]


@case("R4 crawl run has an invalid status", {"R4"})
def _(m):
    m["crawl_runs"][0]["status"] = "done"


# R6
@case("R6 duplicate primary key", {"R6"})
def _(m):
    m["companies"].append(copy.deepcopy(m["companies"][0]))


# R9
@case("R9 manifest.exhibition_id differs from exhibition.json and edition.json", {"R9"})
def _(m):
    m["manifest"]["exhibition_id"] = "other-expo"


@case("R9 only exhibition.json has a different exhibition_id", {"R9"})
def _(m):
    m["exhibition"][0]["exhibition_id"] = "other-expo"


@case("R9 only edition.json has a different edition_id", {"R9"})
def _(m):
    m["edition"][0]["edition_id"] = "example-expo-2027"


@case("R9 only edition.json has a different exhibition_id", {"R9"})
def _(m):
    m["edition"][0]["exhibition_id"] = "other-expo"


@case("R9 edition year differs from manifest.edition_year", {"R9"})
def _(m):
    m["edition"][0]["year"] = 2027


@case("R9 dataset_id does not start with '<edition_id>.'", {"R9"})
def _(m):
    m["manifest"]["dataset_id"] = "other-2026.20261103T000000Z"


# R10
@case("R10 company cites an unknown source", {"R10"})
def _(m):
    m["companies"][1]["source_ids"] = [SRC_UNKNOWN]


@case("R10 field_sources cites an unknown source", {"R10"})
def _(m):
    m["participations"][0]["field_sources"] = {"booth": [SRC_UNKNOWN]}


@case("R10 alias cites an unknown source", {"R10"})
def _(m):
    m["companies"][0]["aliases"][0]["source_ids"] = [SRC_UNKNOWN]


@case("R10 edition.json cites an unknown source", {"R10"})
def _(m):
    m["edition"][0]["source_ids"] = [SRC_UNKNOWN]


@case("R10 exhibition.json cites an unknown source", {"R10"})
def _(m):
    m["exhibition"][0]["source_ids"] = [SRC_UNKNOWN]


@case("R10 manifest.source_snapshot_ids misses a source", {"R10"})
def _(m):
    m["manifest"]["source_snapshot_ids"] = m["manifest"]["source_snapshot_ids"][:1]


@case("R10 manifest.crawl_run_ids differs from crawl_runs.jsonl", {"R10"})
def _(m):
    m["manifest"]["crawl_run_ids"] = []


@case("R10 participation points to an unknown company", {"R10"})
def _(m):
    m["participations"][0]["company_id"] = CO_UNKNOWN


@case("R10 merged_into points to an unknown company", {"R10"})
def _(m):
    m["companies"][1].update(status="merged", merged_into=CO_UNKNOWN)


@case("R10 source points to an unknown crawl run", {"R10"})
def _(m):
    m["sources"][0]["crawl_run_id"] = RUN_UNKNOWN


@case("R10 participation edition_id differs from the manifest", {"R10"})
def _(m):
    m["participations"][0]["edition_id"] = "example-expo-2025"


@case("R10 crawl run edition_id differs from the manifest", {"R10"})
def _(m):
    m["crawl_runs"][0]["edition_id"] = "example-expo-2025"


def _with_change(m: Model, **overrides) -> None:
    change = json.loads(CHANGE_EXAMPLE.read_text(encoding="utf-8"))
    change.update(dataset_id=m["manifest"]["dataset_id"], previous_dataset_id=PREVIOUS_DATASET, source_ids=[SRC1])
    change.update(overrides)
    m["manifest"]["previous_dataset_id"] = PREVIOUS_DATASET
    m["changes"] = [change]


@case("R10 change dataset_id differs from the manifest", {"R10"})
def _(m):
    _with_change(m, dataset_id="example-expo-2026.20261105T000000Z")


@case("R10 change previous_dataset_id differs from the manifest", {"R10"})
def _(m):
    _with_change(m, previous_dataset_id="example-expo-2026.20261031T000000Z")


@case("R10 change cites an unknown source", {"R10"})
def _(m):
    _with_change(m, source_ids=[SRC_UNKNOWN])


@case("R10 first dataset (previous_dataset_id null) has changes", {"R10"})
def _(m):
    change = json.loads(CHANGE_EXAMPLE.read_text(encoding="utf-8"))
    change.update(dataset_id=m["manifest"]["dataset_id"], source_ids=[SRC1])
    m["changes"] = [change]  # manifest.previous_dataset_id stays null; the change keeps a (valid) string


# R11
@case("R11 collected_participation_count differs from listed participations", {"R11"})
def _(m):
    m["manifest"]["completeness"]["collected_participation_count"] = 5


@case("R11 official_count_source_id is not in sources.jsonl", {"R11"})
def _(m):
    m["manifest"]["completeness"]["official_count_source_id"] = SRC_UNKNOWN


@case("R11 status complete but official count differs from listed participations", {"R11"})
def _(m):
    m["manifest"]["completeness_status"] = "complete"  # official count stays 3, listed is 2


@case("R11 official count without a source", {"R11"})
def _(m):
    m["manifest"]["completeness"]["official_count_source_id"] = None


@case("R11 a removed participation is not counted as listed", {"R11"})
def _(m):
    m["participations"][1]["listing_status"] = "removed"  # collected_participation_count stays 2


@pytest.mark.parametrize("label, edit, expected", CASES, ids=[c[0] for c in CASES])
def test_rule_cases(tmp_path: Path, label: str, edit: Edit, expected: set[str]) -> None:
    report = validate_package(build(tmp_path, edit=edit))
    assert rules_of(report) == expected, report.text()


# --------------------------------------------------------------- R5, R6, R7, R8, R2: byte-level cases


def _prefix(name: str, prefix: bytes) -> Callable[[dict[str, bytes]], None]:
    return lambda files: files.__setitem__(name, prefix + files[name])


RAW_CASES: list[tuple[str, Callable[[dict[str, bytes]], None], set[str]]] = [
    ("R5 UTF-8 BOM", _prefix("companies.jsonl", b"\xef\xbb\xbf"), {"R5"}),
    ("R5 CRLF line endings", lambda f: f.__setitem__("companies.jsonl", f["companies.jsonl"].replace(b"\n", b"\r\n")), {"R5"}),
    ("R5 valid JSON that is not canonical", lambda f: f.__setitem__("companies.jsonl", f["companies.jsonl"].replace(b'":', b'": ', 1)), {"R5"}),
    ("R5 blank line", lambda f: f.__setitem__("companies.jsonl", f["companies.jsonl"] + b"\n"), {"R5"}),
    ("R5 invalid JSON line", lambda f: f.__setitem__("companies.jsonl", b'{"company_id":\n'), {"R5"}),
    ("R5 duplicate object key", lambda f: f.__setitem__("companies.jsonl", b'{"a":1,"a":2}\n'), {"R5"}),
    ("R5 non-UTF-8 bytes", lambda f: f.__setitem__("sources.jsonl", b"\xff\xfe\n"), {"R5"}),
    ("R5 single-record file is not canonical", lambda f: f.__setitem__("exhibition.json", f["exhibition.json"].replace(b'":', b'": ', 1)), {"R5"}),
    ("R5 missing final newline (integrity cannot be computed, so R8 also fires)", lambda f: f.__setitem__("companies.jsonl", f["companies.jsonl"].rstrip(b"\n")), {"R5", "R8"}),
]


@pytest.mark.parametrize("label, raw, expected", RAW_CASES, ids=[c[0] for c in RAW_CASES])
def test_byte_level_cases(tmp_path: Path, label: str, raw: Callable, expected: set[str]) -> None:
    report = validate_package(build(tmp_path, raw=raw))
    assert rules_of(report) == expected, report.text()


def test_r2_unreadable_manifest(tmp_path: Path) -> None:
    out = build(tmp_path)
    (out / MANIFEST_FILE).write_bytes(b"{")
    assert rules_of(validate_package(out)) == {"R2"}


@pytest.mark.parametrize(
    "edit, flagged_file",
    [
        (lambda m: m["exhibition"][0].__setitem__("exhibition_id", "other-expo"), "exhibition.json"),
        (lambda m: m["edition"][0].__setitem__("edition_id", "example-expo-2027"), "edition.json"),
        (lambda m: m["edition"][0].__setitem__("exhibition_id", "other-expo"), "edition.json"),
        (lambda m: m["edition"][0].__setitem__("year", 2027), "edition.json"),
    ],
    ids=["exhibition.exhibition_id", "edition.edition_id", "edition.exhibition_id", "edition.year"],
)
def test_r9_names_the_file_that_disagrees_with_the_manifest(tmp_path: Path, edit: Edit, flagged_file: str) -> None:
    report = validate_package(build(tmp_path, edit=edit))
    assert [(f.rule, f.file) for f in report.findings] == [("R9", flagged_file)]


def test_r10_first_dataset_rule_has_its_own_message(tmp_path: Path) -> None:
    def edit(m: Model) -> None:
        change = json.loads(CHANGE_EXAMPLE.read_text(encoding="utf-8"))
        change.update(dataset_id=m["manifest"]["dataset_id"], source_ids=[SRC1])
        m["changes"] = [change]

    report = validate_package(build(tmp_path, edit=edit))
    assert any("first dataset" in f.message for f in report.findings), report.text()


def test_r6_unsorted_records(tmp_path: Path) -> None:
    report = validate_package(build(tmp_path, sort=False, edit=lambda m: m["companies"].reverse()))
    assert rules_of(report) == {"R6"}
    assert "not sorted" in report.text()


def test_r7_record_counts_mismatch(tmp_path: Path) -> None:
    report = validate_package(build(tmp_path, manifest_post=lambda m: m["record_counts"].update(companies=5)))
    assert rules_of(report) == {"R7"}


TAMPER_CASES = [
    ("a data file changed after the manifest was written", lambda f: f.__setitem__("companies.jsonl", f["companies.jsonl"].replace(b"Synthetic Simulation", b"Synthetic Simulatior", 1))),
]


@pytest.mark.parametrize("label, tamper", TAMPER_CASES, ids=[c[0] for c in TAMPER_CASES])
def test_r8_tampered_file(tmp_path: Path, label: str, tamper: Callable) -> None:
    report = validate_package(build(tmp_path, tamper=tamper))
    assert rules_of(report) == {"R8"}
    assert any("sha256" in f.message for f in report.findings) and any("content_hash" in f.message for f in report.findings)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda m: m["files"]["companies.jsonl"].update(sha256="sha256:" + "0" * 64),
        lambda m: m["files"]["companies.jsonl"].update(bytes=1),
        lambda m: m["files"]["companies.jsonl"].update(records=9),
        lambda m: m.update(content_hash="sha256:" + "0" * 64),
    ],
    ids=["files.sha256", "files.bytes", "files.records", "content_hash"],
)
def test_r8_wrong_manifest_integrity_fields(tmp_path: Path, mutate: Callable) -> None:
    assert rules_of(validate_package(build(tmp_path, manifest_post=mutate))) == {"R8"}


# --------------------------------------------------------------------------- behavior


def test_all_findings_are_reported_not_just_the_first(tmp_path: Path) -> None:
    def edit(m: Model) -> None:
        del m["companies"][0]["name"]  # R4
        m["manifest"]["completeness"]["collected_participation_count"] = 9  # R11
        m["edition"][0]["year"] = 2030  # R9
        m["participations"][0]["company_id"] = CO_UNKNOWN  # R10

    assert rules_of(validate_package(build(tmp_path, edit=edit))) == {"R4", "R9", "R10", "R11"}


def test_findings_are_ordered_and_locate_the_problem(tmp_path: Path) -> None:
    def edit(m: Model) -> None:
        del m["companies"][1]["name"]
        m["manifest"]["completeness"]["collected_participation_count"] = 9

    report = validate_package(build(tmp_path, edit=edit))
    assert [f.rule for f in report.findings] == ["R4", "R11"]
    assert (report.findings[0].file, report.findings[0].line) == ("companies.jsonl", 2)
    assert "name" in report.findings[0].message


def test_validation_is_deterministic(tmp_path: Path) -> None:
    out = build(tmp_path, edit=lambda m: m["companies"][0].pop("name"))
    assert validate_package(out).to_dict() == validate_package(out).to_dict()


@pytest.mark.parametrize(
    "manifest",
    [
        {"record_counts": "x", "files": [], "completeness": 5, "source_snapshot_ids": "x"},
        {},
        {"files": {"companies.jsonl": "x"}, "content_hash": 5},
    ],
)
def test_garbage_manifest_values_do_not_crash(tmp_path: Path, manifest: dict) -> None:
    out = build(tmp_path)
    (out / MANIFEST_FILE).write_text(json.dumps(manifest), encoding="utf-8")
    report = validate_package(out)
    assert not report.ok and "R2" in report.rules()


def test_validator_makes_no_network_connection(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*args, **kwargs):  # pragma: no cover - only runs on regression
        raise AssertionError("the validator must not use the network")

    monkeypatch.setattr(socket, "socket", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    assert validate_package(EXAMPLE).ok


# --------------------------------------------------------------------------- command line


def test_cli_exit_codes_and_output(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main([str(EXAMPLE)]) == 0
    assert capsys.readouterr().out.startswith("OK ")
    bad = build(tmp_path, edit=lambda m: m["companies"][0].pop("name"))
    assert main([str(bad)]) == 1
    assert "R4" in capsys.readouterr().out
    assert main([str(EXAMPLE), "--schemas", str(tmp_path / "no-schemas")]) == 2
    assert "error:" in capsys.readouterr().err


def test_cli_json_output(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    bad = build(tmp_path, edit=lambda m: m["companies"][0].pop("name"))
    assert main([str(bad), "--json"]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False and payload["findings"][0]["rule"] == "R4"


def test_module_runs_from_the_command_line() -> None:
    result = subprocess.run([sys.executable, "-m", "etl.validate", str(EXAMPLE)], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0 and result.stdout.startswith("OK "), result.stdout + result.stderr
