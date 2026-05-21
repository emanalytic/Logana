from logana.pipeline.quarantineGate import QuarantineGate
from logana.parsers.parserBase import ParseResult
from logana.models.fieldState import Absent, Known
from logana.models.logEvent import LogEvent

def test_synthetic_timestamp_creates_event():
    gate = QuarantineGate(quarantineThreshold=0.3, allow_synthetic_timestamps=True)
    result = ParseResult(
        "tokenExtractor",
        {"statusCode": Known(200, 0.9, "200")},
        "no timestamp here",
        42,
        [],
    )
    routed = gate.route(result)
    assert isinstance(routed, LogEvent)
    assert isinstance(routed.timestamp, Known)
    assert routed.timestamp.meta.get("timestampSource") == "ingestion_fallback"

def test_without_synthetic_stays_quarantine():
    gate = QuarantineGate(quarantineThreshold=0.3, allow_synthetic_timestamps=False)
    result = ParseResult("tokenExtractor", {}, "no timestamp", 1, [])
    from logana.models.quarantineEntry import QuarantineEntry
    routed = gate.route(result)
    assert isinstance(routed, QuarantineEntry)
