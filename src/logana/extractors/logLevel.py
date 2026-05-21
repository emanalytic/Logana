from logana.models.fieldState import FieldState, Known, Unknown, Absent
from logana.extractors.extractorBase import BaseExtractor

LEVEL_MAP = {
    "ERROR": "ERROR", "SEVERE": "ERROR", "ERR": "ERROR",
    "WARN": "WARN", "WARNING": "WARN",
    "INFO": "INFO", "INF": "INFO",
    "DEBUG": "DEBUG", "DBG": "DEBUG",
    "TRACE": "TRACE", "TRC": "TRACE",
    "FATAL": "FATAL", "FTL": "FATAL",
    "CRITICAL": "CRITICAL", "CRIT": "CRITICAL", "CRT": "CRITICAL"
}

SEMANTIC_MAP = {
    "FAILURE": "ERROR", "FAIL": "ERROR", "FAILED": "ERROR",
    "TIMEOUT": "ERROR", "EXCEPTION": "ERROR", "REFUSED": "ERROR",
    "DENIED": "WARN", "UNAUTHORIZED": "WARN", "PANIC": "FATAL"
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
    """Extractor for standard log levels (INFO, WARN, ERROR, etc.) and semantic implicit levels."""
    
    def __init__(self):
        super().__init__("logLevel")

    def extract(self, token: str) -> FieldState[str]:
        cleaned = self.cleanToken(token).upper()
        if not cleaned:
            return Absent()

        if cleaned in LEVEL_MAP:
            return Known(LEVEL_MAP[cleaned], 0.98, token)
        if cleaned in SEMANTIC_MAP:
            return Known(SEMANTIC_MAP[cleaned], 0.85, f"implicit: {token}")
        if cleaned in SINGLE_CHAR_LEVELS:
            ##lower confidence since single chars like 'I' can easily be false positives##
            return Known(SINGLE_CHAR_LEVELS[cleaned], 0.6, token)

        ##catch-all for other bracketed words that might be a custom level##
        if token.startswith('[') and token.endswith(']') and cleaned.isalpha():
            return Unknown(f"Unrecognized log level: '{cleaned}'", cleaned, 0.4)

        return Absent()
