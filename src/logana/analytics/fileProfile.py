from typing import Dict, Union
from logana.models.logEvent import LogEvent
from logana.models.quarantineEntry import QuarantineEntry
from logana.models.fieldState import Known

class FileProfileTracker:
    """Builds a coarse profile of formats and timestamp assumptions in the file."""

    def __init__(self) -> None:
        self.formatCounts: Dict[str, int] = {}
        self.timestampSources: Dict[str, int] = {}
        self.totalEvents = 0
        self.totalQuarantined = 0

    def ingest(self, item: Union[LogEvent, QuarantineEntry]) -> None:
        if isinstance(item, QuarantineEntry):
            self.totalQuarantined += 1
            return

        self.totalEvents += 1
        parser = item.parserId.split("+")[0]
        self.formatCounts[parser] = self.formatCounts.get(parser, 0) + 1

        ts = item.timestamp
        if isinstance(ts, Known) and ts.meta:
            source = ts.meta.get("timestampSource", "unknown")
            self.timestampSources[source] = self.timestampSources.get(source, 0) + 1

    def toDict(self) -> dict:
        total = self.totalEvents + self.totalQuarantined
        parseRate = self.totalEvents / total if total else 0.0
        explicit = self.timestampSources.get("explicit_offset", 0)
        tsTotal = sum(self.timestampSources.values()) or 1
        return {
            "parseRate": parseRate,
            "formatDistribution": dict(
                sorted(self.formatCounts.items(), key=lambda x: x[1], reverse=True)
            ),
            "timestampSources": self.timestampSources,
            "explicitOffsetRate": explicit / tsTotal,
            "recommendedNaivePolicy": "local",
        }
