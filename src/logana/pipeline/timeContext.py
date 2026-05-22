from dataclasses import dataclass, field
from collections import Counter
from datetime import datetime, timedelta, timezone, tzinfo
from typing import Literal, Optional

NaivePolicy = Literal["local", "utc"]


@dataclass
class PipelineTimeContext:
    """Timezone and year-inference settings for the ingestion pipeline."""

    default_tz: tzinfo
    naive_policy: NaivePolicy = "local"
    reference_year: Optional[int] = field(default=None)
    _anchor_year_votes: Counter[int] = field(default_factory=Counter, init=False, repr=False)

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
        year = dt.year
        if year < 2000 or year > 2050:
            return

        self._anchor_year_votes[year] += 1

        if self.reference_year is None:
            self.reference_year = year
            return

        if self.reference_year not in self._anchor_year_votes:
            return

        top_year, top_votes = self._anchor_year_votes.most_common(1)[0]
        current_votes = self._anchor_year_votes[self.reference_year]
        if top_year != self.reference_year and top_votes > current_votes:
            self.reference_year = top_year


def defaultTimeContext() -> PipelineTimeContext:
    """Uses the host local timezone for naive timestamps."""
    from logana.utils.timeUtils import resolveLocalTimezone
    return PipelineTimeContext(default_tz=resolveLocalTimezone())


def utcTimeContext() -> PipelineTimeContext:
    """Treats naive timestamps as UTC (container-friendly default)."""
    return PipelineTimeContext(default_tz=timezone.utc, naive_policy="utc")
