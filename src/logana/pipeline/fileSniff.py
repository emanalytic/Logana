"""Lightweight file sampling to infer time context (no per-log-file rules)."""
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Optional

YEAR_IN_LINE_RE = re.compile(r"\b(19\d{2}|20\d{2})\b")
CLF_YEAR_RE = re.compile(r"/[A-Za-z]{3}/(\d{4}):")
APACHE_BRACKET_YEAR_RE = re.compile(
    r"\[[A-Za-z]{3}\s+[A-Za-z]{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}\s+(\d{4})\]"
)
ISO_YEAR_RE = re.compile(r"\b(20\d{2})-\d{2}-\d{2}\b")

MIN_YEAR = 1995
MAX_YEAR = datetime.now().year + 1
MIN_VOTE_SHARE = 0.30
MIN_VOTES = 3


def _plausible_year(year: int) -> bool:
    return MIN_YEAR <= year <= MAX_YEAR


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
    total_weight = 0
    try:
        with path.open(encoding=encoding, errors="replace") as handle:
            for idx, line in enumerate(handle):
                if idx >= max_lines:
                    break
                for match in CLF_YEAR_RE.finditer(line):
                    year = int(match.group(1))
                    if _plausible_year(year):
                        counts[year] += 4
                        total_weight += 4
                for match in APACHE_BRACKET_YEAR_RE.finditer(line):
                    year = int(match.group(1))
                    if _plausible_year(year):
                        counts[year] += 4
                        total_weight += 4
                for match in ISO_YEAR_RE.finditer(line):
                    year = int(match.group(1))
                    if _plausible_year(year):
                        counts[year] += 3
                        total_weight += 3
                for match in YEAR_IN_LINE_RE.finditer(line):
                    year = int(match.group(1))
                    if _plausible_year(year):
                        counts[year] += 1
                        total_weight += 1
    except OSError:
        return None

    if not counts or total_weight == 0:
        return None

    year, votes = counts.most_common(1)[0]
    if votes < MIN_VOTES:
        return None
    if votes / total_weight < MIN_VOTE_SHARE:
        return None
    return year
