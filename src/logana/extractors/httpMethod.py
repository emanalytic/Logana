from logana.models.fieldState import FieldState, Known, Unknown, Absent
from logana.extractors.base import BaseExtractor

KNOWN_METHODS = {"GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS", "CONNECT", "TRACE"}

class HttpMethodExtractor(BaseExtractor[str]):
    """Extractor for standard HTTP methods (GET, POST, etc.)."""
    
    def __init__(self):
        super().__init__("httpMethod")

    def extract(self, token: str) -> FieldState[str]:
        cleaned = self.cleanToken(token).upper()
        if not cleaned:
            return Absent()

        if cleaned in KNOWN_METHODS:
            return Known(cleaned, 0.99, token)
            
        if cleaned.isalpha() and 3 <= len(cleaned) <= 10:
            return Unknown(f"Unrecognized HTTP method: '{cleaned}'", cleaned, 0.3)

        return Absent()
