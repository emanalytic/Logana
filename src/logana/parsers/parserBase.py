from abc import ABC, abstractmethod
from typing import Dict, List, Union
from logana.models.fieldState import FieldState, Known, Unknown, Absent
from logana.models.logEvent import LogEvent
from logana.models.quarantineEntry import QuarantineEntry
from logana.parsers.fieldKit import QUALITY_SCORED_FIELDS

class ParseResult:
    """Contains the output of parsing a single log line group."""
    
    def __init__(self, parserId: str, fields: Dict[str, FieldState], rawText: str, lineNumber: int, warnings: List[str] = None):
        self.parserId = parserId
        self.fields = fields  ## mapping of fieldName -> FieldState
        self.rawText = rawText
        self.lineNumber = lineNumber
        self.warnings = warnings if warnings is not None else []

    @property
    def minFieldConfidence(self) -> float:
        """Returns the lowest confidence among parsed fields that carry a confidence score."""
        scoredConfidences = []
        for field in self.fields.values():
            if isinstance(field, Known):
                scoredConfidences.append(field.confidence)
            elif isinstance(field, Unknown):
                scoredConfidences.append(field.guessConfidence)

        if not scoredConfidences:
            return 0.0
        return min(scoredConfidences)

    @property
    def qualityConfidence(self) -> float:
        """Mean confidence over analytical fields (excludes message).

        Unlike minFieldConfidence, a single weak optional field does not
        dominate dispatch and quarantine decisions.
        """
        scores: List[float] = []
        for name in QUALITY_SCORED_FIELDS:
            field = self.fields.get(name)
            if isinstance(field, Known):
                scores.append(field.confidence)

        if not scores:
            return 0.0
        return sum(scores) / len(scores)

    def toLogEvent(self) -> LogEvent:
        """Converts ParseResult into a normalized LogEvent."""
        def getField(fieldName: str) -> FieldState:
            return self.fields.get(fieldName, Absent())

        return LogEvent(
            timestamp=getField("timestamp"),
            ipAddress=getField("ipAddress"),
            httpMethod=getField("httpMethod"),
            urlPath=getField("urlPath"),
            statusCode=getField("statusCode"),
            responseTimeMs=getField("responseTimeMs"),
            logLevel=getField("logLevel"),
            message=getField("message"),
            rawLine=self.rawText,
            lineNumber=self.lineNumber,
            parserId=self.parserId,
            warnings=self.warnings
        )

class Parser(ABC):
    """Abstract Base Class for all specialized format parsers."""
    
    def __init__(self, parserId: str):
        self.parserId = parserId

    @abstractmethod
    def parse(self, text: str, lineNumber: int) -> ParseResult:
        """Parses a log line group and returns a ParseResult."""
        pass
