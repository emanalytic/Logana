from datetime import datetime, timezone
from typing import Union, Dict, Optional, List
from logana.models.logEvent import LogEvent
from logana.models.quarantineEntry import QuarantineEntry
from logana.models.fieldState import Known
from logana.analytics.errorSeverity import isErrorEvent
from logana.analytics.anomalyDetector import StreamingAnomalyDetector
from logana.models.events import AnomalyEvent
from logana.utils.timeUtils import coerceToUtc, nowUtc

class ErrorRateTracker:
    """Tracks error rates over bucketed time windows and performs streaming anomaly detection."""
    
    def __init__(self, windowSizeSec: int = 5, historyCapacity: int = 60, zThreshold: float = 5.0):
        self.windowSizeSec = windowSizeSec
        # Active buckets: windowStartTimestamp (int) -> {'errors': int, 'total': int}
        self.buckets: Dict[int, Dict[str, int]] = {}
        self.detector = StreamingAnomalyDetector(windowSize=historyCapacity, zThreshold=zThreshold)
        self.anomalies: List[AnomalyEvent] = []
        self.lastProcessedBucket: Optional[int] = None
        self._totalErrors = 0
        self._totalLogs = 0

    def ingest(self, item: Union[LogEvent, QuarantineEntry]) -> None:
        """Processes an incoming log event or quarantine entry, updating error statistics."""
        if not isinstance(item, LogEvent):
            return
            
        self._totalLogs += 1
        
        is_error = isErrorEvent(item)
        if is_error:
            self._totalErrors += 1

        evtTime = None
        if isinstance(item.timestamp, Known):
            evtTime = coerceToUtc(item.timestamp.value)
        else:
            evtTime = nowUtc()
            
        bucketId = int(evtTime.timestamp() / self.windowSizeSec) * self.windowSizeSec
        
        if bucketId not in self.buckets:
            self.buckets[bucketId] = {"errors": 0, "total": 0}
            
        self.buckets[bucketId]["total"] += 1
        if is_error:
            self.buckets[bucketId]["errors"] += 1
            
        # Detect completed buckets and run them through the anomaly detector
        self._checkAndRollBuckets(bucketId)

    def _checkAndRollBuckets(self, currentBucket: int) -> None:
        if self.lastProcessedBucket is None:
            self.lastProcessedBucket = currentBucket
            return
            
        if currentBucket > self.lastProcessedBucket:
            # Process all closed buckets chronologically
            for bId in sorted(list(self.buckets.keys())):
                if self.lastProcessedBucket <= bId < currentBucket:
                    bucketData = self.buckets[bId]
                    total = bucketData["total"]
                    errors = bucketData["errors"]
                    rate = float(errors) / float(total) if total > 0 else 0.0
                    
                    dt = datetime.fromtimestamp(bId, tz=timezone.utc)
                    anomaly = self.detector.add(rate, dt)
                    if anomaly:
                        self.anomalies.append(anomaly)
                        
                    # Bounded memory: delete bucket from dictionary once processed
                    del self.buckets[bId]
                    
            self.lastProcessedBucket = currentBucket

    def finalize(self) -> None:
        """Flush the final time bucket after the input stream ends."""
        if not self.buckets:
            return
        flush_through = max(self.buckets.keys()) + self.windowSizeSec + 1
        self._checkAndRollBuckets(flush_through)

    @property
    def totalErrors(self) -> int:
        """Returns the total number of errors seen across successfully parsed events."""
        return self._totalErrors

    @property
    def overallErrorRate(self) -> float:
        """Returns the overall ratio of errors to successfully parsed events."""
        if self._totalLogs == 0:
            return 0.0
        return self._totalErrors / self._totalLogs

    def getRecentRates(self) -> List[float]:
        """Returns the list of rates in the rolling anomaly detector buffer."""
        return self.detector.window.getValues()
