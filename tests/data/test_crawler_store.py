"""Tests for crawler.store (D2-06): immutable snapshot storage, source records, run records, verification."""
from __future__ import annotations

import json
from dataclasses import replace

import pytest

from crawler.file_import import ADAPTER_NAME, FileImportAdapter
from crawler.adapters import AdapterRegistry
from crawler.models import Snapshot
from crawler.runner import RunOptions, run_source
from crawler.store import DEFAULT_MAX_STORED_BYTES, RunStore, StoreError, extension_for, verify_run
from etl.hashing import sha256_of_bytes
from etl.schema_registry import SchemaSet
from tests.data.crawl_testkit import FakeClock, FakeFetcher, fixed_rand, make_config, page
from tests.data.test_crawler_runner import ROBOTS, START, rows_adapter

SCHEMAS = SchemaSet()
SRC = "src_01JCS000000000000000000001"
RUN = "run_01JCR000000000000000000001"


def snap(content=b"<p>hi</p>", **kw) -> Snapshot:
    base = dict(source_id=SRC, crawl_run_id=RUN, url=START, final_url=START, retrieved_at="2026-11-03T06:00:00Z", http_status=200,
                media_type="text/html", content_sha256=sha256_of_bytes(content), size=len(content), content=content)
    base.update(kw)
    return Snapshot(**base)


def crawl(tmp_path, script, **store_kw):
    config = make_config()
    store = RunStore(tmp_path, config, **store_kw)
    result = run_source(config, rows_adapter(), FakeFetcher(script), clock=FakeClock(), rand=fixed_rand, sink=store, options=RunOptions())
    return store, result


# --- saving -------------------------------------------------------------------------------


def test_save_writes_exact_bytes_at_a_predictable_path(tmp_path):
    store = RunStore(tmp_path, make_config())
    store.save(snap(b"\x00raw\xffbytes"))
    path = tmp_path / "example-expo" / "example-expo-2026" / RUN / "snapshots" / f"{SRC}.html"
    assert path.read_bytes() == b"\x00raw\xffbytes"


def test_snapshots_are_immutable(tmp_path):
    store = RunStore(tmp_path, make_config())
    store.save(snap())
    with pytest.raises(StoreError, match="already saved"):
        store.save(snap(b"other", content_sha256=sha256_of_bytes(b"other"), size=5))
    other = RunStore(tmp_path, make_config())  # a fresh store pointing at the same disk must not overwrite either
    with pytest.raises(StoreError, match="immutable"):
        other.save(snap())
    assert (tmp_path / "example-expo/example-expo-2026" / RUN / "snapshots" / f"{SRC}.html").read_bytes() == b"<p>hi</p>"


def test_content_that_does_not_match_its_hash_is_refused(tmp_path):
    store = RunStore(tmp_path, make_config())
    with pytest.raises(StoreError, match="sha256"):
        store.save(replace(snap(), content_sha256=sha256_of_bytes(b"different")))
    with pytest.raises(StoreError, match="sha256"):
        store.save(replace(snap(), size=999))
    assert not any(tmp_path.rglob("*.html"))


@pytest.mark.parametrize("field,value", [("source_id", "src_bad"), ("source_id", "run_01JCR000000000000000000001"), ("crawl_run_id", "../../etc"), ("crawl_run_id", "src_01JCS000000000000000000001")])
def test_ids_that_could_escape_the_directory_are_refused(tmp_path, field, value):
    with pytest.raises(StoreError):
        RunStore(tmp_path, make_config()).save(replace(snap(), **{field: value}))
    assert list(tmp_path.rglob("*")) == []


@pytest.mark.parametrize("exhibition", ["../x", "Upper", "a/b", ""])
def test_unsafe_exhibition_ids_are_refused(tmp_path, exhibition):
    with pytest.raises(StoreError):
        RunStore(tmp_path, make_config(exhibition_id=exhibition))


def test_large_snapshot_is_not_stored_but_recorded(tmp_path):
    store = RunStore(tmp_path, make_config(), max_stored_bytes=10)
    big = snap(b"x" * 11)
    store.save(big)
    assert not any(tmp_path.rglob("*.html"))
    record = store.source_record(big)
    assert record["snapshot"] == {"storage": "not_stored"} and "max_stored_bytes (10)" in record["notes"] and record["content_sha256"] == big.content_sha256
    assert SCHEMAS.errors("source", record) == []
    exact = snap(b"x" * 10, source_id="src_01JCS000000000000000000002")
    store.save(exact)
    assert store.source_record(exact)["snapshot"]["storage"] == "git"  # at the limit is stored


def test_invalid_limit(tmp_path):
    for bad in (-1, True, 1.5):
        with pytest.raises(StoreError):
            RunStore(tmp_path, make_config(), max_stored_bytes=bad)


@pytest.mark.parametrize("media,ext", [("text/html", ".html"), ("TEXT/CSV", ".csv"), ("application/pdf", ".pdf"), ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", ".xlsx"), ("application/x-weird", ".bin"), (None, ".bin")])
def test_extensions(media, ext):
    assert extension_for(media) == ext


# --- source records -------------------------------------------------------------------------


def test_source_record_is_schema_valid_and_points_at_the_file(tmp_path):
    store = RunStore(tmp_path, make_config())
    s = snap(final_url="https://www.example.com/moved")
    store.save(s)
    record = store.source_record(s)
    assert SCHEMAS.errors("source", record) == []
    assert record["snapshot"] == {"storage": "git", "locator": f"data/raw/example-expo/example-expo-2026/{RUN}/snapshots/{SRC}.html"}
    assert record["source_type"] == "official_exhibitor_list" and record["crawl_run_id"] == RUN and record["url"] == START
    assert record["notes"] == "redirected to https://www.example.com/moved"


def test_source_record_for_unsaved_snapshot_is_refused(tmp_path):
    with pytest.raises(StoreError, match="not saved"):
        RunStore(tmp_path, make_config()).source_record(snap())


def test_odd_media_type_is_omitted_not_invalid(tmp_path):
    store = RunStore(tmp_path, make_config())
    s = snap(media_type="TEXT")
    store.save(s)
    record = store.source_record(s)
    assert "media_type" not in record and SCHEMAS.errors("source", record) == []


def test_custom_root_label(tmp_path):
    store = RunStore(tmp_path, make_config(), root_label="/evidence/")
    s = snap()
    store.save(s)
    assert store.source_record(s)["snapshot"]["locator"].startswith("evidence/example-expo/")


# --- a whole run -----------------------------------------------------------------------------


def test_full_run_is_persisted_and_verifies(tmp_path):
    a = "https://www.example.com/a"
    store, result = crawl(tmp_path, {ROBOTS: 404, START: f"follow:{a}", a: 404})
    directory = store.finalize(result)
    assert directory.name == result.crawl_run["crawl_run_id"]
    run_record = json.loads((directory / "crawl_run.json").read_text(encoding="utf-8"))
    assert run_record == result.crawl_run and SCHEMAS.errors("crawl_run", run_record) == []
    sources = [json.loads(line) for line in (directory / "sources.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [s["source_id"] for s in sources] == [s.source_id for s in result.snapshots] and all(SCHEMAS.errors("source", s) == [] for s in sources)
    errors = json.loads((directory / "errors.json").read_text(encoding="utf-8"))
    assert errors[0]["code"] == "http_error" and errors[0]["url"] == a and errors[0]["http_status"] == 404
    assert (directory / "run.log.jsonl").read_text(encoding="utf-8") == result.log_text
    assert verify_run(directory) == []
    stored = {p.name for p in (directory / "snapshots").iterdir()}
    assert stored == {f"{s.source_id}.bin" if s.media_type is None else f"{s.source_id}.html" for s in result.snapshots}


def test_snapshot_is_on_disk_even_if_the_run_never_finalizes(tmp_path):
    store, result = crawl(tmp_path, {ROBOTS: 404, START: "evidence"})
    assert any(p.read_bytes() == b"evidence" for p in tmp_path.rglob("snapshots/*"))  # saved when received, before finalize


def test_finalize_twice_or_over_an_existing_run_is_refused(tmp_path):
    store, result = crawl(tmp_path, {ROBOTS: 404, START: "x"})
    store.finalize(result)
    with pytest.raises(StoreError, match="this run is already finalized"):
        store.finalize(result)
    with pytest.raises(StoreError, match="already finalized"):
        store.save(snap())
    again = RunStore(tmp_path, make_config())
    for s in result.snapshots:
        again._saved[s.source_id] = None
    with pytest.raises(StoreError, match="already finalized on disk"):
        again.finalize(result)


def test_finalize_requires_that_the_store_was_the_sink(tmp_path):
    config = make_config()
    result = run_source(config, rows_adapter(), FakeFetcher({ROBOTS: 404, START: "x"}), clock=FakeClock(), rand=fixed_rand)
    with pytest.raises(StoreError, match="never saved"):
        RunStore(tmp_path, config).finalize(result)
    assert not (tmp_path / "example-expo").exists() or not any((tmp_path / "example-expo").rglob("crawl_run.json"))


def test_failed_run_with_no_snapshots_is_still_recorded(tmp_path):
    store, result = crawl(tmp_path, {ROBOTS: 404, START: 500})
    directory = store.finalize(result)
    assert result.status == "failed" and (directory / "sources.jsonl").read_bytes() == b""
    assert verify_run(directory) == [] and not (directory / "snapshots").exists()


def test_file_import_run_is_persisted_too(tmp_path):
    from crawler.file_import import import_files

    csv_file = tmp_path / "in.csv"
    csv_file.write_bytes(b"Company\nAcme\n")
    origin = "https://files.example.com/in.csv"
    config = make_config(name="imp", adapter=ADAPTER_NAME, start_urls=(origin,), source_type="csv_import", options={"mapping": {"format": "csv", "columns": [{"source": "Company", "field": "name", "required": True}]}})
    registry = AdapterRegistry()
    registry.register(FileImportAdapter)
    store = RunStore(tmp_path / "raw", config)
    result = import_files(config, {origin: csv_file}, adapters=registry, clock=FakeClock(), rand=fixed_rand, sink=store)
    directory = store.finalize(result)
    source = json.loads((directory / "sources.jsonl").read_text(encoding="utf-8"))
    assert source["source_type"] == "csv_import" and source["url"] == origin and SCHEMAS.errors("source", source) == []
    assert (directory / "snapshots" / f"{source['source_id']}.csv").read_bytes() == b"Company\nAcme\n"


# --- verification -----------------------------------------------------------------------------


def stored_run(tmp_path):
    store, result = crawl(tmp_path, {ROBOTS: 404, START: "original"})
    return store.finalize(result), result


def test_verify_detects_tampering_missing_and_extra_files(tmp_path):
    directory, result = stored_run(tmp_path)
    (file,) = list((directory / "snapshots").iterdir())
    file.write_bytes(b"tampered")
    assert any("does not match its sha256" in p for p in verify_run(directory))
    file.unlink()
    assert any("expected one snapshot file, found 0" in p for p in verify_run(directory))
    (directory / "snapshots" / "src_01JCS0000000000000000000ZZ.html").write_bytes(b"extra")
    assert any("without a source record" in p for p in verify_run(directory))
    (directory / "errors.json").unlink()
    assert "missing errors.json" in verify_run(directory)


def test_verify_reports_garbage_source_lines(tmp_path):
    directory, _ = stored_run(tmp_path)
    (directory / "sources.jsonl").write_text("not json\n", encoding="utf-8")
    assert any("line 1 is not a source record" in p for p in verify_run(directory))


def test_verify_accepts_runs_with_unstored_snapshots(tmp_path):
    store, result = crawl(tmp_path, {ROBOTS: 404, START: "x" * 50}, max_stored_bytes=10)
    directory = store.finalize(result)
    assert not (directory / "snapshots").exists() and verify_run(directory) == []


def test_default_limit_is_five_mebibytes():
    assert DEFAULT_MAX_STORED_BYTES == 5 * 1024 * 1024
