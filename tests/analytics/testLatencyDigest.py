from datetime import datetime, timezone
from logana.analytics.latencyDigest import LatencyDigest
from logana.models.logEvent import LogEvent
from logana.models.fieldState import Known, Unknown, Absent
from helpers.eventFactory import buildLogEvent


def test_latencyPercentiles():
    digest = LatencyDigest(confidenceThreshold=0.5)
    for x in range(1, 101):
        digest.ingest(buildLogEvent(responseTimeMs=float(x)))
    assert abs(digest.p50 - 50.0) <= 2.0
    assert digest.count == 100


def test_latencyIgnoresNonHttpEvents():
    digest = LatencyDigest()
    digest.ingest(buildLogEvent(responseTimeMs=None, urlPath=None, httpMethod=None, statusCode=None, parserId="syslog"))
    assert digest.count == 0
    assert digest.unknownCount == 0


def test_latencyTracksLowConfidenceSeparately():
    digest = LatencyDigest(confidenceThreshold=0.5)
    lowConf = LogEvent(
        timestamp=Known(datetime.now(timezone.utc), 0.9, ""),
        ipAddress=Absent(),
        httpMethod=Known("GET", 0.9, "GET"),
        urlPath=Known("/api/slow", 0.9, "/api/slow"),
        statusCode=Known(200, 0.9, "200"),
        responseTimeMs=Known(250.0, 0.2, "250ms"),
        logLevel=Absent(),
        message=Absent(),
        rawLine="",
        lineNumber=1,
        parserId="json",
    )
    digest.ingest(lowConf)
    assert digest.count == 0
    assert digest.lowConfidenceCount == 1
