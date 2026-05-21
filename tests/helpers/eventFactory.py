"""Shared builders for unit and integration tests."""
from datetime import datetime, timezone
from logana.models.logEvent import LogEvent
from logana.models.quarantineEntry import QuarantineEntry
from logana.models.fieldState import Known, Unknown, Absent


def buildLogEvent(
    timestamp=None,
    ipAddress="127.0.0.1",
    httpMethod="GET",
    urlPath="/api/v1/test",
    statusCode=200,
    responseTimeMs=50.0,
    logLevel="INFO",
    message="Operation succeeded",
    parserId="json",
    lineNumber=1,
) -> LogEvent:
    ts = timestamp if timestamp else datetime.now(timezone.utc)
    return LogEvent(
        timestamp=Known(ts, 0.95, str(ts)),
        ipAddress=Known(ipAddress, 0.95, ipAddress) if ipAddress else Absent(),
        httpMethod=Known(httpMethod, 0.99, httpMethod) if httpMethod else Absent(),
        urlPath=Known(urlPath, 0.9, urlPath) if urlPath else Absent(),
        statusCode=Known(statusCode, 0.9, str(statusCode)) if statusCode is not None else Absent(),
        responseTimeMs=(
            Known(responseTimeMs, 0.95, f"{responseTimeMs}ms")
            if responseTimeMs is not None
            else Unknown("bare number")
        ),
        logLevel=Known(logLevel, 0.98, logLevel),
        message=Known(message, 0.95, message),
        rawLine="raw-line-content",
        lineNumber=lineNumber,
        parserId=parserId,
    )


def buildQuarantineEntry(
    lineNumber=1,
    reason="Malformed JSON",
    timestamp=None,
) -> QuarantineEntry:
    ts = timestamp if timestamp else datetime.now(timezone.utc)
    return QuarantineEntry(
        lineNumber=lineNumber,
        rawContent="bad-content",
        bestEffortFields={},
        reason=reason,
        timestamp=ts,
    )
