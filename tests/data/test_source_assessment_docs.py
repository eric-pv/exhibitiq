"""Checks that the source-assessment process and template (D1-11) stay consistent with the contract.

These are documents, so the tests compare them with the things they describe:
the enum values in ``schemas/v1/`` (dataset index, source), the error codes in
``crawler.errors``, the ``SourceConfig`` loader (D1-07), and the path convention in
``docs/specs/dataset-index-contract.md``. They also guard the V2.3 rule that these
documents name no specific exhibition.
"""
from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from crawler.errors import ErrorCode
from crawler.source_config import ConfigError, parse_source_config

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs" / "data-platform"
PROCESS = DOCS / "source-assessment-process.md"
TEMPLATE = DOCS / "source-assessment-template.md"
INDEX_CONTRACT = ROOT / "docs" / "specs" / "dataset-index-contract.md"

FORBIDDEN_NAMES = re.compile(r"\b(mspo|tadte|eurosatory|dsei)\b", re.IGNORECASE)
RESERVED_HOSTS = {"example.com", "example.org", "example.net"}
EVIDENCE_LEVELS = ["已開啟頁面", "搜尋摘要", "人工回報", "未存取"]
REPORT_PATH = "docs/data-platform/<exhibition_id>-source-assessment.md"

TEMPLATE_SECTIONS = [
    "基本資訊", "結論", "候選來源", "各來源評估", "使用條款與限制", "完整度可行性",
    "取得方式決策與理由", "失敗與限制", "建議的來源設定", "未解事項與需要決定的事", "來源清單",
]
PROCESS_SECTIONS = [
    "目的", "輸入與輸出", "步驟", "證據規則", "結論對應表", "來源設定草稿", "與其他工作項目的關係", "已知限制",
]
PROCESS_STEPS = [f"步驟 {n}" for n in range(8)]


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def missing(text: str, headings: list[str]) -> list[str]:
    """Headings (any level) that do not appear in ``text``."""
    found = re.findall(r"^#{2,3}\s+(.+)$", text, re.M)
    return [h for h in headings if not any(h in f for f in found)]


def section(text: str, title: str) -> str:
    match = re.search(rf"^## \d+\. {re.escape(title)}.*?$(.*?)(?=^## |\Z)", text, re.M | re.S)
    assert match, f"section {title!r} not found"
    return match.group(1)


def schema(name: str) -> dict:
    return json.loads((ROOT / "schemas" / "v1" / f"{name}.schema.json").read_text(encoding="utf-8"))


def contract_enums() -> dict[str, list[str]]:
    index = schema("dataset_index")
    acquisition = index["properties"]["exhibitions"]["items"]["properties"]["acquisition"]
    last = index["properties"]["exhibitions"]["items"]["properties"]["editions"]["items"]["properties"]["last_acquisition"]
    return {
        "method": index["$defs"]["acquisition_method"]["enum"],
        "status": acquisition["properties"]["status"]["enum"],
        "last_status": last["properties"]["status"]["enum"],
        "source_type": schema("source")["properties"]["source_type"]["enum"],
        "notes_required_for": acquisition["allOf"][1]["if"]["properties"]["status"]["enum"],
    }


def mapping_rows() -> list[tuple[str, list[str], list[str], str]]:
    """Rows of the section 5 table: (outcome, methods, statuses, notes-cell)."""
    rows = []
    for line in section(read(PROCESS), "結論對應表").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 4 and cells[0] not in ("評估結果",) and not set(cells[0]) <= {"-"}:
            rows.append((cells[0], re.findall(r"`([a-z_]+)`", cells[1]), re.findall(r"`([a-z_]+)`", cells[2]), cells[3]))
    return rows


def toml_blocks(text: str) -> list[str]:
    return re.findall(r"```toml\n(.*?)```", text, re.S)


# --------------------------------------------------------------------------- structure


def test_both_documents_exist_and_internal_links_resolve() -> None:
    for doc in (PROCESS, TEMPLATE):
        assert doc.is_file()
        for target in re.findall(r"\]\(([^)#]+\.md)\)", read(doc)):
            assert (doc.parent / target).resolve().is_file(), f"{doc.name} links to missing {target}"


def test_template_has_every_required_section() -> None:
    assert missing(read(TEMPLATE), TEMPLATE_SECTIONS) == []


def test_process_has_every_section_and_every_step() -> None:
    assert missing(read(PROCESS), PROCESS_SECTIONS) == []
    assert missing(read(PROCESS), PROCESS_STEPS) == []


def test_the_section_check_really_detects_a_missing_section() -> None:
    text = read(TEMPLATE).replace("## 6. 完整度可行性", "## 6. 其他")
    assert missing(text, TEMPLATE_SECTIONS) == ["完整度可行性"]


# --------------------------------------------------------------------------- consistency with the contract


def table_row(text: str, key: str) -> str:
    """The row of a Markdown table whose first cell is ``key`` in backticks."""
    rows = [line for line in text.splitlines() if line.startswith(f"| `{key}` |")]
    assert len(rows) == 1, f"expected exactly one table row for {key!r}, found {len(rows)}"
    return rows[0]


def test_the_templates_conclusion_rows_list_exactly_the_contract_values() -> None:
    enums = contract_enums()
    conclusion = section(read(TEMPLATE), "結論（對應資料集索引 `acquisition`）")
    assert set(re.findall(r"`([a-z_]+)`", table_row(conclusion, "method"))) - {"method"} == set(enums["method"])
    assert set(re.findall(r"`([a-z_]+)`", table_row(conclusion, "status"))) - {"status"} == set(enums["status"])
    assert REPORT_PATH in table_row(conclusion, "report_path")
    # the notes row names the statuses that require notes, exactly as the contract does
    notes_row = table_row(conclusion, "notes")
    assert set(re.findall(r"`([a-z_]+)`", notes_row)) - {"notes"} == set(enums["notes_required_for"])


def test_the_mapping_table_uses_only_contract_values() -> None:
    enums = contract_enums()
    rows = mapping_rows()
    assert len(rows) >= 8
    for outcome, methods, statuses, _ in rows:
        assert methods and statuses, outcome
        assert set(methods) <= set(enums["method"]), (outcome, methods)
        assert set(statuses) <= set(enums["status"]), (outcome, statuses)


def test_the_mapping_table_covers_every_contract_status_and_method() -> None:
    enums = contract_enums()
    rows = mapping_rows()
    assert {s for _, _, statuses, _ in rows for s in statuses} == set(enums["status"])
    assert {m for _, methods, _, _ in rows for m in methods} == set(enums["method"])


def test_notes_are_marked_required_exactly_where_the_contract_requires_them() -> None:
    required = set(contract_enums()["notes_required_for"])
    seen = {"required": 0, "optional": 0, "mixed": 0}
    for outcome, _, statuses, notes in mapping_rows():
        if set(statuses) <= required:  # every status in this row needs notes
            assert "必填" in notes, f"{outcome}: the contract requires notes for {statuses}"
            seen["required"] += 1
        elif not (set(statuses) & required):  # no status in this row needs notes
            assert "必填" not in notes, f"{outcome}: the contract does not require notes for {statuses}"
            seen["optional"] += 1
        else:  # a row that can be either: the doc must at least say what to explain
            assert "說明" in notes, f"{outcome}: mixed statuses {statuses} need an explanation hint"
            seen["mixed"] += 1
    assert seen["required"] >= 3 and seen["optional"] >= 2 and seen["mixed"] >= 1, seen


def test_assessed_at_and_report_path_requirement_is_stated() -> None:
    text = section(read(PROCESS), "結論對應表")
    assert "assessed_at" in text and "report_path" in text and "not_assessed" in text


def test_every_source_type_of_the_contract_is_listed() -> None:
    process = read(PROCESS)
    for value in contract_enums()["source_type"]:
        assert f"`{value}`" in process, value


def test_failed_acquisition_rule_matches_the_index_contract() -> None:
    assert "failed" in contract_enums()["last_status"]
    step5 = section(read(PROCESS), "步驟")
    assert all(word in step5 for word in ("last_acquisition", "failed", "dataset_id", "notes"))


def test_report_path_convention_matches_the_merged_index_contract() -> None:
    assert REPORT_PATH in read(INDEX_CONTRACT)
    assert REPORT_PATH in read(PROCESS) and REPORT_PATH in read(TEMPLATE)


def test_the_templates_error_codes_are_exactly_the_crawler_error_codes() -> None:
    failure = section(read(TEMPLATE), "失敗與限制")
    listed = set(re.findall(r"`([a-z_]+)`", failure))
    assert listed == {code.value for code in ErrorCode}


# --------------------------------------------------------------------------- examples are real


def test_the_process_config_example_loads_with_the_real_loader() -> None:
    blocks = toml_blocks(read(PROCESS))
    assert len(blocks) == 1
    config = parse_source_config(tomllib.loads(blocks[0]))
    assert config.source_type in contract_enums()["source_type"]
    assert all(urlsplit(u).hostname in RESERVED_HOSTS or urlsplit(u).hostname.endswith(tuple("." + h for h in RESERVED_HOSTS)) for u in config.start_urls)
    assert set(config.allowed_domains) <= RESERVED_HOSTS


def test_the_templates_placeholder_config_is_not_a_valid_config() -> None:
    """The template block is a blank form; it must not be mistaken for a usable config."""
    blocks = toml_blocks(read(TEMPLATE))
    assert len(blocks) == 1
    with pytest.raises(ConfigError):
        parse_source_config(tomllib.loads(blocks[0]))


# --------------------------------------------------------------------------- honesty and V2.3 guards


@pytest.mark.parametrize("doc", [PROCESS, TEMPLATE], ids=lambda p: p.name)
def test_no_specific_exhibition_is_named(doc: Path) -> None:
    hits = [line.strip() for line in read(doc).splitlines() if FORBIDDEN_NAMES.search(line)]
    assert hits == []


@pytest.mark.parametrize("doc", [PROCESS, TEMPLATE], ids=lambda p: p.name)
def test_only_reserved_example_domains_appear_in_urls(doc: Path) -> None:
    hosts = {urlsplit(u).hostname for u in re.findall(r"https?://[^\s)`\"'>]+", read(doc))}
    assert all(h in RESERVED_HOSTS or h.endswith(tuple("." + r for r in RESERVED_HOSTS)) for h in hosts), hosts


@pytest.mark.parametrize("doc", [PROCESS, TEMPLATE], ids=lambda p: p.name)
def test_the_four_evidence_levels_are_defined_or_used(doc: Path) -> None:
    text = read(doc)
    assert all(level in text for level in EVIDENCE_LEVELS)


def test_the_core_honesty_rules_are_stated() -> None:
    process = read(PROCESS)
    for rule in ("不得假設一個展覽一定能全自動取得", "第三方來源只當線索", "工具讀不到，不等於來源拒絕", "不繞過", "不得用估計值"):
        assert rule in process, rule
    assert "不得阻礙通用系統繼續開發" in process
