"""Tests for etl.package (D1-04).

The central test regenerates the contract's own example package
(``schemas/v1/examples/package/``) and requires byte-identical data files and an
identical ``content_hash``. The example data is synthetic.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from etl.package import (
    COMPUTED_MANIFEST_FIELDS,
    DATA_FILES,
    MANIFEST_FILE,
    RECORD_SETS,
    PackageError,
    SourceIndex,
    compute_integrity,
    package_path,
    read_manifest,
    read_package,
    write_manifest,
    write_package,
)

EXAMPLE = Path(__file__).resolve().parents[2] / "schemas" / "v1" / "examples" / "package"


def example_inputs() -> dict:
    pkg = read_package(EXAMPLE, require_canonical=True)
    manifest = {k: v for k, v in pkg.manifest.items() if k not in COMPUTED_MANIFEST_FIELDS}
    return dict(exhibition=pkg.exhibition, edition=pkg.edition, records=pkg.records, manifest=manifest)


# --- layout is consistent with the contract's example -------------------------------------


def test_layout_constants_match_the_example_manifest() -> None:
    manifest = json.loads((EXAMPLE / MANIFEST_FILE).read_text(encoding="utf-8"))
    assert set(DATA_FILES) == set(manifest["files"])
    assert set(RECORD_SETS) == set(manifest["record_counts"])
    assert len(DATA_FILES) == 7
    assert DATA_FILES == tuple(sorted(DATA_FILES, key=lambda n: n.encode("utf-8")))


def test_primary_keys_exist_in_the_example_records() -> None:
    pkg = read_package(EXAMPLE)
    for short, (_, key) in RECORD_SETS.items():
        for record in pkg.records[short]:
            assert key in record, (short, key)


# --- the central reproducibility test -------------------------------------------------------


def test_regenerates_the_example_package_byte_for_byte(tmp_path: Path) -> None:
    out = tmp_path / "pkg"
    manifest = write_package(out, **example_inputs())
    for name in DATA_FILES:
        assert (out / name).read_bytes() == (EXAMPLE / name).read_bytes(), name
    expected = json.loads((EXAMPLE / MANIFEST_FILE).read_text(encoding="utf-8"))
    assert manifest == expected
    assert json.loads((out / MANIFEST_FILE).read_text(encoding="utf-8")) == expected
    assert manifest["content_hash"] == "sha256:68fc94dcaeaed1d23842f327b6b3cd05e07cca6610372ebb086622b03fb4d74b"


def test_compute_integrity_of_the_example_equals_its_manifest() -> None:
    expected = json.loads((EXAMPLE / MANIFEST_FILE).read_text(encoding="utf-8"))
    got = compute_integrity(EXAMPLE)
    assert got["files"] == expected["files"]
    assert got["record_counts"] == expected["record_counts"]
    assert got["content_hash"] == expected["content_hash"]


def test_output_is_independent_of_record_input_order(tmp_path: Path) -> None:
    inputs = example_inputs()
    shuffled = {short: list(reversed(rows)) for short, rows in inputs["records"].items()}
    out = tmp_path / "pkg"
    manifest = write_package(out, **{**inputs, "records": shuffled})
    assert manifest["content_hash"] == json.loads((EXAMPLE / MANIFEST_FILE).read_text(encoding="utf-8"))["content_hash"]


# --- immutability and safe writing ----------------------------------------------------------


def test_refuses_to_overwrite_an_existing_package(tmp_path: Path) -> None:
    out = tmp_path / "pkg"
    write_package(out, **example_inputs())
    before = {n: (out / n).read_bytes() for n in (*DATA_FILES, MANIFEST_FILE)}
    with pytest.raises(PackageError, match="immutable"):
        write_package(out, **example_inputs())
    assert before == {n: (out / n).read_bytes() for n in (*DATA_FILES, MANIFEST_FILE)}


def test_failure_leaves_nothing_behind(tmp_path: Path) -> None:
    inputs = example_inputs()
    inputs["records"] = {**inputs["records"], "companies": [{"company_id": "x"}, {"company_id": "x"}]}
    out = tmp_path / "root" / "pkg"
    with pytest.raises(ValueError, match="duplicate primary key"):
        write_package(out, **inputs)
    assert not out.exists()
    leftovers = list((tmp_path / "root").iterdir()) if (tmp_path / "root").exists() else []
    assert leftovers == []


def test_failure_after_files_are_staged_still_leaves_nothing_behind(tmp_path: Path) -> None:
    """The records are fine, so the staging directory is created and filled; the manifest then fails."""
    inputs = example_inputs()
    inputs["manifest"] = {**inputs["manifest"], "bad": float("nan")}
    out = tmp_path / "root" / "pkg"
    with pytest.raises(ValueError):
        write_package(out, **inputs)
    assert not out.exists()
    assert list((tmp_path / "root").iterdir()) == []  # the staging directory was removed


def test_omitted_record_sets_become_empty_files(tmp_path: Path) -> None:
    inputs = example_inputs()
    inputs["records"] = {"sources": inputs["records"]["sources"]}
    inputs["manifest"] = {k: v for k, v in inputs["manifest"].items() if k != "crawl_run_ids"}
    out = tmp_path / "pkg"
    manifest = write_package(out, **inputs)
    for name in ("companies.jsonl", "participations.jsonl", "crawl_runs.jsonl", "changes.jsonl"):
        assert (out / name).read_bytes() == b""
    assert manifest["record_counts"] == {"companies": 0, "participations": 0, "sources": 2, "crawl_runs": 0, "changes": 0}
    assert manifest["crawl_run_ids"] == []


@pytest.mark.parametrize("field", sorted(COMPUTED_MANIFEST_FIELDS))
def test_computed_manifest_fields_cannot_be_supplied(tmp_path: Path, field: str) -> None:
    inputs = example_inputs()
    inputs["manifest"] = {**inputs["manifest"], field: {}}
    with pytest.raises(PackageError, match="computed"):
        write_package(tmp_path / "pkg", **inputs)


def test_unknown_record_set_is_rejected(tmp_path: Path) -> None:
    inputs = example_inputs()
    inputs["records"] = {**inputs["records"], "mystery": []}
    with pytest.raises(PackageError, match="unknown record sets"):
        write_package(tmp_path / "pkg", **inputs)


def test_manifest_ids_must_match_the_records(tmp_path: Path) -> None:
    inputs = example_inputs()
    inputs["manifest"] = {**inputs["manifest"], "source_snapshot_ids": ["src_01JCS000000000000000000001"]}
    with pytest.raises(PackageError, match="source_snapshot_ids"):
        write_package(tmp_path / "pkg", **inputs)


def test_source_and_run_ids_are_derived_when_omitted(tmp_path: Path) -> None:
    inputs = example_inputs()
    inputs["manifest"] = {k: v for k, v in inputs["manifest"].items() if k not in ("source_snapshot_ids", "crawl_run_ids")}
    manifest = write_package(tmp_path / "pkg", **inputs)
    expected = json.loads((EXAMPLE / MANIFEST_FILE).read_text(encoding="utf-8"))
    assert manifest["source_snapshot_ids"] == expected["source_snapshot_ids"]
    assert manifest["crawl_run_ids"] == expected["crawl_run_ids"]


def test_compute_integrity_reports_missing_files(tmp_path: Path) -> None:
    (tmp_path / "exhibition.json").write_bytes(b"{}\n")
    with pytest.raises(PackageError, match="missing data files"):
        compute_integrity(tmp_path)


def test_compute_integrity_detects_a_file_without_final_newline(tmp_path: Path) -> None:
    for name in DATA_FILES:
        (tmp_path / name).write_bytes(b"" if name.endswith(".jsonl") else b"{}\n")
    (tmp_path / "companies.jsonl").write_bytes(b'{"company_id":"x"}')
    with pytest.raises(PackageError, match="missing newline"):
        compute_integrity(tmp_path)


# --- reading --------------------------------------------------------------------------------


def test_read_package_round_trip(tmp_path: Path) -> None:
    out = tmp_path / "pkg"
    write_package(out, **example_inputs())
    again = read_package(out, require_canonical=True)
    inputs = example_inputs()
    assert again.exhibition == inputs["exhibition"] and again.edition == inputs["edition"]
    assert again.records == inputs["records"]


def test_read_package_reports_missing_files(tmp_path: Path) -> None:
    with pytest.raises(PackageError, match="missing files"):
        read_package(tmp_path)


def test_manifest_read_write_round_trip_and_format(tmp_path: Path) -> None:
    manifest = {"b": "中文", "a": [1, 2], "c": None}
    path = tmp_path / "manifest.json"
    write_manifest(path, manifest)
    raw = path.read_bytes()
    assert raw.endswith(b"\n") and b"\r" not in raw and not raw.startswith(b"\xef\xbb\xbf")
    assert "中文".encode("utf-8") in raw  # not \u-escaped
    assert read_manifest(path) == manifest


@pytest.mark.parametrize("data, fragment", [(b'{"a":1,"a":2}', "duplicate"), (b"[1]", "JSON object"), (b"\xef\xbb\xbf{}", "BOM"), (b"{", "invalid JSON")])
def test_read_manifest_is_strict(tmp_path: Path, data: bytes, fragment: str) -> None:
    path = tmp_path / "manifest.json"
    path.write_bytes(data)
    with pytest.raises(PackageError, match=fragment):
        read_manifest(path)


# --- package path ----------------------------------------------------------------------------


def test_package_path_follows_the_contract_layout() -> None:
    assert package_path("data/packages", "example-expo", 2026, "example-expo-2026.20261103T000000Z") == Path(
        "data/packages/example-expo/2026/example-expo-2026.20261103T000000Z"
    )


@pytest.mark.parametrize("exhibition_id, year, dataset_id", [("..", 2026, "d"), ("a/b", 2026, "d"), ("a", 2026, "../x"), ("a", 2026, ""), ("a", 26, "d"), ("a", True, "d")])
def test_package_path_rejects_unsafe_parts(exhibition_id: str, year: int, dataset_id: str) -> None:
    with pytest.raises(PackageError):
        package_path("root", exhibition_id, year, dataset_id)


# --- source index ----------------------------------------------------------------------------


def test_source_index_lookup_and_missing() -> None:
    index = SourceIndex.from_file(EXAMPLE / "sources.jsonl")
    assert len(index) == 2
    ids = sorted(index.ids())
    assert ids[0] in index and "src_missing" not in index
    assert index[ids[0]]["source_id"] == ids[0]
    assert list(index) == ids
    assert index.missing([ids[0], "src_b", "src_a", "src_a"]) == ["src_a", "src_b"]


def test_source_index_rejects_duplicates_and_missing_ids() -> None:
    with pytest.raises(PackageError, match="duplicate"):
        SourceIndex([{"source_id": "a"}, {"source_id": "a"}])
    with pytest.raises(PackageError, match="usable"):
        SourceIndex([{"nope": "a"}])
