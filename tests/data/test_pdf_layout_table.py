"""Tests for crawler.pdf_layout_table (D2-03): numbered PDF tables read by the position of the text."""
from __future__ import annotations

import io
from pathlib import Path

import pytest

from crawler.adapters import AdapterRegistry, ParseError
from crawler.file_import import import_files
from crawler.pdf_layout_table import ADAPTER_NAME, PdfLayoutTableAdapter, Piece, check_options, parse_pieces, pdf_pieces
from crawler.source_config import ConfigError
from tests.data.crawl_testkit import FakeClock, fixed_rand, make_config

COLUMNS = ["_number", "exhibitor_name_as_listed", "country", "booth", "hall"]
OPTS = {"columns": COLUMNS, "ignore_text": [r"^LIST OF EXHIBITORS$", r"^\d{1,2}$"]}
X = {"no": 50.0, "name": 86.0, "country": 285.0, "booth": 370.0, "hall": 455.0}


def p(col: str, y: float, text: str, *, dx: float = 0.0, end: float | None = None) -> Piece:
    x = X[col] + dx
    return Piece(x, y, text, x + 5.0 * len(text) if end is None else end, 10.0)


PAGE1 = [
    p("name", 700, "LIST OF EXHIBITORS"),                       # title: outside the rows, ignored
    p("no", 650, "1"), p("name", 650, "Alpha Co "), p("country", 650, "Countryland"), p("booth", 650, "100A"),
    p("hall", 656, "Pavilion of "), p("hall", 644, "Countryland"),   # two-line cell, centred on the number
    p("name", 628, "Beta Very Long Company "),                    # three-line name: first line ABOVE the number
    p("no", 616, "2"), p("name", 616, "Name That Wraps "), p("country", 616, "Otherland"),
    p("name", 604, "Over Lines"),
    p("no", 590, "3"), p("name", 590, "Gamma"), p("name", 590, "-", dx=25.0, end=X["name"] + 30.0),  # "Gamma-Delta": no gap
    p("name", 590, "Delta", dx=30.0), p("country", 590, "Countryland"),
    p("no", 570, "4"), p("name", 570, "Epsilon Holdings "), p("name", 570, "-", dx=100.0), p("name", 570, "Zeta", dx=108.0),  # gaps
    p("country", 570, "Otherland"), p("booth", 570, "7"),
    p("name", 40, "1"),                                           # page number, ignored
]
PAGE2 = [
    p("no", 650, "5"), p("name", 656, "SUPERLONGWORDTHATBRE"), p("name", 644, "AKS"), p("country", 650, "Countryland"),
    p("no", 620, "6"), p("name", 626, "Theta Company -"), p("name", 614, "Iota"), p("country", 620, "Otherland"),
    p("name", 500, "Unexpected footnote"),
]


def rows(table):
    return [{k: v for k, v in r.items()} for r in table.rows]


def test_rows_columns_wrapping_and_joins() -> None:
    table = parse_pieces([PAGE1, PAGE2], OPTS)
    assert rows(table) == [
        {"exhibitor_name_as_listed": "Alpha Co", "country": "Countryland", "booth": "100A", "hall": "Pavilion of Countryland", "_row": 1},
        {"exhibitor_name_as_listed": "Beta Very Long Company Name That Wraps Over Lines", "country": "Otherland", "_row": 2},
        {"exhibitor_name_as_listed": "Gamma-Delta", "country": "Countryland", "_row": 3},
        {"exhibitor_name_as_listed": "Epsilon Holdings - Zeta", "country": "Otherland", "booth": "7", "_row": 4},
        {"exhibitor_name_as_listed": "SUPERLONGWORDTHATBREAKS", "country": "Countryland", "_row": 5},
        {"exhibitor_name_as_listed": "Theta Company -Iota", "country": "Otherland", "_row": 6},
    ]
    assert table.warnings == ["page 2: text outside the table rows ignored: 'Unexpected footnote'"]


def test_fragments_inside_a_name_are_not_columns() -> None:
    # many rows whose names contain a dash at the same x would make a column if columns were taken by count alone
    page = []
    for i in range(1, 9):
        y = 700 - 20 * i
        page += [p("no", y, str(i)), p("name", y, "Parent "), p("name", y, "-", dx=40), p("name", y, f"Unit {i}", dx=50), p("country", y, "Countryland")]
    page += [p("no", 500, "9"), p("name", 500, "Lone"), p("country", 500, "Countryland"), p("booth", 500, "1"), p("hall", 500, "Hall A")]
    table = parse_pieces([page], OPTS)
    assert table.rows[0] == {"exhibitor_name_as_listed": "Parent - Unit 1", "country": "Countryland", "_row": 1}
    assert table.rows[-1] == {"exhibitor_name_as_listed": "Lone", "country": "Countryland", "booth": "1", "hall": "Hall A", "_row": 9}


def test_numbering_gaps_and_nameless_rows_are_warned() -> None:
    page = [p("no", 650, "1"), p("name", 650, "A"), p("no", 620, "3"), p("country", 620, "X"), p("name", 600, "Z", dx=0)]
    table = parse_pieces([page], {**OPTS, "max_row_offset": 10})
    assert [r["_row"] for r in table.rows] == [1, 3]
    assert any("missing [2]" in w for w in table.warnings) and any("rows without a name: [3]" in w for w in table.warnings)
    assert any("'Z'" in w for w in table.warnings)  # 20 pt from row 3: outside


def test_page_without_rows_is_reported_unless_ignored() -> None:
    assert parse_pieces([[p("name", 700, "LIST OF EXHIBITORS")]], OPTS).warnings == []
    assert parse_pieces([[p("name", 700, "Cover text")]], OPTS).warnings == ["page 1: no table row; text ignored: 'Cover text'"]


@pytest.mark.parametrize("options, message", [
    ({}, "columns must be"),
    ({"columns": ["exhibitor_name_as_listed", "_number"]}, "first"),
    ({"columns": ["_number", "country"]}, "exhibitor_name_as_listed"),
    ({"columns": ["_number", "exhibitor_name_as_listed", "country", "country"]}, "no field twice"),
    ({"columns": ["_number", "Bad Name"]}, "columns must be"),
    ({"columns": COLUMNS, "surprise": 1}, "unknown option"),
    ({"columns": COLUMNS, "ignore_text": "x"}, "must be a list"),
    ({"columns": COLUMNS, "ignore_text": ["("]}, "not a valid regular expression"),
    ({"columns": COLUMNS, "row_number": ""}, "non-empty"),
    ({"columns": COLUMNS, "max_row_offset": 0}, "max_row_offset"),
    ({"columns": COLUMNS, "min_column_gap": True}, "min_column_gap"),
])
def test_bad_options(options, message) -> None:
    with pytest.raises(ConfigError, match=message):
        check_options(options)


def test_skip_column_and_custom_row_number() -> None:
    page = [p("no", 650, "A-1"), p("name", 650, "Alpha"), p("country", 650, "drop me")]
    table = parse_pieces([page], {"columns": ["_number", "exhibitor_name_as_listed", "_skip"], "row_number": r"^A-\d+$"})
    assert table.rows == [{"exhibitor_name_as_listed": "Alpha", "_row": "A-1"}]


def _pdf(encrypt: bool = False) -> bytes:
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    if encrypt:
        writer.encrypt("secret")
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def test_pdf_errors() -> None:
    with pytest.raises(ParseError, match="encrypted"):
        pdf_pieces(_pdf(encrypt=True))
    with pytest.raises(ParseError, match="no text layer"):
        pdf_pieces(_pdf())
    with pytest.raises(ParseError, match="not a readable PDF"):
        pdf_pieces(b"%PDF-1.4 broken")


@pytest.mark.parametrize("body, message", [(b"plain text", "not a PDF"), (b"%PDF-1.4 broken", "not a readable PDF")])
def test_through_the_runner_unusable_files_keep_the_evidence(tmp_path: Path, body: bytes, message: str) -> None:
    path = tmp_path / "list.pdf"
    path.write_bytes(body)
    registry = AdapterRegistry()
    registry.register(PdfLayoutTableAdapter)
    config = make_config(name="t", adapter=ADAPTER_NAME, start_urls=("https://files.example.com/list.pdf",), source_type="pdf_import", options=OPTS)
    result = import_files(config, {"https://files.example.com/list.pdf": path}, adapters=registry, clock=FakeClock(), rand=fixed_rand)
    assert result.status == "partial" and result.records == [] and len(result.snapshots) == 1
    assert any(message in e.message for e in result.errors)


def test_a_repeated_wide_gap_inside_names_is_not_a_column() -> None:
    # "A   Fragment": the fragment starts more than one em after "A" ends, so only the minimum column gap keeps it out
    page = []
    for i in range(1, 10):
        y = 700 - 20 * i
        page += [p("no", y, str(i)), p("name", y, "A", end=X["name"] + 5), p("name", y, f"Frag{i}", dx=17), p("country", y, "Countryland")]
    page += [p("no", 400, "10"), p("name", 400, "Solo"), p("country", 400, "Countryland"), p("booth", 400, "9"), p("hall", 400, "Hall B")]
    table = parse_pieces([page], OPTS)
    assert table.rows[0] == {"exhibitor_name_as_listed": "A Frag1", "country": "Countryland", "_row": 1}
    assert table.rows[-1] == {"exhibitor_name_as_listed": "Solo", "country": "Countryland", "booth": "9", "hall": "Hall B", "_row": 10}


def test_a_tie_between_a_fragment_and_a_column_goes_to_the_column_on_the_right() -> None:
    page = [p("no", 650, "1"), p("name", 650, "Alpha", end=X["name"] + 25), p("name", 650, "Part", dx=60), p("country", 650, "C"), p("booth", 650, "1"),
            p("no", 620, "2"), p("name", 620, "Beta"), p("country", 620, "C"), p("booth", 620, "2"), p("hall", 620, "Hall Z")]
    table = parse_pieces([page], OPTS)
    assert table.rows == [{"exhibitor_name_as_listed": "Alpha Part", "country": "C", "booth": "1", "_row": 1},
                          {"exhibitor_name_as_listed": "Beta", "country": "C", "booth": "2", "hall": "Hall Z", "_row": 2}]


def test_the_order_of_the_pieces_in_the_file_does_not_matter() -> None:
    assert rows(parse_pieces([list(reversed(PAGE1)), list(reversed(PAGE2))], OPTS)) == rows(parse_pieces([PAGE1, PAGE2], OPTS))


def test_estimated_widths() -> None:
    from crawler.pdf_layout_table import _estimated_em, _text_width

    assert _estimated_em("，") == 1.0 and _estimated_em("W") == 0.5
    font = {"/FirstChar": 32, "/Widths": [278] + [500] * 94}
    assert _text_width(" a", font, 10.0) == pytest.approx(7.78)
    assert _text_width("a，", font, 10.0) == pytest.approx(15.0)  # the full-width comma is outside the table: one em
    assert _text_width("a", {}, 10.0) is None
