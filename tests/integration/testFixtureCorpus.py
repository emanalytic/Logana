"""Behavioral checks across the fixture library (not only happy-path pipeline smoke)."""
from datetime import date
from pathlib import Path
import pytest
from logana.pipeline.pipelineConfig import PipelineConfig
from logana.pipeline.pipelineRunner import runPipeline

FIXTURE_EXPECTATIONS = {
    "complex.log": {"minEvents": 10, "maxQuarantineRate": 0.15, "minLatencySamples": 2},
    "sample2.log": {"minEvents": 350, "maxQuarantineRate": 0.10, "minLatencySamples": 100},
    "hdfs_sample.log": {"minEvents": 20, "maxQuarantineRate": 0.60, "minLatencySamples": 0},
    "sample4.log": {"minEvents": 5, "maxQuarantineRate": 0.70, "minLatencySamples": 0},
}


@pytest.mark.parametrize("fileName,expected", FIXTURE_EXPECTATIONS.items())
def test_fixtureMeetsExpectations(fixturesDir: Path, fileName: str, expected: dict):
    path = fixturesDir / fileName
    accumulators = runPipeline(str(path), PipelineConfig.fromCli())

    assert accumulators.eventCounter.totalEvents >= expected["minEvents"]
    assert accumulators.quarantineTracker.rate <= expected["maxQuarantineRate"]
    assert accumulators.latencyDigest.count >= expected["minLatencySamples"]


def test_linuxSyslogNeedsReferenceDate(fixturesDir: Path):
    path = fixturesDir / "Linux_2k.log"
    withoutRef = runPipeline(str(path), PipelineConfig.fromCli())
    withRef = runPipeline(
        str(path),
        PipelineConfig.fromCli(referenceDate=date(2004, 6, 15)),
    )
    assert withRef.logTimeSpan.first is not None
    assert withRef.logTimeSpan.first.year == 2004
    assert withoutRef.logTimeSpan.first is not None
