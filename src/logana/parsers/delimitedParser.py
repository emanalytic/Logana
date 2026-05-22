from typing import Dict, List, Optional
from logana.models.fieldState import FieldState, Known, Unknown, Absent, isKnown
from logana.parsers.parserBase import Parser, ParseResult
from logana.parsers.fieldKit import ParserFieldKit, STANDARD_FIELD_NAMES, DEFAULT_KEY_MAPPINGS
from logana.pipeline.formatProbe import _stableCommaColumns
from logana.pipeline.timeContext import PipelineTimeContext, defaultTimeContext

class DelimitedParser(Parser):
    """Automatically detects delimiters (tabs, pipes, commas) and infers column mappings dynamically."""
    
    def __init__(self, time_context: PipelineTimeContext | None = None):
        super().__init__("delimited")
        self.kit = ParserFieldKit(time_context or defaultTimeContext())

    def _detectDelimiter(self, text: str) -> Optional[str]:
        """Sniffs the line for common delimiters (needs at least 3 columns)."""
        first = text.split("\n", 1)[0]
        for delim in ("\t", "|"):
            if first.count(delim) >= 2 and first.count(delim) + 1 >= 3:
                return delim
        if _stableCommaColumns(text):
            return ","
        return None

    def _try_header_mapping(self, parts: List[str]) -> Dict[str, int]:
        mapping: Dict[str, int] = {}
        for idx, part in enumerate(parts):
            normalized = part.strip().lower().replace("-", "_")
            if not normalized:
                continue
            for field_name, aliases in DEFAULT_KEY_MAPPINGS.items():
                if field_name == "message":
                    continue
                if normalized in [a.lower() for a in aliases]:
                    mapping[field_name] = idx
                    break
        return mapping if len(mapping) >= 2 else {}

    def _inferColumnMapping(self, parts: List[str]) -> Dict[str, int]:
        candidateMapping: Dict[str, int] = {}
        for idx, part in enumerate(parts):
            if not part:
                continue

            ts = self.kit.timestampExt.extract(part)
            if isKnown(ts) and ts.confidence > 0.7:
                candidateMapping["timestamp"] = idx

            ip = self.kit.ipExt.extract(part)
            if isKnown(ip) and ip.confidence > 0.8:
                candidateMapping["ipAddress"] = idx

            method = self.kit.methodExt.extract(part)
            if isKnown(method) and method.confidence > 0.8:
                candidateMapping["httpMethod"] = idx

            path = self.kit.pathExt.extract(part)
            if isKnown(path) and path.confidence > 0.8:
                candidateMapping["urlPath"] = idx

            status = self.kit.statusExt.extract(part)
            if isKnown(status) and status.confidence > 0.8:
                candidateMapping["statusCode"] = idx

            rtime = self.kit.timeExt.extract(part)
            if isKnown(rtime) and rtime.confidence > 0.8:
                candidateMapping["responseTimeMs"] = idx

            level = self.kit.levelExt.extract(part)
            if isKnown(level) and level.confidence > 0.8:
                candidateMapping["logLevel"] = idx

        return candidateMapping

    def parse(self, text: str, lineNumber: int) -> ParseResult:
        cleaned = text.strip()
        
        delim = self._detectDelimiter(cleaned)
            
        if not delim:
            return ParseResult(self.parserId, {}, text, lineNumber, ["No common delimiter detected with sufficient frequency"])

        parts = [p.strip() for p in cleaned.split(delim)]
        if len(parts) < 3:
            return ParseResult(self.parserId, {}, text, lineNumber, ["Line contains too few columns after split"])

        candidateMapping = self._try_header_mapping(parts)
        warnings: List[str] = []
        if candidateMapping:
            warnings.append("Mapped columns from header row")
        else:
            candidateMapping = self._inferColumnMapping(parts)
        if len(candidateMapping) < 2:
            return ParseResult(self.parserId, {}, text, lineNumber, ["Could not reliably map columns to log fields"])

        fields: Dict[str, FieldState] = {}

        for fieldName in STANDARD_FIELD_NAMES:
            if fieldName in candidateMapping:
                colIdx = candidateMapping[fieldName]
                if colIdx < len(parts):
                    fields[fieldName] = self.kit.extractField(fieldName, parts[colIdx])
                else:
                    fields[fieldName] = Unknown("Column index out of bounds")
            else:
                fields[fieldName] = Absent()

        unmappedParts = []
        mappedIndices = set(candidateMapping.values())
        for idx, part in enumerate(parts):
            if idx not in mappedIndices:
                unmappedParts.append(part)

        messageStr = " | ".join(unmappedParts) if unmappedParts else cleaned
        fields["message"] = Known(messageStr, 1.0, messageStr)

        return ParseResult(self.parserId, fields, text, lineNumber, warnings)
