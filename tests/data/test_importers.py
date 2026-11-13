"""Tests for crawler.importers and crawler.file_import (D2-04). Fixtures are built in code; every name is synthetic."""
from __future__ import annotations

import io
import json
import textwrap

import pytest
from openpyxl import Workbook

from crawler.adapters import AdapterRegistry, ParseError
from crawler.errors import ErrorCode
from crawler.file_import import ADAPTER_NAME, FileImportAdapter, LocalFileFetcher, import_files
from crawler.importers import MAX_WARNINGS, ImportMapping, load_mapping, mapping_from_dict, normalize_header, read_rows
from crawler.models import Request
from crawler.source_config import ConfigError
from etl.hashing import sha256_of_bytes
from etl.schema_registry import SchemaSet
from tests.data.crawl_testkit import FakeClock, fixed_rand, make_config

COLUMNS = [
    {"source": "Company", "field": "exhibitor_name_as_listed", "required": True},
    {"source": "Booth", "field": "booth"},
    {"source": "Country", "field": "country"},
]


def mapping(fmt: str, **extra) -> ImportMapping:
    return mapping_from_dict({"format": fmt, "columns": COLUMNS, **extra})


CSV = "Company,Booth,Country\nSynthetic Optics Ltd.,A1,Exampleland\n  Acme Demo  ,B2,\n,C3,Nowhere\n\nBeta Test,,Testonia\n"


# --- mapping validation ---------------------------------------------------------------------


def test_mapping_defaults():
    m = mapping("csv")
    assert (m.header_row, m.encoding, m.delimiter, m.sheet, m.table_index) == (1, "utf-8-sig", ",", None, 0)
    assert [c.field for c in m.columns] == ["exhibitor_name_as_listed", "booth", "country"] and m.columns[0].required


@pytest.mark.parametrize(
    "patch,message",
    [
        ({"format": "docx"}, "format must be one of"),
        ({"format": None}, "format must be one of"),
        ({"columns": []}, "non-empty list"),
        ({"columns": "Company"}, "non-empty list"),
        ({"columns": [{"source": "A"}]}, "field"),
        ({"columns": [{"source": "", "field": "a"}]}, "source"),
        ({"columns": [{"source": "A", "field": "Bad Name"}]}, "field must match"),
        ({"columns": [{"source": "A", "field": "_row"}]}, "field must match"),
        ({"columns": [{"source": "A", "field": "api_token"}]}, "credential"),
        ({"columns": [{"source": "A", "field": "a", "required": "yes"}]}, "required"),
        ({"columns": [{"source": "A", "field": "a", "extra": 1}]}, "must be a table"),
        ({"columns": [{"source": "A", "field": "a"}, {"source": " a ", "field": "b"}]}, "repeats source"),
        ({"columns": [{"source": "A", "field": "a"}, {"source": "B", "field": "a"}]}, "repeats field"),
        ({"header_row": 0}, "header_row"),
        ({"header_row": True}, "header_row"),
        ({"table_index": -1}, "table_index"),
        ({"encoding": "no-such-codec"}, "encoding"),
        ({"delimiter": ";;"}, "delimiter"),
        ({"split_pattern": "("}, "split_pattern"),
        ({"sheet": ""}, "sheet"),
        ({"surprise": 1}, "unknown mapping key"),
    ],
)
def test_bad_mappings_are_rejected(patch, message):
    base = {"format": "csv", "columns": COLUMNS}
    with pytest.raises(ConfigError, match=message):
        mapping_from_dict({**base, **patch})


def test_mapping_must_be_a_table():
    with pytest.raises(ConfigError):
        mapping_from_dict([1])  # type: ignore[arg-type]


def test_load_mapping_from_toml(tmp_path):
    path = tmp_path / "m.toml"
    path.write_text('format = "csv"\ndelimiter = ";"\n[[columns]]\nsource = "Name"\nfield = "name"\nrequired = true\n', encoding="utf-8")
    m = load_mapping(path)
    assert m.delimiter == ";" and m.columns[0].required
    with pytest.raises(ConfigError, match="cannot read"):
        load_mapping(tmp_path / "missing.toml")
    path.write_text("not = [toml", encoding="utf-8")
    with pytest.raises(ConfigError, match="cannot read"):
        load_mapping(path)


def test_normalize_header():
    assert normalize_header("  Company \n  NAME ") == "company name"


# --- CSV --------------------------------------------------------------------------------------


def test_csv_rows_blank_cells_and_row_numbers():
    result = read_rows(CSV.encode(), mapping("csv"))
    assert result.rows == [
        {"exhibitor_name_as_listed": "Synthetic Optics Ltd.", "booth": "A1", "country": "Exampleland", "_row": 2},
        {"exhibitor_name_as_listed": "Acme Demo", "booth": "B2", "_row": 3},  # empty country is left out, not invented
        {"exhibitor_name_as_listed": "Beta Test", "country": "Testonia", "_row": 6},
    ]
    assert result.rows_seen == 4  # the blank line is not data; the row without a company is seen but skipped
    assert result.warnings == ["row 4: required field(s) empty: exhibitor_name_as_listed; skipped"]


def test_csv_header_matching_ignores_case_and_spacing_and_order():
    data = "country , BOOTH,  company name\nX,Y,Zed\n".encode()
    m = mapping_from_dict({"format": "csv", "columns": [{"source": "Company  Name", "field": "name", "required": True}, {"source": "booth", "field": "booth"}]})
    assert read_rows(data, m).rows == [{"name": "Zed", "booth": "Y", "_row": 2}]


def test_csv_bom_delimiter_header_row_and_quotes():
    data = '﻿title line\nCompany;Booth\n"Acme; Inc.";"A ""1"""\n'.encode()
    m = mapping_from_dict({"format": "csv", "delimiter": ";", "header_row": 2, "columns": COLUMNS[:2]})
    assert read_rows(data, m).rows == [{"exhibitor_name_as_listed": "Acme; Inc.", "booth": 'A "1"', "_row": 3}]


def test_csv_other_encoding():
    data = "Company,Booth\n株式會社測試,A1\n".encode("big5")
    m = mapping_from_dict({"format": "csv", "encoding": "big5", "columns": COLUMNS[:2]})
    assert read_rows(data, m).rows[0]["exhibitor_name_as_listed"] == "株式會社測試"


def test_csv_wrong_encoding_is_a_parse_error():
    with pytest.raises(ParseError, match="not valid utf-8"):
        read_rows("Company\n株式會社".encode("big5"), mapping("csv"))


def test_csv_missing_required_column_names_what_was_found():
    with pytest.raises(ParseError, match=r"required column.*Company.*found: Name, Booth"):
        read_rows(b"Name,Booth\nA,B\n", mapping("csv"))


def test_csv_missing_optional_column_is_a_warning():
    result = read_rows(b"Company\nAcme\n", mapping("csv"))
    assert result.rows == [{"exhibitor_name_as_listed": "Acme", "_row": 2}]
    assert sum("optional column" in w for w in result.warnings) == 2


def test_csv_duplicate_headers_are_refused():
    with pytest.raises(ParseError, match="duplicate column header"):
        read_rows(b"Company,company\nA,B\n", mapping("csv"))


def test_csv_header_row_beyond_file():
    with pytest.raises(ParseError, match="header_row 5"):
        read_rows(b"Company\n", mapping("csv", header_row=5))


def test_csv_short_rows_are_handled():
    result = read_rows(b"Company,Booth,Country\nAcme\n", mapping("csv"))
    assert result.rows == [{"exhibitor_name_as_listed": "Acme", "_row": 2}]


def test_repeated_header_rows_are_not_data():
    result = read_rows(b"Company,Booth\nA,1\nCompany, booth\nB,2\n", mapping_from_dict({"format": "csv", "columns": COLUMNS[:2]}))
    assert [r["exhibitor_name_as_listed"] for r in result.rows] == ["A", "B"]


def test_row_limit(monkeypatch):
    import crawler.importers as module

    monkeypatch.setattr(module, "MAX_ROWS", 3)
    assert len(read_rows(b"Company\na\nb\nc\n", mapping("csv")).rows) == 3
    with pytest.raises(ParseError, match="more than 3 rows"):
        read_rows(b"Company\na\nb\nc\nd\n", mapping("csv"))


def test_csv_empty_file():
    with pytest.raises(ParseError):
        read_rows(b"", mapping("csv"))


def test_warning_count_is_bounded():
    data = "Company,Booth\n" + ",x\n" * (MAX_WARNINGS + 50)
    result = read_rows(data.encode(), mapping_from_dict({"format": "csv", "columns": COLUMNS[:2]}))
    assert len(result.warnings) <= MAX_WARNINGS + 2 and result.warnings[-1] == "further warnings omitted" and result.rows == []


# --- HTML table -------------------------------------------------------------------------------

HTML = """<html><body><table id="nav"><tr><td>menu</td></tr></table>
<table id="list" class="x"><caption>c</caption>
<thead><tr><th>Company</th><th>Booth</th><th>Country</th></tr></thead>
<tbody>
<tr><td><a href="/c/1">Synthetic Optics Ltd.</a></td><td>A1<br>Hall&nbsp;2</td><td>Exampleland &amp; Co</td></tr>
<tr><td>Acme   Demo</td><td></td><td>Testonia</td></tr>
<tr><td>Nested</td><td>pre <table><tr><td>inner</td></tr></table> B9</td><td>X</td></tr>
</tbody></table></body></html>"""


def test_html_table_by_id_with_nested_table_and_entities():
    m = mapping("html_table", table_id="list")
    result = read_rows(HTML.encode(), m)
    assert result.rows[0] == {"exhibitor_name_as_listed": "Synthetic Optics Ltd.", "booth": "A1 Hall 2", "country": "Exampleland & Co", "_row": 2}
    assert result.rows[1] == {"exhibitor_name_as_listed": "Acme Demo", "country": "Testonia", "_row": 3}
    assert result.rows[2]["exhibitor_name_as_listed"] == "Nested" and result.rows[2]["booth"] == "pre B9" and "inner" not in json.dumps(result.rows)


def test_html_table_by_index_and_errors():
    assert read_rows(HTML.encode(), mapping("html_table", table_index=1)).rows
    with pytest.raises(ParseError, match="required column"):
        read_rows(HTML.encode(), mapping("html_table", table_index=0))
    with pytest.raises(ParseError, match="only 2 table"):
        read_rows(HTML.encode(), mapping("html_table", table_index=2))
    with pytest.raises(ParseError, match="id='nope'"):
        read_rows(HTML.encode(), mapping("html_table", table_id="nope"))
    with pytest.raises(ParseError, match="no <table>"):
        read_rows(b"<html><p>none</p></html>", mapping("html_table"))


def test_html_spans_are_warned_but_other_attributes_are_not():
    plain = '<table><tr><th class="c" id="h">Company</th></tr><tr><td class="x" title="y">A</td></tr></table>'
    assert not any("colspan" in w for w in read_rows(plain.encode(), mapping("html_table")).warnings)
    spanned = '<table><tr><th>Company</th></tr><tr><td colspan="2">A</td></tr></table>'
    assert any("colspan" in w for w in read_rows(spanned.encode(), mapping("html_table")).warnings)


def test_html_not_utf8_is_decoded_leniently_with_warning():
    page = '<table><tr><th>Company</th></tr><tr><td>Caf\xe9</td></tr></table>'.encode("latin-1")
    result = read_rows(page, mapping("html_table"))
    assert any("not valid UTF-8" in w for w in result.warnings) and result.rows


# --- Excel ------------------------------------------------------------------------------------


def workbook_bytes(sheets: dict[str, list[list]]) -> bytes:
    book = Workbook()
    book.remove(book.active)
    for name, rows in sheets.items():
        sheet = book.create_sheet(name)
        for row in rows:
            sheet.append(row)
    buffer = io.BytesIO()
    book.save(buffer)
    return buffer.getvalue()


def test_xlsx_first_sheet_numbers_dates_and_warning():
    import datetime

    data = workbook_bytes({"Main": [["Company", "Booth", "Country"], ["Synthetic Optics", 12.0, "X"], ["Beta", 3.5, datetime.date(2026, 5, 1)], [None, None, None], ["Gamma", "G7", None]], "Other": [["x"]]})
    result = read_rows(data, mapping("xlsx"))
    assert [r["booth"] for r in result.rows] == ["12", "3.5", "G7"]
    assert result.rows[1]["country"] == "2026-05-01"
    assert any("2 sheets" in w for w in result.warnings)


def test_xlsx_named_sheet_and_missing_sheet():
    data = workbook_bytes({"A": [["nothing"]], "List": [["Company"], ["Acme"]]})
    assert read_rows(data, mapping("xlsx", sheet="List")).rows[0]["exhibitor_name_as_listed"] == "Acme"
    with pytest.raises(ParseError, match=r"sheet 'Nope' not found.*A, List"):
        read_rows(data, mapping("xlsx", sheet="Nope"))


def test_xlsx_formula_cached_values_are_read_not_evaluated():
    book = Workbook()
    book.active.append(["Company"])
    book.active.append(["=1+1"])
    buffer = io.BytesIO()
    book.save(buffer)
    # openpyxl writes no cached value, so a never-calculated formula reads as empty: the row is skipped, not guessed
    result = read_rows(buffer.getvalue(), mapping("xlsx"))
    assert result.rows == []


@pytest.mark.parametrize("junk", [b"", b"not a zip", b"PK\x03\x04broken"])
def test_xlsx_garbage_is_a_parse_error(junk):
    with pytest.raises(ParseError, match="not a readable .xlsx"):
        read_rows(junk, mapping("xlsx"))


# --- PDF text ---------------------------------------------------------------------------------


def make_pdf(pages: list[list[str]]) -> bytes:
    """A minimal valid PDF whose text layer holds the given lines (one page per list)."""
    objects: list[bytes] = []
    kids = " ".join(f"{3 + 2 * i} 0 R" for i in range(len(pages)))
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>".encode())
    font_id = 3 + 2 * len(pages)
    for i, lines in enumerate(pages):
        content_id = 4 + 2 * i
        objects.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 600 800] /Contents {content_id} 0 R /Resources << /Font << /F1 {font_id} 0 R >> >> >>".encode())
        ops = "BT /F1 10 Tf 14 TL 20 780 Td " + " T* ".join("(" + line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)") + ") Tj" for line in lines) + " ET"
        objects.append(f"<< /Length {len(ops)} >>\nstream\n{ops}\nendstream".encode())
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(out.tell())
        out.write(f"{number} 0 obj\n".encode() + body + b"\nendobj\n")
    xref = out.tell()
    out.write(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    for offset in offsets:
        out.write(f"{offset:010d} 00000 n \n".encode())
    out.write(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    return out.getvalue()


def test_pdf_text_rows_across_pages_with_repeated_header():
    pdf = make_pdf([["Exhibitor List", "Company  Booth  Country", "Synthetic Optics  A1  Exampleland", "Acme Demo  B2  Testonia"], ["Company  Booth  Country", "Beta Test  C3  Examplestan", "broken line only"]])
    m = mapping("pdf_text", header_row=2)
    result = read_rows(pdf, m)
    assert [(r["exhibitor_name_as_listed"], r["booth"], r["_row"]) for r in result.rows] == [("Synthetic Optics", "A1", 3), ("Acme Demo", "B2", 4), ("Beta Test", "C3", 6)]  # the repeated header is not a row
    assert any("verify the result" in w for w in result.warnings)
    assert any("line 7" in w and "expected 3" in w for w in result.warnings)


def test_pdf_wrong_column_count_is_skipped_with_warning():
    pdf = make_pdf([["Company  Booth", "Acme  A1", "only one"]])
    result = read_rows(pdf, mapping_from_dict({"format": "pdf_text", "columns": COLUMNS[:2]}))
    assert [r["exhibitor_name_as_listed"] for r in result.rows] == ["Acme"]
    assert any("line 3" in w and "expected 2" in w for w in result.warnings)


def test_pdf_without_text_layer_or_garbage():
    with pytest.raises(ParseError, match="no text layer"):
        read_rows(make_pdf([[]]).replace(b"BT /F1 10 Tf 14 TL 20 780 Td  ET", b""), mapping("pdf_text"))
    with pytest.raises(ParseError, match="not a readable PDF"):
        read_rows(b"%PDF-1.4 garbage", mapping("pdf_text"))
    with pytest.raises(ParseError):
        read_rows(b"", mapping("pdf_text"))


# --- adapter and runner integration ----------------------------------------------------------

ORIGIN = "https://files.example.com/exhibitors.csv"


def import_config(fmt="csv", **extra):
    return make_config(
        name="csv-import", adapter=ADAPTER_NAME, start_urls=(ORIGIN,), allowed_domains=("example.com",), source_type="csv_import",
        options={"mapping": {"format": fmt, "columns": COLUMNS, **extra}},
    )


def registry():
    reg = AdapterRegistry()
    reg.register(FileImportAdapter)
    return reg


def test_adapter_validates_options():
    adapter = FileImportAdapter()
    adapter.validate_options({"mapping": {"format": "csv", "columns": COLUMNS}})
    for bad, message in [({}, "required"), ({"mapping": {"format": "x", "columns": COLUMNS}}, "format"), ({"mapping": {"format": "csv", "columns": COLUMNS}, "other": 1}, "unknown option")]:
        with pytest.raises(ConfigError, match=message):
            adapter.validate_options(bad)


def test_import_files_end_to_end_with_provenance(tmp_path):
    path = tmp_path / "list.csv"
    path.write_bytes(CSV.encode())
    result = import_files(import_config(), {ORIGIN: path}, adapters=registry(), clock=FakeClock(), rand=fixed_rand)
    assert result.status == "succeeded" and result.errors == []
    (snap,) = result.snapshots
    assert snap.content_sha256 == sha256_of_bytes(CSV.encode()) and snap.url == ORIGIN and snap.media_type == "text/csv"
    assert [r.data["exhibitor_name_as_listed"] for r in result.records] == ["Synthetic Optics Ltd.", "Acme Demo", "Beta Test"]
    assert all(r.source_id == snap.source_id and r.snapshot_sha256 == snap.content_sha256 for r in result.records)
    assert result.crawl_run["trigger"] == "import" and result.crawl_run["crawler"] == {"name": "file-import", "version": "1.0.0"}
    assert SchemaSet().errors("crawl_run", result.crawl_run) == []
    assert "row 4" in result.log_text  # the skipped row's warning reached the log


def test_import_unreadable_file_is_recorded_not_raised(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_bytes(b"Name\nx\n")
    result = import_files(import_config(), {ORIGIN: path}, adapters=registry(), clock=FakeClock(), rand=fixed_rand)
    assert [e.code for e in result.errors] == [ErrorCode.PARSE_ERROR] and result.snapshots and not result.records
    assert result.status == "partial"  # evidence kept, data not usable


def test_import_missing_file_and_unlisted_url(tmp_path):
    result = import_files(import_config(), {ORIGIN: tmp_path / "nope.csv"}, adapters=registry(), clock=FakeClock(), rand=fixed_rand)
    assert result.status == "failed" and result.errors[0].code is ErrorCode.HTTP_ERROR
    with pytest.raises(ConfigError, match="not in start_urls"):
        import_files(import_config(), {"https://files.example.com/other.csv": tmp_path / "x"}, adapters=registry())


def test_import_never_touches_network_or_robots(tmp_path):
    path = tmp_path / "list.csv"
    path.write_bytes(CSV.encode())
    result = import_files(import_config(), {ORIGIN: path}, adapters=registry(), clock=FakeClock(), rand=fixed_rand)
    assert result.crawl_run["stats"]["requests_attempted"] == 1  # the file only; no robots.txt


def test_local_fetcher_size_limit_and_unknown_url(tmp_path):
    path = tmp_path / "big.csv"
    path.write_bytes(b"x" * 100)
    fetcher = LocalFileFetcher({ORIGIN: path})
    kw = dict(timeout=1.0, user_agent="t", allowed_domains=("example.com",))
    from crawler.fetch import FetchError

    with pytest.raises(FetchError, match="max_bytes"):
        fetcher.fetch(Request(ORIGIN), max_bytes=10, **kw)
    with pytest.raises(FetchError) as caught:
        fetcher.fetch(Request("https://files.example.com/else"), max_bytes=1000, **kw)
    assert caught.value.http_status == 404


def test_default_registry_has_the_adapter():
    from crawler.adapters import default_registry

    assert ADAPTER_NAME in default_registry


def test_two_differently_structured_files_need_only_two_mappings(tmp_path):
    """V2.3: same code, different layouts: only the mapping differs."""
    page = tmp_path / "a.html"
    page.write_text('<table><tr><th>Aussteller</th><th>Halle</th></tr><tr><td>Beispiel GmbH</td><td>3</td></tr></table>', encoding="utf-8")
    sheet = tmp_path / "b.xlsx"
    sheet.write_bytes(workbook_bytes({"S": [["x"], ["Name", "Stand"], ["Demo Corp", "Z9"]]}))
    url_a, url_b = "https://files.example.com/a.html", "https://files.example.com/b.xlsx"
    cfg_a = make_config(name="a", adapter=ADAPTER_NAME, start_urls=(url_a,), source_type="official_exhibitor_list", options={"mapping": {"format": "html_table", "columns": [{"source": "Aussteller", "field": "exhibitor_name_as_listed", "required": True}, {"source": "Halle", "field": "hall"}]}})
    cfg_b = make_config(name="b", exhibition_id="other-fair", edition_id="other-fair-2026", adapter=ADAPTER_NAME, start_urls=(url_b,), source_type="excel_import", options={"mapping": {"format": "xlsx", "header_row": 2, "columns": [{"source": "Name", "field": "exhibitor_name_as_listed", "required": True}, {"source": "Stand", "field": "booth"}]}})
    ra = import_files(cfg_a, {url_a: page}, adapters=registry(), clock=FakeClock(), rand=fixed_rand)
    rb = import_files(cfg_b, {url_b: sheet}, adapters=registry(), clock=FakeClock(), rand=fixed_rand)
    assert [r.data for r in ra.records] == [{"exhibitor_name_as_listed": "Beispiel GmbH", "hall": "3", "_row": 2}]
    assert [r.data for r in rb.records] == [{"exhibitor_name_as_listed": "Demo Corp", "booth": "Z9", "_row": 3}]
