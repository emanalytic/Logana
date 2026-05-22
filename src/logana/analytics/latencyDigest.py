from typing import Union
from logana.models.logEvent import LogEvent
from logana.models.quarantineEntry import QuarantineEntry
from logana.models.fieldState import Known, Unknown
from logana.utils.tdigest import TDigest

MAX_HTTP_LATENCY_MS = 120_000.0


def _is_http_shaped(event: LogEvent) -> bool:
    """Latency metrics are meaningful when the event looks request- or API-shaped."""
    if isinstance(event.urlPath, Known):
        return True
    if isinstance(event.httpMethod, Known) and isinstance(event.statusCode, Known):
        return True
    if isinstance(event.statusCode, Known):
        return True
    if isinstance(event.responseTimeMs, Known):
        return True
    return event.parserId in ("clf", "json", "kv") and isinstance(event.statusCode, Known)


class LatencyDigest:
    """Uncertainty-aware latency digest using a streaming T-Digest for percentile estimation."""

    def __init__(self, confidenceThreshold: float = 0.5, compression: float = 100.0):
        self.confidenceThreshold = confidenceThreshold
        self.digest = TDigest(compression=compression)
        self._lowConfidenceCount = 0
        self._unknownCount = 0
        self._totalIngested = 0

    def ingest(self, item: Union[LogEvent, QuarantineEntry]) -> None:
        if not isinstance(item, LogEvent):
            return

        self._totalIngested += 1
        if not _is_http_shaped(item):
            return

        state = item.responseTimeMs

        if isinstance(state, Known):
            if state.confidence >= self.confidenceThreshold and state.value <= MAX_HTTP_LATENCY_MS:
                self.digest.add(state.value)
            else:
                self._lowConfidenceCount += 1
        elif isinstance(state, Unknown):
            self._unknownCount += 1

    @property
    def p50(self) -> float:
        return self.digest.quantile(0.5)

    @property
    def p95(self) -> float:
        return self.digest.quantile(0.95)

    @property
    def p99(self) -> float:
        return self.digest.quantile(0.99)

    @property
    def min(self) -> float:
        val = self.digest.minVal
        return val if val != float("inf") else 0.0

    @property
    def max(self) -> float:
        val = self.digest.maxVal
        return val if val != float("-inf") else 0.0

    @property
    def count(self) -> int:
        return int(self.digest.totalWeight)

    @property
    def lowConfidenceCount(self) -> int:
        return self._lowConfidenceCount

    @property
    def unknownCount(self) -> int:
        return self._unknownCount
