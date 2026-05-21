from dataclasses import dataclass, field
from datetime import datetime
from typing import List
from logana.models.fieldState import FieldState

@dataclass(frozen=True)
class LogEvent:
    """Represents a normalized log event containing uncertainty-aware field states and parsing metadata."""
    timestamp: FieldState[datetime]
    ipAddress: FieldState[str]
    httpMethod: FieldState[str]
    urlPath: FieldState[str]
    statusCode: FieldState[int]
    responseTimeMs: FieldState[float]
    logLevel: FieldState[str]
    message: FieldState[str]
    rawLine: str
    lineNumber: int
    parserId: str
    warnings: List[str] = field(default_factory=list)
