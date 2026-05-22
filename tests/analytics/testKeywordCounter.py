from datetime import datetime, timezone

from logana.analytics.keywordCounter import KeywordCounter
from logana.models.fieldState import Known
from logana.models.logEvent import LogEvent


def _event(message: str) -> LogEvent:
    return LogEvent(
        timestamp=Known(datetime.now(timezone.utc), 0.95, "ts"),
        ipAddress=Known("127.0.0.1", 0.95, "127.0.0.1"),
        httpMethod=Known("GET", 0.95, "GET"),
        urlPath=Known("/", 0.95, "/"),
        statusCode=Known(200, 0.95, "200"),
        responseTimeMs=Known(10.0, 0.95, "10ms"),
        logLevel=Known("INFO", 0.95, "INFO"),
        message=Known(message, 0.95, message),
        rawLine="raw",
        lineNumber=1,
        parserId="json",
    )


def test_keywordCounter_keepsMostFrequentTokensWhenCapped():
    counter = KeywordCounter(maxTokens=2)

    counter.ingest(_event("alpha alpha beta"))
    counter.ingest(_event("alpha beta beta"))
    counter.ingest(_event("gamma"))

    top = counter.getTop(limit=10)
    tokens = {entry["token"] for entry in top}

    assert "alpha" in tokens
    assert "beta" in tokens
    assert "gamma" not in tokens