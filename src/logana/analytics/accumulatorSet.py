from typing import Union
from logana.models.logEvent import LogEvent
from logana.models.quarantineEntry import QuarantineEntry
from logana.analytics.eventCounter import EventCounter
from logana.analytics.errorRate import ErrorRateTracker
from logana.analytics.latencyDigest import LatencyDigest
from logana.analytics.endpointTable import EndpointTable
from logana.analytics.errorClusterer import StreamingErrorClusterer
from logana.analytics.formatTracker import FormatTracker
from logana.analytics.quarantineTracker import QuarantineTracker
from logana.analytics.dataQuality import DataQualityTracker
from logana.analytics.logTimeSpan import LogTimeSpanTracker
from logana.analytics.fileProfile import FileProfileTracker
from logana.analytics.keywordCounter import KeywordCounter

class AccumulatorSet:
    """Manages and orchestrates streaming accumulators for one analysis run."""
    
    def __init__(self, max_endpoints: int = 200):
        self.eventCounter = EventCounter()
        self.errorRate = ErrorRateTracker()
        self.latencyDigest = LatencyDigest()
        self.endpointTable = EndpointTable(max_endpoints=max_endpoints)
        self.errorClusterer = StreamingErrorClusterer()
        self.formatTracker = FormatTracker()
        self.quarantineTracker = QuarantineTracker()
        self.dataQuality = DataQualityTracker()
        self.logTimeSpan = LogTimeSpanTracker()
        self.fileProfile = FileProfileTracker()
        self.keywordCounter = KeywordCounter()

    def ingest(self, item: Union[LogEvent, QuarantineEntry]) -> None:
        self.eventCounter.ingest(item)
        self.errorRate.ingest(item)
        self.latencyDigest.ingest(item)
        self.endpointTable.ingest(item)
        self.errorClusterer.ingest(item)
        self.formatTracker.ingest(item)
        self.quarantineTracker.ingest(item)
        self.dataQuality.ingest(item)
        self.logTimeSpan.ingest(item)
        self.fileProfile.ingest(item)
        self.keywordCounter.ingest(item)
