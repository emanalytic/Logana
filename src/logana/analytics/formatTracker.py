from datetime import datetime
from typing import Union, List, Optional
from collections import Counter
from logana.models.logEvent import LogEvent
from logana.models.quarantineEntry import QuarantineEntry
from logana.utils.ringBuffer import RingBuffer
from logana.models.events import DriftEvent

class FormatTracker:
    """Lightweight schema drift detection tracking the dominant log formats in the stream."""
    
    def __init__(self, windowSize: int = 100):
        self.window = RingBuffer(windowSize)
        self.driftEvents: List[DriftEvent] = []

    def ingest(self, item: Union[LogEvent, QuarantineEntry]) -> None:
        """Processes a log event or quarantine entry, recording its format and detecting drift."""
        # For LogEvent, we use its parserId. For QuarantineEntry, we use 'quarantined'
        formatName = "quarantined"
        lineNum = item.lineNumber
        
        # Get timestamp
        timestamp = None
        if isinstance(item, LogEvent):
            formatName = item.parserId
            if hasattr(item.timestamp, "value"):
                timestamp = item.timestamp.value
        else:
            timestamp = item.timestamp
            
        self.record(formatName, lineNum, timestamp)

    def record(self, formatName: str, lineNum: int, timestamp: Optional[datetime]) -> None:
        """Pushes the format into the rolling window and checks if the dominant format shifted."""
        prevDominant = self._dominantFormat()
        self.window.push(formatName)
        newDominant = self._dominantFormat()
        
        if prevDominant is not None and newDominant != prevDominant:
            drift = DriftEvent(
                lineNumber=lineNum,
                fromFormat=prevDominant,
                toFormat=newDominant,
                timestamp=timestamp
            )
            self.driftEvents.append(drift)

    def _dominantFormat(self) -> Optional[str]:
        """Calculates the most common format in the rolling window."""
        if self.window.count == 0:
            return None
            
        counts = Counter(self.window.getValues())
        return counts.most_common(1)[0][0]

    def getFormatDistribution(self) -> dict[str, float]:
        """Returns the percentage distribution of formats currently in the rolling window."""
        values = self.window.getValues()
        if not values:
            return {}
            
        counts = Counter(values)
        total = len(values)
        return {fmt: count / total for fmt, count in counts.items()}
