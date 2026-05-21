from datetime import datetime, timezone, tzinfo
from typing import Optional, Tuple
from zoneinfo import ZoneInfo

from logana.pipeline.timeContext import PipelineTimeContext, defaultTimeContext

# Provenance labels exported in JSON and field meta.
TIMESTAMP_SOURCE_EXPLICIT = "explicit_offset"
TIMESTAMP_SOURCE_LOCAL = "configured_local"
TIMESTAMP_SOURCE_UTC = "configured_utc"
TIMESTAMP_SOURCE_SYSLOG = "syslog_inferred"
TIMESTAMP_SOURCE_EPOCH = "epoch_utc"

_CONFIDENCE_BY_SOURCE = {
    TIMESTAMP_SOURCE_EXPLICIT: 1.0,
    TIMESTAMP_SOURCE_LOCAL: 0.85,
    TIMESTAMP_SOURCE_UTC: 0.8,
    TIMESTAMP_SOURCE_SYSLOG: 0.75,
    TIMESTAMP_SOURCE_EPOCH: 1.0,
}


def nowUtc() -> datetime:
    """Returns a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


class TimestampNormalizer:
    """Converts parsed datetimes to aware UTC with provenance-based confidence."""

    def __init__(self, context: PipelineTimeContext) -> None:
        self.context = context

    def normalize(
        self,
        dt: datetime,
        provenance: str,
        base_confidence: float,
    ) -> Tuple[datetime, float, str]:
        if dt.tzinfo is not None:
            utc_dt = dt.astimezone(timezone.utc)
            source = TIMESTAMP_SOURCE_EXPLICIT
            scale = _CONFIDENCE_BY_SOURCE[source]
            return utc_dt, base_confidence * scale, source
        if provenance == TIMESTAMP_SOURCE_EPOCH:
            utc_dt = dt.replace(tzinfo=timezone.utc)
            source = TIMESTAMP_SOURCE_EPOCH
        elif provenance == TIMESTAMP_SOURCE_SYSLOG:
            local = dt.replace(tzinfo=self.context.default_tz)
            utc_dt = local.astimezone(timezone.utc)
            source = TIMESTAMP_SOURCE_SYSLOG
        elif self.context.naive_policy == "utc":
            utc_dt = dt.replace(tzinfo=timezone.utc)
            source = TIMESTAMP_SOURCE_UTC
        else:
            local = dt.replace(tzinfo=self.context.default_tz)
            utc_dt = local.astimezone(timezone.utc)
            source = TIMESTAMP_SOURCE_LOCAL

        scale = _CONFIDENCE_BY_SOURCE.get(source, 1.0)
        return utc_dt, min(base_confidence, base_confidence * scale), source


def coerceToUtc(
    value: datetime,
    context: Optional[PipelineTimeContext] = None,
) -> datetime:
    """Normalizes a datetime to UTC using pipeline context for naive values."""
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc)

    ctx = context or defaultTimeContext()
    normalizer = TimestampNormalizer(ctx)
    utc_dt, _, _ = normalizer.normalize(value, TIMESTAMP_SOURCE_LOCAL, 1.0)
    return utc_dt


def resolveLocalTimezone() -> tzinfo:
    """Returns the host timezone, falling back to UTC when unavailable."""
    try:
        return ZoneInfo("localtime")
    except Exception:
        pass
    local = datetime.now().astimezone().tzinfo
    if local is not None:
        return local
    return timezone.utc


def parseTimezone(name: str) -> tzinfo:
    """Resolves an IANA timezone name, mapping 'local' to the host zone."""
    if name.lower() in ("local", "localtime", "system"):
        return resolveLocalTimezone()
    if name.upper() == "UTC":
        return timezone.utc
    try:
        return ZoneInfo(name)
    except Exception:
        return timezone.utc
