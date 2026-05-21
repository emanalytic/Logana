"""Fuzzy timestamp parsing via python-dateutil (fallback after format-specific rules)."""

import re
import warnings
from datetime import datetime
from typing import Optional, Tuple

from dateutil import parser as dateutil_parser

_DATE_HINT = re.compile(
    r"\d{4}[-/]\d{2}|"
    r"\d{2}/[A-Za-z]{3}/\d{4}|"
    r"[A-Za-z]{3}\s+\d{1,2}\s+\d{2}:\d{2}|"
    r"\b\d{10,13}\b"
)


def tryFuzzyTimestamp(
    text: str,
    default: datetime,
) -> Optional[Tuple[datetime, str]]:
    """Parse a timestamp from free text; returns (datetime, matched span hint) or None."""
    cleaned = text.strip()
    if not cleaned or not _DATE_HINT.search(cleaned):
        return None
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=Warning)
            dt = dateutil_parser.parse(cleaned, fuzzy=True, default=default)
        return dt, cleaned[:120]
    except (ValueError, TypeError, OverflowError, dateutil_parser.ParserError):
        return None
