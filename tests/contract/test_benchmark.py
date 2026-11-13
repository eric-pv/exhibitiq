"""A3-07: known-relationship list (human benchmark) format and comparison with relate()."""
import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "skills" / "exhibitiq" / "scripts"))
import profile_tools as pt  # noqa: E402

G = ROOT / "data" / "golden" / "v1" / "package"
KNOWN = ROOT / "data" / "golden" / "v1" / "known" / "known-relationships.csv"
TOOLS = ROOT / "skills" / "exhibitiq" / "scripts" / "exhibitiq_tools.py"
HEADER = "company_name,aliases,country,website,relationship,source,notes\n"


def _profile(signals):
    p = copy.deepcopy(pt.load_profile("default-library"))
    p["relationship_signals"] = signals
    return p


def test_sample_list_is_valid_and_strict_matching():
    rows, errors = pt.load_known(KNOWN)
    assert errors == [] and len(rows) == 3
    r = pt.benchmark(KNOWN, G, _profile({"competitor": ["Training"]}))
    e = {x["company_name"]: x for x in r["entries"]}
    assert e["Alpha Training Systems (Synthetic)"]["matched_by"] == "name"
    assert e["Beta Components"]["company_id"] is None  # no fuzzy matching: a different name is not the same company
    assert e["Omega Simulation (Synthetic)"]["company_id"] is None
    c = r["per_relationship"]["competitor"]
    assert c["known"] == 2 and c["in_package"] == 1 and c["detected"] == 1 and c["recall"] == 1.0
    assert r["per_relationship"]["partner"]["recall"] is None  # nothing to measure -> no number
    assert any("不完整" in n for n in r["notes"])


def test_missed_and_not_listed_are_reported_never_called_wrong(tmp_path):
    r = pt.benchmark(KNOWN, G, _profile({"competitor": ["Sensors"]}))  # flags Delta, misses Alpha
    c = r["per_relationship"]["competitor"]
    assert c["detected"] == 0 and c["recall"] == 0.0
    alpha = next(x for x in r["entries"] if x["company_id"])
    assert alpha["missed"] == ["competitor"]
    assert c["not_listed_candidates"] == ["co_01JDC000000000000000000004"]


def test_match_by_website_and_alias(tmp_path):
    f = tmp_path / "k.csv"
    f.write_text(HEADER + "Alpha Co,,,http://alpha.example/about,competitor,test,\nDelta,Delta Sensors (Synthetic),,,partner,test,\n", encoding="utf-8")
    r = pt.benchmark(f, G, _profile({}))
    assert [x["matched_by"] for x in r["entries"]] == ["website", "name"]


@pytest.mark.parametrize("body,needle", [
    ("name,relationship\nA,competitor\n", "missing column"),
    (HEADER + "A,,,,rival,src,\n", "not in"),
    (HEADER + "A,,,,competitor,,\n", "source is empty"),
    (HEADER + "A,,,,competitor,s,\na,,,,partner,s,\n", "duplicate"),
    (HEADER, "no data rows"),
])
def test_invalid_lists_are_rejected(tmp_path, body, needle):
    f = tmp_path / "k.csv"
    f.write_text(body, encoding="utf-8")
    _, errors = pt.load_known(f)
    assert any(needle in e for e in errors), errors
    with pytest.raises(ValueError):
        pt.benchmark(f, G)


def test_excel_bom_and_cli(tmp_path):
    f = tmp_path / "k.csv"
    f.write_bytes(("﻿" + HEADER + "測試企業,,TW,,competitor,公司內部認知,\n").encode("utf-8"))
    ok = subprocess.run([sys.executable, str(TOOLS), "validate-known", str(f)], capture_output=True, text=True)
    assert ok.returncode == 0 and json.loads(ok.stdout)["ok"]
    bad = tmp_path / "bad.csv"
    bad.write_text("x\n1\n", encoding="utf-8")
    assert subprocess.run([sys.executable, str(TOOLS), "validate-known", str(bad)], capture_output=True).returncode == 1
    out = subprocess.run([sys.executable, str(TOOLS), "benchmark", str(KNOWN), str(G)], capture_output=True, text=True, check=True)
    assert json.loads(out.stdout)["known_rows"] == 3


def test_owner_provided_competitor_list_is_valid():
    rows, errors = pt.load_known(ROOT / "knowledge" / "benchmarks" / "known-competitors.csv")
    assert errors == [] and len(rows) >= 19
    assert all(r["source"] for r in rows)
