from datetime import datetime, timezone
from typing import Union, Dict, List, Optional
from logana.models.logEvent import LogEvent
from logana.models.quarantineEntry import QuarantineEntry
from logana.models.fieldState import Known
from logana.utils.ringBuffer import RingBuffer
from logana.analytics.anomalyDetector import StreamingAnomalyDetector
from logana.models.events import AnomalyEvent
from logana.utils.timeUtils import coerceToUtc, nowUtc

class QuarantineTracker:
    """Tracks the quarantine rate as a first-class health metric and detects anomaly spikes."""
    
    def __init__(self, windowSizeSec: int = 5, historyCapacity: int = 60, zThreshold: float = 3.0):
        self.windowSizeSec = windowSizeSec
        self.totalEvents = 0
        self.totalQuarantined = 0
        self.recentSamples = RingBuffer(50)  # Bounded ring buffer of recent QuarantineEntries
        self.reasonCounts: Dict[str, int] = {}
        
        # Buckets for streaming anomaly detection: windowStartTimestamp -> {'quarantined': int, 'total': int}
        self.buckets: Dict[int, Dict[str, int]] = {}
        self.detector = StreamingAnomalyDetector(windowSize=historyCapacity, zThreshold=zThreshold)
        self.anomalies: List[AnomalyEvent] = []
        self.lastProcessedBucket: Optional[int] = None

    def ingest(self, item: Union[LogEvent, QuarantineEntry]) -> None:
        """Records an ingested item, tracking quarantine rates and evaluating for anomalies."""
        self.totalEvents += 1
        isQuarantined = isinstance(item, QuarantineEntry)
        
        if isQuarantined:
            self.totalQuarantined += 1
            self.recentSamples.push(item)
            self._recordReasons(item.reason)
            
        # Resolve timestamp
        evtTime = None
        if isinstance(item, LogEvent) and isinstance(item.timestamp, Known):
            evtTime = coerceToUtc(item.timestamp.value)
        elif isinstance(item, QuarantineEntry) and item.timestamp:
            evtTime = coerceToUtc(item.timestamp)
        else:
            evtTime = nowUtc()
            
        bucketId = int(evtTime.timestamp() / self.windowSizeSec) * self.windowSizeSec
        
        if bucketId not in self.buckets:
            self.buckets[bucketId] = {"quarantined": 0, "total": 0}
            
        self.buckets[bucketId]["total"] += 1
        if isQuarantined:
            self.buckets[bucketId]["quarantined"] += 1
            
        self._checkAndRollBuckets(bucketId)

    def _checkAndRollBuckets(self, currentBucket: int) -> None:
        if self.lastProcessedBucket is None:
            self.lastProcessedBucket = currentBucket
            return
            
        if currentBucket > self.lastProcessedBucket:
            # Process all closed buckets
            for bId in sorted(list(self.buckets.keys())):
                if self.lastProcessedBucket <= bId < currentBucket:
                    bucketData = self.buckets[bId]
                    total = bucketData["total"]
                    quarantined = bucketData["quarantined"]
                    rate = float(quarantined) / float(total) if total > 0 else 0.0
                    
                    dt = datetime.fromtimestamp(bId, tz=timezone.utc)
                    anomaly = self.detector.add(rate, dt)
                    if anomaly:
                        self.anomalies.append(anomaly)
                        
                    # Bounded memory: remove processed bucket
                    del self.buckets[bId]
                    
            self.lastProcessedBucket = currentBucket

    def finalize(self) -> None:
        """Flush the final time bucket after the input stream ends."""
        if not self.buckets:
            return
        flush_through = max(self.buckets.keys()) + self.windowSizeSec + 1
        self._checkAndRollBuckets(flush_through)

    def _recordReasons(self, reason: str) -> None:
        for part in reason.split(";"):
            key = part.strip()
            if not key:
                continue
            if key.startswith("Field confidence below threshold"):
                key = "Field confidence below threshold"
            elif key.startswith("Mean field confidence"):
                key = "Mean field confidence below threshold"
            self.reasonCounts[key] = self.reasonCounts.get(key, 0) + 1

    def getReasonBreakdown(self) -> Dict[str, int]:
        """Returns quarantine reason counts sorted by frequency."""
        return dict(
            sorted(self.reasonCounts.items(), key=lambda item: item[1], reverse=True)
        )

    def getRecentSamples(self, limit: int = 10) -> List[QuarantineEntry]:
        """Returns the most recent quarantine entries (up to limit)."""
        samples = self.recentSamples.getValues()
        return samples[-limit:] if limit else samples

    @property
    def rate(self) -> float:
        """Returns the overall quarantine rate across all ingested items."""
        if self.totalEvents == 0:
            return 0.0
        return self.totalQuarantined / self.totalEvents

    def getRecentRates(self) -> List[float]:
        """Returns the list of rates in the rolling anomaly detector buffer."""
        return self.detector.window.getValues()
