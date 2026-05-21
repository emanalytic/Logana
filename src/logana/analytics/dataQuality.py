from typing import Union, Dict, List
from logana.models.logEvent import LogEvent
from logana.models.quarantineEntry import QuarantineEntry
from logana.models.fieldState import Known, Unknown, Absent

class DataQualityTracker:
    """Tracks field-level data quality (Known, Unknown, and Absent counts) across all processed logs."""
    
    FIELDS = [
        "timestamp",
        "ipAddress",
        "httpMethod",
        "urlPath",
        "statusCode",
        "responseTimeMs",
        "logLevel",
        "message"
    ]

    def __init__(self):
        # Maps fieldName -> {'known': int, 'unknown': int, 'absent': int, 'totalWeight': float}
        self.stats: Dict[str, Dict[str, Union[int, float]]] = {}
        for f in self.FIELDS:
            self.stats[f] = {"known": 0, "unknown": 0, "absent": 0, "totalConfidence": 0.0}

    def ingest(self, item: Union[LogEvent, QuarantineEntry]) -> None:
        """Ingests a log event or quarantine entry, updating quality statistics for each field."""
        if isinstance(item, LogEvent):
            for field in self.FIELDS:
                state = getattr(item, field, None)
                self._recordState(field, state)
        elif isinstance(item, QuarantineEntry):
            for field in self.FIELDS:
                state = item.bestEffortFields.get(field, Absent())
                self._recordState(field, state)

    def _recordState(self, fieldName: str, state) -> None:
        if fieldName not in self.stats:
            self.stats[fieldName] = {"known": 0, "unknown": 0, "absent": 0, "totalConfidence": 0.0}
            
        if isinstance(state, Known):
            self.stats[fieldName]["known"] += 1
            self.stats[fieldName]["totalConfidence"] += state.confidence
        elif isinstance(state, Unknown):
            self.stats[fieldName]["unknown"] += 1
        elif isinstance(state, Absent) or state is None:
            self.stats[fieldName]["absent"] += 1

    def getFieldQuality(self, fieldName: str) -> Dict[str, int]:
        """Returns the absolute counts of known, unknown, and absent values for a field."""
        stats = self.stats.get(fieldName, {"known": 0, "unknown": 0, "absent": 0})
        return {
            "known": int(stats["known"]),
            "unknown": int(stats["unknown"]),
            "absent": int(stats["absent"])
        }

    def getFieldQualityRates(self, fieldName: str) -> Dict[str, float]:
        """Returns the ratios of known, unknown, and absent values for a field."""
        stats = self.stats.get(fieldName, {"known": 0, "unknown": 0, "absent": 0})
        total = stats["known"] + stats["unknown"] + stats["absent"]
        if total == 0:
            return {"known": 0.0, "unknown": 0.0, "absent": 0.0}
        return {
            "known": stats["known"] / total,
            "unknown": stats["unknown"] / total,
            "absent": stats["absent"] / total
        }

    def getAverageConfidence(self, fieldName: str) -> float:
        """Returns the average confidence for all Known occurrences of a field."""
        stats = self.stats.get(fieldName, {"known": 0, "totalConfidence": 0.0})
        knownCount = stats["known"]
        if knownCount == 0:
            return 0.0
        return stats["totalConfidence"] / knownCount

    def getOverallQualityScore(self) -> float:
        """Returns the overall proportion of successfully parsed (Known) fields across all logs."""
        totalKnown = 0
        totalCount = 0
        for f in self.FIELDS:
            stats = self.stats[f]
            totalKnown += stats["known"]
            totalCount += stats["known"] + stats["unknown"] + stats["absent"]
            
        if totalCount == 0:
            return 1.0
        return totalKnown / totalCount
