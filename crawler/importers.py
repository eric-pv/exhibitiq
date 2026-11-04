"""Readers that turn a file's bytes into raw rows, driven by a mapping (D2-04).

Four formats, one mapping shape. A mapping says which file column becomes which raw field; it is the
*only* place a particular file layout is described, so a new file structure needs a new mapping, not
new code (V2.3). Output rows are "as listed": text, stripped, no guessing. A cell that is empty is
left out of the row, never filled in. Normalization into schema fields is the ETL's job (D2-07).

| format       | reads                                   | notes                                                          |
|--------------|-----------------------------------------|----------------------------------------------------------------|
| `csv`        | text, any encoding/delimiter            | stdlib `csv`                                                   |
| `html_table` | one `<table>` of an HTML page           | stdlib parser; `colspan`/`rowspan` are not expanded (warned)   |
| `xlsx`       | one worksheet                           | `openpyxl`, cached values only (formulas are not evaluated)    |
| `pdf_text`   | the text layer of a PDF, line by line   | `pypdf`; columns split on a separator pattern; **no OCR**      |

Reading problems that make the whole file unusable raise ``ParseError``; problems with single rows
become warnings and the row is skipped, so one bad row never hides the others.
"""
from __future__ import annotations

import csv
import io
import re
import tomllib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from crawler.adapters import ParseError
from crawler.source_config import ConfigError

FORMATS = ("csv", "html_table", "xlsx", "pdf_text")
_FIELD = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_SECRET_WORDS = ("password", "passwd", "secret", "token", "api_key", "apikey", "credential")
MAX_ROWS = 200_000
MAX_WARNINGS = 200


@dataclass(frozen=True)
class ColumnMap:
    source: str  # the header text in the file (matched ignoring case and extra spaces)
    field: str  # the raw field name in the output row
    required: bool = False


@dataclass(frozen=True)
class ImportMapping:
    format: str
    columns: tuple[ColumnMap, ...]
    header_row: int = 1  # 1-based; csv/xlsx: row number, html_table: row in the table, pdf_text: non-empty line
    encoding: str = "utf-8-sig"  # csv
    delimiter: str = ","  # csv
    sheet: str | None = None  # xlsx; default is the first sheet
    table_index: int = 0  # html_table: which <table> (0-based) in document order
    table_id: str | None = None  # html_table: id attribute; wins over table_index
    split_pattern: str = r"\s{2,}|\t"  # pdf_text: separates columns within a line
    options: Mapping[str, Any] = field(default_factory=dict)  # reserved; always empty today


def normalize_header(text: str) -> str:
    return " ".join(str(text).split()).casefold()


_ALLOWED_KEYS = {"format", "columns", "header_row", "encoding", "delimiter", "sheet", "table_index", "table_id", "split_pattern"}


def mapping_from_dict(data: Mapping[str, Any]) -> ImportMapping:
    """Validate and build a mapping (from TOML or a source config's ``[options.mapping]``)."""
    if not isinstance(data, Mapping):
        raise ConfigError("mapping must be a table")
    unknown = sorted(set(data) - _ALLOWED_KEYS)
    if unknown:
        raise ConfigError(f"unknown mapping key(s): {', '.join(map(str, unknown))}")
    fmt = data.get("format")
    if fmt not in FORMATS:
        raise ConfigError(f"mapping.format must be one of {', '.join(FORMATS)}, got {fmt!r}")
    raw_columns = data.get("columns")
    if not isinstance(raw_columns, Sequence) or isinstance(raw_columns, (str, bytes)) or not raw_columns:
        raise ConfigError("mapping.columns must be a non-empty list of tables")
    columns: list[ColumnMap] = []
    for index, raw in enumerate(raw_columns):
        where = f"mapping.columns[{index}]"
        if not isinstance(raw, Mapping) or set(raw) - {"source", "field", "required"}:
            raise ConfigError(f"{where} must be a table with source, field and optional required")
        source, name, required = raw.get("source"), raw.get("field"), raw.get("required", False)
        if not isinstance(source, str) or not normalize_header(source):
            raise ConfigError(f"{where}.source must be non-empty text")
        if not isinstance(name, str) or not _FIELD.fullmatch(name):
            raise ConfigError(f"{where}.field must match {_FIELD.pattern}, got {name!r}")
        if any(word in name for word in _SECRET_WORDS):
            raise ConfigError(f"{where}.field {name!r} looks like a credential; imports never carry credentials")
        if not isinstance(required, bool):
            raise ConfigError(f"{where}.required must be true or false")
        columns.append(ColumnMap(source, name, required))
    fields = [c.field for c in columns]
    sources = [normalize_header(c.source) for c in columns]
    for label, values in (("field", fields), ("source", sources)):
        duplicates = sorted({v for v in values if values.count(v) > 1})
        if duplicates:
            raise ConfigError(f"mapping.columns repeats {label} {duplicates[0]!r}")

    def integer(key: str, default: int, minimum: int) -> int:
        value = data.get(key, default)
        if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
            raise ConfigError(f"mapping.{key} must be an integer >= {minimum}")
        return value

    def text(key: str, default: str | None) -> str | None:
        value = data.get(key, default)
        if value is not None and (not isinstance(value, str) or value == ""):
            raise ConfigError(f"mapping.{key} must be non-empty text")
        return value

    encoding = text("encoding", "utf-8-sig")
    try:
        "".encode(encoding or "")
    except LookupError:
        raise ConfigError(f"mapping.encoding {encoding!r} is not a known encoding") from None
    delimiter = text("delimiter", ",")
    if delimiter is not None and len(delimiter) != 1:
        raise ConfigError("mapping.delimiter must be a single character")
    pattern = text("split_pattern", r"\s{2,}|\t")
    try:
        re.compile(pattern or "")
    except re.error as exc:
        raise ConfigError(f"mapping.split_pattern is not a valid regular expression: {exc}") from None
    return ImportMapping(
        format=fmt, columns=tuple(columns), header_row=integer("header_row", 1, 1), encoding=encoding or "utf-8-sig",
        delimiter=delimiter or ",", sheet=text("sheet", None), table_index=integer("table_index", 0, 0),
        table_id=text("table_id", None), split_pattern=pattern or r"\s{2,}|\t",
    )


def load_mapping(path: str | Path) -> ImportMapping:
    path = Path(path)
    try:
        with path.open("rb") as handle:
            return mapping_from_dict(tomllib.load(handle))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ConfigError(f"cannot read mapping {path}: {exc}") from exc


@dataclass
class ImportRows:
    rows: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    rows_seen: int = 0  # data rows examined (blank rows excluded)


# ----------------------------------------------------------------------------- table extraction


def _csv_table(data: bytes, mapping: ImportMapping) -> list[list[str]]:
    try:
        text = data.decode(mapping.encoding)
    except UnicodeDecodeError as exc:
        raise ParseError(f"file is not valid {mapping.encoding}: {exc.reason} at byte {exc.start}") from None
    try:
        return [row for row in csv.reader(io.StringIO(text, newline=""), delimiter=mapping.delimiter, strict=True)]
    except csv.Error as exc:
        raise ParseError(f"CSV could not be read: {exc}") from None


class _TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[tuple[str | None, list[list[str]]]] = []
        self.depth = 0
        self.row: list[str] | None = None
        self.cell: list[str] | None = None
        self.spans = False
        self._stack: list[tuple[str | None, list[list[str]]]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "table":
            self.depth += 1
            if self.depth == 1:
                self._stack.append((dict(attrs).get("id"), []))
        elif self.depth == 1 and tag == "tr":
            self.row = []
        elif self.depth == 1 and tag in ("td", "th") and self.row is not None:
            self.cell = []
            self.spans = self.spans or any(k in ("colspan", "rowspan") and v not in (None, "", "1") for k, v in attrs)
        elif self.depth == 1 and tag == "br" and self.cell is not None:
            self.cell.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag == "table" and self.depth:
            if self.depth == 1 and self._stack:
                self.tables.append(self._stack.pop())
            self.depth -= 1
        elif self.depth == 1 and tag in ("td", "th") and self.cell is not None and self.row is not None:
            self.row.append(" ".join("".join(self.cell).split()))
            self.cell = None
        elif self.depth == 1 and tag == "tr" and self.row is not None:
            self._stack[-1][1].append(self.row)
            self.row = None

    def handle_data(self, data: str) -> None:
        if self.depth == 1 and self.cell is not None:
            self.cell.append(data)


def _html_table(data: bytes, mapping: ImportMapping, warnings: list[str]) -> list[list[str]]:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = data.decode(mapping.encoding if mapping.encoding != "utf-8-sig" else "latin-1", errors="replace")
        warnings.append("HTML is not valid UTF-8; decoded leniently")
    parser = _TableParser()
    parser.feed(text)
    parser.close()
    if not parser.tables:
        raise ParseError("no <table> found in the HTML")
    if mapping.table_id is not None:
        chosen = [t for t in parser.tables if t[0] == mapping.table_id]
        if not chosen:
            raise ParseError(f"no <table id={mapping.table_id!r}> in the HTML")
        rows = chosen[0][1]
    else:
        if mapping.table_index >= len(parser.tables):
            raise ParseError(f"table_index {mapping.table_index} but the HTML has only {len(parser.tables)} table(s)")
        rows = parser.tables[mapping.table_index][1]
    if parser.spans:
        warnings.append("the HTML uses colspan/rowspan, which are not expanded; cells may be misaligned")
    return rows


def _xlsx_table(data: bytes, mapping: ImportMapping, warnings: list[str]) -> list[list[str]]:
    import datetime
    import zipfile

    from openpyxl import load_workbook

    def cell_text(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, datetime.datetime):
            return value.date().isoformat() if value.time() == datetime.time(0) else value.isoformat()
        if isinstance(value, (datetime.date, datetime.time)):
            return value.isoformat()
        return str(value)

    try:
        workbook = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except (zipfile.BadZipFile, KeyError, ValueError, OSError) as exc:
        raise ParseError(f"not a readable .xlsx workbook: {exc}") from None
    except Exception as exc:  # openpyxl raises assorted types for damaged files
        raise ParseError(f"not a readable .xlsx workbook: {type(exc).__name__}: {exc}") from None
    try:
        if mapping.sheet is not None:
            if mapping.sheet not in workbook.sheetnames:
                raise ParseError(f"sheet {mapping.sheet!r} not found; the workbook has {', '.join(workbook.sheetnames) or 'no sheets'}")
            sheet = workbook[mapping.sheet]
        else:
            if not workbook.sheetnames:
                raise ParseError("the workbook has no sheets")
            sheet = workbook[workbook.sheetnames[0]]
            if len(workbook.sheetnames) > 1:
                warnings.append(f"the workbook has {len(workbook.sheetnames)} sheets; read the first ({sheet.title!r}); set mapping.sheet to choose")
        return [[cell_text(v) for v in row] for row in sheet.iter_rows(values_only=True)]
    finally:
        workbook.close()


def _pdf_table(data: bytes, mapping: ImportMapping, warnings: list[str]) -> list[list[str]]:
    from pypdf import PdfReader
    from pypdf.errors import PyPdfError

    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise ParseError("the PDF is encrypted; acquisition does not bypass protection")
        pages = [page.extract_text() or "" for page in reader.pages]
    except ParseError:
        raise
    except (PyPdfError, ValueError, OSError, KeyError, TypeError) as exc:
        raise ParseError(f"not a readable PDF: {exc}") from None
    lines = [line.strip() for page in pages for line in page.splitlines()]
    lines = [line for line in lines if line]
    if not lines:
        raise ParseError("the PDF has no text layer (scanned image?); OCR is not part of acquisition")
    splitter = re.compile(mapping.split_pattern)
    warnings.append("PDF rows are split by text position/spacing; verify the result against the original")
    return [[part.strip() for part in splitter.split(line)] for line in lines]


# ----------------------------------------------------------------------------- mapping applied


def read_rows(data: bytes, mapping: ImportMapping) -> ImportRows:
    """Rows from one file, with the mapping applied. Raises ``ParseError`` if the file cannot be used at all."""
    result = ImportRows()
    warnings = result.warnings
    if mapping.format == "csv":
        table = _csv_table(data, mapping)
    elif mapping.format == "html_table":
        table = _html_table(data, mapping, warnings)
    elif mapping.format == "xlsx":
        table = _xlsx_table(data, mapping, warnings)
    else:
        table = _pdf_table(data, mapping, warnings)

    index = mapping.header_row - 1  # pdf_text: blank lines were already dropped, so this counts non-empty lines
    if index >= len(table):
        raise ParseError(f"header_row {mapping.header_row} but the file has only {len(table)} row(s)")
    header = [normalize_header(cell) for cell in table[index]]
    seen = [h for h in header if h]
    duplicates = sorted({h for h in seen if seen.count(h) > 1})
    if duplicates:
        raise ParseError(f"duplicate column header {duplicates[0]!r}; the mapping cannot tell them apart")
    position = {h: i for i, h in enumerate(header) if h}
    missing_required = [c.source for c in mapping.columns if c.required and normalize_header(c.source) not in position]
    if missing_required:
        raise ParseError(f"required column(s) not found in the file: {', '.join(missing_required)}; found: {', '.join(t for t in table[index] if t) or '(none)'}")
    present: list[tuple[ColumnMap, int]] = []
    for column in mapping.columns:
        where = position.get(normalize_header(column.source))
        if where is None:
            warnings.append(f"optional column {column.source!r} not found; the field {column.field!r} is absent from every row")
        else:
            present.append((column, where))

    def warn(message: str) -> None:
        if len(warnings) < MAX_WARNINGS:
            warnings.append(message)
        elif len(warnings) == MAX_WARNINGS:
            warnings.append("further warnings omitted")

    for offset, cells in enumerate(table[index + 1 :], start=index + 2):
        if not any(str(c).strip() for c in cells):
            continue  # blank rows are not data
        if [normalize_header(c) for c in cells] == header:
            continue  # the header repeated (e.g. at the top of every PDF page or printed page): not data
        result.rows_seen += 1
        if result.rows_seen > MAX_ROWS:
            raise ParseError(f"more than {MAX_ROWS} rows; split the file")
        if mapping.format == "pdf_text" and len(cells) != len(header):
            warn(f"line {offset}: {len(cells)} column(s), expected {len(header)}; skipped")
            continue
        row: dict[str, Any] = {}
        for column, where in present:
            value = str(cells[where]).strip() if where < len(cells) else ""
            if value:
                row[column.field] = value
        missing = [c.field for c, _ in present if c.required and c.field not in row]
        if missing:
            warn(f"row {offset}: required field(s) empty: {', '.join(missing)}; skipped")
            continue
        if not row:
            continue
        row["_row"] = offset
        result.rows.append(row)
    return result
