"""Tests for etl.integrity (D4-03): snapshots, byte-exact regeneration, backup and restore, regeneration from evidence."""
from __future__ import annotations

import gzip
import io
import json
import shutil
import tarfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from crawler.adapters import AdapterRegistry
from crawler.file_import import ADAPTER_NAME, FileImportAdapter, import_files
from crawler.importers import mapping_from_dict, read_rows
from crawler.store import RunStore, verify_run
from etl.assemble import assemble_package, load_run
from etl.build_records import RawListing, build_records
from etl.hashing import sha256_of_bytes
from etl.integrity import (
    BACKUP_MANIFEST, IntegrityError, check_regenerable, create_backup, main, restore_backup, verify_backup, verify_snapshots,
)
from etl.package import read_package
from etl.registry import CompanyRegistry
from etl.validate import validate_package
from tests.data.crawl_testkit import FakeClock, fixed_rand, make_config
from tests.data.test_assemble import COLUMNS, CREATED, CSV, ORIGIN, PRODUCER

ROOT = Path(__file__).resolve().parents[2]
SAMPLES = ROOT / "data" / "samples"
PACKAGES = sorted(p for p in SAMPLES.glob("*/*/*") if (p / "manifest.json").is_file())
V2 = SAMPLES / "sample-fair" / "2026" / "sample-fair-2026.20261104T020000Z"
WHEN = datetime(2026, 11, 9, tzinfo=timezone.utc)


def repo_copy(tmp_path: Path) -> Path:
    """A miniature repository root holding a copy of data/samples (packages and raw snapshots)."""
    root = tmp_path / "repo"
    shutil.copytree(SAMPLES, root / "data" / "samples", ignore=shutil.ignore_patterns("*.py", "__pycache__"))
    return root


def copied(root: Path, package: Path) -> Path:
    return root / package.relative_to(ROOT)


# ------------------------------------------------------------------------------------------ snapshots


@pytest.mark.parametrize("package", PACKAGES, ids=lambda p: p.name)
def test_every_sample_snapshot_is_present_and_unchanged(package: Path) -> None:
    result = verify_snapshots(package, ROOT)
    assert result["problems"] == [] and result["verified"]
    sources = read_package(package).records["sources"]
    assert sorted(result["verified"] + result["not_stored"] + [e["source_id"] for e in result["stored_elsewhere"]]) == sorted(s["source_id"] for s in sources)


def test_missing_and_changed_snapshots_are_reported(tmp_path: Path) -> None:
    root = repo_copy(tmp_path)
    package = copied(root, V2)
    sources = {s["source_id"]: s for s in read_package(package).records["sources"] if s["snapshot"]["storage"] == "git"}
    first, second = sorted(sources)
    (root / sources[first]["snapshot"]["locator"]).unlink()
    target = root / sources[second]["snapshot"]["locator"]
    target.write_bytes(target.read_bytes() + b" ")
    problems = verify_snapshots(package, root)["problems"]
    assert problems == [f"{first}: {sources[first]['snapshot']['locator']} does not exist", f"{second}: {sources[second]['snapshot']['locator']} does not match content_sha256"]


def test_not_stored_and_other_storage_are_listed_not_verified(tmp_path: Path) -> None:
    pkg = read_package(V2)
    sources = pkg.records["sources"]
    verified = [s["source_id"] for s in sources if s["snapshot"]["storage"] == "git"]
    assert verified  # the sample stores its snapshots in Git
    result = verify_snapshots(V2, tmp_path)  # a root without the files: every Git snapshot is a problem, none is silently verified
    assert result["verified"] == [] and len(result["problems"]) == len(verified)


def test_an_unsafe_locator_is_a_problem_not_a_file_read(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import etl.integrity as integrity

    real = integrity.read_package

    def with_bad_locator(path):
        package = real(path)
        package.records["sources"][0]["snapshot"] = {"storage": "git", "locator": "../../etc/passwd"}
        package.records["sources"][1]["snapshot"] = {"storage": "not_stored"}
        package.records["sources"][2]["snapshot"] = {"storage": "release", "locator": "x"}
        return package

    monkeypatch.setattr(integrity, "read_package", with_bad_locator)
    result = verify_snapshots(V2, ROOT)
    assert len(result["problems"]) == 1 and "unsafe path" in result["problems"][0]
    assert len(result["not_stored"]) == 1 and result["stored_elsewhere"][0]["storage"] == "release"


# --------------------------------------------------------------------------------------- regeneration


@pytest.mark.parametrize("package", PACKAGES, ids=lambda p: p.name)
def test_every_sample_package_regenerates_byte_for_byte(package: Path) -> None:
    assert check_regenerable(package) == []


def test_a_package_that_differs_from_its_regeneration_is_reported(tmp_path: Path) -> None:
    root = repo_copy(tmp_path)
    package = copied(root, V2)
    manifest = package / "manifest.json"
    manifest.write_text(json.dumps(json.loads(manifest.read_text(encoding="utf-8")), ensure_ascii=False, indent=4) + "\n", encoding="utf-8")
    assert validate_package(package).ok  # the manifest format is free (contract §5), so the validator accepts it...
    assert check_regenerable(package) == ["manifest.json: bytes differ from the regenerated file"]  # ...but it is not what the code writes


def test_a_tampered_data_file_is_reported_with_the_content_hash(tmp_path: Path) -> None:
    root = repo_copy(tmp_path)
    package = copied(root, V2)
    target = package / "companies.jsonl"
    target.write_bytes(target.read_bytes().replace(b"Sample Mobility Works", b"Sample Mobility Workz", 1))
    problems = check_regenerable(package)
    assert "companies.jsonl: bytes differ from the regenerated file" not in problems  # regenerated from the tampered records: same bytes
    assert any(p.startswith("manifest.json") for p in problems) and any("content_hash" in p for p in problems)


# ------------------------------------------------------------------------------------- backup/restore


def test_backup_restore_round_trip_is_lossless(tmp_path: Path) -> None:
    bundle = tmp_path / "backup.tar.gz"
    info = create_backup(PACKAGES, bundle, repo_root=ROOT, created_at=WHEN)
    assert info["packages"] == 3 and info["sha256"] == sha256_of_bytes(bundle.read_bytes())
    assert verify_backup(bundle) == []
    restored = restore_backup(bundle, tmp_path / "restored")
    assert restored["ok"] and [p["ok"] for p in restored["packages"]] == [True, True, True]
    for package in PACKAGES:
        for file in package.iterdir():
            assert (tmp_path / "restored" / file.relative_to(ROOT)).read_bytes() == file.read_bytes()
    for raw in SAMPLES.glob("*/raw/*"):
        assert (tmp_path / "restored" / raw.relative_to(ROOT)).read_bytes() == raw.read_bytes()


def test_backup_is_byte_reproducible(tmp_path: Path) -> None:
    a, b, c = tmp_path / "a.tgz", tmp_path / "b.tgz", tmp_path / "c.tgz"
    create_backup(PACKAGES, a, repo_root=ROOT, created_at=WHEN)
    create_backup(list(reversed(PACKAGES)), b, repo_root=ROOT, created_at=WHEN)
    create_backup(PACKAGES, c, repo_root=ROOT, created_at=datetime(2026, 11, 10, tzinfo=timezone.utc))
    assert a.read_bytes() == b.read_bytes() != c.read_bytes()


def test_backup_listing_records_every_file_and_package(tmp_path: Path) -> None:
    NOT_STORED = [s["source_id"] for s in read_package(V2).records["sources"] if s["snapshot"]["storage"] == "not_stored"]
    assert NOT_STORED  # the sample has one source that was deliberately not stored
    bundle = tmp_path / "b.tgz"
    create_backup([V2], bundle, repo_root=ROOT, created_at=WHEN)
    with tarfile.open(bundle, "r:gz") as tar:
        names = tar.getnames()
        listing = json.loads(tar.extractfile(BACKUP_MANIFEST).read())
    assert names[0] == BACKUP_MANIFEST and sorted(names[1:]) == sorted(f["path"] for f in listing["files"])
    assert listing["packages"] == [{"dataset_id": V2.name, "path": V2.relative_to(ROOT).as_posix(), "content_hash": read_package(V2).manifest["content_hash"],
                                    "data_origin": "synthetic", "snapshots_verified": 2, "snapshots_not_stored": NOT_STORED}]
    assert listing["created_at"] == "2026-11-09T00:00:00Z"


def test_backup_refusals(tmp_path: Path) -> None:
    root = repo_copy(tmp_path)
    existing = tmp_path / "exists.tgz"
    existing.write_bytes(b"x")
    with pytest.raises(IntegrityError, match="never overwritten"):
        create_backup([V2], existing, repo_root=ROOT, created_at=WHEN)
    with pytest.raises(IntegrityError, match="no packages"):
        create_backup([], tmp_path / "n.tgz", repo_root=ROOT, created_at=WHEN)
    with pytest.raises(IntegrityError, match="not inside the repository root"):
        create_backup([V2], tmp_path / "o.tgz", repo_root=root, created_at=WHEN)
    bad = copied(root, V2)
    (bad / "companies.jsonl").write_bytes((bad / "companies.jsonl").read_bytes().replace(b"Sample Mobility Works", b"Sample Mobility Workz", 1))
    with pytest.raises(IntegrityError, match="fails validation"):
        create_backup([bad], tmp_path / "v.tgz", repo_root=root, created_at=WHEN)
    other = copied(root, SAMPLES / "demo-trade-show" / "2025" / "demo-trade-show-2025.20261104T030000Z")
    (root / "data" / "samples" / "demo-trade-show" / "raw" / "exhibitors.csv").unlink()
    with pytest.raises(IntegrityError, match="snapshots cannot be backed up"):
        create_backup([other], tmp_path / "s.tgz", repo_root=root, created_at=WHEN)
    assert not any((tmp_path / n).exists() for n in ("n.tgz", "o.tgz", "v.tgz", "s.tgz"))


def rewrite_bundle(src: Path, dst: Path, change) -> Path:
    """Rewrite a bundle's members (name -> bytes) through ``change`` and pack them again."""
    with tarfile.open(src, "r:gz") as tar:
        members = {m.name: tar.extractfile(m).read() for m in tar.getmembers()}
    members = change(members)
    buffer = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=buffer, mtime=0) as gz, tarfile.open(fileobj=gz, mode="w") as tar:
        for name, data in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    dst.write_bytes(buffer.getvalue())
    return dst


@pytest.fixture()
def bundle(tmp_path: Path) -> Path:
    path = tmp_path / "good.tgz"
    create_backup([V2], path, repo_root=ROOT, created_at=WHEN)
    return path


def test_verify_backup_finds_changed_missing_and_unlisted_members(bundle: Path, tmp_path: Path) -> None:
    some = V2.relative_to(ROOT).as_posix() + "/companies.jsonl"

    def tamper(m):
        m[some] = m[some] + b"x"
        del m[V2.relative_to(ROOT).as_posix() + "/edition.json"]
        m["data/extra.txt"] = b"surprise"
        return m

    problems = verify_backup(rewrite_bundle(bundle, tmp_path / "t.tgz", tamper))
    assert f"{some} does not match its listed sha256/bytes" in problems
    assert any("edition.json is listed but missing" in p for p in problems)
    assert "member data/extra.txt is not listed in backup-manifest.json" in problems
    assert len(problems) == 3


def test_unreadable_bundles_are_input_errors(bundle: Path, tmp_path: Path) -> None:
    junk = tmp_path / "junk.tgz"
    junk.write_bytes(b"not a tar")
    with pytest.raises(IntegrityError, match="cannot be read"):
        verify_backup(junk)
    no_listing = rewrite_bundle(bundle, tmp_path / "nl.tgz", lambda m: {k: v for k, v in m.items() if k != BACKUP_MANIFEST})
    with pytest.raises(IntegrityError, match="has no backup-manifest.json"):
        verify_backup(no_listing)
    wrong = rewrite_bundle(bundle, tmp_path / "w.tgz", lambda m: {**m, BACKUP_MANIFEST: b'{"version": 99, "files": [], "packages": []}'})
    with pytest.raises(IntegrityError, match="not a version 1 backup listing"):
        verify_backup(wrong)


def test_restore_refuses_a_bundle_that_does_not_verify_and_writes_nothing(bundle: Path, tmp_path: Path) -> None:
    some = V2.relative_to(ROOT).as_posix() + "/companies.jsonl"
    tampered = rewrite_bundle(bundle, tmp_path / "t.tgz", lambda m: {**m, some: m[some] + b"x"})
    with pytest.raises(IntegrityError, match="does not verify; nothing restored"):
        restore_backup(tampered, tmp_path / "out")
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize("evil", ["../evil.txt", "/abs/evil.txt", "data/./x", "data//x"])
def test_restore_refuses_unsafe_member_paths(bundle: Path, tmp_path: Path, evil: str) -> None:
    unsafe = rewrite_bundle(bundle, tmp_path / "u.tgz", lambda m: {**m, evil: b"x"})
    assert any("unsafe path" in p for p in verify_backup(unsafe))
    with pytest.raises(IntegrityError, match="nothing restored"):
        restore_backup(unsafe, tmp_path / "out")
    assert not (tmp_path / "evil.txt").exists() and not (tmp_path / "out").exists()


def test_restore_refuses_links(bundle: Path, tmp_path: Path) -> None:
    with tarfile.open(bundle, "r:gz") as tar:
        members = [(m, tar.extractfile(m).read()) for m in tar.getmembers()]
    buffer = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=buffer, mtime=0) as gz, tarfile.open(fileobj=gz, mode="w") as tar:
        for info, data in members:
            tar.addfile(info, io.BytesIO(data))
        link = tarfile.TarInfo("data/link")
        link.type, link.linkname = tarfile.SYMTYPE, "/etc/passwd"
        tar.addfile(link)
    path = tmp_path / "l.tgz"
    path.write_bytes(buffer.getvalue())
    assert "member data/link is not a regular file" in verify_backup(path)


def test_restore_never_overwrites(bundle: Path, tmp_path: Path) -> None:
    target = tmp_path / "busy"
    target.mkdir()
    (target / "keep.txt").write_text("mine", encoding="utf-8")
    with pytest.raises(IntegrityError, match="never overwrites"):
        restore_backup(bundle, target)
    assert sorted(p.name for p in target.iterdir()) == ["keep.txt"]
    empty = tmp_path / "empty"
    empty.mkdir()
    assert restore_backup(bundle, empty)["ok"]


def test_restore_reports_a_listing_that_disagrees_with_the_package(bundle: Path, tmp_path: Path) -> None:
    def lie(m):
        listing = json.loads(m[BACKUP_MANIFEST])
        listing["packages"][0]["content_hash"] = "sha256:" + "0" * 64
        return {**m, BACKUP_MANIFEST: json.dumps(listing).encode()}

    result = restore_backup(rewrite_bundle(bundle, tmp_path / "x.tgz", lie), tmp_path / "out")
    assert not result["ok"] and "differs from the backup listing" in result["packages"][0]["problems"][0]


# ------------------------------------------------------------------------ regeneration from raw evidence


def test_records_and_package_regenerate_from_the_stored_raw_snapshot(tmp_path: Path) -> None:
    """Acquire once, keep only the evidence and the company registry, rebuild: the same records and the same content_hash."""
    fixed_rand.counter = 0
    repo = tmp_path / "repo"
    (repo / "list.csv").parent.mkdir(parents=True)
    (repo / "list.csv").write_text(CSV, encoding="utf-8")
    mapping = {"format": "csv", "columns": COLUMNS}
    config = make_config(name="imp", adapter=ADAPTER_NAME, start_urls=(ORIGIN,), source_type="csv_import", options={"mapping": mapping})
    registry = AdapterRegistry()
    registry.register(FileImportAdapter)
    store = RunStore(repo / "data" / "raw", config)
    result = import_files(config, {ORIGIN: repo / "list.csv"}, adapters=registry, clock=FakeClock(), rand=fixed_rand, sink=store)
    run_dir = store.finalize(result)
    assert verify_run(run_dir) == []
    sources, crawl_run = load_run(run_dir)
    stamps = {s["source_id"]: s["retrieved_at"] for s in sources}
    companies = CompanyRegistry(rand=fixed_rand, now_ms=lambda: 1_700_000_000_000)
    built = build_records([RawListing(r.data, r.source_id) for r in result.records], edition_id="example-expo-2026", retrieved_at=stamps, registry=companies, country_aliases={"exampleland": "ZZ"})
    companies.save(repo / "registry.json")
    common = dict(
        exhibition={"exhibition_id": "example-expo", "name": "Example Expo", "source_ids": [sources[0]["source_id"]], "verification_status": "unverified"},
        edition={"edition_id": "example-expo-2026", "exhibition_id": "example-expo", "year": 2026, "source_ids": [sources[0]["source_id"]], "verification_status": "unverified"},
        sources=sources, crawl_runs=[crawl_run], data_origin="synthetic", producer=PRODUCER, created_at=CREATED,
    )
    original = assemble_package(repo / "data" / "packages", companies=built.companies, participations=built.participations, **common)
    (repo / "list.csv").unlink()  # the original input file is gone: only the stored evidence remains

    assert verify_snapshots(original.path, repo)["problems"] == []
    listings = []
    for source in sources:
        rows = read_rows((repo / source["snapshot"]["locator"]).read_bytes(), mapping_from_dict(mapping)).rows
        listings.extend(RawListing(row, source["source_id"]) for row in rows)
    rebuilt = build_records(listings, edition_id="example-expo-2026", retrieved_at=stamps, registry=CompanyRegistry.load(repo / "registry.json"), country_aliases={"exampleland": "ZZ"})
    assert rebuilt.companies == built.companies and rebuilt.participations == built.participations
    again = assemble_package(tmp_path / "again", companies=rebuilt.companies, participations=rebuilt.participations, **common)
    assert again.manifest["content_hash"] == original.manifest["content_hash"]
    assert check_regenerable(original.path) == []


# --------------------------------------------------------------------------------------------- CLI


def test_cli(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    paths = [str(p) for p in PACKAGES]
    assert main(["snapshots", "--repo-root", str(ROOT), *paths]) == 0
    assert main(["regen", *paths]) == 0
    capsys.readouterr()
    out = tmp_path / "b.tgz"
    assert main(["backup", "--out", str(out), "--repo-root", str(ROOT), "--created-at", "2026-11-09T00:00:00Z", *paths]) == 0
    assert json.loads(capsys.readouterr().out)["packages"] == 3
    assert main(["verify-backup", str(out)]) == 0
    assert main(["restore", str(out), str(tmp_path / "r")]) == 0
    assert main(["restore", str(out), str(tmp_path / "r")]) == 2  # not empty any more
    assert "never overwrites" in capsys.readouterr().err
    assert main(["snapshots", "--repo-root", str(tmp_path), paths[0]]) == 1  # snapshots not found under that root
    with pytest.raises(SystemExit):
        main(["backup", "--out", str(tmp_path / "c.tgz"), "--created-at", "yesterday", paths[0]])


def test_bundle_members_carry_no_time_or_owner(bundle: Path) -> None:
    with tarfile.open(bundle, "r:gz") as tar:
        for info in tar.getmembers():
            assert (info.mtime, info.uid, info.gid, info.uname, info.gname, info.mode) == (0, 0, 0, "", "", 0o644), info.name
    assert gzip.open(bundle).read(1) and bundle.read_bytes()[4:8] == b"\x00\x00\x00\x00"  # gzip header mtime is 0


def test_restore_revalidates_packages_even_when_the_listing_was_rewritten_to_match(bundle: Path, tmp_path: Path) -> None:
    """A bundle whose listing was recomputed after a data file changed verifies, but the restored package does not."""
    some = V2.relative_to(ROOT).as_posix() + "/companies.jsonl"

    def forge(m):
        m[some] = m[some].replace(b"Sample Mobility Works", b"Sample Mobility Workz", 1)
        listing = json.loads(m[BACKUP_MANIFEST])
        for entry in listing["files"]:
            if entry["path"] == some:
                entry["sha256"], entry["bytes"] = sha256_of_bytes(m[some]), len(m[some])
        return {**m, BACKUP_MANIFEST: json.dumps(listing).encode()}

    forged = rewrite_bundle(bundle, tmp_path / "f.tgz", forge)
    assert verify_backup(forged) == []
    result = restore_backup(forged, tmp_path / "out")
    assert not result["ok"] and any("R8" in p for p in result["packages"][0]["problems"])
