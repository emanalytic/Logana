from logana.models.logEvent import LogEvent
from logana.models.fieldState import Known

_ERROR_LEVELS = frozenset({
    "ERROR", "FATAL", "CRITICAL", "ERR", "EMERGENCY", "ALERT",
})


def isErrorEvent(event: LogEvent) -> bool:
    """True when log level indicates failure or HTTP status is 5xx."""
    if isinstance(event.logLevel, Known):
        if str(event.logLevel.value).upper() in _ERROR_LEVELS:
            return True

    if isinstance(event.statusCode, Known):
        code = event.statusCode.value
        if isinstance(code, int) and code >= 500:
            return True

    return False
