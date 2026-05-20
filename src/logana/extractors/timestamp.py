import re
from datetime import datetime, timezone
from logana.models.fieldState import FieldState, Known, Unknown, Absent
from logana.extractors.base import BaseExtractor

# Search patterns (without strict ^ and $ anchors) to find timestamps embedded in text
ISO_8601_RE = re.compile(
    r'(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2}:\d{2}(?:\.\d+)?)(Z|[+-]\d{2}:?\d{2})?'
)
CLF_RE = re.compile(
    r'(\d{2})/([A-Za-z]{3})/(\d{4}):(\d{2}):(\d{2}):(\d{2})\s+([+-]\d{4})'
)
SYSLOG_RE = re.compile(
    r'\b([A-Za-z]{3})\s+(\d{1,2})\s+(\d{2}):(\d{2}):(\d{2})\b'
)
PLAIN_DT_RE = re.compile(
    r'(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2}:\d{2}(?:\.\d+)?)'
)
EPOCH_RE = re.compile(
    r'\b(\d{10}|\d{13})\b'
)

MONTH_MAP = {
    'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6,
    'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12
}

class TimestampExtractor(BaseExtractor[datetime]):
    """Extractor for various date and timestamp formats, capable of searching within text."""
    
    def __init__(self):
        super().__init__("timestamp")

    def extract(self, token: str) -> FieldState[datetime]:
        cleaned = self.cleanToken(token)
        if not cleaned:
            return Absent()

        # 1. ISO 8601 / RFC 3339
        match = ISO_8601_RE.search(cleaned)
        if match:
            try:
                matchedText = match.group(0)
                val = matchedText
                if val.endswith('Z'):
                    val = val[:-1] + '+00:00'
                dt = datetime.fromisoformat(val)
                if 2000 <= dt.year <= 2050:
                    return Known(dt, 0.95, matchedText)
                return Unknown("ISO 8601 timestamp year out of sane bounds", dt, 0.4)
            except ValueError as e:
                return Unknown(f"Failed parsing ISO 8601: {str(e)}")

        # 2. Plain Date Time (YYYY-MM-DD HH:MM:SS)
        match = PLAIN_DT_RE.search(cleaned)
        if match:
            try:
                matchedText = match.group(0)
                # fromisoformat expects T or space separator
                dt = datetime.fromisoformat(matchedText)
                if 2000 <= dt.year <= 2050:
                    return Known(dt, 0.85, matchedText)
                return Unknown("Plain date-time year out of sane bounds", dt, 0.4)
            except ValueError as e:
                return Unknown(f"Failed parsing plain date-time: {str(e)}")

        # 3. CLF (Apache Combined Log Format) 10/Oct/2000:13:55:36 -0700
        match = CLF_RE.search(cleaned)
        if match:
            day, monthStr, year, hour, minute, second, tzStr = match.groups()
            month = MONTH_MAP.get(monthStr)
            if month:
                try:
                    tzFormatted = tzStr[:3] + ':' + tzStr[3:]
                    dtStr = f"{year}-{month:02d}-{int(day):02d}T{hour}:{minute}:{second}{tzFormatted}"
                    dt = datetime.fromisoformat(dtStr)
                    return Known(dt, 0.9, match.group(0))
                except ValueError as e:
                    return Unknown(f"Failed parsing CLF date-time: {str(e)}")

        # 4. Syslog Oct 11 13:14:15
        match = SYSLOG_RE.search(cleaned)
        if match:
            monthStr, day, hour, minute, second = match.groups()
            month = MONTH_MAP.get(monthStr)
            if month:
                try:
                    currentYear = datetime.now(timezone.utc).year
                    dt = datetime(
                        year=currentYear,
                        month=month,
                        day=int(day),
                        hour=int(hour),
                        minute=int(minute),
                        second=int(second),
                        tzinfo=timezone.utc
                    )
                    return Known(dt, 0.75, match.group(0))
                except ValueError as e:
                    return Unknown(f"Failed parsing Syslog date-time: {str(e)}")

        # 5. Epoch Seconds/Millis
        match = EPOCH_RE.search(cleaned)
        if match:
            try:
                matchedText = match.group(0)
                val = int(matchedText)
                if len(matchedText) == 13:
                    dt = datetime.fromtimestamp(val / 1000.0, tz=timezone.utc)
                    conf = 0.8
                else:
                    dt = datetime.fromtimestamp(val, tz=timezone.utc)
                    conf = 0.75

                if 2000 <= dt.year <= 2050:
                    return Known(dt, conf, matchedText)
                return Unknown("Epoch timestamp year out of sane bounds", dt, 0.3)
            except (ValueError, OSError, OverflowError) as e:
                return Unknown(f"Failed parsing Epoch: {str(e)}")

        return Absent()
