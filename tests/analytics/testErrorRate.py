from datetime import datetime, timedelta
from logana.analytics.errorRate import ErrorRateTracker
from helpers.eventFactory import buildLogEvent


def test_errorRateTotals():
    tracker = ErrorRateTracker()
    for _ in range(5):
        tracker.ingest(buildLogEvent(logLevel="INFO"))
    tracker.ingest(buildLogEvent(logLevel="ERROR"))
    tracker.ingest(buildLogEvent(logLevel="FATAL"))
    assert tracker.totalErrors == 2
    assert tracker.overallErrorRate == 2 / 7


def test_errorRateDetectsSpike():
    tracker = ErrorRateTracker(windowSizeSec=1, historyCapacity=30, zThreshold=3.0)
    baseTime = datetime(2024, 3, 15, 12, 0, 0)
    for offset in range(25):
        evtTime = baseTime + timedelta(seconds=offset)
        errCount = 80 if offset == 20 else 2
        for i in range(100):
            level = "ERROR" if i < errCount else "INFO"
            tracker.ingest(buildLogEvent(timestamp=evtTime, logLevel=level))
    assert len(tracker.anomalies) > 0
    assert tracker.anomalies[0].direction == "spike"
