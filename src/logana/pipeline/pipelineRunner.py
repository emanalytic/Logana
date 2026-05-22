from collections import deque
from typing import Callable, Deque, Optional
from logana.analytics.accumulatorSet import AccumulatorSet
from logana.pipeline.pipelineConfig import PipelineConfig
from logana.pipeline.lineBoundary import LineBoundaryDetector
from logana.pipeline.parserDispatch import ParserDispatch
from logana.pipeline.fileSniff import sniffReferenceYear
from logana.pipeline.quarantineGate import QuarantineGate
from logana.pipeline.streamReader import streamReader


def runPipeline(
    filePath: str,
    config: PipelineConfig,
    onProgress: Optional[Callable[[], None]] = None,
    accumulators: Optional[AccumulatorSet] = None,
) -> AccumulatorSet:
    """Runs ingest -> parse -> quarantine -> accumulators for one log file."""
    if accumulators is None:
        accumulators = AccumulatorSet(max_endpoints=config.maxEndpoints)
    time_context = config.resolvedTimeContext()
    if time_context.reference_year is None:
        inferred = sniffReferenceYear(filePath, encoding=config.encoding)
        if inferred is not None:
            time_context.reference_year = inferred

    boundary = LineBoundaryDetector()
    dispatcher = ParserDispatch(
        quarantineThreshold=config.quarantineThreshold,
        time_context=time_context,
    )
    gate = QuarantineGate(
        quarantine_threshold=config.quarantineThreshold,
        allow_synthetic_timestamps=config.allowSyntheticTimestamps,
        profile=config.quarantineProfile,
    )

    contextBuffer: Deque[str] = deque(maxlen=config.contextLines)

    for groupText, startLine in boundary.detectBoundaries(
        streamReader(filePath, encoding=config.encoding)
    ):
        parseResult = dispatcher.dispatch(groupText, startLine)
        context = list(contextBuffer)
        routed = gate.route(parseResult, contextBefore=context)
        accumulators.ingest(routed)
        contextBuffer.append(groupText[:200])
        if onProgress is not None:
            onProgress()

    accumulators.errorRate.finalize()
    accumulators.quarantineTracker.finalize()
    return accumulators
