"""Contract tests for the dataset-index schema v1 (A1-07)."""
from __future__ import annotations

import json

import pytest

import index_check as ic
import package_check as pc

EXAMPLE = pc.SCHEMA_DIR / "examples" / "index" / "dataset_index.example.json"


def base() -> dict:
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


def schema_errors(r) -> list:
    return list(pc.validator("dataset_index").iter_errors(r))


def _rules(errors):
    return {e.split()[0] for e in errors}


EX0, EX1 = ["exhibitions", 0], ["exhibitions", 1]
ED0 = EX0 + ["editions", 0]
DS0 = ED0 + ["datasets", 0]
ED1 = EX1 + ["editions", 0]


def _at(r, path):
    for p in path:
        r = r[p]
    return r


def _set(path, key, value):
    def f(r):
        _at(r, path)[key] = value
    return f


def _del(path, key):
    def f(r):
        del _at(r, path)[key]
    return f


# ------------------------------------------------------------------ positive
def test_example_is_valid():
    assert ic.check_index(base()) == []


def test_example_shows_success_and_failure():
    r = base()
    assert {e["acquisition"]["status"] for e in r["exhibitions"]} == {"feasible", "not_feasible"}
    assert {e["editions"][0]["last_acquisition"]["status"] for e in r["exhibitions"]} == {"succeeded", "failed"}
    assert _at(r, ED1)["latest_dataset_id"] is None


def test_schema_version_matches_version_file():
    assert pc.load_schemas()["dataset_index"]["properties"]["schema_version"]["const"] == pc.VERSION


# ------------------------------------------------------------------ negative: schema
SCHEMA_NEGATIVE = [
    ("missing-acquisition", _del(EX0, "acquisition")),
    ("unknown-method", _set(EX0 + ["acquisition"], "method", "scrape_anything")),
    ("assessed-without-report", _del(EX0 + ["acquisition"], "report_path")),
    ("not-feasible-without-notes", _del(EX1 + ["acquisition"], "notes")),
    ("failed-attempt-without-notes", _del(ED1 + ["last_acquisition"], "notes")),
    ("failed-attempt-with-dataset", _set(ED1 + ["last_acquisition"], "dataset_id", "sample-fair-2026.20261103T000000Z")),
    ("missing-latest-field", _del(ED0, "latest_dataset_id")),
    ("bad-storage", _set(DS0 + ["location"], "storage", "dropbox")),
    ("bare-content-hash", _set(DS0, "content_hash", "a" * 64)),
    ("validation-passed-without-validator", _del(DS0 + ["validation"], "validator")),
    ("validation-failed-without-messages", _set(DS0, "validation", {"status": "failed", "validated_at": "2026-11-03T00:05:00Z",
        "validator": {"name": "v", "version": "0"}, "error_count": 1})),
    ("unknown-field", _set(DS0, "row_count", 2)),
    ("wrong-schema-version", lambda r: r.update(schema_version="1.0.0-draft.2")),
    ("bad-notice-level", _set(["notices", 0], "level", "fatal")),
]


@pytest.mark.parametrize("case_id,mutation", SCHEMA_NEGATIVE, ids=[c[0] for c in SCHEMA_NEGATIVE])
def test_schema_rejects(case_id, mutation):
    r = base()
    assert schema_errors(r) == []
    mutation(r)
    assert schema_errors(r), f"{case_id} was not rejected"


# ------------------------------------------------------------------ negative: rules
def test_edition_outside_exhibition_detected():
    r = base()
    _at(r, ED1)["edition_id"] = "other-fair-2026"
    assert "IR3" in _rules(ic.check_index(r))


def test_duplicate_exhibition_detected():
    r = base()
    r["exhibitions"][1]["exhibition_id"] = "example-expo"
    _at(r, ED1)["edition_id"] = "example-expo-2025"
    _at(r, ED1)["year"] = 2025
    r["notices"][0]["exhibition_id"] = "example-expo"
    assert _rules(ic.check_index(r)) == {"IR3"}


def test_latest_must_be_newest_passed_dataset():
    r = base()
    _at(r, ED0)["latest_dataset_id"] = None
    assert _rules(ic.check_index(r)) == {"IR4"}


def test_failed_validation_cannot_be_latest():
    r = base()
    _at(r, DS0)["validation"] = {"status": "failed", "validated_at": "2026-11-03T00:05:00Z",
                                 "validator": {"name": "v", "version": "0"}, "error_count": 1, "messages": ["R8 content_hash"]}
    assert "IR4" in _rules(ic.check_index(r))


def test_summary_must_match_manifest():
    r = base()
    _at(r, DS0)["record_counts"]["companies"] = 5
    _at(r, DS0)["completeness_status"] = "complete"
    assert _rules(ic.check_index(r)) == {"IR6"}


def test_missing_package_detected():
    r = base()
    _at(r, DS0)["location"]["locator"] = "data/packages/nowhere"
    assert "IR6" in _rules(ic.check_index(r))


def test_last_acquisition_dataset_must_be_listed():
    r = base()
    _at(r, ED0)["last_acquisition"]["dataset_id"] = "example-expo-2026.20261104T000000Z"
    assert _rules(ic.check_index(r)) == {"IR5"}


def test_notice_reference_detected():
    r = base()
    r["notices"][0]["exhibition_id"] = "ghost-expo"
    assert _rules(ic.check_index(r)) == {"IR7"}
