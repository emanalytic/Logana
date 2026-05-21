import time
from typing import Union
from logana.models.logEvent import LogEvent
from logana.models.quarantineEntry import QuarantineEntry

class EventCounter:
    """Tracks absolute volume counts (events vs quarantined lines) and streaming throughput."""
    
    def __init__(self):
        self._totalEvents = 0
        self._totalQuarantined = 0
        self.startTime = time.monotonic()
        self.lastEventTime = self.startTime

    def ingest(self, item: Union[LogEvent, QuarantineEntry]) -> None:
        """Increments counts depending on the item type."""
        self.lastEventTime = time.monotonic()
        if isinstance(item, LogEvent):
            self._totalEvents += 1
        elif isinstance(item, QuarantineEntry):
            self._totalQuarantined += 1

    @property
    def totalLines(self) -> int:
        """Returns the total number of lines processed."""
        return self._totalEvents + self._totalQuarantined

    @property
    def totalEvents(self) -> int:
        """Returns the total number of successfully parsed log events."""
        return self._totalEvents

    @property
    def totalQuarantined(self) -> int:
        """Returns the total number of quarantined log entries."""
        return self._totalQuarantined

    @property
    def elapsedTime(self) -> float:
        """Returns the elapsed time in seconds since the counter was initialized."""
        return max(time.monotonic() - self.startTime, 0.001)

    @property
    def throughput(self) -> float:
        """Returns the processing throughput in lines per second."""
        return self.totalLines / self.elapsedTime
