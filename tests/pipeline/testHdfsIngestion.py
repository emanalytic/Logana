from logana.pipeline.pipelineConfig import PipelineConfig
from logana.pipeline.pipelineRunner import runPipeline


def test_hdfsSampleParses(hdfsLogPath: str):
    accumulators = runPipeline(hdfsLogPath, PipelineConfig.fromCli())
    assert accumulators.eventCounter.totalEvents > 0
    assert accumulators.quarantineTracker.rate < 0.5
