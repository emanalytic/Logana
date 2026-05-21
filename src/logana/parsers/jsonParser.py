import json
from typing import Any, Dict, List, Tuple
from logana.models.fieldState import FieldState, Known, Absent
from logana.parsers.parserBase import Parser, ParseResult
from logana.parsers.fieldKit import ParserFieldKit, DEFAULT_KEY_MAPPINGS
from logana.pipeline.timeContext import PipelineTimeContext, defaultTimeContext
from logana.utils.jsonLoad import loadJsonObject

KEY_MAPPINGS = DEFAULT_KEY_MAPPINGS


def extractJsonObject(text: str) -> Tuple[Any, List[str]]:
    """Extracts a JSON object from a raw line, tolerating non-JSON prefixes."""
    return loadJsonObject(text)

class JsonParser(Parser):
    """Parses JSON-formatted log lines, mapping common keys to standard log fields."""
    
    def __init__(self, time_context: PipelineTimeContext | None = None):
        super().__init__("json")
        self.kit = ParserFieldKit(time_context or defaultTimeContext())

    def parse(self, text: str, lineNumber: int) -> ParseResult:
        try:
            data, warnings = extractJsonObject(text)
            if not isinstance(data, dict):
                return ParseResult(self.parserId, {}, text, lineNumber, ["JSON is not an object"])
        except json.JSONDecodeError as e:
            return ParseResult(self.parserId, {}, text, lineNumber, [f"Invalid JSON: {str(e)}"])

        fields: Dict[str, FieldState] = self.kit.applyMappedFields(data, KEY_MAPPINGS)

        msgVal = self.kit.findMappedValue(data, KEY_MAPPINGS["message"])
        if msgVal is not None:
            fields["message"] = Known(str(msgVal), 1.0, str(msgVal))
        else:
            fields["message"] = Absent()

        return ParseResult(self.parserId, fields, text, lineNumber, warnings)
