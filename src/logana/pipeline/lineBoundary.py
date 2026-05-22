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
    depth, inString, escapeNext = _scanJsonState(stripped, depth, inString, escapeNext)
    return depth > 0

def _scanJsonState(
    text: str,
    depth: int,
    inString: bool,
    escapeNext: bool,
) -> Tuple[int, bool, bool]:
    for char in text:
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
                return 0, inString, escapeNext

    return depth, inString, escapeNext


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
        self._jsonDepth = 0
        self._jsonInString = False
        self._jsonEscapeNext = False

    def _resetJsonState(self) -> None:
        self._jsonDepth = 0
        self._jsonInString = False
        self._jsonEscapeNext = False

    def _updateJsonState(self, line: str) -> None:
        self._jsonDepth, self._jsonInString, self._jsonEscapeNext = _scanJsonState(
            line,
            self._jsonDepth,
            self._jsonInString,
            self._jsonEscapeNext,
        )

    def detectBoundaries(
        self, rawLineStream: Generator[str, None, None]
    ) -> Generator[Tuple[str, int], None, None]:
        for idx, rawLine in enumerate(rawLineStream, start=1):
            line = rawLine.rstrip('\r\n')

            if not self.currentGroup:
                self.currentGroup.append(line)
                self.startLineNum = idx
                self._resetJsonState()
                self._updateJsonState(line)
                continue

            if self._jsonDepth > 0:
                should_continue = True
            else:
                should_continue = _isContinuationLine(
                    rawLine,
                    line,
                    "\n".join(self.currentGroup),
                )

            # NDJSON: complete one-line JSON starts a new record
            if isCompleteJsonLine(line) and self._jsonDepth == 0:
                should_continue = False

            if should_continue and len(self.currentGroup) < self.maxGroupSize:
                self.currentGroup.append(line)
                self._updateJsonState(line)
            else:
                yield "\n".join(self.currentGroup), self.startLineNum
                self.currentGroup = [line]
                self.startLineNum = idx
                self._resetJsonState()
                self._updateJsonState(line)

        if self.currentGroup:
            yield "\n".join(self.currentGroup), self.startLineNum
            self.currentGroup = []
