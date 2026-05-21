import re
from logana.models.logEvent import LogEvent
from logana.models.fieldState import Known

_FINGERPRINT_RE = re.compile(r"[^a-zA-Z0-9]+")
_MONTH_TOKENS = {
    "jan", "feb", "mar", "apr", "may", "jun",
    "jul", "aug", "sep", "oct", "nov", "dec",
    "sun", "mon", "tue", "wed", "thu", "fri", "sat",
}


def _token_ok(token: str) -> bool:
    if len(token) <= 2 or token.isdigit():
        return False
    if token in _MONTH_TOKENS:
        return False
    if re.fullmatch(r"\d{4}", token):
        return False
    return True


def _message_fingerprint(message: str) -> str | None:
    tokens = _FINGERPRINT_RE.split(message.lower())[:12]
    tokens = [t for t in tokens if _token_ok(t)]
    if not tokens:
        return None
    return "msg:" + "-".join(tokens[:5])


def _syslog_program(message: str) -> str | None:
    head = message.split(":", 1)[0].strip()
    if not head or len(head) > 80:
        return None
    program = head.split("[", 1)[0].split("(", 1)[0].strip()
    if program and re.match(r"^[a-zA-Z][\w.-]+$", program):
        return f"svc:{program}"
    return None


def resolveActivityKey(event: LogEvent) -> str:
    """HTTP path when available; otherwise syslog program or a short message fingerprint."""
    if isinstance(event.urlPath, Known):
        path = str(event.urlPath.value).strip()
        if path and path != "/":
            return path

    if isinstance(event.message, Known):
        msg = str(event.message.value).strip()
        if msg:
            program = _syslog_program(msg)
            if program:
                return program
            fingerprint = _message_fingerprint(msg)
            if fingerprint:
                return fingerprint

    return f"parser:{event.parserId}"
