"""Governance document checks for P1-AI-03 (Issue #3), V2.1 and V2.2.

Verifies that the module-boundary table covers every directory in the
project spec (§5), that each path has exactly one owner, that the owner's
2026-11-03 decisions are recorded, that the shared-file sync commands are
consistent, and that internal Markdown links resolve.

Standard library + pytest only.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "docs" / "ExhibitIQ_專案總規範.md"
BOUNDARIES = ROOT / "docs" / "architecture" / "module-boundaries.md"
VERSIONING = ROOT / "schemas" / "VERSIONING.md"
PLAN = ROOT / "docs" / "DEVELOPMENT_PLAN.md"
PROGRESS = ROOT / "docs" / "PROGRESS.md"
CLAUDE = ROOT / "CLAUDE.md"

OWNERS = {"ai", "data"}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _ownership_table() -> list[tuple[str, str]]:
    """Rows of the §2 table: (path, owner)."""
    text = _read(BOUNDARIES)
    section = text.split("## 2.", 1)[1].split("\n## ", 1)[0]
    rows = []
    for line in section.splitlines():
        m = re.match(r"^\|\s*`([^`]+)`\s*\|\s*([^|]+?)\s*\|", line)
        if m:
            rows.append((m.group(1), m.group(2)))
    return rows


def _owner_of(path: str, table: dict[str, str]) -> str | None:
    """Longest-prefix match, as defined in module-boundaries.md §2."""
    best = None
    for p in table:
        if path == p or (p.endswith("/") and path.startswith(p)):
            if best is None or len(p) > len(best):
                best = p
    return table[best] if best else None


def _spec_tree_paths() -> list[str]:
    """Parse the directory tree in spec §5 into repo-relative paths."""
    text = _read(SPEC)
    block = text.split("## 5.", 1)[1].split("```text", 1)[1].split("```", 1)[0]
    paths: list[str] = []
    stack: list[str] = []
    for line in block.splitlines():
        m = re.search(r"[├└]── (\S+)", line)
        if not m:
            continue
        depth = m.start() // 4
        name = m.group(1)
        stack = stack[:depth] + [name]
        paths.append("".join(stack))
    return paths


def test_spec_tree_parsed():
    paths = _spec_tree_paths()
    assert "schemas/" in paths
    assert "data/samples/" in paths
    assert "CLAUDE.md" in paths


def test_table_owners_valid_and_unique():
    rows = _ownership_table()
    assert rows, "ownership table not found"
    seen = set()
    for path, owner in rows:
        assert owner in OWNERS, f"{path}: owner {owner!r} not in {OWNERS}"
        assert path not in seen, f"{path} listed more than once"
        seen.add(path)


@pytest.mark.parametrize("path", _spec_tree_paths())
def test_every_spec_directory_has_owner(path):
    table = dict(_ownership_table())
    # A path is covered if it has an owner, or if the table assigns
    # owners to its children (e.g. tests/ -> tests/contract/, tests/data/).
    covered = _owner_of(path, table) is not None or any(
        p.startswith(path) for p in table if p != path
    )
    assert covered, f"spec §5 path {path} has no owner in module-boundaries.md"


@pytest.mark.parametrize(
    "path,owner",
    [
        # Owner decisions of 2026-11-03.
        ("schemas/", "ai"),
        ("schemas/v1/company.schema.json", "ai"),
        ("etl/", "data"),  # data validators live under etl/
        ("tests/contract/", "ai"),
        ("tests/contract/test_x.py", "ai"),
        ("tests/data/", "data"),
        ("data/samples/golden/", "ai"),
        ("data/samples/golden/v1/manifest.json", "ai"),
        ("data/samples/sample-fair/", "data"),
        # V2.2: test data for any exhibition lives under data/samples/<exhibition_id>/.
        ("data/samples/synthetic-expo-a/companies.csv", "data"),
        ("data/packages/", "data"),
        ("data/raw/", "data"),
        (".github/ISSUE_TEMPLATE/", "ai"),
        (".github/pull_request_template.md", "ai"),
        (".github/workflows/", "data"),
        (".github/workflows/validate.yml", "data"),
        ("skills/exhibitiq/SKILL.md", "ai"),
        ("crawler/sample-fair/", "data"),
        # V2.1 (2026-11-03): Web Dashboard owned by ai; its workflows stay with data.
        ("site/", "ai"),
        ("site/src/components/KpiCard.tsx", "ai"),
        ("site/package.json", "ai"),
        (".github/workflows/site-build.yml", "data"),
        ("docs/PROGRESS.md", "ai"),
        ("docs/DEVELOPMENT_PLAN.md", "ai"),
        ("docs/data-platform/environment.md", "data"),
        ("data/index/", "data"),
        (".gitignore", "ai"),  # Eric, 2026-11-04
        ("site/package-lock.json", "ai"),
        ("README.md", "ai"),
    ],
)
def test_owner_decisions(path, owner):
    assert _owner_of(path, dict(_ownership_table())) == owner


def test_sync_commands_list_same_existing_paths():
    text = _read(BOUNDARIES)
    checkout = re.search(r"git checkout origin/dev/ai-intelligence -- (.+)", text)
    diff = re.search(r"git diff --stat origin/dev/ai-intelligence origin/dev/data-platform -- (.+)", text)
    assert checkout and diff, "sync commands not found in module-boundaries.md §4"
    a, b = checkout.group(1).split(), diff.group(1).split()
    assert a == b, "sync checkout paths and consistency-check paths differ"
    table = dict(_ownership_table())
    for p in a:
        key = p + "/" if (ROOT / p).is_dir() or p == "schemas" else p
        assert _owner_of(key, table) == "ai", f"sync path {p} is not ai-owned"
        if p != "schemas":  # schemas/ contents are added by P1-AI-04 onward
            assert (ROOT / p).exists(), f"sync path {p} does not exist"
    assert not any(p.startswith("docs/data-platform") for p in a)


def test_versioning_policy_content():
    text = _read(VERSIONING)
    for needle in [
        "Draft 2020-12",
        "https://json-schema.org/draft/2020-12/schema",
        "MAJOR",
        "MINOR",
        "PATCH",
        "1.0.0-draft.1",
        "## 5. 變更程序",
    ]:
        assert needle in text, f"VERSIONING.md missing {needle!r}"


def _markdown_files() -> list[Path]:
    files = [ROOT / "README.md", ROOT / "CLAUDE.md"]
    files += sorted((ROOT / "docs").rglob("*.md"))
    files += sorted((ROOT / "schemas").glob("*.md"))
    return files


@pytest.mark.parametrize("md", _markdown_files(), ids=lambda p: str(p.relative_to(ROOT)))
def test_internal_links_resolve(md):
    for target in re.findall(r"\]\(([^)#\s]+)(?:#[^)]*)?\)", _read(md)):
        if re.match(r"^[a-z]+://", target):
            continue
        assert (md.parent / target).resolve().exists(), f"{md.name}: broken link {target}"


# ---------------------------------------------------------------- V2.1 process
def test_claude_md_points_to_plan_and_progress():
    text = _read(CLAUDE)
    for needle in ["docs/DEVELOPMENT_PLAN.md", "docs/PROGRESS.md", "docs/ExhibitIQ_專案總規範.md",
                   "docs/architecture/module-boundaries.md", "No GitHub Issue is needed for normal work"]:
        assert needle in text, f"CLAUDE.md missing {needle!r}"
    assert "for EVERY Issue" not in text


def test_spec_defers_work_items_to_plan():
    s8 = _read(SPEC).split("## 8.", 1)[1].split("\n## 9.", 1)[0]
    assert "DEVELOPMENT_PLAN.md" in s8
    # No numbered work lists left in §8: the plan is the only work list.
    assert not re.search(r"^\d+\. ", s8, flags=re.M)


def _plan_ids() -> list[str]:
    return re.findall(r"^\| ([AWD][1-4]-\d{2}) \|", _read(PLAN), flags=re.M)


def test_plan_work_item_ids_unique_and_well_formed():
    ids = _plan_ids()
    assert ids, "no work items found in DEVELOPMENT_PLAN.md"
    assert len(ids) == len(set(ids)), "duplicate work item IDs"


@pytest.mark.parametrize("phase", [1, 2, 3, 4])
def test_every_phase_has_items_for_all_roles_and_visual_gate(phase):
    ids = _plan_ids()
    for role in "AWD":
        assert any(i.startswith(f"{role}{phase}-") for i in ids), f"Phase {phase} has no {role} items"
    section = _read(PLAN).split(f"## Phase {phase} ", 1)[1].split("\n## Phase ", 1)[0]
    assert f"### Phase {phase} 可視化成果" in section


def test_progress_references_existing_plan_ids():
    ids = set(_plan_ids())
    for ref in re.findall(r"\b([AWD][1-4]-\d{2})\b", _read(PROGRESS)):
        assert ref in ids, f"PROGRESS.md references unknown work item {ref}"


# ---------------------------------------------------------------- V2.2 generic platform
SPECIFIC_EXHIBITIONS = re.compile(r"MSPO|TADTE", re.IGNORECASE)
MANDATORY_RULE = ("ExhibitIQ 嚴禁將任何特定展覽列為預設開發目標、主要資料來源、必要驗收對象或專案負責人必須指定的測試案例。"
                  "所有展覽資料來源均由通用探索與評估流程決定。特定展覽的取得失敗，不得阻礙通用系統繼續開發。")


def _section(text: str, start: str, end: str) -> str:
    return text.split(start, 1)[1].split(end, 1)[0]


def test_claude_md_defines_generic_platform():
    text = _read(CLAUDE)
    for needle in ["general-purpose", MANDATORY_RULE, "No exhibition is hard-coded in core code",
                   "Generality acceptance", "Data Platform, AI Intelligence and the Web Dashboard"]:
        assert needle in text, f"CLAUDE.md missing {needle!r}"
    # V2.3: CLAUDE.md names no specific exhibition at all.
    assert not SPECIFIC_EXHIBITIONS.search(text), "CLAUDE.md names a specific exhibition"


def test_spec_generic_principles_and_acceptance():
    text = _read(SPEC)
    for heading in ["### 1.1 通用性原則", "### 4.1 Dashboard 能直接做與不能直接做的事", "### 8.1 通用性驗收"]:
        assert heading in text, f"spec missing {heading!r}"
    assert "通用型 AI 展會情報搜尋、蒐集、分析與可視化平台" in text
    # Phase gates must not name a specific exhibition.
    gates = _section(text, "## 8.", "### 8.1")
    assert not SPECIFIC_EXHIBITIONS.search(gates), "spec §8 phase gates name a specific exhibition"
    acceptance = _section(text, "### 8.1", "\n## 9.")
    for needle in ["不修改核心程式", "兩組不同結構", "synthetic", "合法取得的公開資料"]:
        assert needle in acceptance, f"spec §8.1 missing {needle!r}"


def test_spec_does_not_claim_static_site_runs_backend_tasks():
    s41 = _section(_read(SPEC), "### 4.1", "\n## 5.")
    for needle in ["靜態 SPA", "不能", "workflow_dispatch", "Token", "核准"]:
        assert needle in s41, f"spec §4.1 missing {needle!r}"


def test_plan_items_mention_specific_exhibitions_only_as_test_cases():
    for line in _read(PLAN).splitlines():
        if re.match(r"^\| [AWD][1-4]-\d{2} \|", line) and SPECIFIC_EXHIBITIONS.search(line):
            assert "歷史紀錄" in line and "不是任何工作項目的依賴" in line, f"work item depends on an exhibition: {line}"


@pytest.mark.parametrize("phase", [1, 2, 3, 4])
def test_visual_gates_are_exhibition_agnostic(phase):
    plan = _read(PLAN)
    gate = plan.split(f"### Phase {phase} 可視化成果", 1)[1].split("\n## ", 1)[0]
    assert not SPECIFIC_EXHIBITIONS.search(gate), f"Phase {phase} visual gate names a specific exhibition"


def test_plan_generality_acceptance_covers_every_phase():
    s6 = _section(_read(PLAN), "## 6. 通用性驗收", "\n## Phase ")
    for phase in [1, 2, 3, 4]:
        assert f"| Phase {phase} |" in s6, f"plan §6 has no Phase {phase} row"
    for needle in ["不修改核心程式", "partial", "unknown", "匯入"]:
        assert needle in s6, f"plan §6 missing {needle!r}"


def test_dashboard_menu_has_required_pages():
    plan = _read(PLAN)
    menu = re.search(r"\*\*主選單（(\d+) 項）：\*\*(.+)", plan)
    assert menu, "main menu not found in plan §3"
    pages = [p.strip(" 。") for p in menu.group(2).split("。")[0].split("、")]
    assert len(pages) == int(menu.group(1)), "menu count does not match listed pages"
    for page in ["系統總覽", "展覽搜尋與新增", "展覽情報與比較", "參展商與企業情報", "商機分析與評分",
                 "BXR 產品推薦", "AI 報告中心", "分析設定", "資料及系統狀態"]:
        assert page in pages, f"menu missing {page}"
    assert "PDF／CSV 匯出" in plan
    assert f"{menu.group(1)} 個主選單" in plan, "W1-02 / Phase 1 gate menu count out of date"


def test_three_core_modules_and_reverse_sync_documented():
    text = _read(BOUNDARIES)
    assert "**Data Platform**（`data`）、**AI Intelligence**（`ai`）、**Web Dashboard**（`ai`）" in text
    assert "### 4.6" in text and "只由專案負責人確認並合併" in text
    assert "README.md" in re.search(r"git checkout origin/dev/ai-intelligence -- (.+)", text).group(1)


# ---------------------------------------------------------------- V2.3 no fixed exhibition
GENERAL_DOCS = [CLAUDE, ROOT / "README.md", SPEC, PLAN, PROGRESS, ROOT / "docs" / "specs" / "mvp-scope.md"]


@pytest.mark.parametrize("doc", GENERAL_DOCS, ids=lambda p: p.name)
def test_specific_exhibitions_only_as_history(doc):
    for line in _read(doc).splitlines():
        if SPECIFIC_EXHIBITIONS.search(line):
            assert "歷史" in line, f"{doc.name}: specific exhibition outside a historical note: {line}"
        assert "1,209" not in line and "1209" not in line, f"{doc.name}: exhibition-specific count: {line}"


def test_spec_states_mandatory_rule_and_capability_acceptance():
    text = _read(SPEC)
    assert MANDATORY_RULE in text, "spec §1.1 missing the mandatory rule"
    acceptance = _section(text, "### 8.1", "\n## 9.")
    for needle in ["可重用的系統能力", "參展商數量", "不阻礙"]:
        assert needle in acceptance, f"spec §8.1 missing {needle!r}"


def test_plan_does_not_require_owner_to_pick_exhibitions():
    plan = _read(PLAN)
    s6 = plan.split("## 6. 通用性驗收", 1)[1].split("\n## ", 1)[0]
    for needle in ["不需要專案負責人指定展覽", "參展商數量都不是驗收指標", "至少一組真實、合法取得的公開資料"]:
        assert needle in s6, f"DEVELOPMENT_PLAN §6 missing {needle!r}"
    for item in ("D1-11", "D2-02"):
        row = next(l for l in plan.splitlines() if l.startswith(f"| {item} |"))
        assert "D1-10" not in row, f"{item} still depends on D1-10"


def test_progress_has_no_exhibition_blocker_or_owner_pick():
    text = _read(PROGRESS)
    blockers = _section(text, "## 阻礙事項", "## 待專案負責人決定")
    decisions = _section(text, "## 待專案負責人決定", "## 已存在的 Issue")
    assert not SPECIFIC_EXHIBITIONS.search(blockers)
    assert "第一組" not in blockers and "測試展覽" not in decisions


# ---------------------------------------------------------------- A1-01 MVP scope
MVP = ROOT / "docs" / "specs" / "mvp-scope.md"


def test_mvp_scope_covers_every_main_menu_item():
    text = _read(MVP)
    for menu in ["系統總覽", "展覽搜尋與新增", "展覽情報與比較", "參展商與企業情報",
                 "商機分析與評分", "BXR 產品推薦", "AI 報告中心", "資料及系統狀態"]:
        assert f"| {menu} |" in text, f"mvp-scope.md has no row for {menu}"


def test_mvp_metrics_are_capabilities_not_exhibitor_counts():
    text = _read(MVP)
    metrics = _section(text, "## 4. MVP 驗收指標", "## 5.")
    assert "不修改核心程式" in metrics and "不作為驗收指標" in metrics
    assert "參展商數量" in metrics.split("**不作為驗收指標：**", 1)[1]
    assert not re.search(r"\d{3,}\s*家", metrics), "an exhibitor count is used as a metric"
