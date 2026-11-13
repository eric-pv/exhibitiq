"""Tests for etl.screening (D2-10): labels only, nothing deleted."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from etl.package import read_package
from etl.screening import RuleSet, ScreeningError, load_rules, parse_rules, save_screening, screen_package, screen_records

V2 = Path(__file__).resolve().parents[2] / "data" / "samples" / "sample-fair" / "2026" / "sample-fair-2026.20261104T020000Z"


def rules(*items, name="t"):
    return parse_rules({"name": name, "rules": list(items)})


def rule(id, field, op, outcome, terms=None, **kw):
    item = {"id": id, "field": field, "op": op, "outcome": outcome, **kw}
    if terms is not None:
        item["terms"] = terms
    return item


P = lambda n, **kw: {"participation_id": f"pt_{n}", "company_id": f"co_{n}", **kw}  # noqa: E731
C = lambda n, **kw: {"company_id": f"co_{n}", **kw}  # noqa: E731


def labels(parts, companies, rs):
    return {k: v["label"] for k, v in screen_records(parts, companies, rs).items()}


def test_labels_for_each_outcome():
    rs = rules(rule("inc", "categories_as_listed", "contains_any", "include", ["Optic", "laser"]), rule("exc", "booth", "equals_any", "exclude", ["x1"]), rule("rev", "hall", "present", "review"))
    parts = [P(1, categories_as_listed=["Precision OPTICS"]), P(2, booth="X1"), P(3, hall="2"), P(4, booth="A1"), P(5, categories_as_listed=["laser"], booth="x1")]
    assert labels(parts, [], rs) == {"pt_1": "include", "pt_2": "excluded", "pt_3": "review", "pt_4": "unscreened", "pt_5": "review"}  # include + exclude -> a person decides


def test_matched_rules_are_listed_and_company_fields_work():
    rs = rules(rule("c", "company.country", "equals_any", "include", ["zz"]), rule("d", "company.description", "absent", "review"))
    result = screen_records([P(1), P(2)], [C(1, country="ZZ", description="x"), C(2)], rs)
    assert result["pt_1"] == {"label": "include", "matched_rules": ["c"]} and result["pt_2"] == {"label": "review", "matched_rules": ["d"]}


def test_missing_company_is_treated_as_empty_not_an_error():
    assert labels([P(9)], [], rules(rule("a", "company.website", "absent", "review"))) == {"pt_9": "review"}


@pytest.mark.parametrize("op,value,expected", [("present", "", False), ("present", [], False), ("present", None, False), ("present", ["a"], True), ("absent", "", True), ("absent", "a", False)])
def test_present_and_absent_ignore_empty_values(op, value, expected):
    rs = rules(rule("r", "booth", op, "review"))
    assert (labels([P(1, booth=value)], [], rs)["pt_1"] == "review") is expected


def test_equals_is_exact_contains_is_substring():
    parts = [P(1, booth="A10")]
    assert labels(parts, [], rules(rule("e", "booth", "equals_any", "include", ["a1"])))["pt_1"] == "unscreened"
    assert labels(parts, [], rules(rule("c", "booth", "contains_any", "include", ["a1"])))["pt_1"] == "include"


def test_nothing_is_removed_or_changed():
    parts, companies = [P(1, booth="X1"), P(2)], [C(1), C(2)]
    before = copy.deepcopy((parts, companies))
    result = screen_records(parts, companies, rules(rule("x", "booth", "equals_any", "exclude", ["x1"])))
    assert set(result) == {"pt_1", "pt_2"} and (parts, companies) == before  # the excluded one is still reported, and the inputs are untouched


@pytest.mark.parametrize(
    "data,message",
    [
        ({"rules": [rule("a", "booth", "present", "include")]}, "`name`"),
        ({"name": "x", "rules": []}, "at least one"),
        ({"name": "x", "extra": 1, "rules": [rule("a", "booth", "present", "include")]}, "only contain"),
        ({"name": "x", "rules": [rule("A", "booth", "present", "include")]}, "id must"),
        ({"name": "x", "rules": [rule("a", "booth", "present", "include"), rule("a", "hall", "present", "include")]}, "unique"),
        ({"name": "x", "rules": [rule("a", "Bad Field", "present", "include")]}, "field"),
        ({"name": "x", "rules": [rule("a", "booth", "like", "include")]}, "op must"),
        ({"name": "x", "rules": [rule("a", "booth", "present", "delete")]}, "outcome"),
        ({"name": "x", "rules": [rule("a", "booth", "contains_any", "include")]}, "non-empty list"),
        ({"name": "x", "rules": [rule("a", "booth", "contains_any", "include", [" "])]}, "non-empty list"),
        ({"name": "x", "rules": [rule("a", "booth", "present", "include", ["t"])]}, "takes no terms"),
        ({"name": "x", "rules": [dict(rule("a", "booth", "present", "include"), color="red")]}, "unknown or missing"),
    ],
)
def test_bad_rules_are_rejected(data, message):
    with pytest.raises(ScreeningError, match=message):
        parse_rules(data)


def test_load_rules_from_toml(tmp_path):
    path = tmp_path / "r.toml"
    path.write_text('name = "demo"\n[[rules]]\nid = "o"\nfield = "booth"\nop = "present"\noutcome = "review"\n', encoding="utf-8")
    assert load_rules(path).rules[0].id == "o"
    with pytest.raises(ScreeningError, match="cannot read"):
        load_rules(tmp_path / "none.toml")
    path.write_text("[[", encoding="utf-8")
    with pytest.raises(ScreeningError, match="cannot read"):
        load_rules(path)


def test_fingerprint_changes_with_the_rules_not_the_name():
    a = rules(rule("r", "booth", "present", "review"), name="one")
    b = rules(rule("r", "booth", "present", "review"), name="two")
    c = rules(rule("r", "booth", "present", "include"))
    assert a.fingerprint() == b.fingerprint() != c.fingerprint()


def test_screen_package_over_the_sample_covers_every_participation(tmp_path):
    rs = rules(rule("any", "booth", "present", "include"), rule("gone", "listing_status", "equals_any", "exclude", ["removed"]))
    result = screen_package(V2, rs)
    package = read_package(V2)
    assert result["total"] == len(package.records["participations"]) == 5 and set(result["participations"]) == {p["participation_id"] for p in package.records["participations"]}
    assert result["kind"] == "rule_based" and "not an AI judgement" in result["note"] and result["data_origin"] == "synthetic" and sum(result["counts"].values()) == 5
    removed = next(p for p in package.records["participations"] if p["listing_status"] == "removed")
    assert result["participations"][removed["participation_id"]]["label"] == "review"  # booth present (include) and removed (exclude) conflict
    assert result["rules_fingerprint"] == rs.fingerprint()
    path = tmp_path / "s" / "out.json"
    save_screening(result, path)
    assert json.loads(path.read_text(encoding="utf-8")) == result and not list(path.parent.glob("*.tmp"))


def test_excluded_participations_stay_in_the_output_of_a_whole_package():
    result = screen_package(V2, rules(rule("gone", "listing_status", "equals_any", "exclude", ["removed"])))
    assert result["counts"]["excluded"] == 1 and result["total"] == 5 and len(result["participations"]) == 5
    assert sorted(v["label"] for v in result["participations"].values()).count("excluded") == 1


def test_failed_save_leaves_old_file(tmp_path, monkeypatch):
    import os

    path = tmp_path / "o.json"
    save_screening({"a": 1}, path)
    monkeypatch.setattr(os, "replace", lambda *a: (_ for _ in ()).throw(OSError("disk")))
    with pytest.raises(OSError):
        save_screening({"a": 2}, path)
    assert json.loads(path.read_text(encoding="utf-8")) == {"a": 1} and not list(tmp_path.glob("*.tmp"))
