from dataclasses import dataclass
from datetime import date
from typing import Optional
from logana.pipeline.timeContext import PipelineTimeContext, defaultTimeContext
from logana.utils.timeUtils import parseTimezone


@dataclass
class PipelineConfig:
    """Runtime options for log ingestion and analysis."""

    quarantineThreshold: float = 0.3
    timeContext: Optional[PipelineTimeContext] = None
    encoding: str = "utf-8"
    contextLines: int = 5
    allowSyntheticTimestamps: bool = False
    maxEndpoints: int = 200

    @classmethod
    def fromCli(
        cls,
        quarantineThreshold: float = 0.3,
        logTimezone: str = "local",
        naiveTimestamps: str = "local",
        referenceDate: Optional[date] = None,
        encoding: str = "utf-8",
        allowSyntheticTimestamps: bool = False,
    ) -> "PipelineConfig":
        ctx = PipelineTimeContext(
            default_tz=parseTimezone(logTimezone),
            naive_policy=naiveTimestamps,  # type: ignore[arg-type]
        )
        if referenceDate is not None:
            ctx.reference_year = referenceDate.year
        return cls(
            quarantineThreshold=quarantineThreshold,
            timeContext=ctx,
            encoding=encoding,
            allowSyntheticTimestamps=allowSyntheticTimestamps,
        )

    def resolvedTimeContext(self) -> PipelineTimeContext:
        return self.timeContext or defaultTimeContext()
