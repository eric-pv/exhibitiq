"""Tests for crawler.printed_listing (D2-02): printed exhibitor-list pages read as an import source."""
from __future__ import annotations

from pathlib import Path

import pytest

from crawler.adapters import AdapterRegistry, ParseError
from crawler.file_import import import_files
from crawler.printed_listing import ADAPTER_NAME, PrintedListingAdapter, check_options, parse_listing
from crawler.source_config import ConfigError
from tests.data.crawl_testkit import FakeClock, fixed_rand, make_config

HEADING = r"^ALL EXHIBITORS \( (?P<count>\d+) \)$"
OPTS = {"section_heading": HEADING, "ignore_lines": [r"^Page header$", r"^Footer © Example$"]}

# The shapes seen in a printed list: logo alt text glued to the name and the booth; a name without a logo;
# a long name that wraps; an entry without a detail line; repeated page furniture between entries.
TEXT = """\
Some page title
FEATURED EXHIBITORS ( 1 )
Acme Acme Corp12
Acme Corp
ALL EXHIBITORS ( 5 )
AcmeLogo Acme Corp12
Acme Corp
  Beta Systems
301, Client Suite #4
Beta Systems
Gamma Institute for Research, Training and
Long Names
77A
Page header
Gamma Institute for Research, Training and Long Names
  Delta Unboothed
Delta Unboothed
Footer © Example
Epsilon Epsilon
905
Epsilon
"""


def names(rows):
    return [(r["exhibitor_name_as_listed"], r.get("booth")) for r in rows]


def test_every_shape_is_read() -> None:
    listing = parse_listing(TEXT, OPTS)
    assert names(listing.rows) == [
        ("Acme Corp", "12"), ("Beta Systems", "301, Client Suite #4"),
        ("Gamma Institute for Research, Training and Long Names", "77A"), ("Delta Unboothed", None), ("Epsilon", "905"),
    ]
    assert [r["_row"] for r in listing.rows] == [1, 2, 3, 4, 5]
    assert listing.stated_count == 5 and listing.warnings == []


def test_a_count_mismatch_and_leftover_text_are_warned_not_hidden() -> None:
    listing = parse_listing(TEXT.replace("( 5 )", "( 6 )") + "Zeta Dangling\n", OPTS)
    assert len(listing.rows) == 5
    assert any("states 6 entries but 5 were read" in w for w in listing.warnings)
    assert any("Zeta Dangling" in w for w in listing.warnings)


def test_page_furniture_is_needed_to_keep_the_detail_clean() -> None:
    listing = parse_listing(TEXT, {"section_heading": HEADING})  # without ignore_lines the header splits an entry
    assert ("Gamma Institute for Research, Training and Long Names", "77A") not in names(listing.rows)
    assert any("states 5 entries but" in w for w in listing.warnings)


def test_stop_heading_and_other_section_and_detail_field() -> None:
    featured = parse_listing(TEXT, {"section_heading": r"^FEATURED EXHIBITORS \( (?P<count>\d+) \)$", "stop_heading": r"^ALL EXHIBITORS", "detail_field": "stand"})
    assert featured.rows == [{"exhibitor_name_as_listed": "Acme Corp", "_row": 1, "stand": "12"}] and featured.warnings == []


def test_heading_without_count() -> None:
    listing = parse_listing(TEXT, {**OPTS, "section_heading": r"^ALL EXHIBITORS"})
    assert listing.stated_count is None and len(listing.rows) == 5


def test_missing_section_is_a_parse_error() -> None:
    with pytest.raises(ParseError, match="section heading not found"):
        parse_listing("nothing here\n", OPTS)


@pytest.mark.parametrize("options, message", [
    ({}, "section_heading is required"),
    ({"section_heading": "("}, "not a valid regular expression"),
    ({"section_heading": "x", "surprise": 1}, "unknown option"),
    ({"section_heading": "x", "ignore_lines": "x"}, "must be a list"),
    ({"section_heading": "x", "ignore_lines": ["("]}, "not a valid regular expression"),
    ({"section_heading": "x", "stop_heading": ""}, "non-empty"),
    ({"section_heading": "x", "detail_field": "Bad Field"}, "detail_field"),
    ({"section_heading": "x", "detail_field": "exhibitor_name_as_listed"}, "detail_field"),
])
def test_bad_options_are_config_errors(options, message) -> None:
    with pytest.raises(ConfigError, match=message):
        check_options(options)


def _config(**options):
    return make_config(name="print", adapter=ADAPTER_NAME, start_urls=("https://files.example.com/list.txt",), source_type="pdf_import", options=options)


def test_through_the_runner_text_file(tmp_path: Path) -> None:
    path = tmp_path / "list.txt"
    path.write_text(TEXT, encoding="utf-8")
    registry = AdapterRegistry()
    registry.register(PrintedListingAdapter)
    result = import_files(_config(**OPTS), {"https://files.example.com/list.txt": path}, adapters=registry, clock=FakeClock(), rand=fixed_rand)
    assert result.status == "succeeded" and [r.data["exhibitor_name_as_listed"] for r in result.records][0] == "Acme Corp"
    assert all(r.source_id == result.snapshots[0].source_id for r in result.records)


@pytest.mark.parametrize("body, message", [(b"Nothing\n", "section heading not found"), (b"ALL EXHIBITORS ( 0 )\n", "no entries"),
                                           (b"\xff\xfe", "not a PDF"), (b"%PDF-1.4 broken", "not a readable PDF")])
def test_unusable_files_are_parse_errors_with_the_evidence_kept(tmp_path: Path, body: bytes, message: str) -> None:
    path = tmp_path / "list.txt"
    path.write_bytes(body)
    registry = AdapterRegistry()
    registry.register(PrintedListingAdapter)
    result = import_files(_config(**OPTS), {"https://files.example.com/list.txt": path}, adapters=registry, clock=FakeClock(), rand=fixed_rand)
    assert result.status == "partial" and result.records == [] and len(result.snapshots) == 1
    assert any(message in e.message for e in result.errors)


def test_bad_options_are_refused_by_the_adapter() -> None:
    with pytest.raises(ConfigError):
        PrintedListingAdapter().validate_options({"section_heading": "("})


def test_an_encrypted_pdf_is_refused_not_decrypted() -> None:
    import io

    from pypdf import PdfWriter

    from crawler.printed_listing import pdf_text

    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.encrypt("secret")
    buffer = io.BytesIO()
    writer.write(buffer)
    with pytest.raises(ParseError, match="encrypted"):
        pdf_text(buffer.getvalue())
