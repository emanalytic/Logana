from datetime import datetime, timezone

from logana.analytics.fileProfile import FileProfileTracker
from logana.models.fieldState import Known
from logana.models.logEvent import LogEvent


def _event_with_source(source: str) -> LogEvent:
    return LogEvent(
        timestamp=Known(datetime.now(timezone.utc), 0.95, "ts", meta={"timestampSource": source}),
        ipAddress=Known("127.0.0.1", 0.95, "127.0.0.1"),
        httpMethod=Known("GET", 0.95, "GET"),
        urlPath=Known("/", 0.95, "/"),
        statusCode=Known(200, 0.95, "200"),
        responseTimeMs=Known(10.0, 0.95, "10ms"),
        logLevel=Known("INFO", 0.95, "INFO"),
        message=Known("ok", 0.95, "ok"),
        rawLine="raw",
        lineNumber=1,
        parserId="json",
    )


def test_fileProfile_recommendsUtcForUtcishSources():
    tracker = FileProfileTracker()
    tracker.ingest(_event_with_source("explicit_offset"))
    tracker.ingest(_event_with_source("configured_utc"))

    profile = tracker.toDict()

    assert profile["recommendedNaivePolicy"] == "utc"


def test_fileProfile_recommendsLocalWhenLocalishSourcesDominate():
    tracker = FileProfileTracker()
    tracker.ingest(_event_with_source("configured_local"))
    tracker.ingest(_event_with_source("syslog_inferred"))
    tracker.ingest(_event_with_source("explicit_offset"))

    profile = tracker.toDict()

    assert profile["recommendedNaivePolicy"] == "local"