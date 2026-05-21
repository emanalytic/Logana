from logana.analytics.errorSeverity import isErrorEvent
from logana.models.logEvent import LogEvent
from logana.models.fieldState import Known, Absent
from datetime import datetime, timezone

def _event(**kwargs):
    defaults = dict(
        timestamp=Known(datetime.now(timezone.utc), 0.9, ""),
        ipAddress=Absent(),
        httpMethod=Absent(),
        urlPath=Absent(),
        statusCode=Absent(),
        responseTimeMs=Absent(),
        logLevel=Known("INFO", 0.9, "INFO"),
        message=Absent(),
        rawLine="",
        lineNumber=1,
        parserId="test",
    )
    defaults.update(kwargs)
    return LogEvent(**defaults)

def test_error_level():
    assert isErrorEvent(_event(logLevel=Known("ERROR", 0.9, "ERROR")))

def test_http_5xx_is_error():
    assert isErrorEvent(_event(statusCode=Known(503, 0.9, "503"), logLevel=Known("INFO", 0.9, "INFO")))

def test_info_200_not_error():
    assert not isErrorEvent(_event(statusCode=Known(200, 0.9, "200")))
