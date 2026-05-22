from logana.models.logEvent import LogEvent
from logana.models.quarantineEntry import QuarantineEntry
from logana.models.fieldState import Known
from logana.utils.ringBuffer import RingBuffer
from logana.utils.timeUtils import coerceToUtc, nowUtc
from typing import Dict, List, Union
from logana.analytics.rollingRateTracker import RollingRateTracker


class QuarantineTracker(RollingRateTracker):
    """Tracks the quarantine rate as a first-class health metric and detects anomaly spikes."""

    def __init__(
        self,
        windowSizeSec: int = 5,
        historyCapacity: int = 60,
        zThreshold: float = 3.0,
    ):
        super().__init__(
            windowSizeSec=windowSizeSec,
            historyCapacity=historyCapacity,
            zThreshold=zThreshold,
        )

        self.totalEvents = 0
        self.totalQuarantined = 0
        self.recentSamples = RingBuffer(50)
        self.reasonCounts: Dict[str, int] = {}

    def ingest(self, item: Union[LogEvent, QuarantineEntry]) -> None:
        """Records an ingested item, tracking quarantine rates and evaluating for anomalies."""

        self.totalEvents += 1

        isQuarantined = isinstance(item, QuarantineEntry)

        if isQuarantined:
            self.totalQuarantined += 1
            self.recentSamples.push(item)
            self._recordReasons(item.reason)

        # Resolve timestamp
        if isinstance(item, LogEvent) and isinstance(item.timestamp, Known):
            evtTime = coerceToUtc(item.timestamp.value)
        elif isinstance(item, QuarantineEntry) and item.timestamp:
            evtTime = coerceToUtc(item.timestamp)
        else:
            evtTime = nowUtc()

        bucketId = int(evtTime.timestamp() / self.windowSizeSec) * self.windowSizeSec

        bucket = self._getOrCreateBucket(bucketId)

        bucket["total"] += 1
        if isQuarantined:
            bucket["quarantined"] += 1

        self._checkAndRollBuckets(bucketId)

    def _newBucket(self):
        return {"quarantined": 0, "total": 0}

    def _computeRate(self, bucketData):
        total = bucketData["total"]
        quarantined = bucketData["quarantined"]
        return float(quarantined) / float(total) if total > 0 else 0.0

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
        return dict(
            sorted(self.reasonCounts.items(), key=lambda item: item[1], reverse=True)
        )

    def getRecentSamples(self, limit: int = 10) -> List[QuarantineEntry]:
        samples = self.recentSamples.getValues()
        return samples[-limit:] if limit else samples

    @property
    def rate(self) -> float:
        if self.totalEvents == 0:
            return 0.0
        return self.totalQuarantined / self.totalEvents

    def getRecentRates(self) -> List[float]:
        return self.detector.window.getValues()