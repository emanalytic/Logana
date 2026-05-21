from datetime import datetime
from typing import Optional
from logana.utils.ringBuffer import RingBuffer
from logana.models.events import AnomalyEvent

class StreamingAnomalyDetector:
    """Detects spikes and drops in a streaming rate signal using a rolling modified Z-score."""
    
    def __init__(self, windowSize: int = 60, zThreshold: float = 3.0):
        self.window = RingBuffer(windowSize)
        self.zThreshold = zThreshold

    def add(self, value: float, timestamp: datetime) -> Optional[AnomalyEvent]:
        """Pushes a rate value into the detector and evaluates if it is an anomaly.
        
        Returns an AnomalyEvent if a spike or drop is detected, otherwise None.
        """
        self.window.push(value)
        if self.window.count < 20:
            return None  # Insufficient baseline data
            
        median = self.window.median()
        mad = self.window.mad()  # Median Absolute Deviation
        
        if mad == 0.0:
            if value == median:
                return None
            mad = 1e-4
            
        # Modified Z-score using 0.6745 coefficient
        z = 0.6745 * (value - median) / mad
        
        if abs(z) > self.zThreshold:
            return AnomalyEvent(
                timestamp=timestamp,
                metricValue=value,
                baseline=median,
                zScore=z,
                direction="spike" if z > 0.0 else "drop"
            )
            
        return None
