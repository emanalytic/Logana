import re
from typing import Dict
from logana.models.fieldState import FieldState, Known, Absent
from logana.parsers.parserBase import Parser, ParseResult
from logana.extractors.ipAddress import IpAddressExtractor
from logana.extractors.logLevel import LogLevelExtractor
from logana.parsers.fieldKit import ParserFieldKit
from logana.pipeline.timeContext import PipelineTimeContext, defaultTimeContext

# RFC 5424 (IETF Syslog) regex
RFC_5424_PATTERN = re.compile(
    r'^<(\d+)>1\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(-|\[[^\]]+\])\s+(.*)$'
)

# RFC 3164 (BSD Syslog) regex
RFC_3164_PATTERN = re.compile(
    r'^<(\d+)>([A-Za-z]{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})\s+(\S+)\s+(.*)$'
)

SYSLOG_SEVERITIES = {
    0: "FATAL",      # Emergency
    1: "CRITICAL",   # Alert
    2: "CRITICAL",   # Critical
    3: "ERROR",      # Error
    4: "WARN",       # Warning
    5: "INFO",       # Notice (mapped to INFO)
    6: "INFO",       # Informational
    7: "DEBUG"       # Debug
}

class SyslogParser(Parser):
    """Parses RFC 3164 (BSD) and RFC 5424 (IETF) Syslog lines."""
    
    def __init__(self, time_context: PipelineTimeContext | None = None):
        super().__init__("syslog")
        self.kit = ParserFieldKit(time_context or defaultTimeContext())
        self.ipExt = IpAddressExtractor()
        self.levelExt = LogLevelExtractor()

    def parse(self, text: str, lineNumber: int) -> ParseResult:
        cleaned = text.strip()
        fields: Dict[str, FieldState] = {}
        warnings = []
        priority = None
        hostname = None
        timestampStr = None
        messageStr = None

        match = RFC_5424_PATTERN.match(cleaned)
        if match:
            groups = match.groups()
            priority = int(groups[0])
            timestampStr = groups[1]
            hostname = groups[2]
            # app_name = groups[3]
            # proc_id = groups[4]
            # msg_id = groups[5]
            messageStr = groups[7]
        else:
            match = RFC_3164_PATTERN.match(cleaned)
            if match:
                groups = match.groups()
                priority = int(groups[0])
                timestampStr = groups[1]
                hostname = groups[2]
                messageStr = groups[3]

        if not match:
            return ParseResult(
                self.parserId,
                {},
                text,
                lineNumber,
                ["Line does not match Syslog format"]
            )

        fields["timestamp"] = self.kit.timestampExt.extract(timestampStr)

        fields["ipAddress"] = self.ipExt.extract(hostname)

        severityNum = priority % 8
        stdLevel = SYSLOG_SEVERITIES.get(severityNum, "INFO")
        fields["logLevel"] = Known(
            stdLevel,
            0.95,
            f"priority {priority} (severity {severityNum})"
        )

        fields["message"] = Known(messageStr, 1.0, messageStr)

        fields["httpMethod"] = Absent()
        fields["urlPath"] = Absent()
        fields["statusCode"] = Absent()
        fields["responseTimeMs"] = Absent()

        firstToken = messageStr.split()[0] if messageStr.split() else ""
        embeddedLevel = self.levelExt.extract(firstToken)
        if isinstance(embeddedLevel, Known):
            syslogLevel = fields["logLevel"]
            if embeddedLevel.value != syslogLevel.value:
                warnings.append(
                    f"Embedded message token '{firstToken}' level {embeddedLevel.value} "
                    f"overrides syslog-derived level {syslogLevel.value}"
                )
            if embeddedLevel.confidence >= syslogLevel.confidence:
                fields["logLevel"] = embeddedLevel

        return ParseResult(
            self.parserId, 
            fields, 
            text, 
            lineNumber, 
            warnings
        )
