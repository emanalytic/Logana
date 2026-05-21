import re
from datetime import datetime, timezone
from typing import Optional, Tuple
from logana.models.fieldState import FieldState, Known, Unknown, Absent
from logana.extractors.extractorBase import BaseExtractor
from logana.pipeline.timeContext import PipelineTimeContext, defaultTimeContext
from logana.utils.dateutilParse import tryFuzzyTimestamp
from logana.utils.timeUtils import (
    TimestampNormalizer,
    TIMESTAMP_SOURCE_EPOCH,
    TIMESTAMP_SOURCE_SYSLOG,
    TIMESTAMP_SOURCE_LOCAL,
    TIMESTAMP_SOURCE_UTC,
)

ISO_8601_RE = re.compile(
    r'(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2}:\d{2}(?:\.\d+)?)(Z|[+-]\d{2}:?\d{2})?'
)
CLF_RE = re.compile(
    r'(\d{2})/([A-Za-z]{3})/(\d{4}):(\d{2}):(\d{2}):(\d{2})\s+([+-]\d{4})'
)
SYSLOG_RE = re.compile(
    r'\b([A-Za-z]{3})\s+(\d{1,2})\s+(\d{2}):(\d{2}):(\d{2})\b'
)
APACHE_ERROR_RE = re.compile(
    r'\[(\w{3})\s+(\w{3})\s+(\d{1,2})\s+(\d{2}:\d{2}:\d{2})\s+(\d{4})\]'
)
HDFS_RE = re.compile(r'\b(\d{6})\s+(\d{6})\b')
PLAIN_DT_RE = re.compile(
    r'(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2}:\d{2}(?:\.\d+)?)'
)
JAVA_BRACKET_RE = re.compile(
    r'\[(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2}:\d{2})(?:[,.](\d{1,6}))?\]'
)
EPOCH_RE = re.compile(r'\b(\d{10}|\d{13})\b')
EPOCH_FLOAT_RE = re.compile(r'\b(\d{10})\.(\d{1,6})\b')

MONTH_MAP = {
    'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6,
    'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12
}


class TimestampExtractor(BaseExtractor[datetime]):
    """Extracts timestamps and normalizes them to aware UTC with provenance metadata."""

    def __init__(self, time_context: Optional[PipelineTimeContext] = None):
        super().__init__("timestamp")
        self.time_context = time_context or defaultTimeContext()
        self._normalizer = TimestampNormalizer(self.time_context)

    def extract(self, token: str) -> FieldState[datetime]:
        text = token.strip()
        cleaned = self.cleanToken(token)
        if not text and not cleaned:
            return Absent()

        candidates = [
            self._try_iso8601(text),
            self._try_apache_error(text),
            self._try_java_bracket(text),
            self._try_plain(text),
            self._try_clf(text),
            self._try_hdfs(text),
            self._try_syslog(text),
            self._try_epoch_float(text),
            self._try_epoch(text),
            self._try_dateutil(text),
        ]

        best: Optional[Tuple[datetime, float, str, str]] = None
        for candidate in candidates:
            if candidate is None:
                continue
            if best is None or candidate[1] > best[1]:
                best = candidate

        if best is None:
            return Absent()

        dt, conf, raw, provenance = best
        if not (2000 <= dt.year <= 2050):
            utc_dt, adj_conf, source = self._normalizer.normalize(dt, provenance, conf)
            return Unknown(
                "Timestamp year out of sane bounds",
                utc_dt,
                min(adj_conf, 0.4),
            )

        return self._as_known(dt, conf, raw, provenance)

    def _as_known(
        self,
        dt: datetime,
        confidence: float,
        raw: str,
        provenance: str,
    ) -> Known[datetime]:
        utc_dt, adj_conf, source = self._normalizer.normalize(dt, provenance, confidence)
        return Known(
            utc_dt,
            adj_conf,
            raw,
            meta={"timestampSource": source},
        )

    def _try_iso8601(self, cleaned: str) -> Optional[Tuple[datetime, float, str, str]]:
        match = ISO_8601_RE.search(cleaned)
        if not match:
            return None
        try:
            matched_text = match.group(0)
            val = matched_text
            if val.endswith('Z'):
                val = val[:-1] + '+00:00'
            dt = datetime.fromisoformat(val)
            prov = (
                TIMESTAMP_SOURCE_UTC
                if dt.tzinfo is None and self.time_context.naive_policy == "utc"
                else TIMESTAMP_SOURCE_LOCAL
            )
            return (dt, 0.95, matched_text, prov)
        except ValueError:
            return None

    def _try_apache_error(self, cleaned: str) -> Optional[Tuple[datetime, float, str, str]]:
        match = APACHE_ERROR_RE.search(cleaned)
        if not match:
            return None
        _weekday, month_str, day, time_part, year = match.groups()
        month = MONTH_MAP.get(month_str)
        if not month:
            return None
        try:
            hour, minute, second = (int(x) for x in time_part.split(":"))
            dt = datetime(int(year), month, int(day), hour, minute, second)
            return (dt, 0.92, match.group(0), TIMESTAMP_SOURCE_LOCAL)
        except ValueError:
            return None

    def _try_hdfs(self, cleaned: str) -> Optional[Tuple[datetime, float, str, str]]:
        match = HDFS_RE.search(cleaned)
        if not match:
            return None
        date_part, time_part = match.groups()
        try:
            yy = int(date_part[:2])
            mm = int(date_part[2:4])
            dd = int(date_part[4:6])
            hour = int(time_part[:2])
            minute = int(time_part[2:4])
            second = int(time_part[4:6])
            year = 2000 + yy if yy < 70 else 1900 + yy
            dt = datetime(year, mm, dd, hour, minute, second)
            return (dt, 0.82, match.group(0), TIMESTAMP_SOURCE_LOCAL)
        except ValueError:
            return None

    def _try_java_bracket(self, cleaned: str) -> Optional[Tuple[datetime, float, str, str]]:
        match = JAVA_BRACKET_RE.search(cleaned)
        if not match:
            return None
        try:
            date_part, time_part, frac = match.groups()
            matched_text = match.group(0)
            text = f"{date_part}T{time_part}"
            if frac:
                text += f".{frac[:6]}"
            dt = datetime.fromisoformat(text)
            prov = (
                TIMESTAMP_SOURCE_UTC
                if self.time_context.naive_policy == "utc"
                else TIMESTAMP_SOURCE_LOCAL
            )
            return (dt, 0.88, matched_text, prov)
        except ValueError:
            return None

    def _try_plain(self, cleaned: str) -> Optional[Tuple[datetime, float, str, str]]:
        match = PLAIN_DT_RE.search(cleaned)
        if not match:
            return None
        try:
            matched_text = match.group(0)
            dt = datetime.fromisoformat(matched_text)
            prov = (
                TIMESTAMP_SOURCE_UTC
                if self.time_context.naive_policy == "utc"
                else TIMESTAMP_SOURCE_LOCAL
            )
            return (dt, 0.85, matched_text, prov)
        except ValueError:
            return None

    def _try_clf(self, cleaned: str) -> Optional[Tuple[datetime, float, str, str]]:
        match = CLF_RE.search(cleaned)
        if not match:
            return None
        day, month_str, year, hour, minute, second, tz_str = match.groups()
        month = MONTH_MAP.get(month_str)
        if not month:
            return None
        try:
            tz_formatted = tz_str[:3] + ':' + tz_str[3:]
            dt_str = (
                f"{year}-{month:02d}-{int(day):02d}T{hour}:{minute}:{second}{tz_formatted}"
            )
            dt = datetime.fromisoformat(dt_str)
            return (dt, 0.9, match.group(0), TIMESTAMP_SOURCE_LOCAL)
        except ValueError:
            return None

    def _try_syslog(self, cleaned: str) -> Optional[Tuple[datetime, float, str, str]]:
        match = SYSLOG_RE.search(cleaned)
        if not match:
            return None
        month_str, day, hour, minute, second = match.groups()
        month = MONTH_MAP.get(month_str)
        if not month:
            return None
        try:
            year = self.time_context.resolve_syslog_year(month, int(day))
            dt = datetime(
                year=year,
                month=month,
                day=int(day),
                hour=int(hour),
                minute=int(minute),
                second=int(second),
            )
            return (dt, 0.75, match.group(0), TIMESTAMP_SOURCE_SYSLOG)
        except ValueError:
            return None

    def _try_epoch(self, cleaned: str) -> Optional[Tuple[datetime, float, str, str]]:
        match = EPOCH_RE.search(cleaned)
        if not match:
            return None
        matched_text = match.group(0)
        if '.' in matched_text:
            return None
        try:
            val = int(matched_text)
            if len(matched_text) == 13:
                dt = datetime.fromtimestamp(val / 1000.0, tz=timezone.utc)
                conf = 0.8
            else:
                dt = datetime.fromtimestamp(val, tz=timezone.utc)
                conf = 0.75
            return (dt, conf, matched_text, TIMESTAMP_SOURCE_EPOCH)
        except (ValueError, OSError, OverflowError):
            return None

    def _try_dateutil(self, cleaned: str) -> Optional[Tuple[datetime, float, str, str]]:
        if cleaned.startswith("<") and len(cleaned) > 2 and cleaned[1].isdigit():
            return None
        if self._try_syslog(cleaned) is not None:
            return None
        ref_year = self.time_context.reference_year or datetime.now().year
        default = datetime(ref_year, 1, 1, tzinfo=None)
        parsed = tryFuzzyTimestamp(cleaned, default=default)
        if parsed is None:
            return None
        dt, raw = parsed
        prov = (
            TIMESTAMP_SOURCE_UTC
            if self.time_context.naive_policy == "utc"
            else TIMESTAMP_SOURCE_LOCAL
        )
        return (dt, 0.68, raw[:80], prov)

    def _try_epoch_float(self, cleaned: str) -> Optional[Tuple[datetime, float, str, str]]:
        match = EPOCH_FLOAT_RE.search(cleaned)
        if not match:
            return None
        try:
            whole, frac = match.groups()
            val = float(f"{whole}.{frac}")
            dt = datetime.fromtimestamp(val, tz=timezone.utc)
            return (dt, 0.78, match.group(0), TIMESTAMP_SOURCE_EPOCH)
        except (ValueError, OSError, OverflowError):
            return None
