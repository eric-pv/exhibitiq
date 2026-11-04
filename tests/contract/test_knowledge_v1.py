"""Contract tests for the knowledge base (A1-09): taxonomy + BXR product cards."""
from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path

import pytest

import knowledge_check as kc
import package_check as pc

EX = pc.SCHEMA_DIR / "examples" / "knowledge"
KB = pc.ROOT / "knowledge"
DIMS = ["industry", "technology", "application", "capability", "problem", "need"]


def load(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def rules(errors):
    return {e.split()[0] for e in errors}


# ------------------------------------------------------------------ repository content
def test_knowledge_dir_is_valid():
    assert kc.check_knowledge_dir(KB) == []


def test_taxonomy_skeleton_has_all_six_dimensions():
    assert sorted(f.stem for f in (KB / "taxonomy").glob("*.json")) == sorted(DIMS)


def test_no_product_cards_without_owner_material():
    # A1-09 is structure only: product content needs Eric's approved source documents (A2-05).
    assert list((KB / "bxr-products").glob("*.json")) == []


# ------------------------------------------------------------------ examples
def test_examples_are_valid():
    tax = load(EX / "taxonomy.example.json")
    assert kc.check_taxonomy(tax) == []
    approved = {t["term_id"] for t in tax["terms"]}
    assert kc.check_product(load(EX / "bxr_product.example.json"), approved_terms=approved) == []


# ------------------------------------------------------------------ negative: schema
PRODUCT_NEGATIVE = [
    ("approved-without-approver", lambda d: d.update(approval_status="approved")),
    ("no-sources", lambda d: d.update(sources=[])),
    ("bad-product-id", lambda d: d.update(product_id="Police Box")),
    ("unknown-field", lambda d: d.update(price="TBD")),
    ("spec-without-source", lambda d: d["specifications"][0].pop("source_index")),
    ("bad-term-id", lambda d: d.update(capabilities=["Scenario Training"])),
    ("wrong-version", lambda d: d.update(schema_version="1.0.0-draft.3")),
]


@pytest.mark.parametrize("case,mut", PRODUCT_NEGATIVE, ids=[c[0] for c in PRODUCT_NEGATIVE])
def test_product_schema_rejects(case, mut):
    d = load(EX / "bxr_product.example.json")
    mut(d)
    assert "KB1" in rules(kc.check_product(d)), case


TAXONOMY_NEGATIVE = [
    ("unknown-dimension", lambda d: d.update(dimension="color")),
    ("approved-without-approver", lambda d: (d.pop("approved_by"), d.pop("approved_at"))),
    ("term-without-label", lambda d: d["terms"][0].pop("label")),
]


@pytest.mark.parametrize("case,mut", TAXONOMY_NEGATIVE, ids=[c[0] for c in TAXONOMY_NEGATIVE])
def test_taxonomy_schema_rejects(case, mut):
    d = load(EX / "taxonomy.example.json")
    mut(d)
    assert "KB1" in rules(kc.check_taxonomy(d)), case


# ------------------------------------------------------------------ negative: rules
def test_term_outside_dimension():
    d = load(EX / "taxonomy.example.json")
    d["terms"][0]["term_id"] = "industry.example"
    d["terms"][1]["parent_id"] = "industry.example"
    assert rules(kc.check_taxonomy(d)) == {"KB3"}


def test_missing_parent_and_duplicate_term():
    d = load(EX / "taxonomy.example.json")
    d["terms"][1]["parent_id"] = "capability.nowhere"
    assert rules(kc.check_taxonomy(d)) == {"KB3"}
    d = load(EX / "taxonomy.example.json")
    d["terms"].append(copy.deepcopy(d["terms"][0]))
    assert rules(kc.check_taxonomy(d)) == {"KB3"}


def test_field_must_reference_its_dimension():
    d = load(EX / "bxr_product.example.json")
    d["applications"] = ["capability.example-simulation"]
    assert rules(kc.check_product(d)) == {"KB4"}


def test_spec_source_must_exist():
    d = load(EX / "bxr_product.example.json")
    d["specifications"][0]["source_index"] = 3
    assert rules(kc.check_product(d)) == {"KB5"}


def test_approved_product_needs_approved_terms():
    d = load(EX / "bxr_product.example.json")
    d.update(approval_status="approved", approved_by="Eric", approved_at="2026-11-04")
    assert rules(kc.check_product(d, approved_terms=set())) == {"KB6"}
    assert kc.check_product(d, approved_terms={"capability.example-scenario-training"}) == []


def test_file_names_must_match_ids(tmp_path):
    (tmp_path / "taxonomy").mkdir()
    (tmp_path / "bxr-products").mkdir()
    shutil.copy(EX / "taxonomy.example.json", tmp_path / "taxonomy" / "industry.json")
    shutil.copy(EX / "bxr_product.example.json", tmp_path / "bxr-products" / "wrong-name.json")
    errs = kc.check_knowledge_dir(tmp_path)
    assert any("KB3" in e for e in errs) and any("KB4" in e for e in errs)


# ------------------------------------------------------------------ AR10: analysis may cite approved products only
def test_analysis_cannot_cite_unapproved_products(tmp_path):
    (tmp_path / "taxonomy").mkdir()
    (tmp_path / "bxr-products").mkdir()
    analysis = load(pc.SCHEMA_DIR / "examples" / "analysis" / "analysis_result.example.json")
    assert kc.check_analysis_products(analysis, tmp_path) == []  # example cites no product
    analysis["recommendations"][0]["product_ids"] = ["bxr-example-device"]
    assert rules(kc.check_analysis_products(analysis, tmp_path)) == {"AR10"}  # no card
    shutil.copy(EX / "bxr_product.example.json", tmp_path / "bxr-products" / "bxr-example-device.json")
    assert rules(kc.check_analysis_products(analysis, tmp_path)) == {"AR10"}  # draft card
    card = load(tmp_path / "bxr-products" / "bxr-example-device.json")
    card.update(approval_status="approved", approved_by="Eric", approved_at="2026-11-04")
    (tmp_path / "bxr-products" / "bxr-example-device.json").write_text(json.dumps(card), encoding="utf-8")
    assert kc.check_analysis_products(analysis, tmp_path) == []
