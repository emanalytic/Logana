import os
import pytest
from logana.pipeline.streamReader import streamReader
from logana.pipeline.lineBoundary import LineBoundaryDetector
from logana.pipeline.pipelineConfig import PipelineConfig
from logana.pipeline.pipelineRunner import runPipeline
from logana.models.logEvent import LogEvent
from logana.models.quarantineEntry import QuarantineEntry
from logana.models.fieldState import getValueOrDefault, isKnown

def test_line_boundary_ignores_json_braces_inside_strings():
    detector = LineBoundaryDetector()
    rawLines = iter([
        '{"timestamp": "2024-03-15T14:23:01Z", "message": "payload has { brace"}\n',
        '{"timestamp": "2024-03-15T14:23:02Z", "message": "next event"}\n',
    ])

    groups = list(detector.detectBoundaries(rawLines))

    assert len(groups) == 2
    assert groups[0][1] == 1
    assert "payload has { brace" in groups[0][0]
    assert groups[1][1] == 2

def test_complex_log_pipeline():
    fixturePath = os.path.join(os.path.dirname(__file__), "..", "fixtures", "complex.log")
    
    boundaryDetector = LineBoundaryDetector()
    lines = streamReader(fixturePath)
    groups = list(boundaryDetector.detectBoundaries(lines))

    config = PipelineConfig.fromCli(quarantineThreshold=0.3)
    accumulators = runPipeline(fixturePath, config)

    logEvents = []
    quarantineEntries = []
    # Re-run boundary count only; events from accumulators via re-parse is heavy.
    # Use runPipeline output: infer from counters + re-walk for assertions.
    dispatcher_events = []
    from logana.pipeline.parserDispatch import ParserDispatch
    from logana.pipeline.quarantineGate import QuarantineGate
    dispatcher = ParserDispatch(quarantineThreshold=0.3, time_context=config.resolvedTimeContext())
    gate = QuarantineGate(quarantineThreshold=0.3)
    for groupText, startLineNum in groups:
        parseResult = dispatcher.dispatch(groupText, startLineNum)
        routed = gate.route(parseResult)
        if isinstance(routed, LogEvent):
            logEvents.append(routed)
        elif isinstance(routed, QuarantineEntry):
            quarantineEntries.append(routed)

    assert accumulators.eventCounter.totalEvents == len(logEvents)

    # 3. Print summaries for debugging
    print(f"\n--- Pipelined Log Events ({len(logEvents)}) ---")
    for event in logEvents:
        ts = getValueOrDefault(event.timestamp, "N/A")
        ip = getValueOrDefault(event.ipAddress, "N/A")
        level = getValueOrDefault(event.logLevel, "N/A")
        parser = event.parserId
        print(f"Line {event.lineNumber} | Parser: {parser} | TS: {ts} | IP: {ip} | Level: {level}")

    print(f"\n--- Quarantined Entries ({len(quarantineEntries)}) ---")
    for entry in quarantineEntries:
        print(f"Line {entry.lineNumber} | Reason: {entry.reason} | Preview: {entry.rawContent[:50]}...")

    # 4. Assertions to verify correct parsing behavior

    # - We expect 12 logical group boundaries:
    # 1.  CLF line 1
    # 2.  CLF line 2
    # 3.  JSON line 3
    # 4.  JSON line 4
    # 5.  Multi-line stack trace (starts line 5, ends line 11)
    # 6.  Syslog line 12
    # 7.  Syslog line 13
    # 8.  KV line 14
    # 9.  KV line 15
    # 10. Random un-structured line (line 16)
    # 11. Malformed JSON (line 17)
    # 12. CLF line 18
    assert len(groups) == 12

    # - Check multi-line stacktrace grouping (group index 4, 0-based)
    stackTraceGroup = groups[4]
    assert stackTraceGroup[1] == 5  # Start line number
    assert "Connection pool exhausted" in stackTraceGroup[0]
    assert "java.sql.SQLTimeoutException" in stackTraceGroup[0]

    # - Check CLF parsing
    assert any(e.parserId == "clf" and getValueOrDefault(e.ipAddress, "") == "127.0.0.1" for e in logEvents)

    # - Check JSON parsing
    assert any(e.parserId == "json" and getValueOrDefault(e.logLevel, "") == "ERROR" for e in logEvents)

    # - Check Syslog parsing
    assert any(e.parserId == "syslog" and getValueOrDefault(e.logLevel, "") == "CRITICAL" for e in logEvents)

    # - Check KV parsing
    assert any(e.parserId == "kv" and getValueOrDefault(e.statusCode, 0) == 503 for e in logEvents)

    # - Check quarantine gate
    # Random un-structured line (line 16) has no timestamp -> must be quarantined
    assert any(q.lineNumber == 16 and "Missing or invalid timestamp" in q.reason for q in quarantineEntries)

    # Malformed JSON (line 17) is accepted as a LogEvent but contains Unknown/Absent states for failed fields
    malformedJsonEvent = next(e for e in logEvents if e.lineNumber == 17)
    assert isinstance(malformedJsonEvent, LogEvent)
    assert not isKnown(malformedJsonEvent.ipAddress)  # Invalid IP is Unknown/Absent
    assert not isKnown(malformedJsonEvent.responseTimeMs)  # Invalid duration is Absent
