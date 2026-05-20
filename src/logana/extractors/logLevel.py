from logana.models.fieldState import FieldState, Known, Unknown, Absent
from logana.extractors.base import BaseExtractor

LEVEL_MAP = {
    "ERROR": "ERROR", "SEVERE": "ERROR", "ERR": "ERROR",
    "WARN": "WARN", "WARNING": "WARN",
    "INFO": "INFO", "INF": "INFO",
    "DEBUG": "DEBUG", "DBG": "DEBUG",
    "TRACE": "TRACE", "TRC": "TRACE",
    "FATAL": "FATAL", "FTL": "FATAL",
    "CRITICAL": "CRITICAL", "CRIT": "CRITICAL", "CRT": "CRITICAL"
}

SINGLE_CHAR_LEVELS = {
    "E": "ERROR",
    "W": "WARN",
    "I": "INFO",
    "D": "DEBUG",
    "T": "TRACE",
    "F": "FATAL",
    "C": "CRITICAL"
}

class LogLevelExtractor(BaseExtractor[str]):
    """Extractor for standard log levels (INFO, WARN, ERROR, etc.)."""
    
    def __init__(self):
        super().__init__("logLevel")

    def extract(self, token: str) -> FieldState[str]:
        cleaned = self.cleanToken(token).upper()
        if not cleaned:
            return Absent()

        # Match standard levels
        if cleaned in LEVEL_MAP:
            return Known(LEVEL_MAP[cleaned], 0.98, token)

        # Match single-character levels
        if cleaned in SINGLE_CHAR_LEVELS:
            # Lower confidence since single chars like 'I' can easily be false positives
            return Known(SINGLE_CHAR_LEVELS[cleaned], 0.6, token)

        # Catch-all for other bracketed words that might be a custom level
        if token.startswith('[') and token.endswith(']') and cleaned.isalpha():
            return Unknown(f"Unrecognized log level: '{cleaned}'", cleaned, 0.4)

        return Absent()
