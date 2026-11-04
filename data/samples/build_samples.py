"""Builds the two synthetic sample exhibitions (D1-06). Everything here is made up.

Regenerates ``data/samples/<exhibition_id>/`` deterministically, using the D1-04
writer (``etl.package.write_package``); the D1-05 validator (``etl.validate``) is
what proves the output is a valid package. Run from the repository root:

    python data/samples/build_samples.py           # create (refuses to overwrite)
    python data/samples/build_samples.py --force   # delete and recreate the two sample directories

The two exhibitions differ in structure on purpose (V2.3 generality acceptance):

- ``sample-fair``: rich optional fields (booth, hall, products, aliases, domains), HTML
  raw snapshots, two datasets of the same edition (v1, then v2 with change records, a
  removed listing and a merged company), completeness ``partial`` then ``complete``.
- ``demo-trade-show``: only required fields, a CSV raw snapshot, a manual entry, an
  official document, one recorded failed run, one dataset, completeness ``complete``.

Every record is marked synthetic. ``manifest.data_origin`` is ``synthetic``; country is
``ZZ``; URLs use reserved example domains. Synthetic data must never be used as fact.
"""
from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from etl.package import package_path, write_package  # noqa: E402

SAMPLES_ROOT = Path(__file__).resolve().parent
SCHEMA_VERSION_FILE = REPO / "schemas" / "v1" / "VERSION"
SYNTHETIC_NOTE = "合成測試資料（synthetic）：所有名稱、網址與數字皆為虛構，不代表任何真實展覽或企業。"
EXHIBITIONS = ("sample-fair", "demo-trade-show")


def make_id(prefix: str, series: str, number: int) -> str:
    """A valid ID of the form ``<prefix>_<26-char ULID-shaped>``; ``series`` is two letters."""
    return f"{prefix}_01JF{series}{number:020d}"


def sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


# --------------------------------------------------------------------------- raw snapshots


def html_listing(title: str, rows: list[tuple[str, str, str, str]], total: int) -> bytes:
    body = "".join(f"<tr><td>{n}</td><td>{h}</td><td>{b}</td><td>{c}</td></tr>\n" for n, h, b, c in rows)
    text = (
        "<!DOCTYPE html>\n<html lang=\"en\"><head><meta charset=\"utf-8\"><title>" + title + "</title></head>\n"
        "<body>\n<!-- synthetic sample: not a real exhibition -->\n<h1>" + title + "</h1>\n"
        f"<p>Total exhibitors: {total}</p>\n"
        "<table>\n<tr><th>Exhibitor</th><th>Hall</th><th>Booth</th><th>Category</th></tr>\n" + body + "</table>\n</body></html>\n"
    )
    return text.encode("utf-8")


def csv_listing(rows: list[tuple[str, str, str]]) -> bytes:
    lines = ["exhibitor,type,country"] + [",".join(r) for r in rows]
    return ("\n".join(lines) + "\n").encode("utf-8")


# --------------------------------------------------------------------------- sample-fair


def build_sample_fair(root: Path, schema_version: str) -> list[Path]:
    fair = "sample-fair"
    edition_id = "sample-fair-2026"
    v1_html = html_listing(
        "Sample Fair 2026 — Exhibitor List (synthetic)",
        [
            ("SYNTHETIC OPTICS LTD", "1", "A-01", "Optics"),
            ("Sample Mobility Works", "1", "A-02", "Vehicles"),
            ("Dummy Sensors Inc.", "2", "B-07", "Sensors"),
            ("Test Harness Labs", "2", "B-08", "Test equipment"),
        ],
        total=5,
    )
    v2_html = html_listing(
        "Sample Fair 2026 — Exhibitor List (synthetic, updated)",
        [
            ("SYNTHETIC OPTICS LTD", "1", "A-01", "Optics"),
            ("Sample Mobility Works", "1", "A-02", "Vehicles"),
            ("Dummy Sensors Inc.", "2", "B-12", "Sensors"),
            ("Sample Cyber Range LLC", "3", "C-03", "Cyber"),
        ],
        total=4,
    )
    raw_dir = root / fair / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    (raw_dir / "exhibitors-v1.html").write_bytes(v1_html)
    (raw_dir / "exhibitors-v2.html").write_bytes(v2_html)
    loc1 = "data/samples/sample-fair/raw/exhibitors-v1.html"
    loc2 = "data/samples/sample-fair/raw/exhibitors-v2.html"

    S = lambda n: make_id("src", "SA", n)  # noqa: E731
    C = lambda n: make_id("co", "CA", n)  # noqa: E731
    P = lambda n: make_id("pt", "PA", n)  # noqa: E731
    R = lambda n: make_id("run", "RA", n)  # noqa: E731
    H = lambda n: make_id("chg", "HA", n)  # noqa: E731

    exhibition = {
        "exhibition_id": fair,
        "name": "Sample Fair (Synthetic)",
        "name_zh_hant": "範例展覽（合成資料）",
        "organizer": "Synthetic Organizer Ltd.",
        "country": "ZZ",
        "city": "Sample City",
        "website": "https://www.example.com/sample-fair/",
        "source_ids": [S(1)],
        "verification_status": "unverified",
        "notes": SYNTHETIC_NOTE,
    }
    edition = {
        "edition_id": edition_id,
        "exhibition_id": fair,
        "year": 2026,
        "name": "Sample Fair 2026",
        "start_date": "2026-06-02",
        "end_date": "2026-06-05",
        "venue": "Sample Exhibition Centre",
        "source_ids": [S(1)],
        "field_sources": {"start_date": [S(1)], "end_date": [S(1)]},
        "verification_status": "unverified",
        "notes": SYNTHETIC_NOTE,
    }

    def source_list(n: int, locator: str, data: bytes, run: int, at: str, url: str) -> dict[str, Any]:
        return {
            "source_id": S(n),
            "source_type": "official_exhibitor_list",
            "url": url,
            "title": f"Exhibitor list v{n} (synthetic)",
            "retrieved_at": at,
            "crawl_run_id": R(run),
            "content_sha256": sha256(data),
            "media_type": "text/html",
            "language": "en",
            "http_status": 200,
            "snapshot": {"storage": "git", "locator": locator},
            "notes": SYNTHETIC_NOTE,
        }

    src_v1 = source_list(1, loc1, v1_html, 1, "2026-11-04T00:10:00Z", "https://www.example.com/sample-fair/exhibitors")
    src_site = {
        "source_id": S(2),
        "source_type": "official_website",
        "url": "https://www.example.com/sample-fair/",
        "title": "Sample Fair home page (synthetic)",
        "retrieved_at": "2026-11-04T00:12:00Z",
        "crawl_run_id": R(1),
        "content_sha256": sha256(b"synthetic home page, not stored"),
        "media_type": "text/html",
        "snapshot": {"storage": "not_stored"},
        "notes": "合成範例：示範未保存快照時必須說明原因（此處為合成資料，沒有實際快照）。",
    }
    src_v2 = source_list(3, loc2, v2_html, 2, "2026-11-04T01:40:00Z", "https://www.example.com/sample-fair/exhibitors")

    run1 = {
        "crawl_run_id": R(1),
        "exhibition_id": fair,
        "edition_id": edition_id,
        "crawler": {"name": "sample-builder", "version": "0.0.0"},
        "trigger": "manual",
        "started_at": "2026-11-04T00:09:00Z",
        "finished_at": "2026-11-04T00:15:00Z",
        "status": "succeeded",
        "stats": {"requests_attempted": 2, "requests_succeeded": 2, "records_extracted": 4, "error_count": 0},
        "notes": SYNTHETIC_NOTE,
    }
    run2 = {
        "crawl_run_id": R(2),
        "exhibition_id": fair,
        "edition_id": edition_id,
        "crawler": {"name": "sample-builder", "version": "0.0.0"},
        "trigger": "schedule",
        "started_at": "2026-11-04T01:39:00Z",
        "finished_at": "2026-11-04T01:42:00Z",
        "status": "succeeded",
        "stats": {"requests_attempted": 1, "requests_succeeded": 1, "records_extracted": 4, "error_count": 0},
        "notes": SYNTHETIC_NOTE,
    }

    def company(n: int, **kw: Any) -> dict[str, Any]:
        base = {"company_id": C(n), "status": "active", "country": "ZZ", "first_seen_at": "2026-11-04T00:10:00Z", "notes": SYNTHETIC_NOTE}
        base.update(kw)
        return base

    c1 = company(
        1,
        name="Synthetic Optics Ltd.",
        name_zh_hant="合成光學有限公司",
        aliases=[{"name": "SynOptics", "lang": "en", "source_ids": [S(1)]}],
        website="https://www.example.org/synoptics/",
        domains=["example.org"],
        description="合成資料：虛構的光學設備廠商。",
        source_ids=[S(1), S(2)],
        field_sources={"website": [S(2)]},
        verification_status="verified",
    )
    c2 = company(2, name="Sample Mobility Works", name_en="Sample Mobility Works", source_ids=[S(1)], verification_status="unverified")
    c3 = company(3, name="Dummy Sensors Inc.", domains=["example.net"], source_ids=[S(1)], verification_status="unverified")
    c4 = company(4, name="Test Harness Labs", source_ids=[S(1)], verification_status="insufficient_data")
    c3_merged = dict(c3, status="merged", merged_into=C(1), notes=SYNTHETIC_NOTE + " 合成範例：示範兩筆紀錄確認為同一企業。")
    c5 = company(5, name="Sample Cyber Range LLC", first_seen_at="2026-11-04T01:40:00Z", source_ids=[S(3)], verification_status="unverified")

    def part(n: int, company_n: int, name: str, hall: str, booth: str | None, category: str, src: int, **kw: Any) -> dict[str, Any]:
        record: dict[str, Any] = {
            "participation_id": P(n),
            "company_id": C(company_n),
            "edition_id": edition_id,
            "exhibitor_name_as_listed": name,
            "participation_type": "exhibitor",
            "listing_status": "listed",
            "hall": hall,
            "categories_as_listed": [category],
            "first_seen_at": "2026-11-04T00:10:00Z",
            "last_seen_at": "2026-11-04T00:10:00Z",
            "source_ids": [S(src)],
            "verification_status": "unverified",
            "notes": SYNTHETIC_NOTE,
        }
        if booth is not None:
            record["booth"] = booth
        record.update(kw)
        return record

    p1 = part(1, 1, "SYNTHETIC OPTICS LTD", "1", "A-01", "Optics", 1, products_as_listed=["Synthetic lens A", "Synthetic lens B"])
    p2 = part(2, 2, "Sample Mobility Works", "1", "A-02", "Vehicles", 1, participation_type="co_exhibitor", website_as_listed="https://www.example.org/mobility/")
    p3 = part(3, 3, "Dummy Sensors Inc.", "2", None, "Sensors", 1, country_as_listed="Exampleland")
    p4 = part(4, 4, "Test Harness Labs", "2", "B-08", "Test equipment", 1)
    p3_v2 = dict(p3, booth="B-12", last_seen_at="2026-11-04T01:40:00Z", source_ids=[S(1), S(3)])
    p1_v2 = dict(p1, last_seen_at="2026-11-04T01:40:00Z")
    p2_v2 = dict(p2, last_seen_at="2026-11-04T01:40:00Z")
    p4_v2 = dict(p4, listing_status="removed", notes=SYNTHETIC_NOTE + " 合成範例：先前列出，最新名單已不在其中；紀錄保留。")
    p5 = part(5, 5, "Sample Cyber Range LLC", "3", "C-03", "Cyber", 3, first_seen_at="2026-11-04T01:40:00Z", last_seen_at="2026-11-04T01:40:00Z")

    created_v1 = "2026-11-04T01:00:00Z"
    created_v2 = "2026-11-04T02:00:00Z"
    ds1 = f"{edition_id}.20261104T010000Z"
    ds2 = f"{edition_id}.20261104T020000Z"
    producer = {"name": "sample-builder", "version": "0.0.0"}

    out1 = package_path(root, fair, 2026, ds1)
    write_package(
        out1,
        exhibition=exhibition,
        edition=edition,
        records={"companies": [c1, c2, c3, c4], "participations": [p1, p2, p3, p4], "sources": [src_v1, src_site], "crawl_runs": [run1], "changes": []},
        manifest={
            "schema_version": schema_version, "dataset_id": ds1, "exhibition_id": fair, "edition_id": edition_id, "edition_year": 2026,
            "created_at": created_v1, "data_origin": "synthetic", "producer": producer, "previous_dataset_id": None,
            "completeness_status": "partial",
            "completeness": {
                "official_exhibitor_count": 5, "official_count_source_id": S(1), "official_count_as_of": "2026-11-04",
                "collected_participation_count": 4, "notes": "合成範例：名單頁寫 5 家，只列出 4 家，因此為 partial。",
            },
            "notes": SYNTHETIC_NOTE,
        },
    )

    def change(n: int, entity_type: str, entity_id: str, change_type: str, **kw: Any) -> dict[str, Any]:
        record = {
            "change_id": H(n), "dataset_id": ds2, "previous_dataset_id": ds1, "entity_type": entity_type, "entity_id": entity_id,
            "change_type": change_type, "detected_at": "2026-11-04T01:45:00Z", "source_ids": [S(3)], "notes": SYNTHETIC_NOTE,
        }
        record.update(kw)
        return record

    changes = [
        change(1, "participation", P(3), "modified", field_changes=[{"field": "booth", "before": None, "after": "B-12"}]),
        change(2, "participation", P(4), "removed"),
        change(3, "company", C(3), "modified", field_changes=[{"field": "status", "before": "active", "after": "merged"}, {"field": "merged_into", "before": None, "after": C(1)}]),
        change(4, "company", C(5), "added"),
        change(5, "participation", P(5), "added"),
    ]
    out2 = package_path(root, fair, 2026, ds2)
    write_package(
        out2,
        exhibition=exhibition,
        edition=edition,
        records={
            "companies": [c1, c2, c3_merged, c4, c5],
            "participations": [p1_v2, p2_v2, p3_v2, p4_v2, p5],
            "sources": [src_v1, src_site, src_v2],
            "crawl_runs": [run1, run2],
            "changes": changes,
        },
        manifest={
            "schema_version": schema_version, "dataset_id": ds2, "exhibition_id": fair, "edition_id": edition_id, "edition_year": 2026,
            "created_at": created_v2, "data_origin": "synthetic", "producer": producer, "previous_dataset_id": ds1,
            "completeness_status": "complete",
            "completeness": {
                "official_exhibitor_count": 4, "official_count_source_id": S(3), "official_count_as_of": "2026-11-04",
                "collected_participation_count": 4, "notes": "合成範例：更新後的名單頁寫 4 家，已列出 4 家（另有 1 筆已下架），因此為 complete。",
            },
            "notes": SYNTHETIC_NOTE,
        },
    )
    return [out1, out2]


# --------------------------------------------------------------------------- demo-trade-show


def build_demo_trade_show(root: Path, schema_version: str) -> list[Path]:
    show = "demo-trade-show"
    edition_id = "demo-trade-show-2025"
    csv = csv_listing([("Alpha Demo Co", "exhibitor", "ZZ"), ("Beta Demo Trading", "sponsor", "ZZ"), ("Gamma Demo Works", "unknown", "ZZ")])
    raw_dir = root / show / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    (raw_dir / "exhibitors.csv").write_bytes(csv)
    locator = "data/samples/demo-trade-show/raw/exhibitors.csv"

    S = lambda n: make_id("src", "SB", n)  # noqa: E731
    C = lambda n: make_id("co", "CB", n)  # noqa: E731
    P = lambda n: make_id("pt", "PB", n)  # noqa: E731
    R = lambda n: make_id("run", "RB", n)  # noqa: E731

    exhibition = {"exhibition_id": show, "name": "Demo Trade Show (Synthetic)", "source_ids": [S(2)], "verification_status": "human_confirmed", "notes": SYNTHETIC_NOTE}
    edition = {"edition_id": edition_id, "exhibition_id": show, "year": 2025, "source_ids": [S(2)], "verification_status": "human_confirmed", "notes": SYNTHETIC_NOTE}

    sources = [
        {
            "source_id": S(1), "source_type": "csv_import", "url": "https://www.example.net/demo-trade-show/exhibitors.csv",
            "title": "Exhibitor CSV (synthetic)", "retrieved_at": "2026-11-04T03:00:00Z", "crawl_run_id": R(1),
            "content_sha256": sha256(csv), "media_type": "text/csv", "language": "en",
            "snapshot": {"storage": "git", "locator": locator}, "notes": SYNTHETIC_NOTE,
        },
        {
            "source_id": S(2), "source_type": "manual_entry", "title": "Entered by hand (synthetic)", "retrieved_at": "2026-11-04T03:05:00Z",
            "content_sha256": sha256(b"edition and exhibition names typed in by a person (synthetic)"),
            "snapshot": {"storage": "not_stored"}, "notes": "合成範例：人工輸入展覽與屆次名稱，沒有外部快照。",
        },
        {
            "source_id": S(3), "source_type": "official_document", "url": "https://www.example.net/demo-trade-show/press-release.pdf",
            "title": "Press release (synthetic)", "retrieved_at": "2026-11-04T03:06:00Z", "crawl_run_id": R(1),
            "content_sha256": sha256(b"press release stating 3 exhibitors (synthetic)"), "media_type": "application/pdf", "language": "en",
            "snapshot": {"storage": "not_stored"}, "notes": "合成範例：官方文件說明參展商數；此處為合成資料，沒有實際快照。",
        },
    ]
    runs = [
        {
            "crawl_run_id": R(1), "exhibition_id": show, "edition_id": edition_id, "crawler": {"name": "sample-importer", "version": "0.0.0"},
            "trigger": "import", "started_at": "2026-11-04T02:59:00Z", "finished_at": "2026-11-04T03:07:00Z", "status": "succeeded",
            "stats": {"requests_attempted": 2, "requests_succeeded": 2, "records_extracted": 3, "error_count": 0}, "notes": SYNTHETIC_NOTE,
        },
        {
            "crawl_run_id": R(2), "exhibition_id": show, "edition_id": edition_id, "crawler": {"name": "sample-crawler", "version": "0.0.0"},
            "trigger": "manual", "started_at": "2026-11-04T02:30:00Z", "finished_at": "2026-11-04T02:31:00Z", "status": "failed",
            "stats": {"requests_attempted": 1, "requests_succeeded": 0, "records_extracted": 0, "error_count": 1},
            "error_samples": [{"code": "access_blocked", "message": "合成範例：來源網站回應 403，依規定停止，不繞過。", "url": "https://www.example.net/demo-trade-show/exhibitors", "occurred_at": "2026-11-04T02:30:30Z"}],
            "notes": "合成範例：記錄一次取得失敗；失敗只記錄，改用其他來源（CSV 匯入）繼續，不阻礙開發。",
        },
    ]
    companies = [
        {"company_id": C(n), "name": name, "status": "active", "source_ids": [S(1)], "verification_status": vs}
        for n, name, vs in ((1, "Alpha Demo Co", "unverified"), (2, "Beta Demo Trading", "human_confirmed"), (3, "Gamma Demo Works", "insufficient_data"))
    ]
    participations = [
        {
            "participation_id": P(n), "company_id": C(n), "edition_id": edition_id, "exhibitor_name_as_listed": name, "participation_type": ptype,
            "listing_status": "listed", "source_ids": [S(1)], "verification_status": "unverified",
        }
        for n, name, ptype in ((1, "Alpha Demo Co", "exhibitor"), (2, "Beta Demo Trading", "sponsor"), (3, "Gamma Demo Works", "unknown"))
    ]
    dataset_id = f"{edition_id}.20261104T030000Z"
    out = package_path(root, show, 2025, dataset_id)
    write_package(
        out,
        exhibition=exhibition,
        edition=edition,
        records={"companies": companies, "participations": participations, "sources": sources, "crawl_runs": runs, "changes": []},
        manifest={
            "schema_version": schema_version, "dataset_id": dataset_id, "exhibition_id": show, "edition_id": edition_id, "edition_year": 2025,
            "created_at": "2026-11-04T03:10:00Z", "data_origin": "synthetic", "producer": {"name": "sample-builder", "version": "0.0.0"},
            "previous_dataset_id": None, "completeness_status": "complete",
            "completeness": {
                "official_exhibitor_count": 3, "official_count_source_id": S(3), "official_count_as_of": "2026-11-04",
                "collected_participation_count": 3, "notes": "合成範例：官方文件寫 3 家，已列出 3 家，因此為 complete。",
            },
            "notes": SYNTHETIC_NOTE,
        },
    )
    return [out]


# --------------------------------------------------------------------------- entry points


def build_all(root: Path = SAMPLES_ROOT, schema_version: str | None = None) -> list[Path]:
    """Create both sample exhibitions under ``root`` and return the package directories."""
    version = schema_version or SCHEMA_VERSION_FILE.read_text(encoding="utf-8").strip()
    return [*build_sample_fair(root, version), *build_demo_trade_show(root, version)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the synthetic sample exhibitions under data/samples/.")
    parser.add_argument("--force", action="store_true", help="delete the two sample directories first, then rebuild")
    args = parser.parse_args(argv)
    if args.force:
        for name in EXHIBITIONS:
            shutil.rmtree(SAMPLES_ROOT / name, ignore_errors=True)
    for path in build_all():
        print(path.relative_to(REPO))
    return 0


if __name__ == "__main__":
    sys.exit(main())
