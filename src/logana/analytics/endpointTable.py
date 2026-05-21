from typing import Union, Dict, List
from logana.models.logEvent import LogEvent
from logana.models.quarantineEntry import QuarantineEntry
from logana.models.fieldState import Known
from logana.analytics.errorSeverity import isErrorEvent
from logana.analytics.activityKey import resolveActivityKey
from logana.utils.tdigest import TDigest
from logana.utils.ringBuffer import RingBuffer

class EndpointStats:
    """Accumulates real-time analytics for a single activity key (URL, fingerprint, etc.)."""
    
    def __init__(self, endpoint: str):
        self.endpoint = endpoint
        self.count = 0
        self.errors = 0
        self.latencyDigest = TDigest(compression=50.0)
        self.recentLatencies = RingBuffer(20)

    def ingest(self, event: LogEvent) -> None:
        self.count += 1
        if isErrorEvent(event):
            self.errors += 1
        if isinstance(event.responseTimeMs, Known):
            val = event.responseTimeMs.value
            self.latencyDigest.add(val)
            self.recentLatencies.push(val)

    @property
    def errorRate(self) -> float:
        if self.count == 0:
            return 0.0
        return self.errors / self.count

    @property
    def p99Latency(self) -> float:
        return self.latencyDigest.quantile(0.99)

    @property
    def p95Latency(self) -> float:
        return self.latencyDigest.quantile(0.95)

    @property
    def p50Latency(self) -> float:
        return self.latencyDigest.quantile(0.5)

    @property
    def trend(self) -> str:
        values = self.recentLatencies.getValues()
        if len(values) < 10:
            return "STABLE"
        mid = len(values) // 2
        older_half = values[:mid]
        newer_half = values[mid:]
        older_median = sorted(older_half)[len(older_half) // 2]
        newer_median = sorted(newer_half)[len(newer_half) // 2]
        if older_median == 0.0:
            return "STABLE"
        ratio = newer_median / older_median
        if ratio > 1.15:
            return "DEGRADING"
        if ratio < 0.85:
            return "IMPROVING"
        return "STABLE"


class EndpointTable:
    """Tracks activity volume, errors, and latency with bounded cardinality."""
    
    def __init__(self, max_endpoints: int = 200):
        self.max_endpoints = max_endpoints
        self.endpoints: Dict[str, EndpointStats] = {}
        self._other: EndpointStats = EndpointStats("(other)")

    def ingest(self, item: Union[LogEvent, QuarantineEntry]) -> None:
        if not isinstance(item, LogEvent):
            return

        key = resolveActivityKey(item)
        if key not in self.endpoints:
            if len(self.endpoints) >= self.max_endpoints:
                self._other.ingest(item)
                return
            self.endpoints[key] = EndpointStats(key)

        self.endpoints[key].ingest(item)

    def getSortedEndpoints(self, sortBy: str = "volume", limit: int = 10) -> List[EndpointStats]:
        stats_list = list(self.endpoints.values())
        if self._other.count > 0:
            stats_list.append(self._other)
        if sortBy == "volume":
            stats_list.sort(key=lambda s: s.count, reverse=True)
        elif sortBy == "errorRate":
            stats_list.sort(key=lambda s: s.errorRate, reverse=True)
        elif sortBy == "latency":
            stats_list.sort(key=lambda s: s.p99Latency, reverse=True)
        return stats_list[:limit]
