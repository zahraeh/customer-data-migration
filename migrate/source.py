"""Reading legacy CSV exports the way they actually arrive.

Legacy French tools and Excel typically export Windows-1252 (not UTF-8),
semicolon-delimited (because the comma is the decimal separator). Reading
them as UTF-8/comma either crashes or, worse, silently mangles accents.
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List


@dataclass
class SourceFile:
    path: Path
    encoding: str
    delimiter: str
    headers: List[str]
    rows: List[Dict[str, str]] = field(default_factory=list)

    def line_number(self, index: int) -> int:
        """Spreadsheet line number for row `index` (header is line 1)."""
        return index + 2


def _decode(raw: bytes) -> tuple:
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return raw.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1"), "latin-1"


def _sniff_delimiter(first_line: str) -> str:
    counts = {d: first_line.count(d) for d in (";", ",", "\t", "|")}
    return max(counts, key=counts.get)


def read(path) -> SourceFile:
    path = Path(path)
    text, encoding = _decode(path.read_bytes())
    first_line = text.splitlines()[0] if text else ""
    delimiter = _sniff_delimiter(first_line)
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    headers = [h.strip() for h in (reader.fieldnames or [])]
    rows = []
    for raw_row in reader:
        rows.append({(k or "").strip(): (v if v is not None else "") for k, v in raw_row.items()})
    return SourceFile(path=path, encoding=encoding, delimiter=delimiter, headers=headers, rows=rows)
