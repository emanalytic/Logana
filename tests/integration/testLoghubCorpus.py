"""Regression bounds for LogHub-derived fixtures (real-world logs)."""
from datetime import date
from pathlib import Path

import pytest

from logana.pipeline.pipelineConfig import PipelineConfig
from logana.pipeline.pipelineRunner import runPipeline

# (filename, config kwargs, expectations)
LOGHUB_CASES = [
    (
        "Linux_2k.log",
        {"referenceDate": date(2004, 6, 15)},
        {"minEvents": 1800, "maxQuarantineRate": 0.08, "minLatencySamples": 0},
    ),
    (
        "Apache_2k.log",
        {"referenceDate": date(2005, 12, 4)},
        {"minEvents": 1900, "maxQuarantineRate": 0.02, "minLatencySamples": 0},
    ),
    (
        "OpenSSH_2k.log",
        {},
        {"minEvents": 1800, "maxQuarantineRate": 0.10, "minLatencySamples": 0},
    ),
    (
        "OpenStack_2k.log",
        {},
        {"minEvents": 1900, "maxQuarantineRate": 0.02, "minLatencySamples": 0},
    ),
    (
        "Hadoop_2k.log",
        {},
        {"minEvents": 1500, "maxQuarantineRate": 0.25, "minLatencySamples": 0},
    ),
    (
        "HDFS_2k.log",
        {},
        {"minEvents": 900, "maxQuarantineRate": 0.55, "minLatencySamples": 0},
    ),
    (
        "HealthApp_2k.log",
        {},
        {"minEvents": 700, "maxQuarantineRate": 0.70, "minLatencySamples": 0},
    ),
]


@pytest.mark.parametrize("fileName,configKw,expected", LOGHUB_CASES)
def test_loghubFixtureMeetsBounds(
    fixturesDir: Path, fileName: str, configKw: dict, expected: dict
):
    path = fixturesDir / fileName
    assert path.exists(), f"Missing LogHub fixture: {fileName}"
    accumulators = runPipeline(str(path), PipelineConfig.fromCli(**configKw))

    assert accumulators.eventCounter.totalEvents >= expected["minEvents"]
    assert accumulators.quarantineTracker.rate <= expected["maxQuarantineRate"]
    assert accumulators.latencyDigest.count >= expected["minLatencySamples"]


@pytest.mark.parametrize(
    "fileName",
    ["Spark_2k.log", "Proxifier_2k.log"],
)
def test_loghubKnownHardFormatsMostlyQuarantine(fixturesDir: Path, fileName: str):
    """Document formats we do not parse yet — expect very high quarantine."""
    path = fixturesDir / fileName
    accumulators = runPipeline(str(path), PipelineConfig.fromCli())
    assert accumulators.eventCounter.totalLines == 2000
    assert accumulators.quarantineTracker.rate >= 0.95
