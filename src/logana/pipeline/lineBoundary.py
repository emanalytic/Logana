from typing import Generator, List, Tuple

_CONTINUATION_PREFIXES = (
    "at ",
    "Caused by:",
    "Exception in thread",
    "...",
    "Traceback (",
)


def hasIncompleteJsonObject(text: str) -> bool:
    """Returns True when text starts a JSON object whose braces are not balanced yet."""
    stripped = text.lstrip()
    if not stripped.startswith('{'):
        return False

    depth = 0
    inString = False
    escapeNext = False

    for char in stripped:
        if escapeNext:
            escapeNext = False
            continue

        if char == '\\' and inString:
            escapeNext = True
            continue

        if char == '"':
            inString = not inString
            continue

        if inString:
            continue

        if char == '{':
            depth += 1
        elif char == '}':
            depth -= 1
            if depth <= 0:
                return False

    return depth > 0


def isCompleteJsonLine(line: str) -> bool:
    """True when a single physical line is a self-contained JSON object."""
    stripped = line.strip()
    return stripped.startswith("{") and not hasIncompleteJsonObject(stripped)


def _isContinuationLine(raw_line: str, line: str, group_text: str) -> bool:
    if hasIncompleteJsonObject(group_text):
        return True
    if raw_line.startswith((" ", "\t")):
        return True
    stripped = line.lstrip()
    for prefix in _CONTINUATION_PREFIXES:
        if stripped.startswith(prefix):
            return True
    return False


class LineBoundaryDetector:
    """Accumulates physical log lines into logical line groups."""

    def __init__(self, maxGroupSize: int = 50):
        self.maxGroupSize = maxGroupSize
        self.currentGroup: List[str] = []
        self.startLineNum = 1

    def detectBoundaries(
        self, rawLineStream: Generator[str, None, None]
    ) -> Generator[Tuple[str, int], None, None]:
        for idx, rawLine in enumerate(rawLineStream, start=1):
            line = rawLine.rstrip('\r\n')

            if not self.currentGroup:
                self.currentGroup.append(line)
                self.startLineNum = idx
                continue

            group_text = "\n".join(self.currentGroup)
            should_continue = _isContinuationLine(rawLine, line, group_text)

            # NDJSON: complete one-line JSON starts a new record
            if isCompleteJsonLine(line) and not hasIncompleteJsonObject(group_text):
                should_continue = False

            if should_continue and len(self.currentGroup) < self.maxGroupSize:
                self.currentGroup.append(line)
            else:
                yield "\n".join(self.currentGroup), self.startLineNum
                self.currentGroup = [line]
                self.startLineNum = idx

        if self.currentGroup:
            yield "\n".join(self.currentGroup), self.startLineNum
            self.currentGroup = []
