import re
from typing import Dict
from logana.models.fieldState import FieldState, Known, Absent
from logana.parsers.parserBase import Parser, ParseResult
from logana.parsers.fieldKit import ParserFieldKit
from logana.pipeline.timeContext import PipelineTimeContext, defaultTimeContext

CLF_PATTERN = re.compile(
    r'^(\S+)\s+(\S+)\s+(\S+)\s+\[([^\]]+)\]\s+"([^"]*)"\s+(\d{3})\s+(\S+)(?:\s+"([^"]*)"\s+"([^"]*)")?$'
)

class ClfParser(Parser):
    """Parses Common Log Format (CLF) and Combined Log Format lines."""
    
    def __init__(self, time_context: PipelineTimeContext | None = None):
        super().__init__("clf")
        self.kit = ParserFieldKit(time_context or defaultTimeContext())

    def parse(self, text: str, lineNumber: int) -> ParseResult:
        cleaned = text.strip()
        match = CLF_PATTERN.match(cleaned)
        if not match:
            return ParseResult(self.parserId, {}, text, lineNumber, ["Line does not match CLF format"])

        groups = match.groups()
        host = groups[0]
        dateStr = groups[3]
        request = groups[4]
        status = groups[5]

        fields: Dict[str, FieldState] = {}
        warnings = []

        fields["ipAddress"] = self.kit.ipExt.extract(host)
        fields["timestamp"] = self.kit.timestampExt.extract(dateStr)
        fields["statusCode"] = self.kit.statusExt.extract(status)
        requestParts = request.split()
        if len(requestParts) >= 2:
            fields["httpMethod"] = self.kit.methodExt.extract(requestParts[0])
            fields["urlPath"] = self.kit.pathExt.extract(requestParts[1])
            fields["message"] = Known(request, 1.0, request)
        else:
            fields["httpMethod"] = Absent()
            fields["urlPath"] = Absent()
            fields["message"] = Known(request, 1.0, request)

        fields["responseTimeMs"] = Absent()
        fields["logLevel"] = Absent()

        return ParseResult(self.parserId, fields, text, lineNumber, warnings)
