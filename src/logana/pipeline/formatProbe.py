import re
from enum import Enum
from typing import Tuple

class FormatHint(Enum):
    JSON = "json"
    SYSLOG = "syslog"
    CLF = "clf"
    KV = "kv"
    DELIMITED = "delimited"
    UNKNOWN = "unknown"

# Quick check patterns
CLF_QUICK_RE = re.compile(r'^\S+\s+\S+\s+\S+\s+\[[^\]]+\]\s+"[^"]*"')
KV_PAIR_RE = re.compile(r'[a-zA-Z0-9_.-]+=(?:"[^"]*"|\S+)')
ISO_DATE_COMMA_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2},\d"
)


def _stableCommaColumns(text: str) -> bool:
    """Comma must form consistent multi-column rows, not a single ISO date comma."""
    lines = [ln for ln in text.split("\n")[:3] if ln.strip()]
    if not lines:
        return False
    first = lines[0]
    if first.count(",") < 2:
        return False
    if ISO_DATE_COMMA_RE.match(first.lstrip()):
        return False
    counts = [ln.count(",") + 1 for ln in lines if ln.count(",") >= 2]
    if not counts:
        return False
    return min(counts) >= 3 and len(set(counts)) == 1


def hasConsistentDelimiter(text: str) -> bool:
    """Checks for a repeated separator that looks like real column structure."""
    sample = text[:400]
    first_line = sample.split("\n", 1)[0]

    for delim in ("\t", "|"):
        if first_line.count(delim) >= 2 and first_line.count(delim) + 1 >= 3:
            return True

    return _stableCommaColumns(sample)


def probeFormat(text: str) -> Tuple[FormatHint, float]:
    """Inspects the start of a log line group (O(1)) and returns a predicted format and confidence."""
    stripped = text.lstrip()
    if not stripped:
        return FormatHint.UNKNOWN, 0.0

    # 1. JSON Sniff
    if stripped.startswith('{'):
        return FormatHint.JSON, 0.95

    # 2. Syslog Sniff (BSD/IETF starts with <priority>)
    if stripped.startswith('<'):
        bracketEnd = stripped.find('>')
        if bracketEnd > 0 and stripped[1:bracketEnd].isdigit():
            return FormatHint.SYSLOG, 0.9

    # 3. CLF Sniff (Common / Combined Log Format)
    if CLF_QUICK_RE.match(stripped[:300]):
        return FormatHint.CLF, 0.85

    # 4. Embedded JSON (prefix-tolerant)
    if "{" in stripped[:300]:
        return FormatHint.JSON, 0.7

    # 5. Logfmt / LTSV (tab-separated key-value)
    if "\t" in stripped[:200] and stripped.count("\t") >= 2:
        return FormatHint.KV, 0.75

    # 6. Key-Value Sniff
    kvCount = len(KV_PAIR_RE.findall(stripped[:200]))
    if kvCount >= 3:
        return FormatHint.KV, 0.8

    # 7. Delimited Sniff (tab, pipe, or stable comma columns)
    if hasConsistentDelimiter(stripped):
        return FormatHint.DELIMITED, 0.65

    return FormatHint.UNKNOWN, 0.0
