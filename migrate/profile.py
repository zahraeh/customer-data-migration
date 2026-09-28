"""Profile a legacy export before writing a single mapping rule.

The "shape" of a value (digits → 9, letters → a) surfaces format problems
at a glance: a postcode column showing both `99999` and `9999` means Excel
has eaten leading zeros; an amount column showing `9.999` next to `999,99`
means two conventions are mixed in one field.
"""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import List

from . import source as source_io


def shape(value: str) -> str:
    s = re.sub(r"[0-9]", "9", value.strip())
    s = re.sub(r"[A-Za-zÀ-ÿ]+", "a", s)
    return s[:24]


def profile_file(path) -> str:
    src = source_io.read(path)
    n = len(src.rows)
    out: List[str] = [
        f"## {src.path.name}\n",
        f"- Rows: **{n}**",
        f"- Encoding detected: `{src.encoding}`" + ("  ⚠️ not UTF-8, accents will break if read naively" if src.encoding != "utf-8-sig" else ""),
        f"- Delimiter: `{src.delimiter}`\n",
        "| Column | Filled | Distinct | Most common shapes | Example |",
        "|---|---:|---:|---|---|",
    ]
    for h in src.headers:
        values = [r.get(h, "") for r in src.rows]
        filled = [v for v in values if v.strip()]
        # Top 3, plus any other shape covering ≥ 2% of rows: a minority format
        # is exactly the one that gets missed (see docs/04, corrective action 2).
        ranked = Counter(shape(v) for v in filled).most_common()
        shapes = [s for i, s in enumerate(ranked) if i < 3 or s[1] >= 0.02 * n][:8]
        shape_txt = ", ".join(f"`{s}` ×{c}" for s, c in shapes)
        example = filled[0].strip()[:30] if filled else ""
        pct = len(filled) / n if n else 0
        # Only structured columns (numbers, dates, codes) should have one shape;
        # free text like names naturally has many.
        structured = bool(shapes) and "a" not in shapes[0][0]
        flag = " ⚠️" if structured and len(shapes) > 1 and shapes[1][1] > 0.02 * n else ""
        out.append(f"| {h} | {pct:.0%} | {len(set(filled))} | {shape_txt}{flag} | {example} |")
    out.append("")
    return "\n".join(out)


def profile(paths, out_path=None) -> str:
    text = "# Source data profile\n\n⚠️ = more than one format in the same column, worth a question to the customer.\n\n"
    text += "\n".join(profile_file(p) for p in paths)
    if out_path:
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        Path(out_path).write_text(text, encoding="utf-8")
    return text
