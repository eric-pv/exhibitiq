"""Governance document checks for P1-AI-03 (Issue #3).

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
        ("data/samples/mspo/", "data"),
        ("data/packages/", "data"),
        ("data/raw/", "data"),
        (".github/ISSUE_TEMPLATE/", "ai"),
        (".github/pull_request_template.md", "ai"),
        (".github/workflows/", "data"),
        (".github/workflows/validate.yml", "data"),
        ("skills/exhibitiq/SKILL.md", "ai"),
        ("crawler/mspo/", "data"),
        # V2.1 (2026-11-03): Web Dashboard owned by ai; its workflows stay with data.
        ("site/", "ai"),
        ("site/src/components/KpiCard.tsx", "ai"),
        ("site/package.json", "ai"),
        (".github/workflows/site-build.yml", "data"),
        ("docs/PROGRESS.md", "ai"),
        ("docs/DEVELOPMENT_PLAN.md", "ai"),
        ("docs/data-platform/environment.md", "data"),
        ("data/index/", "data"),
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
