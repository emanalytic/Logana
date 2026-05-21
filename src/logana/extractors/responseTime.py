import re
from logana.models.fieldState import FieldState, Known, Unknown, Absent
from logana.extractors.extractorBase import BaseExtractor

RESPONSE_TIME_RE = re.compile(
    r'^([0-9]+(?:\.[0-9]+)?)\s*(ms|us|s|ns|sec|seconds|milliseconds)?$',
    re.IGNORECASE
)
class ResponseTimeExtractor(BaseExtractor[float]):
    """Extractor for response times (normalizing units to milliseconds)."""

    def __init__(self):
        super().__init__("responseTimeMs")

    def extract(self, token: str) -> FieldState[float]:
        cleaned = self.cleanToken(token)
        cleaned = (
            cleaned
            .replace("\u00c2\u00b5", "u")
            .replace("\u00b5", "u")
            .replace("\u03bc", "u")
        )
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
                if val > 120_000.0:
                    return Unknown("Response time exceeds plausible HTTP range", bestGuess=val, guessConfidence=0.3)
                return Known(val, 0.95, token)
            if unit in ('s', 'sec', 'seconds'):
                ms = val * 1000.0
                if ms > 120_000.0:
                    return Unknown("Response time exceeds plausible HTTP range", bestGuess=ms, guessConfidence=0.3)
                return Known(ms, 0.95, token)
            if unit == 'us':
                return Known(val / 1000.0, 0.95, token)
            if unit == 'ns':
                return Known(val / 1000000.0, 0.95, token)

        return Unknown(
            "Bare number response time: unit ambiguous",
            bestGuess=val,
            guessConfidence=0.5
        )
