"""Printed exhibitor-list pages (browser "Save as PDF") as an import source (D2-02).

Many exhibitor-list platforms render a list where every entry shows the exhibitor name (often next to a logo whose
alt text repeats the name), a detail line (usually the booth), and then the name again as a link. Printed to PDF,
the text layer of such a page reads, entry by entry::

    <logo alt text> <name><detail>        or    <name>
    <name>                                       <detail>
                                                 <name>

The entry ends where the name is repeated on a line of its own. Long names wrap over several lines in the first
occurrence and are matched across the line breaks. Nothing is guessed: an entry whose structure does not fit is
reported, and the count printed in the section heading is compared with the number of entries read.

Everything that differs between sites lives in the source config ``[options]`` (no site is named in this code):

``section_heading`` (required)
    Regular expression for the heading line that starts the list to read. A named group ``count`` captures the
    number of entries the page states (for example ``^ALL EXHIBITORS \\( (?P<count>\\d+) \\)$``).
``stop_heading``
    Regular expression for a line that ends the list (default: none, the list runs to the end of the text).
``ignore_lines``
    Regular expressions for page furniture to drop wherever it appears (repeated page headers and footers).
``detail_field``
    Raw field that receives the detail line (default ``booth``).

Records: ``exhibitor_name_as_listed``, the detail field when present, and ``_row`` (1-based position in the list).
"""
from __future__ import annotations

import io
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from crawler.adapters import AdapterRegistry, ParseError, SourceAdapter, default_registry
from crawler.models import ParseResult, Request, Response
from crawler.source_config import ConfigError, SourceConfig

ADAPTER_NAME = "printed-listing"
_FIELD = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_OPTIONS = {"section_heading", "stop_heading", "ignore_lines", "detail_field"}


@dataclass
class Listing:
    rows: list[dict[str, Any]] = field(default_factory=list)
    stated_count: int | None = None
    warnings: list[str] = field(default_factory=list)


def _compile(value: Any, name: str) -> re.Pattern[str]:
    if not isinstance(value, str) or not value:
        raise ConfigError(f"{ADAPTER_NAME}: {name} must be a non-empty regular expression")
    try:
        return re.compile(value)
    except re.error as exc:
        raise ConfigError(f"{ADAPTER_NAME}: {name} is not a valid regular expression: {exc}") from None


def check_options(options: Mapping[str, Any]) -> None:
    unknown = sorted(set(options) - _OPTIONS)
    if unknown:
        raise ConfigError(f"{ADAPTER_NAME}: unknown option(s): {', '.join(unknown)}")
    if "section_heading" not in options:
        raise ConfigError(f"{ADAPTER_NAME}: section_heading is required")
    _compile(options["section_heading"], "section_heading")
    if "stop_heading" in options:
        _compile(options["stop_heading"], "stop_heading")
    ignore = options.get("ignore_lines", [])
    if not isinstance(ignore, list):
        raise ConfigError(f"{ADAPTER_NAME}: ignore_lines must be a list of regular expressions")
    for i, pattern in enumerate(ignore):
        _compile(pattern, f"ignore_lines[{i}]")
    detail = options.get("detail_field", "booth")
    if not isinstance(detail, str) or not _FIELD.fullmatch(detail) or detail == "exhibitor_name_as_listed":
        raise ConfigError(f"{ADAPTER_NAME}: detail_field must be a raw field name other than exhibitor_name_as_listed")


def _clean(line: str) -> str:
    return re.sub(r"\s+", " ", line.replace("\xa0", " ")).strip()


def _name_pattern(name: str) -> re.Pattern[str]:
    return re.compile(r"\s+".join(re.escape(token) for token in name.split()))


def parse_listing(text: str, options: Mapping[str, Any]) -> Listing:
    """Entries of the configured section of a printed list. Raises ``ParseError`` if the section is not there."""
    check_options(options)
    heading = _compile(options["section_heading"], "section_heading")
    stop = _compile(options["stop_heading"], "stop_heading") if "stop_heading" in options else None
    ignore = [_compile(p, "ignore_lines") for p in options.get("ignore_lines", [])]
    detail_field = options.get("detail_field", "booth")
    result = Listing()

    lines = [_clean(line) for line in text.splitlines()]
    start = next((i for i, line in enumerate(lines) if heading.search(line)), None)
    if start is None:
        raise ParseError(f"section heading not found (pattern {options['section_heading']!r}); the page layout may have changed")
    found = heading.search(lines[start])
    if found and "count" in found.groupdict() and found.group("count") is not None:
        result.stated_count = int(found.group("count"))

    buffer: list[str] = []
    for line in lines[start + 1:]:
        if stop is not None and stop.search(line):
            break
        if not line or any(p.search(line) for p in ignore):
            continue
        closed = False
        if buffer:
            joined = "\n".join(buffer)
            matches = list(_name_pattern(line).finditer(joined))
            if matches:
                rest = [part for part in (joined[matches[-1].end():]).split("\n")]
                trailing = [part.strip() for part in rest[1:] if part.strip()]
                same_line = rest[0].strip()
                details = ([same_line] if same_line else []) + trailing
                if len(details) <= 1:
                    row: dict[str, Any] = {"exhibitor_name_as_listed": line, "_row": len(result.rows) + 1}
                    if details:
                        row[detail_field] = details[0]
                    result.rows.append(row)
                    closed = True
        if closed:
            buffer = []
        else:
            buffer.append(line)
    if buffer:
        result.warnings.append(f"text after the last entry was not an entry and was ignored: {' / '.join(buffer)[:300]!r}")
    if result.stated_count is not None and result.stated_count != len(result.rows):
        result.warnings.append(f"the heading states {result.stated_count} entries but {len(result.rows)} were read; check the original")
    return result


def pdf_text(data: bytes) -> str:
    """The text layer of a PDF, pages joined by newlines. Raises ``ParseError``; never OCRs or decrypts."""
    from pypdf import PdfReader
    from pypdf.errors import PyPdfError

    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise ParseError("the PDF is encrypted; acquisition does not bypass protection")
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    except ParseError:
        raise
    except (PyPdfError, ValueError, OSError, KeyError, TypeError) as exc:
        raise ParseError(f"not a readable PDF: {exc}") from None
    if not text.strip():
        raise ParseError("the PDF has no text layer (scanned image?); OCR is not part of acquisition")
    return text


class PrintedListingAdapter(SourceAdapter):
    name = ADAPTER_NAME
    version = "1.0.0"

    def validate_options(self, options: Mapping[str, Any]) -> None:
        check_options(options)

    def parse(self, response: Response, request: Request, config: SourceConfig) -> ParseResult:
        if (response.media_type or "").split(";")[0].strip() == "application/pdf" or response.content[:5] == b"%PDF-":
            text = pdf_text(response.content)
        else:
            try:
                text = response.content.decode("utf-8")
            except UnicodeDecodeError:
                raise ParseError("not a PDF and not UTF-8 text") from None
        listing = parse_listing(text, config.options)
        if not listing.rows:
            raise ParseError("the section has no entries")
        return ParseResult(records=listing.rows, warnings=listing.warnings)


def register_printed_listing(registry: AdapterRegistry | None = None) -> None:
    target = registry or default_registry
    if ADAPTER_NAME not in target:
        target.register(PrintedListingAdapter)


register_printed_listing()

__all__ = ["ADAPTER_NAME", "Listing", "PrintedListingAdapter", "check_options", "parse_listing", "pdf_text", "register_printed_listing"]
