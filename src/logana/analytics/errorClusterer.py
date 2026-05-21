import re
from datetime import datetime
from typing import Union, List, Set, Tuple, Optional
from logana.models.logEvent import LogEvent
from logana.models.quarantineEntry import QuarantineEntry
from logana.models.fieldState import Known, Unknown
from logana.utils.similarity import tokenize, jaccardSimilarity
from logana.utils.timeUtils import coerceToUtc, nowUtc
from logana.analytics.errorSeverity import isErrorEvent
from logana.analytics.activityKey import resolveActivityKey

# Pattern to strip common timestamp and log-level prefixes from raw lines
_TIMESTAMP_PREFIX = re.compile(
    r'^'
    r'(?:\d{4}[-/]\d{2}[-/]\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?\s*)?'  # ISO / common datetime
    r'(?:\[(?:ERROR|WARN|WARNING|INFO|DEBUG|FATAL|CRITICAL|ERR|TRACE)\]\s*)?'                      # [LEVEL]
    r'(?:(?:ERROR|WARN|WARNING|INFO|DEBUG|FATAL|CRITICAL|ERR|TRACE)\s*[-:]\s*)?',                   # LEVEL: or LEVEL -
    re.IGNORECASE
)

def _stripTimestampPrefix(rawLine: str) -> str:
    """Strips leading timestamp and log-level markers from a raw log line for cleaner clustering."""
    cleaned = _TIMESTAMP_PREFIX.sub('', rawLine).strip()
    return cleaned if cleaned else rawLine

class ErrorCluster:
    """Represents a grouped cluster of similar error log messages."""
    
    def __init__(self, representative: str, tokens: Set[str], timestamp: Optional[datetime], endpoint: Optional[str]):
        self.representative = representative
        self.tokens = tokens
        self.count = 1
        self.lastSeen = coerceToUtc(timestamp) if timestamp else nowUtc()
        self.endpoints: Set[str] = {endpoint} if endpoint else set()

    def absorb(self, errorMessage: str, tokens: Set[str], timestamp: Optional[datetime], endpoint: Optional[str]) -> None:
        """Absorbs a new error event into this cluster, updating counts and tracking statistics."""
        self.count += 1
        timestampUtc = coerceToUtc(timestamp) if timestamp else None
        if timestampUtc and timestampUtc > self.lastSeen:
            self.lastSeen = timestampUtc
            # Update representative sample to the latest error message to reflect current context
            self.representative = errorMessage
            self.tokens = tokens
        if endpoint:
            self.endpoints.add(endpoint)


class StreamingErrorClusterer:
    """Streams and clusters error messages online with a bounded memory footprint."""
    
    def __init__(self, maxClusters: int = 50, similarityThreshold: float = 0.5):
        self.clusters: List[ErrorCluster] = []
        self.maxClusters = maxClusters
        self.threshold = similarityThreshold

    def ingest(self, item: Union[LogEvent, QuarantineEntry]) -> None:
        """Processes an incoming log event. If it is an error, clusters its message."""
        if not isinstance(item, LogEvent):
            return
            
        if not isErrorEvent(item):
            return
            
        # Extract the error message
        errorMessage = ""
        if isinstance(item.message, Known):
            errorMessage = item.message.value
        elif isinstance(item.message, Unknown) and item.message.bestGuess:
            errorMessage = item.message.bestGuess
        else:
            errorMessage = _stripTimestampPrefix(item.rawLine)
            
        # Resolve timestamp and endpoint
        timestamp = item.timestamp.value if isinstance(item.timestamp, Known) else None
        endpoint = resolveActivityKey(item)
        
        self.addError(errorMessage, timestamp, endpoint)

    def addError(self, errorMessage: str, timestamp: Optional[datetime], endpoint: Optional[str]) -> None:
        """Tokenizes and assigns an error message to a cluster, merging if at capacity."""
        tokens = tokenize(errorMessage)
        if not tokens:
            return
            
        bestMatch, bestSim = self._findNearest(tokens)
        
        if bestSim >= self.threshold and bestMatch is not None:
            bestMatch.absorb(errorMessage, tokens, timestamp, endpoint)
        else:
            newCluster = ErrorCluster(errorMessage, tokens, timestamp, endpoint)
            self.clusters.append(newCluster)
            
            if len(self.clusters) > self.maxClusters:
                self._mergeSmallestPair()

    def _findNearest(self, tokens: Set[str]) -> Tuple[Optional[ErrorCluster], float]:
        """Finds the existing cluster with the highest Jaccard similarity score."""
        bestMatch = None
        bestSim = 0.0
        
        for cluster in self.clusters:
            sim = jaccardSimilarity(tokens, cluster.tokens)
            if sim > bestSim:
                bestSim = sim
                bestMatch = cluster
                
        return bestMatch, bestSim

    def _mergeSmallestPair(self) -> None:
        """Merges the two clusters in the set that are most similar to each other to bound size."""
        if len(self.clusters) < 2:
            return
            
        bestI, bestJ = 0, 1
        maxSim = -1.0
        
        # Find the pair of clusters with maximum Jaccard similarity
        for i in range(len(self.clusters)):
            for j in range(i + 1, len(self.clusters)):
                sim = jaccardSimilarity(self.clusters[i].tokens, self.clusters[j].tokens)
                if sim > maxSim:
                    maxSim = sim
                    bestI, bestJ = i, j
                    
        clusterA = self.clusters[bestI]
        clusterB = self.clusters[bestJ]
        
        # Merge clusterB into clusterA
        clusterA.count += clusterB.count
        clusterA.lastSeen = max(clusterA.lastSeen, clusterB.lastSeen)
        clusterA.endpoints.update(clusterB.endpoints)
        
        # Retain the representative from the one with more events
        if clusterB.count > clusterA.count:
            clusterA.representative = clusterB.representative
            clusterA.tokens = clusterB.tokens
            
        # Delete clusterB
        self.clusters.pop(bestJ)

    def getTopClusters(self, limit: int = 5) -> List[ErrorCluster]:
        """Returns the top N error clusters sorted by volume (event count)."""
        sortedClusters = sorted(self.clusters, key=lambda c: c.count, reverse=True)
        return sortedClusters[:limit]
