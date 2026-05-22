from typing import Any, Dict, List, Optional, Sequence
from logana.models.fieldState import FieldState, Absent, Known, isKnown, pickBetterFieldState
from logana.extractors.timestamp import TimestampExtractor
from logana.extractors.timestampHunter import huntTimestamp
from logana.pipeline.timeContext import PipelineTimeContext, defaultTimeContext
from logana.extractors.ipAddress import IpAddressExtractor
from logana.extractors.httpMethod import HttpMethodExtractor
from logana.extractors.statusCode import StatusCodeExtractor
from logana.extractors.responseTime import ResponseTimeExtractor
from logana.extractors.urlPath import UrlPathExtractor
from logana.extractors.logLevel import LogLevelExtractor
from logana.extractors.extractorBase import BaseExtractor
from logana.extractors.linePatterns import scanLinePatterns

STANDARD_FIELD_NAMES: List[str] = [
    "timestamp",
    "ipAddress",
    "httpMethod",
    "urlPath",
    "statusCode",
    "responseTimeMs",
    "logLevel",
]

QUALITY_SCORED_FIELDS = STANDARD_FIELD_NAMES

DEFAULT_KEY_MAPPINGS: Dict[str, List[str]] = {
    "timestamp": ["timestamp", "time", "ts", "@timestamp", "datetime"],
    "ipAddress": ["ip", "ipAddress", "clientIp", "client_ip", "host"],
    "httpMethod": ["method", "httpMethod", "http_method", "verb"],
    "urlPath": ["path", "urlPath", "url_path", "uri", "url", "request"],
    "statusCode": ["status", "statusCode", "status_code", "code"],
    "responseTimeMs": [
        "responseTime",
        "responseTimeMs",
        "response_time",
        "duration",
        "duration_ms",
        "latency",
        "latency_ms",
        "timeMs",
        "time_ms",
    ],
    "logLevel": ["level", "logLevel", "log_level", "severity"],
    "message": ["message", "msg", "log", "text"],
}

_MILLISECOND_KEY_HINTS = frozenset({
    "responseTimeMs",
    "duration_ms",
    "latency_ms",
    "time_ms",
    "response_time_ms",
})


class ParserFieldKit:
    """Shared extractor instances and helpers used across format parsers."""

    def __init__(self, time_context: Optional[PipelineTimeContext] = None) -> None:
        ctx = time_context or defaultTimeContext()
        self.time_context = ctx
        self.timestampExt = TimestampExtractor(ctx)
        self.ipExt = IpAddressExtractor()
        self.methodExt = HttpMethodExtractor()
        self.pathExt = UrlPathExtractor()
        self.statusExt = StatusCodeExtractor()
        self.timeExt = ResponseTimeExtractor()
        self.levelExt = LogLevelExtractor()
        self._byField: Dict[str, BaseExtractor] = {
            "timestamp": self.timestampExt,
            "ipAddress": self.ipExt,
            "httpMethod": self.methodExt,
            "urlPath": self.pathExt,
            "statusCode": self.statusExt,
            "responseTimeMs": self.timeExt,
            "logLevel": self.levelExt,
        }
        self.tokenScanOrder: Sequence[BaseExtractor] = [
            self.timestampExt,
            self.ipExt,
            self.methodExt,
            self.pathExt,
            self.statusExt,
            self.timeExt,
            self.levelExt,
        ]

    def emptyStandardFields(self) -> Dict[str, FieldState]:
        return {name: Absent() for name in STANDARD_FIELD_NAMES}

    def extractField(self, fieldName: str, rawValue: str) -> FieldState:
        return self._byField[fieldName].extract(rawValue)

    def findMappedValue(
        self, data: Dict[str, Any], keys: List[str]
    ) -> Optional[Any]:
        for key in keys:
            if key in data:
                return data[key]
        return None

    def findMappedKeyValue(
        self, data: Dict[str, Any], keys: List[str]
    ) -> Optional[tuple[str, Any]]:
        for key in keys:
            if key in data:
                return key, data[key]
        return None

    def _extractResponseTimeFromMappedValue(self, key: str, raw: Any) -> FieldState:
        if raw is None:
            return Absent()

        if key in _MILLISECOND_KEY_HINTS:
            try:
                return Known(float(raw), 0.95, str(raw))
            except (TypeError, ValueError):
                pass

        return self.extractField("responseTimeMs", str(raw))

    def applyMappedFields(
        self,
        data: Dict[str, Any],
        keyMappings: Dict[str, List[str]] = DEFAULT_KEY_MAPPINGS,
    ) -> Dict[str, FieldState]:
        fields = self.emptyStandardFields()
        for fieldName in STANDARD_FIELD_NAMES:
            aliases = keyMappings.get(fieldName, [])
            mapped = self.findMappedKeyValue(data, aliases)
            if mapped is not None:
                rawKey, raw = mapped
                if fieldName == "responseTimeMs":
                    fields[fieldName] = self._extractResponseTimeFromMappedValue(
                        rawKey,
                        raw,
                    )
                else:
                    fields[fieldName] = self.extractField(fieldName, str(raw))
        return fields

    def mergeField(
        self,
        fields: Dict[str, FieldState],
        fieldName: str,
        candidate: FieldState,
    ) -> None:
        current = fields.get(fieldName, Absent())
        fields[fieldName] = pickBetterFieldState(current, candidate)

    def scanTokens(
        self,
        fields: Dict[str, FieldState],
        tokens: List[str],
        *,
        lineText: Optional[str] = None,
    ) -> None:
        """Scan tokens (and optionally the full line for timestamp) for standard fields."""
        if lineText is not None:
            ts = huntTimestamp(lineText, self.timestampExt)
            if isKnown(ts):
                self.mergeField(fields, "timestamp", ts)

        for token in tokens:
            for ext in self.tokenScanOrder:
                if (
                    ext is self.timestampExt
                    and isKnown(fields.get("timestamp", Absent()))
                ):
                    continue
                self.mergeField(fields, ext.fieldName, ext.extract(token))

        scanLinePatterns(fields, self, lineText)
