from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass(frozen=True)
class DriftEvent:
    """Fired when a schema drift/format change is detected in the stream."""
    lineNumber: int
    fromFormat: str
    toFormat: str
    timestamp: Optional[datetime] = None

@dataclass(frozen=True)
class AnomalyEvent:
    """Fired when an anomaly (e.g. spike in error rate or quarantine rate) is detected."""
    timestamp: datetime
    metricValue: float
    baseline: float
    zScore: float
    direction: str  # 'spike' or 'drop'
