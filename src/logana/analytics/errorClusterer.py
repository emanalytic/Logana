import re
from datetime import datetime
from typing import Dict, List, Optional, Union
from drain3 import TemplateMiner
from drain3.template_miner_config import TemplateMinerConfig
from logana.models.logEvent import LogEvent
from logana.models.quarantineEntry import QuarantineEntry
from logana.models.fieldState import Known, Unknown
from logana.utils.timeUtils import coerceToUtc, nowUtc
from logana.analytics.errorSeverity import isErrorEvent
from logana.analytics.activityKey import resolveActivityKey

_TIMESTAMP_PREFIX = re.compile(
    r'^'
    r'(?:\d{4}[-/]\d{2}[-/]\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?\s*)?'
    r'(?:\[(?:ERROR|WARN|WARNING|INFO|DEBUG|FATAL|CRITICAL|ERR|TRACE)\]\s*)?'
    r'(?:(?:ERROR|WARN|WARNING|INFO|DEBUG|FATAL|CRITICAL|ERR|TRACE)\s*[-:]\s*)?',
    re.IGNORECASE
)


def _stripTimestampPrefix(rawLine: str) -> str:
    """Strips leading timestamp and log-level markers from a raw log line for cleaner clustering."""
    cleaned = _TIMESTAMP_PREFIX.sub('', rawLine).strip()
    return cleaned if cleaned else rawLine


class ErrorCluster:
    """Represents a grouped cluster of similar error log messages (Drain3 template)."""

    def __init__(
        self,
        representative: str,
        drainClusterId: int,
        timestamp: Optional[datetime],
        endpoint: Optional[str],
    ):
        self.representative = representative
        self.drainClusterId = drainClusterId
        self.count = 1
        self.lastSeen = coerceToUtc(timestamp) if timestamp else nowUtc()
        self.endpoints: set[str] = {endpoint} if endpoint else set()

    def absorb(
        self,
        template: str,
        timestamp: Optional[datetime],
        endpoint: Optional[str],
    ) -> None:
        """Absorbs a new error event into this cluster."""
        self.count += 1
        timestampUtc = coerceToUtc(timestamp) if timestamp else None
        if timestampUtc and timestampUtc > self.lastSeen:
            self.lastSeen = timestampUtc
            self.representative = template
        if endpoint:
            self.endpoints.add(endpoint)


class StreamingErrorClusterer:
    """Streams and clusters error messages with Drain3 (bounded template count)."""

    def __init__(self, maxClusters: int = 50, similarityThreshold: float = 0.5):
        self.maxClusters = maxClusters
        self.threshold = similarityThreshold
        config = TemplateMinerConfig()
        config.profiling_enabled = False
        config.max_clusters = maxClusters
        config.drain_sim_th = similarityThreshold
        self._miner = TemplateMiner(config=config)
        self._clustersById: Dict[int, ErrorCluster] = {}

    @property
    def clusters(self) -> List[ErrorCluster]:
        return list(self._clustersById.values())

    def ingest(self, item: Union[LogEvent, QuarantineEntry]) -> None:
        if not isinstance(item, LogEvent):
            return

        if not isErrorEvent(item):
            return

        errorMessage = ""
        if isinstance(item.message, Known):
            errorMessage = item.message.value
        elif isinstance(item.message, Unknown) and item.message.bestGuess:
            errorMessage = item.message.bestGuess
        else:
            errorMessage = _stripTimestampPrefix(item.rawLine)

        timestamp = item.timestamp.value if isinstance(item.timestamp, Known) else None
        endpoint = resolveActivityKey(item)
        self.addError(errorMessage, timestamp, endpoint)

    def addError(
        self,
        errorMessage: str,
        timestamp: Optional[datetime],
        endpoint: Optional[str],
    ) -> None:
        text = errorMessage.strip()
        if not text:
            return

        result = self._miner.add_log_message(text)
        clusterId = int(result["cluster_id"])
        template = result.get("template_mined") or text

        existing = self._clustersById.get(clusterId)
        if existing is not None:
            existing.absorb(template, timestamp, endpoint)
            return

        self._clustersById[clusterId] = ErrorCluster(template, clusterId, timestamp, endpoint)

    def getTopClusters(self, limit: int = 5) -> List[ErrorCluster]:
        sortedClusters = sorted(self.clusters, key=lambda c: c.count, reverse=True)
        return sortedClusters[:limit]
