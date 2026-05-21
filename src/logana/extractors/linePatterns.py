"""Generic line-level field patterns (format families, not per-log-file parsers)."""
from __future__ import annotations

import re
from typing import TYPE_CHECKING, Dict, Optional, Tuple

from logana.models.fieldState import Absent, FieldState, Known, isKnown

if TYPE_CHECKING:
    from logana.parsers.fieldKit import ParserFieldKit

STATUS_LINE_RE = re.compile(
    r"\b(?:status|status_code|sc-status|http_status)[=:]\s*(\d{3})\b",
    re.IGNORECASE,
)
LEVEL_LINE_RE = re.compile(
    r"\b(?:level|lvl|severity|log_level)[=:]\s*([A-Za-z]+)\b",
    re.IGNORECASE,
)
BRACKET_LEVEL_RE = re.compile(r"\[(ERROR|WARN|WARNING|INFO|DEBUG|TRACE|FATAL|CRITICAL)\]", re.I)
TIME_KV_RE = re.compile(
    r"\b(?:time|duration_ms|latency_ms|response_time|elapsed)[=:]\s*"
    r"([0-9]+(?:\.[0-9]+)?)\s*(ms|s|sec|seconds|milliseconds)?\b",
    re.IGNORECASE,
)
HTTP_INLINE_RE = re.compile(
    r'"\s*(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)\s+(\S+)\s+HTTP/[\d.]+"',
    re.IGNORECASE,
)


def _secondsToMs(seconds: float) -> Optional[float]:
    if seconds <= 0 or seconds > 120_000.0:
        return None
    return seconds * 1000.0


def _parseTimeKv(match: re.Match[str]) -> Optional[Tuple[float, str]]:
    try:
        val = float(match.group(1))
    except ValueError:
        return None
    unit = (match.group(2) or "").lower()
    raw = match.group(0)
    if unit in ("ms", "milliseconds"):
        if val > 120_000.0:
            return None
        return val, raw
    if unit in ("s", "sec", "seconds"):
        ms = _secondsToMs(val)
        return (ms, raw) if ms is not None else None
    if val >= 1000.0:
        if val > 120_000.0:
            return None
        return val, raw
    ms = _secondsToMs(val)
    return (ms, raw) if ms is not None else None


def applyLinePatterns(
    fields: Dict[str, FieldState],
    kit: ParserFieldKit,
    line: str,
) -> None:
    """Fill standard fields from colon/bracket/HTTP patterns on the full line."""
    if not line:
        return

    if not isKnown(fields.get("statusCode", Absent())):
        match = STATUS_LINE_RE.search(line)
        if match:
            kit.mergeField(
                fields,
                "statusCode",
                kit.statusExt.extract(match.group(1)),
            )

    if not isKnown(fields.get("responseTimeMs", Absent())):
        match = TIME_KV_RE.search(line)
        if match:
            parsed = _parseTimeKv(match)
            if parsed is not None:
                ms, raw = parsed
                kit.mergeField(fields, "responseTimeMs", Known(ms, 0.88, raw))

    if not isKnown(fields.get("logLevel", Absent())):
        match = LEVEL_LINE_RE.search(line)
        if match:
            kit.mergeField(
                fields,
                "logLevel",
                kit.levelExt.extract(match.group(1)),
            )
        if not isKnown(fields.get("logLevel", Absent())):
            bracket = BRACKET_LEVEL_RE.search(line)
            if bracket:
                kit.mergeField(
                    fields,
                    "logLevel",
                    kit.levelExt.extract(bracket.group(1)),
                )

    if not isKnown(fields.get("httpMethod", Absent())) or not isKnown(
        fields.get("urlPath", Absent())
    ):
        http = HTTP_INLINE_RE.search(line)
        if http:
            method, path = http.group(1), http.group(2)
            kit.mergeField(fields, "httpMethod", kit.methodExt.extract(method))
            kit.mergeField(fields, "urlPath", kit.pathExt.extract(path))


def scanLinePatterns(
    fields: Dict[str, FieldState],
    kit: ParserFieldKit,
    lineText: Optional[str],
) -> None:
    if lineText is not None:
        applyLinePatterns(fields, kit, lineText)
