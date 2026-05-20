from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional
from logana.models.fieldState import FieldState

@dataclass(frozen=True)
class QuarantineEntry:
    """Represents a log entry that could not be parsed with high enough confidence."""
    lineNumber: int
    rawContent: str
    bestEffortFields: Dict[str, FieldState]  # Any partially parsed fields
    reason: str                             # The reason for quarantine (e.g. why parsing failed)
    timestamp: Optional[datetime] = None    # Extracted timestamp if possible, for time series reporting
    contextBefore: List[str] = field(default_factory=list) # A few preceding lines to assist debugging
