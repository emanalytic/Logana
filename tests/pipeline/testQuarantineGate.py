from datetime import datetime
from logana.models.fieldState import Known, Unknown
from logana.models.logEvent import LogEvent
from logana.models.quarantineEntry import QuarantineEntry
from logana.parsers.parserBase import ParseResult
from logana.pipeline.quarantineGate import QuarantineGate


def test_quarantineGateAcceptsValidEvent():
    gate = QuarantineGate(quarantineThreshold=0.3)
    fields = {
        "timestamp": Known(datetime.now(), 0.9, "now"),
        "statusCode": Known(200, 0.9, "200"),
    }
    assert isinstance(gate.route(ParseResult("test", fields, "raw", 1)), LogEvent)


def test_quarantineGateRejectsMissingTimestamp():
    gate = QuarantineGate(quarantineThreshold=0.3)
    fields = {"statusCode": Known(200, 0.9, "200")}
    entry = gate.route(ParseResult("test", fields, "raw", 2))
    assert isinstance(entry, QuarantineEntry)
    assert "Missing or invalid timestamp" in entry.reason


def test_quarantineGateRejectsLowConfidence():
    gate = QuarantineGate(quarantineThreshold=0.3)
    fields = {
        "timestamp": Known(datetime.now(), 0.9, "now"),
        "statusCode": Known(200, 0.1, "200"),
    }
    entry = gate.route(ParseResult("test", fields, "raw", 3))
    assert isinstance(entry, QuarantineEntry)
    assert "confidence" in entry.reason
