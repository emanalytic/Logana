from logana.models.fieldState import FieldState, Known, Unknown, Absent
from logana.extractors.base import BaseExtractor

class StatusCodeExtractor(BaseExtractor[int]):
    """Extractor for HTTP status codes (2xx, 3xx, 4xx, 5xx, etc.)."""
    
    def __init__(self):
        super().__init__("statusCode")

    def extract(self, token: str) -> FieldState[int]:
        cleaned = self.cleanToken(token)
        if not cleaned:
            return Absent()

        if not cleaned.isdigit():
            return Absent()

        try:
            val = int(cleaned)
            if 100 <= val <= 599:
                return Known(val, 0.9, token)
            if 100 <= val <= 999:
                return Unknown(f"Non-standard HTTP status code: {val}", val, 0.4)
            return Absent()
        except ValueError:
            return Absent()
