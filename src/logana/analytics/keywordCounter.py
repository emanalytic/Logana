import re
from collections import Counter
from typing import Dict, List, Union
from logana.models.logEvent import LogEvent
from logana.models.quarantineEntry import QuarantineEntry
from logana.models.fieldState import Known

_TOKEN_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9_-]{2,}")


class KeywordCounter:
    """Counts frequent message tokens for unstructured log insight."""

    def __init__(self, maxTokens: int = 500) -> None:
        self._counts: Counter[str] = Counter()
        self.maxTokens = maxTokens

    def ingest(self, item: Union[LogEvent, QuarantineEntry]) -> None:
        if not isinstance(item, LogEvent):
            return
        if not isinstance(item.message, Known):
            return
        text = str(item.message.value).lower()
        for token in _TOKEN_RE.findall(text):
            if token in ("the", "and", "for", "with", "from", "http", "true", "false"):
                continue
            self._counts[token] += 1
            if len(self._counts) > self.maxTokens:
                self._counts = Counter(dict(self._counts.most_common(self.maxTokens)))

    def getTop(self, limit: int = 15) -> List[Dict[str, Union[str, int]]]:
        return [
            {"token": word, "count": count}
            for word, count in self._counts.most_common(limit)
        ]
