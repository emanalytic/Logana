from urllib.parse import urlparse
from logana.models.fieldState import FieldState, Known, Unknown, Absent
from logana.extractors.extractorBase import BaseExtractor

class UrlPathExtractor(BaseExtractor[str]):
    """Extractor for URL paths from relative paths or absolute URLs."""
    
    def __init__(self):
        super().__init__("urlPath")

    def extract(self, token: str) -> FieldState[str]:
        cleaned = self.cleanToken(token)
        if not cleaned:
            return Absent()

        # If it is a relative path starting with '/'
        if cleaned.startswith('/'):
            if ' ' in cleaned:
                return Absent()
            try:
                parsed = urlparse(cleaned)
                if parsed.path:
                    return Known(parsed.path, 0.95, token)
            except ValueError:
                pass

        # If it looks like an absolute URL (starts with http:// or https://)
        if cleaned.startswith(('http://', 'https://')):
            try:
                parsed = urlparse(cleaned)
                if parsed.path:
                    return Known(parsed.path, 0.9, token)
                return Known("/", 0.8, token)
            except ValueError:
                return Unknown(f"Malformed absolute URL: '{cleaned}'", cleaned, 0.3)

        return Absent()
