"""Tests for etl.schema_registry (D1-05)."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from etl.schema_registry import DEFAULT_SCHEMA_DIR, SchemaError, SchemaSet

ROOT = Path(__file__).resolve().parents[2]


def test_default_directory_is_the_repository_schemas_v1() -> None:
    assert DEFAULT_SCHEMA_DIR == ROOT / "schemas" / "v1"


def test_loads_every_schema_file_and_the_version() -> None:
    schemas = SchemaSet()
    on_disk = sorted(p.name.removesuffix(".schema.json") for p in DEFAULT_SCHEMA_DIR.glob("*.schema.json"))
    assert schemas.entities() == on_disk
    assert {"manifest", "company", "participation", "source", "crawl_run", "change", "exhibition", "edition", "common"} <= set(on_disk)
    assert schemas.version == (DEFAULT_SCHEMA_DIR / "VERSION").read_text(encoding="utf-8").strip()


def test_refs_between_schema_files_resolve_locally() -> None:
    """A company record is checked through ``$ref`` into common.schema.json."""
    schemas = SchemaSet()
    assert schemas.errors("company", {"company_id": "not-an-id"})  # fails on required fields and on the id pattern
    messages = " ".join(schemas.errors("company", {"company_id": "not-an-id", "name": "x", "status": "active", "source_ids": ["src_x"], "verification_status": "unverified"}))
    assert "does not match" in messages  # the id pattern lives in common.schema.json, so the $ref was followed


def test_unknown_entity_is_an_error() -> None:
    with pytest.raises(SchemaError, match="no schema named"):
        SchemaSet().validator("nope")


def test_missing_directory_and_missing_version(tmp_path: Path) -> None:
    with pytest.raises(SchemaError, match="no \\*.schema.json"):
        SchemaSet(tmp_path / "absent")
    copy = tmp_path / "v1"
    shutil.copytree(DEFAULT_SCHEMA_DIR, copy)
    (copy / "VERSION").unlink()
    with pytest.raises(SchemaError, match="VERSION"):
        SchemaSet(copy)


def test_schema_without_id_or_with_bad_json_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "VERSION").write_text("1.0.0\n", encoding="utf-8")
    (tmp_path / "a.schema.json").write_text(json.dumps({"type": "object"}), encoding="utf-8")
    with pytest.raises(SchemaError, match="\\$id"):
        SchemaSet(tmp_path)
    (tmp_path / "a.schema.json").write_text("{", encoding="utf-8")
    with pytest.raises(SchemaError, match="invalid JSON"):
        SchemaSet(tmp_path)


def test_an_unresolvable_ref_is_reported_as_a_schema_error(tmp_path: Path) -> None:
    (tmp_path / "VERSION").write_text("1.0.0\n", encoding="utf-8")
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://exhibitiq.invalid/schemas/v1/lonely.schema.json",
        "type": "object",
        "properties": {"x": {"$ref": "missing.schema.json"}},
    }
    (tmp_path / "lonely.schema.json").write_text(json.dumps(schema), encoding="utf-8")
    with pytest.raises(SchemaError, match="cannot be resolved locally"):
        SchemaSet(tmp_path).errors("lonely", {"x": 1})


# --------------------------------------------------- COMPATIBILITY.json (Schema draft.6+)


def test_accepted_versions_come_from_compatibility_json() -> None:
    schemas = SchemaSet()
    data = json.loads((DEFAULT_SCHEMA_DIR / "COMPATIBILITY.json").read_text(encoding="utf-8"))
    assert schemas.accepted == tuple(data["accepted"])
    assert data["current"] == schemas.version and schemas.version in schemas.accepted


def _copy_with_compat(tmp_path: Path, content: str | None) -> Path:
    copy = tmp_path / "v1"
    shutil.copytree(DEFAULT_SCHEMA_DIR, copy)
    target = copy / "COMPATIBILITY.json"
    if content is None:
        target.unlink()
    else:
        target.write_text(content, encoding="utf-8")
    return copy


def test_without_compatibility_json_only_version_is_accepted(tmp_path: Path) -> None:
    schemas = SchemaSet(_copy_with_compat(tmp_path, None))
    assert schemas.accepted == (schemas.version,)


@pytest.mark.parametrize(
    "content, match",
    [
        ("{", "invalid JSON"),
        ("[]", "'accepted' must be"),
        (json.dumps({"current": "x", "accepted": []}), "'accepted' must be"),
        (json.dumps({"current": "x", "accepted": ["a", 1]}), "'accepted' must be"),
        ("CURRENT_IS_NOT_VERSION", "'current' must equal VERSION"),
        ("CURRENT_NOT_ACCEPTED", "'current' must equal VERSION"),
    ],
)
def test_malformed_compatibility_json_is_rejected(tmp_path: Path, content: str, match: str) -> None:
    version = (DEFAULT_SCHEMA_DIR / "VERSION").read_text(encoding="utf-8").strip()
    if content == "CURRENT_IS_NOT_VERSION":
        content = json.dumps({"current": "1.0.0-draft.0", "accepted": ["1.0.0-draft.0", version]})
    if content == "CURRENT_NOT_ACCEPTED":
        content = json.dumps({"current": version, "accepted": ["1.0.0-draft.0"]})
    with pytest.raises(SchemaError, match=match):
        SchemaSet(_copy_with_compat(tmp_path, content))
