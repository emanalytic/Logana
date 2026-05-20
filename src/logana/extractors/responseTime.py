import re
from logana.models.fieldState import FieldState, Known, Unknown, Absent
from logana.extractors.base import BaseExtractor

RESPONSE_TIME_RE = re.compile(
    r'^([0-9]+(?:\.[0-9]+)?)\s*(ms|µs|us|s|ns|sec|seconds|milliseconds|µs)?$',
    re.IGNORECASE
)

class ResponseTimeExtractor(BaseExtractor[float]):
    """Extractor for response times (normalizing units to milliseconds)."""
    
    def __init__(self):
        super().__init__("responseTimeMs")

    def extract(self, token: str) -> FieldState[float]:
        cleaned = self.cleanToken(token)
        if not cleaned:
            return Absent()

        match = RESPONSE_TIME_RE.match(cleaned)
        if not match:
            return Absent()

        numStr, unitStr = match.groups()
        try:
            val = float(numStr)
        except ValueError:
            return Absent()

        if unitStr:
            unit = unitStr.lower()
            if unit in ('ms', 'milliseconds'):
                return Known(val, 0.95, token)
            elif unit in ('s', 'sec', 'seconds'):
                return Known(val * 1000.0, 0.95, token)
            elif unit in ('us', 'µs'):
                return Known(val / 1000.0, 0.95, token)
            elif unit == 'ns':
                return Known(val / 1000000.0, 0.95, token)

        # Bare number unit ambiguous
        return Unknown(
            "Bare number response time: unit ambiguous",
            bestGuess=val,
            guessConfidence=0.5
        )
