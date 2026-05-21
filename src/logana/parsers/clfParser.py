import re
from typing import Dict, Optional
from apachelogs import COMBINED, COMMON, parse as parse_apache_log
from apachelogs.errors import InvalidEntryError
from logana.models.fieldState import FieldState, Known, Absent
from logana.parsers.parserBase import Parser, ParseResult
from logana.parsers.fieldKit import ParserFieldKit
from logana.pipeline.timeContext import PipelineTimeContext, defaultTimeContext
from logana.utils.timeUtils import TIMESTAMP_SOURCE_LOCAL, coerceToUtc

CLF_PATTERN = re.compile(
    r'^(\S+)\s+(\S+)\s+(\S+)\s+\[([^\]]+)\]\s+"([^"]*)"\s+(\d{3})\s+(\S+)(?:\s+"([^"]*)"\s+"([^"]*)")?$'
)

_APACHE_FORMATS = (COMBINED, COMMON)


class ClfParser(Parser):
    """Parses Common Log Format (CLF) and Combined Log Format lines."""

    def __init__(self, time_context: PipelineTimeContext | None = None):
        super().__init__("clf")
        self.kit = ParserFieldKit(time_context or defaultTimeContext())

    def _parseWithApachelogs(self, cleaned: str) -> Optional[Dict[str, FieldState]]:
        for fmt in _APACHE_FORMATS:
            try:
                entry = parse_apache_log(fmt, cleaned)
            except InvalidEntryError:
                continue

            fields: Dict[str, FieldState] = {}
            host = getattr(entry, "remote_host", None) or "-"
            fields["ipAddress"] = self.kit.ipExt.extract(str(host))

            request_time = getattr(entry, "request_time", None)
            if request_time is not None:
                utc_dt = coerceToUtc(request_time)
                fields["timestamp"] = Known(
                    utc_dt,
                    0.93,
                    str(getattr(entry, "request_time_fields", request_time)),
                    meta={"timestampSource": TIMESTAMP_SOURCE_LOCAL},
                )
            else:
                fields["timestamp"] = Absent()

            status = getattr(entry, "final_status", None)
            if status is not None:
                fields["statusCode"] = self.kit.statusExt.extract(str(status))
            else:
                fields["statusCode"] = Absent()

            request_line = getattr(entry, "request_line", "") or ""
            request_parts = request_line.split()
            if len(request_parts) >= 2:
                fields["httpMethod"] = self.kit.methodExt.extract(request_parts[0])
                fields["urlPath"] = self.kit.pathExt.extract(request_parts[1])
                fields["message"] = Known(request_line, 1.0, request_line)
            else:
                fields["httpMethod"] = Absent()
                fields["urlPath"] = Absent()
                fields["message"] = Known(request_line, 1.0, request_line) if request_line else Absent()

            fields["responseTimeMs"] = Absent()
            fields["logLevel"] = Absent()
            return fields

        return None

    def parse(self, text: str, lineNumber: int) -> ParseResult:
        cleaned = text.strip()
        apache_fields = self._parseWithApachelogs(cleaned)
        if apache_fields is not None:
            return ParseResult(self.parserId, apache_fields, text, lineNumber, [])

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
