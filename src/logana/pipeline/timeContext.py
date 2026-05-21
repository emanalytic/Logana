from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone, tzinfo
from typing import Literal, Optional
from zoneinfo import ZoneInfo

NaivePolicy = Literal["local", "utc"]


@dataclass
class PipelineTimeContext:
    """Timezone and year-inference settings for the ingestion pipeline."""

    default_tz: tzinfo
    naive_policy: NaivePolicy = "local"
    reference_year: Optional[int] = field(default=None)

    def resolve_syslog_year(self, month: int, day: int) -> int:
        """Pick a year for BSD syslog timestamps missing a year component."""
        if self.reference_year is not None:
            return self.reference_year

        now = datetime.now(self.default_tz)
        year = now.year
        try:
            candidate = datetime(year, month, day, tzinfo=self.default_tz)
            if candidate > now + timedelta(days=30):
                year -= 1
        except ValueError:
            pass
        return year

    def note_anchor(self, dt: datetime) -> None:
        """Learn reference year from a fully specified timestamp in the stream."""
        if self.reference_year is not None:
            return
        if 2000 <= dt.year <= 2050:
            self.reference_year = dt.year


def defaultTimeContext() -> PipelineTimeContext:
    """Uses the host local timezone for naive timestamps."""
    from logana.utils.timeUtils import resolveLocalTimezone
    return PipelineTimeContext(default_tz=resolveLocalTimezone())


def utcTimeContext() -> PipelineTimeContext:
    """Treats naive timestamps as UTC (container-friendly default)."""
    return PipelineTimeContext(default_tz=timezone.utc, naive_policy="utc")
