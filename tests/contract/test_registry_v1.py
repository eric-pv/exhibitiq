"""Contract tests for exhibition registration (A1-10)."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

import package_check as pc
import registry_check as rc

EX = pc.SCHEMA_DIR / "examples" / "registry"
INDEX = pc.SCHEMA_DIR / "examples" / "index" / "dataset_index.example.json"


def load(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def rules(errors):
    return {e.split()[0] if not e.split()[0].endswith(":") else e.split()[1] for e in errors}


def test_example_registry_is_valid_and_matches_example_index():
    assert rc.check_registry_dir(EX) == []
    assert rc.check_registry_vs_index(EX, load(INDEX)) == []


def test_example_covers_accepted_and_rejected_duplicate():
    statuses = {k: v["registration_status"] for k, v in rc.load_registry(EX).items()}
    assert set(statuses.values()) == {"accepted", "rejected"}


NEGATIVE = [
    ("missing-years", lambda d: d.pop("years")),
    ("empty-years", lambda d: d.update(years=[])),
    ("duplicate-year", lambda d: d.update(years=[2026, 2026])),
    ("bad-id", lambda d: d.update(exhibition_id="Example Expo")),
    ("bad-website", lambda d: d.update(website="example.com")),
    ("bad-country", lambda d: d.update(country="Taiwan")),
    ("unknown-status", lambda d: d.update(registration_status="active")),
    ("unknown-channel", lambda d: d.update(request_channel="email")),
    ("local-time", lambda d: d.update(requested_at="2026-11-01T16:00:00+08:00")),
    ("unknown-field", lambda d: d.update(exhibitor_count=1200)),
    ("rejected-without-notes", lambda d: (d.update(registration_status="rejected"), d.pop("notes"))),
    ("wrong-version", lambda d: d.update(schema_version="1.0.0-draft.4")),
]


@pytest.mark.parametrize("case,mut", NEGATIVE, ids=[c[0] for c in NEGATIVE])
def test_schema_rejects(case, mut):
    d = load(EX / "example-expo" / "registration.json")
    mut(d)
    assert "RG1" in rules(rc.check_registration(d)), case


def test_registration_holds_no_source_facts():
    # Facts (dates, venue, counts) belong to the data package, not to the registration.
    props = set(pc.load_schemas()["exhibition_registration"]["properties"])
    assert not props & {"start_date", "end_date", "venue", "official_exhibitor_count", "source_ids", "verification_status"}


def test_folder_must_match_id(tmp_path):
    shutil.copytree(EX, tmp_path / "reg")
    (tmp_path / "reg" / "example-expo").rename(tmp_path / "reg" / "renamed")
    assert any("RG3" in e for e in rc.check_registry_dir(tmp_path / "reg"))


def test_folder_without_registration(tmp_path):
    shutil.copytree(EX, tmp_path / "reg")
    (tmp_path / "reg" / "empty-folder").mkdir()
    assert any("RG3" in e for e in rc.check_registry_dir(tmp_path / "reg"))


def test_duplicate_must_point_to_accepted_registration(tmp_path):
    shutil.copytree(EX, tmp_path / "reg")
    p = tmp_path / "reg" / "sample-fair-duplicate" / "registration.json"
    d = load(p)
    d["duplicate_of"] = "ghost-fair"
    p.write_text(json.dumps(d), encoding="utf-8")
    assert any("RG5" in e for e in rc.check_registry_dir(tmp_path / "reg"))


def test_duplicate_of_only_on_rejected():
    d = load(EX / "example-expo" / "registration.json")
    d["duplicate_of"] = "sample-fair"
    assert "RG4" in rules(rc.check_registration(d))


def test_index_must_list_exactly_accepted_registrations():
    idx = load(INDEX)
    idx["exhibitions"] = idx["exhibitions"][:1]
    assert any("missing from dataset index" in e for e in rc.check_registry_vs_index(EX, idx))
    idx = load(INDEX)
    idx["exhibitions"][1]["exhibition_id"] = "unregistered-fair"
    errs = rc.check_registry_vs_index(EX, idx)
    assert any("without an accepted registration" in e for e in errs)


def test_registered_years_need_editions_in_index(tmp_path):
    shutil.copytree(EX, tmp_path / "reg")
    p = tmp_path / "reg" / "example-expo" / "registration.json"
    d = load(p)
    d["years"] = [2026, 2027]
    p.write_text(json.dumps(d), encoding="utf-8")
    assert any("2027" in e for e in rc.check_registry_vs_index(tmp_path / "reg", load(INDEX)))
