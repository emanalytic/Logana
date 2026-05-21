from typing import List, Union
from logana.models.fieldState import Known, Unknown, Absent, isKnown
from logana.models.logEvent import LogEvent
from logana.models.quarantineEntry import QuarantineEntry
from logana.parsers.parserBase import ParseResult
from logana.parsers.fieldKit import QUALITY_SCORED_FIELDS
from logana.utils.timeUtils import nowUtc

class QuarantineGate:
    """Evaluates ParseResults and routes them to either a LogEvent or a QuarantineEntry."""
    
    def __init__(
        self,
        quarantineThreshold: float = 0.3,
        allow_synthetic_timestamps: bool = False,
    ):
        self.quarantineThreshold = quarantineThreshold
        self.allow_synthetic_timestamps = allow_synthetic_timestamps

    def _inject_synthetic_timestamp(self, result: ParseResult) -> ParseResult:
        fields = dict(result.fields)
        synthetic = Known(
            nowUtc(),
            0.35,
            "synthetic-ingestion-time",
            meta={"timestampSource": "ingestion_fallback"},
        )
        fields["timestamp"] = synthetic
        warnings = list(result.warnings)
        warnings.append(
            "Synthetic ingestion timestamp applied (original line had no parseable time)"
        )
        return ParseResult(
            parserId=result.parserId,
            fields=fields,
            rawText=result.rawText,
            lineNumber=result.lineNumber,
            warnings=warnings,
        )

    def route(
        self,
        result: ParseResult,
        contextBefore: List[str] = None,
    ) -> Union[LogEvent, QuarantineEntry]:
        timestamp_field = result.fields.get("timestamp")
        if not timestamp_field or not isKnown(timestamp_field):
            if self.allow_synthetic_timestamps:
                result = self._inject_synthetic_timestamp(result)
                timestamp_field = result.fields.get("timestamp")

        warnings = list(result.warnings)
        reasons = []

        if not timestamp_field or not isKnown(timestamp_field):
            reasons.append("Missing or invalid timestamp")

        low_fields = []
        for field_name in QUALITY_SCORED_FIELDS:
            field = result.fields.get(field_name)
            if isinstance(field, Known) and field.confidence < self.quarantineThreshold:
                low_fields.append(f"{field_name} ({field.confidence:.2f})")
            elif isinstance(field, Unknown) and field.guessConfidence < self.quarantineThreshold:
                low_fields.append(f"{field_name} ({field.guessConfidence:.2f})")

        if low_fields:
            reasons.append(
                f"Field confidence below threshold ({self.quarantineThreshold:.2f}): "
                + ", ".join(low_fields)
            )

        mean_conf = result.qualityConfidence
        if mean_conf < self.quarantineThreshold:
            reasons.append(
                f"Mean field confidence ({mean_conf:.2f}) below threshold "
                f"({self.quarantineThreshold:.2f})"
            )

        if reasons:
            reason_str = "; ".join(reasons)
            timestamp_val = None
            if timestamp_field and isKnown(timestamp_field):
                timestamp_val = timestamp_field.value
            elif timestamp_field and isinstance(timestamp_field, Unknown) and timestamp_field.bestGuess:
                timestamp_val = timestamp_field.bestGuess

            return QuarantineEntry(
                lineNumber=result.lineNumber,
                rawContent=result.rawText,
                bestEffortFields=result.fields,
                reason=reason_str,
                timestamp=timestamp_val,
                contextBefore=contextBefore if contextBefore is not None else [],
            )

        return result.toLogEvent()
