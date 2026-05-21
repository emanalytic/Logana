from collections import Counter
from datetime import datetime
from typing import List, Optional, Union
from logana.models.logEvent import LogEvent
from logana.models.quarantineEntry import QuarantineEntry
from logana.models.fieldState import Known
from logana.utils.timeUtils import coerceToUtc


class LogTimeSpanTracker:
    """Tracks first/last log-time among successfully parsed events."""

    def __init__(self) -> None:
        self._timestamps: List[datetime] = []
        self.eventCount = 0

    def ingest(self, item: Union[LogEvent, QuarantineEntry]) -> None:
        if not isinstance(item, LogEvent):
            return
        if not isinstance(item.timestamp, Known):
            return

        ts = coerceToUtc(item.timestamp.value)
        self._timestamps.append(ts)
        self.eventCount += 1

    def _dominant_window(self) -> List[datetime]:
        if not self._timestamps:
            return []
        year_counts = Counter(ts.year for ts in self._timestamps)
        dominant_year, count = year_counts.most_common(1)[0]
        if count >= max(3, len(self._timestamps) // 4):
            return [ts for ts in self._timestamps if ts.year == dominant_year]
        return self._timestamps

    @property
    def first(self) -> Optional[datetime]:
        window = self._dominant_window()
        return min(window) if window else None

    @property
    def last(self) -> Optional[datetime]:
        window = self._dominant_window()
        return max(window) if window else None

    @property
    def spanSeconds(self) -> Optional[float]:
        if self.first is None or self.last is None:
            return None
        return (self.last - self.first).total_seconds()

    def toDict(self) -> dict:
        if self.first is None:
            return {"available": False, "message": "No timed events in this file."}
        return {
            "available": True,
            "first": self.first.isoformat(),
            "last": self.last.isoformat(),
            "spanSeconds": self.spanSeconds,
            "eventCount": self.eventCount,
        }
