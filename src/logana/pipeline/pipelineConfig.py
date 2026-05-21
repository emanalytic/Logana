from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from logana.pipeline.timeContext import PipelineTimeContext, defaultTimeContext
from logana.utils.timeUtils import parseTimezone


class PipelineConfig(BaseModel):
    """Runtime options for log ingestion and analysis."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    quarantineThreshold: float = Field(default=0.3, ge=0.0, le=1.0)
    timeContext: Optional[PipelineTimeContext] = None
    encoding: str = "utf-8"
    contextLines: int = Field(default=5, ge=0)
    allowSyntheticTimestamps: bool = False
    maxEndpoints: int = Field(default=200, ge=1)

    @classmethod
    def fromCli(
        cls,
        quarantineThreshold: float = 0.3,
        logTimezone: str = "local",
        naiveTimestamps: Literal["local", "utc"] = "local",
        referenceDate: Optional[date] = None,
        encoding: str = "utf-8",
        allowSyntheticTimestamps: bool = False,
    ) -> "PipelineConfig":
        ctx = PipelineTimeContext(
            default_tz=parseTimezone(logTimezone),
            naive_policy=naiveTimestamps,
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
