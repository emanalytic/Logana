from typing import Dict, Union, List

from logana.models.logEvent import LogEvent
from logana.models.quarantineEntry import QuarantineEntry
from logana.models.fieldState import Known
from logana.analytics.errorSeverity import isErrorEvent
from logana.utils.timeUtils import coerceToUtc, nowUtc
from logana.analytics.rollingRateTracker import RollingRateTracker


class ErrorRateTracker(RollingRateTracker):
    """Tracks error rates over bucketed time windows and performs streaming anomaly detection."""

    def __init__(
        self,
        windowSizeSec: int = 5,
        historyCapacity: int = 60,
        zThreshold: float = 5.0,
    ):
        super().__init__(
            windowSizeSec=windowSizeSec,
            historyCapacity=historyCapacity,
            zThreshold=zThreshold,
        )

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

        # timestamp resolution
        if isinstance(item.timestamp, Known):
            evtTime = coerceToUtc(item.timestamp.value)
        else:
            evtTime = nowUtc()

        bucketId = int(evtTime.timestamp() / self.windowSizeSec) * self.windowSizeSec

        bucket = self._getOrCreateBucket(bucketId)

        bucket["total"] += 1
        if is_error:
            bucket["errors"] += 1

        # CRITICAL: advance rolling window
        self._checkAndRollBuckets(bucketId)

    def _newBucket(self) -> Dict[str, int]:
        return {"errors": 0, "total": 0}

    def _computeRate(self, bucketData: Dict[str, int]) -> float:
        total = bucketData["total"]
        errors = bucketData["errors"]
        return float(errors) / float(total) if total > 0 else 0.0

    @property
    def totalErrors(self) -> int:
        return self._totalErrors

    @property
    def overallErrorRate(self) -> float:
        if self._totalLogs == 0:
            return 0.0
        return self._totalErrors / self._totalLogs

    def getRecentRates(self) -> List[float]:
        return self.detector.window.getValues()