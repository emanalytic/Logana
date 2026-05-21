import os

import pytest

from logana.models.fieldState import getValueOrDefault, isKnown
from logana.models.logEvent import LogEvent
from logana.models.quarantineEntry import QuarantineEntry
from logana.pipeline.lineBoundary import LineBoundaryDetector
from logana.pipeline.pipelineConfig import PipelineConfig
from logana.pipeline.pipelineRunner import runPipeline
from logana.pipeline.parserDispatch import ParserDispatch
from logana.pipeline.quarantineGate import QuarantineGate
from logana.pipeline.streamReader import streamReader


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


def test_openstack_loghub_pipeline():
    """Smoke test on real LogHub OpenStack nova logs (HTTP-shaped, 2k lines)."""
    fixturePath = os.path.join(os.path.dirname(__file__), "..", "fixtures", "OpenStack_2k.log")

    boundaryDetector = LineBoundaryDetector()
    groups = list(boundaryDetector.detectBoundaries(streamReader(fixturePath)))

    config = PipelineConfig.fromCli(quarantineThreshold=0.3)
    accumulators = runPipeline(fixturePath, config)

    dispatcher = ParserDispatch(
        quarantineThreshold=0.3,
        time_context=config.resolvedTimeContext(),
    )
    gate = QuarantineGate(quarantineThreshold=0.3)

    logEvents: list[LogEvent] = []
    quarantineEntries: list[QuarantineEntry] = []
    for groupText, startLineNum in groups:
        parseResult = dispatcher.dispatch(groupText, startLineNum)
        routed = gate.route(parseResult)
        if isinstance(routed, LogEvent):
            logEvents.append(routed)
        else:
            quarantineEntries.append(routed)

    assert accumulators.eventCounter.totalLines == 2000
    assert accumulators.eventCounter.totalEvents == len(logEvents)
    assert accumulators.quarantineTracker.rate < 0.02
    assert len(logEvents) >= 1900

    assert any("/v2/" in getValueOrDefault(e.urlPath, "") for e in logEvents)
    assert any(isKnown(e.timestamp) for e in logEvents)
