from typing import Dict, Optional
from logana.models.fieldState import FieldState, isKnown, Known
from logana.parsers.parserBase import ParseResult, Parser
from logana.parsers.jsonParser import JsonParser
from logana.parsers.clfParser import ClfParser
from logana.parsers.syslogParser import SyslogParser
from logana.parsers.kvParser import KvParser
from logana.parsers.delimitedParser import DelimitedParser
from logana.parsers.tokenExtractor import TokenExtractor
from logana.pipeline.formatProbe import probeFormat, FormatHint
from logana.pipeline.timeContext import PipelineTimeContext, defaultTimeContext
from logana.extractors.timestampHunter import huntTimestamp


class ParserDispatch:
    """Manages format probe classification, primary parser execution, and fallback merging."""

    def __init__(
        self,
        quarantineThreshold: float = 0.3,
        time_context: Optional[PipelineTimeContext] = None,
    ):
        self.quarantineThreshold = quarantineThreshold
        self.time_context = time_context or defaultTimeContext()

        ctx = self.time_context
        self.parsers: Dict[FormatHint, Parser] = {
            FormatHint.JSON: JsonParser(ctx),
            FormatHint.CLF: ClfParser(ctx),
            FormatHint.SYSLOG: SyslogParser(ctx),
            FormatHint.KV: KvParser(ctx),
            FormatHint.DELIMITED: DelimitedParser(ctx),
        }
        self.fallbackParser = TokenExtractor(ctx)

    def mergeBestFields(self, primary: ParseResult, fallback: ParseResult) -> ParseResult:
        """Merges two ParseResults, keeping the higher confidence Known fields for each key."""
        mergedFields: Dict[str, FieldState] = {}
        allKeys = set(primary.fields.keys()) | set(fallback.fields.keys())

        for key in allKeys:
            pField = primary.fields.get(key)
            fField = fallback.fields.get(key)

            if pField is None:
                mergedFields[key] = fField
            elif fField is None:
                mergedFields[key] = pField
            else:
                pIsKnown = isKnown(pField)
                fIsKnown = isKnown(fField)

                if pIsKnown and fIsKnown:
                    if pField.confidence >= fField.confidence:
                        mergedFields[key] = pField
                    else:
                        mergedFields[key] = fField
                elif pIsKnown:
                    mergedFields[key] = pField
                else:
                    mergedFields[key] = fField

        mergedWarnings = primary.warnings + fallback.warnings
        mergedWarnings.append(f"Merged fallback parser '{fallback.parserId}' due to low confidence")

        return ParseResult(
            parserId=f"{primary.parserId}+{fallback.parserId}",
            fields=mergedFields,
            rawText=primary.rawText,
            lineNumber=primary.lineNumber,
            warnings=mergedWarnings,
        )

    def _finalize(self, result: ParseResult) -> ParseResult:
        """Apply line-level timestamp hunting and learn anchor years from the stream."""
        fields = dict(result.fields)
        warnings = list(result.warnings)
        ts_field = fields.get("timestamp")

        if not isKnown(ts_field):
            hunted = huntTimestamp(result.rawText, self.fallbackParser.kit.timestampExt)
            if isKnown(hunted):
                fields["timestamp"] = hunted
                warnings.append("Timestamp recovered via line-level hunter")

        ts_field = fields.get("timestamp")
        if isinstance(ts_field, Known):
            self.time_context.note_anchor(ts_field.value)

        return ParseResult(
            parserId=result.parserId,
            fields=fields,
            rawText=result.rawText,
            lineNumber=result.lineNumber,
            warnings=warnings,
        )

    def dispatch(self, text: str, lineNumber: int) -> ParseResult:
        """Runs the format probe, invokes the primary parser, and falls back to token extraction if needed."""
        hint, confidence = probeFormat(text)

        if confidence >= 0.6 and hint in self.parsers:
            primaryParser = self.parsers[hint]
            primaryResult = primaryParser.parse(text, lineNumber)

            if primaryResult.fields and primaryResult.qualityConfidence >= self.quarantineThreshold:
                return self._finalize(primaryResult)

            fallbackResult = self.fallbackParser.parse(text, lineNumber)
            return self._finalize(self.mergeBestFields(primaryResult, fallbackResult))

        return self._finalize(self.fallbackParser.parse(text, lineNumber))
