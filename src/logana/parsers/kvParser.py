import re
from typing import Dict
from logana.models.fieldState import FieldState, Known, Absent
from logana.parsers.parserBase import Parser, ParseResult
from logana.parsers.fieldKit import ParserFieldKit, DEFAULT_KEY_MAPPINGS
from logana.pipeline.timeContext import PipelineTimeContext, defaultTimeContext

KV_PATTERN = re.compile(r'([a-zA-Z0-9_.-]+)=("([^"]*)"|(\S+))')

KEY_MAPPINGS = {
    **DEFAULT_KEY_MAPPINGS,
    "timestamp": ["timestamp", "time", "ts", "datetime"],
    "urlPath": ["path", "urlPath", "url_path", "uri", "url"],
}

class KvParser(Parser):
    """Parses logfmt/key-value logs (e.g. key=value or key=\"quoted value\")."""
    
    def __init__(self, time_context: PipelineTimeContext | None = None):
        super().__init__("kv")
        self.kit = ParserFieldKit(time_context or defaultTimeContext())

    def _parseLogfmt(self, cleaned: str) -> Dict[str, str]:
        data: Dict[str, str] = {}
        matches = KV_PATTERN.findall(cleaned)
        for match in matches:
            key = match[0]
            val = match[2] if match[2] else match[3]
            data[key] = val
        return data

    def _parseTabSeparated(self, cleaned: str) -> Dict[str, str]:
        data: Dict[str, str] = {}
        for part in cleaned.split("\t"):
            part = part.strip()
            if not part:
                continue
            if "=" in part:
                key, _, val = part.partition("=")
                data[key.strip()] = val.strip().strip('"')
            elif ":" in part:
                key, _, val = part.partition(":")
                data[key.strip()] = val.strip()
        return data

    def parse(self, text: str, lineNumber: int) -> ParseResult:
        cleaned = text.strip()
        data = self._parseLogfmt(cleaned)
        if len(data) < 2 and "\t" in cleaned:
            data = self._parseTabSeparated(cleaned)

        if len(data) < 2:
            return ParseResult(
                self.parserId,
                {},
                text,
                lineNumber,
                ["Not enough key-value pairs found"],
            )

        fields: Dict[str, FieldState] = self.kit.applyMappedFields(data, KEY_MAPPINGS)

        msgVal = self.kit.findMappedValue(data, KEY_MAPPINGS["message"])
        if msgVal is not None:
            fields["message"] = Known(msgVal, 1.0, msgVal)
        else:
            fields["message"] = Absent()

        return ParseResult(
            self.parserId,
            fields,
            text,
            lineNumber,
            []
        )
