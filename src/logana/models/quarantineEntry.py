from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional
from logana.models.fieldState import FieldState

@dataclass(frozen=True)
class QuarantineEntry:
    """Represents a log entry that could not be parsed with high enough confidence."""
    lineNumber: int
    rawContent: str
    bestEffortFields: Dict[str, FieldState] 
    reason: str 
    timestamp: Optional[datetime] = None    
    contextBefore: List[str] = field(default_factory=list) 
