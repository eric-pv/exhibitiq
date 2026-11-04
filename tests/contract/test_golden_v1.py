"""A2-02: golden integration samples must satisfy every contract."""
from __future__ import annotations

import json

import analysis_check as ac
import index_check as ic
import knowledge_check as kc
import package_check as pc

G = pc.ROOT / "data" / "samples" / "golden" / "v1"


def load(p):
    return json.loads(p.read_text(encoding="utf-8"))


def test_golden_package_is_valid():
    assert pc.check_package(G / "package") == []


def test_golden_index_is_valid():
    assert ic.check_index(load(G / "dataset_index.json")) == []


def test_golden_analysis_is_valid():
    a = load(G / "expected" / "analysis" / "analysis_result.json")
    assert ac.check_analysis(a, G / "package") == []
    assert kc.check_analysis_products(a, pc.ROOT / "knowledge") == []


def test_golden_differs_in_structure_from_examples():
    # Two differently structured synthetic datasets (generality acceptance, spec §8.1).
    parts = [json.loads(l) for l in (G / "package" / "participations.jsonl").read_text().splitlines()]
    sources = [json.loads(l) for l in (G / "package" / "sources.jsonl").read_text().splitlines()]
    m = load(G / "package" / "manifest.json")
    assert {p["listing_status"] for p in parts} == {"listed", "removed"}
    assert "csv_import" in {s["source_type"] for s in sources}
    assert m["completeness_status"] == "unknown" and m["completeness"]["official_exhibitor_count"] is None
    assert m["data_origin"] == "synthetic"
