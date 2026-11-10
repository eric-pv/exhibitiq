"""Numbered tables in PDFs, read by the position of the text on the page (D2-03).

Exhibitor lists published as PDF tables often have no column separators in the text layer, long cells wrap onto
several lines, and cells are centred vertically in their row (so the first line of a three-line name sits *above* the
row number). Reading the text line by line cannot tell which row such a line belongs to. This adapter uses where each
piece of text is drawn instead:

- A **row** is anchored at a row-number text (``row_number`` pattern) in the leftmost column.
- Every other text piece belongs to the row whose number is vertically nearest, if it is within ``max_row_offset``
  points of it; pieces farther from every row (titles, page numbers, footers) are not table content.
- **Columns** are the horizontal positions used most across the whole table, at least ``min_column_gap`` apart (a
  dash or second fragment inside a long name is not a column); a piece belongs to the rightmost column starting at
  or before it. The row-number column is the leftmost.
- A cell's pieces are joined top to bottom, left to right, with single spaces.

Nothing is guessed: text outside the table that is not covered by ``ignore_text`` is reported, and so are row numbers
that are not consecutive and rows without a name.

Options (source config ``[options]``; no site is named in this code):

``columns`` (required)
    Raw field names left to right; the column holding the row number is ``_number``; ``_skip`` drops a column.
    Example: ``["_number", "exhibitor_name_as_listed", "country", "booth", "hall"]``.
``ignore_text``
    Regular expressions for text pieces outside the table that are expected (titles, column headers, page numbers,
    "updated as of" notes); they are dropped without a warning.
``row_number``
    Regular expression for the row-number text (default ``^\\d+$``).
``max_row_offset``
    Largest vertical distance in points between a piece of text and its row number (default 14).
``min_column_gap``
    Smallest horizontal distance in points between two column starts (default 20).

Records: the fields above and ``_row`` (the row number printed in the table).
"""
from __future__ import annotations

import io
import re
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from crawler.adapters import AdapterRegistry, ParseError, SourceAdapter, default_registry
from crawler.models import ParseResult, Request, Response
from crawler.source_config import ConfigError, SourceConfig

ADAPTER_NAME = "pdf-layout-table"
_FIELD = re.compile(r"^(?:_number|_skip|[a-z][a-z0-9_]{0,63})$")
_OPTIONS = {"columns", "ignore_text", "row_number", "max_row_offset", "min_column_gap"}
_X_TOLERANCE = 5.0  # points: pieces of one column start within this distance of each other


@dataclass(frozen=True)
class Piece:
    x: float
    y: float  # PDF coordinates: larger is higher on the page
    text: str
    end: float | None = None  # where the text ends (from the font's widths); None when unknown
    size: float = 10.0  # font size in points


def _join_cell(parts: Sequence[Piece]) -> str:
    """Pieces of one cell: lines top to bottom joined by a space; pieces on one line joined by a space only where the
    page shows a gap (the next piece starts after the previous one ends, or the previous text ended in a space)."""
    lines: dict[float, list[Piece]] = {}
    for piece in parts:
        key = next((k for k in lines if abs(k - piece.y) <= 1.0), piece.y)
        lines.setdefault(key, []).append(piece)
    out: list[str] = []
    for key in sorted(lines, reverse=True):
        text = ""
        previous: Piece | None = None
        for piece in sorted(lines[key], key=lambda p: p.x):
            word = re.sub(r"\s+", " ", piece.text.replace("\xa0", " "))
            if previous is not None:
                gap = previous.end is not None and piece.x - previous.end > 0.15 * previous.size
                if (gap or previous.text[-1:].isspace()) and not text.endswith(" ") and not word.startswith(" "):
                    text += " "
            text += word
            previous = piece
        out.append(text)
    joined = ""
    previous_line = ""
    for raw_line in (t for t in out if t.strip()):
        line = raw_line.strip()
        # a line break adds a space, except after a hyphen or a full-width comma, or after a line with no space at
        # all (a word too long for the cell, broken where the cell ends)
        if joined and not previous_line.rstrip().endswith(("-", "，")) and " " in previous_line:
            joined += " "
        joined += line
        previous_line = raw_line
    return joined


def _text_width(text: str, font: Any, size: float) -> float | None:
    """Width of ``text`` in points from a simple font's /Widths table; None without one. Characters the table does not
    cover (outside its single-byte range) count as half an em."""
    try:
        widths = font["/Widths"]
        first = int(font["/FirstChar"])
    except (KeyError, TypeError, ValueError):
        return None
    total = 0.0
    for char in text:
        index = ord(char) - first
        total += float(widths[index]) if 0 <= index < len(widths) and ord(char) <= 255 else 1000.0 * _estimated_em(char)
    return total / 1000.0 * size


def _estimated_em(char: str) -> float:
    """Rough advance width in em when the font gives none: full-width (East Asian) characters 1, others 0.5."""
    return 1.0 if unicodedata.east_asian_width(char) in ("F", "W") else 0.5


@dataclass
class Table:
    rows: list[dict[str, Any]] = field(default_factory=list)
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
    columns = options.get("columns")
    if not isinstance(columns, list) or len(columns) < 2 or not all(isinstance(c, str) and _FIELD.fullmatch(c) for c in columns):
        raise ConfigError(f"{ADAPTER_NAME}: columns must be a list of at least two raw field names")
    named = [c for c in columns if c != "_skip"]
    if named.count("_number") != 1 or len(set(named)) != len(named):
        raise ConfigError(f"{ADAPTER_NAME}: columns must name _number exactly once and no field twice")
    if columns[0] != "_number":
        raise ConfigError(f"{ADAPTER_NAME}: the row number must be the first (leftmost) column")
    if "exhibitor_name_as_listed" not in columns:
        raise ConfigError(f"{ADAPTER_NAME}: columns must include exhibitor_name_as_listed")
    ignore = options.get("ignore_text", [])
    if not isinstance(ignore, list):
        raise ConfigError(f"{ADAPTER_NAME}: ignore_text must be a list of regular expressions")
    for i, pattern in enumerate(ignore):
        _compile(pattern, f"ignore_text[{i}]")
    if "row_number" in options:
        _compile(options["row_number"], "row_number")
    offset = options.get("max_row_offset", 14)
    if isinstance(offset, bool) or not isinstance(offset, (int, float)) or not 0 < offset <= 200:
        raise ConfigError(f"{ADAPTER_NAME}: max_row_offset must be a number of points between 0 and 200")
    gap = options.get("min_column_gap", 20)
    if isinstance(gap, bool) or not isinstance(gap, (int, float)) or not 0 < gap <= 500:
        raise ConfigError(f"{ADAPTER_NAME}: min_column_gap must be a number of points between 0 and 500")


def _column_starts(xs: Sequence[float], width: int, min_gap: float) -> list[float]:
    """The ``width`` horizontal positions used most often, left to right.

    Positions are clustered; clusters are taken by how many pieces use them (ties: the one further right), skipping
    any that start within ``min_gap`` of one already taken.
    """
    clusters: list[list[float]] = []
    for x in sorted(xs):
        if clusters and x - clusters[-1][-1] <= _X_TOLERANCE:
            clusters[-1].append(x)
        else:
            clusters.append([x])
    chosen: list[float] = []
    for cluster in sorted(clusters, key=lambda c: (len(c), min(c)), reverse=True):
        if len(chosen) == width:
            break
        if all(abs(min(cluster) - c) >= min_gap for c in chosen):
            chosen.append(min(cluster))
    return sorted(chosen)


def parse_pieces(pages: Sequence[Sequence[Piece]], options: Mapping[str, Any]) -> Table:
    check_options(options)
    columns: list[str] = list(options["columns"])
    number = _compile(options.get("row_number", r"^\d+$"), "row_number")
    ignore = [_compile(p, "ignore_text") for p in options.get("ignore_text", [])]
    max_offset = float(options.get("max_row_offset", 14))
    min_gap = float(options.get("min_column_gap", 20))
    table = Table()

    grouped: list[tuple[Piece, list[Piece]]] = []  # (row anchor, its pieces), in reading order
    for page_no, raw in enumerate(pages, start=1):
        pieces = [p for p in raw if p.text.strip()]
        numbers = [p for p in pieces if number.fullmatch(p.text.strip())]
        if not numbers:
            stray = [p.text.strip() for p in pieces if not any(r.search(p.text.strip()) for r in ignore)]
            if stray:
                table.warnings.append(f"page {page_no}: no table row; text ignored: {' / '.join(stray)[:200]!r}")
            continue
        left = min(p.x for p in numbers)
        anchors = sorted((p for p in numbers if p.x - left <= _X_TOLERANCE), key=lambda p: -p.y)  # top to bottom
        anchor_ids = {id(p) for p in anchors}
        members: list[list[Piece]] = [[] for _ in anchors]
        outside: list[str] = []
        for piece in pieces:
            if id(piece) in anchor_ids:
                continue
            nearest = min(range(len(anchors)), key=lambda i: (abs(anchors[i].y - piece.y), i))
            if abs(anchors[nearest].y - piece.y) <= max_offset:
                members[nearest].append(piece)
            elif not any(r.search(piece.text.strip()) for r in ignore):
                outside.append(piece.text.strip())
        if outside:
            table.warnings.append(f"page {page_no}: text outside the table rows ignored: {' / '.join(outside)[:200]!r}")
        grouped.extend(zip(anchors, members))

    # columns: the positions used most across the whole table (cells are left-aligned at the same x on every page).
    # A piece that starts right after another piece on the same line (within one em of its end) continues that cell
    # and is no evidence of a column.
    def continues(piece: Piece, group: Sequence[Piece]) -> bool:
        return any(o is not piece and abs(o.y - piece.y) <= 1.0 and o.x < piece.x and o.end is not None
                   and piece.x - o.end <= o.size for o in group)

    left_edge = min((a.x for a, _ in grouped), default=0.0)
    candidates = [p.x for _, group in grouped for p in group if p.x > left_edge + min_gap and not continues(p, group)]
    starts = [left_edge] + _column_starts(candidates, len(columns) - 1, min_gap)
    if grouped and len(starts) < len(columns):
        table.warnings.append(f"only {len(starts)} column position(s) found for {len(columns)} configured columns")
    for anchor, group in grouped:
        cells: dict[str, list[Piece]] = {name: [] for name in columns}
        for piece in group:
            index = max(j for j, s in enumerate(starts) if s <= piece.x + _X_TOLERANCE)
            cells[columns[index]].append(piece)
        record: dict[str, Any] = {}
        for name, parts in cells.items():
            if name in ("_skip", "_number") or not parts:
                continue
            record[name] = _join_cell(parts)
        number_text = anchor.text.strip()
        record["_row"] = int(number_text) if number_text.isdigit() else number_text
        table.rows.append(record)

    numbers_read = [r["_row"] for r in table.rows]
    if numbers_read and all(isinstance(n, int) for n in numbers_read) and numbers_read != list(range(numbers_read[0], numbers_read[0] + len(numbers_read))):
        missing = sorted(set(range(min(numbers_read), max(numbers_read) + 1)) - set(numbers_read))
        repeated = sorted({n for n in numbers_read if numbers_read.count(n) > 1})
        table.warnings.append(f"row numbers are not consecutive (missing {missing[:20]}, repeated {repeated[:20]}); check the original")
    nameless = [r["_row"] for r in table.rows if not r.get("exhibitor_name_as_listed")]
    if nameless:
        table.warnings.append(f"rows without a name: {nameless[:20]}")
    return table


def pdf_pieces(data: bytes) -> list[list[Piece]]:
    """Text pieces of each page with their position. Raises ``ParseError``; never OCRs or decrypts."""
    from pypdf import PdfReader
    from pypdf.errors import PyPdfError

    pages: list[list[Piece]] = []
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise ParseError("the PDF is encrypted; acquisition does not bypass protection")
        for page in reader.pages:
            found: list[Piece] = []

            def visit(text: str, cm: Sequence[float], tm: Sequence[float], font: Any, size: Any, found: list[Piece] = found) -> None:
                if text and text.strip():
                    x = tm[4] * cm[0] + tm[5] * cm[2] + cm[4]
                    y = tm[4] * cm[1] + tm[5] * cm[3] + cm[5]
                    points = float(size or 0) * abs(tm[0] * cm[0]) or 10.0
                    width = _text_width(text, font, points)
                    if width is None:  # composite fonts carry no simple /Widths table: estimate from the characters
                        width = sum(_estimated_em(c) for c in text) * points
                    found.append(Piece(round(x, 1), round(y, 1), text, round(x + width, 1), round(points, 2)))

            page.extract_text(visitor_text=visit)
            pages.append(found)
    except ParseError:
        raise
    except (PyPdfError, ValueError, OSError, KeyError, TypeError, ZeroDivisionError) as exc:
        raise ParseError(f"not a readable PDF: {exc}") from None
    if not any(pages):
        raise ParseError("the PDF has no text layer (scanned image?); OCR is not part of acquisition")
    return pages


class PdfLayoutTableAdapter(SourceAdapter):
    name = ADAPTER_NAME
    version = "1.0.0"

    def validate_options(self, options: Mapping[str, Any]) -> None:
        check_options(options)

    def parse(self, response: Response, request: Request, config: SourceConfig) -> ParseResult:
        if response.content[:5] != b"%PDF-":
            raise ParseError("not a PDF")
        table = parse_pieces(pdf_pieces(response.content), config.options)
        if not table.rows:
            raise ParseError("no table rows found")
        return ParseResult(records=table.rows, warnings=table.warnings)


def register_pdf_layout_table(registry: AdapterRegistry | None = None) -> None:
    target = registry or default_registry
    if ADAPTER_NAME not in target:
        target.register(PdfLayoutTableAdapter)


register_pdf_layout_table()

__all__ = ["ADAPTER_NAME", "PdfLayoutTableAdapter", "Piece", "Table", "check_options", "parse_pieces", "pdf_pieces", "register_pdf_layout_table"]
