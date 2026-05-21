"""Lightweight file sampling to infer time context (no per-log-file rules)."""
import re
from collections import Counter
from pathlib import Path
from typing import Optional

YEAR_IN_LINE_RE = re.compile(r"\b(19\d{2}|20\d{2})\b")
CLF_YEAR_RE = re.compile(r"/[A-Za-z]{3}/(\d{4}):")
APACHE_BRACKET_YEAR_RE = re.compile(
    r"\[[A-Za-z]{3}\s+[A-Za-z]{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}\s+(\d{4})\]"
)


def sniffReferenceYear(
    file_path: str,
    *,
    encoding: str = "utf-8",
    max_lines: int = 400,
) -> Optional[int]:
    """Pick a reference year from early lines when CLI did not set one."""
    path = Path(file_path)
    if not path.is_file():
        return None

    counts: Counter[int] = Counter()
    try:
        with path.open(encoding=encoding, errors="replace") as handle:
            for idx, line in enumerate(handle):
                if idx >= max_lines:
                    break
                for match in CLF_YEAR_RE.finditer(line):
                    counts[int(match.group(1))] += 2
                for match in APACHE_BRACKET_YEAR_RE.finditer(line):
                    counts[int(match.group(1))] += 2
                for match in YEAR_IN_LINE_RE.finditer(line):
                    year = int(match.group(1))
                    if 1990 <= year <= 2035:
                        counts[year] += 1
    except OSError:
        return None

    if not counts:
        return None
    year, _ = counts.most_common(1)[0]
    return year
