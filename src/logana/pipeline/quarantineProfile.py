from enum import Enum


class QuarantineProfile(str, Enum):
    """How strictly parsed lines are accepted vs quarantined."""

    STRICT = "strict"
    PRAGMATIC = "pragmatic"
    FORENSICS = "forensics"


def parseQuarantineProfile(value: str) -> QuarantineProfile:
    try:
        return QuarantineProfile(value.strip().lower())
    except ValueError as exc:
        allowed = ", ".join(p.value for p in QuarantineProfile)
        raise ValueError(f"Unknown profile {value!r}; use one of: {allowed}") from exc
