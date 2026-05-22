
from datetime import datetime, timezone
from typing import Dict, List, Optional

from logana.analytics.anomalyDetector import StreamingAnomalyDetector
from logana.models.events import AnomalyEvent


class RollingRateTracker:
    """Shared rolling-window anomaly tracking for bucketed rate metrics."""

    def __init__(
        self,
        *,
        windowSizeSec: int,
        historyCapacity: int,
        zThreshold: float,
    ):
        self.windowSizeSec = windowSizeSec

        # windowStartTimestamp -> bucket payload
        self.buckets: Dict[int, Dict[str, int]] = {}

        self.detector = StreamingAnomalyDetector(
            windowSize=historyCapacity,
            zThreshold=zThreshold,
        )

        self.anomalies: List[AnomalyEvent] = []
        self.lastProcessedBucket: Optional[int] = None

    def _newBucket(self) -> Dict[str, int]:
        raise NotImplementedError

    def _computeRate(self, bucketData: Dict[str, int]) -> float:
        raise NotImplementedError

    def _getOrCreateBucket(self, bucketId: int) -> Dict[str, int]:
        if bucketId not in self.buckets:
            self.buckets[bucketId] = self._newBucket()
        return self.buckets[bucketId]

    def _checkAndRollBuckets(self, currentBucket: int) -> None:
        if self.lastProcessedBucket is None:
            self.lastProcessedBucket = currentBucket
            return

        if currentBucket <= self.lastProcessedBucket:
            return

        for bId in sorted(list(self.buckets.keys())):
            if self.lastProcessedBucket <= bId < currentBucket:
                bucketData = self.buckets[bId]

                rate = self._computeRate(bucketData)

                dt = datetime.fromtimestamp(bId, tz=timezone.utc)

                anomaly = self.detector.add(rate, dt)
                if anomaly:
                    self.anomalies.append(anomaly)

                del self.buckets[bId]

        self.lastProcessedBucket = currentBucket

    def finalize(self) -> None:
        """Flushes all remaining buckets through anomaly detection."""
        if not self.buckets:
            return

        flushThrough = max(self.buckets.keys()) + self.windowSizeSec + 1
        self._checkAndRollBuckets(flushThrough)

    def getRecentRates(self):
        return self.detector.window.getValues()