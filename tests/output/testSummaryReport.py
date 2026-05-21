from logana.analytics.accumulatorSet import AccumulatorSet
from logana.output.summaryReport import generateSummary
from helpers.eventFactory import buildLogEvent, buildQuarantineEntry


def test_summaryIncludesKeyMetrics():
    accumulators = AccumulatorSet()
    accumulators.ingest(buildLogEvent(lineNumber=1, responseTimeMs=45.0))
    accumulators.ingest(buildLogEvent(lineNumber=2, responseTimeMs=90.0, logLevel="ERROR", message="NullPointer"))
    accumulators.ingest(buildQuarantineEntry(lineNumber=3))

    summary = generateSummary(accumulators)
    assert "Log ingestion processed 3 lines" in summary
    assert "error rate of 50.00%" in summary
    assert "median response time" in summary


def test_summaryWhenNoLatencyData():
    accumulators = AccumulatorSet()
    accumulators.ingest(
        buildLogEvent(responseTimeMs=None, urlPath="", parserId="syslog", message="kernel: boot ok")
    )
    summary = generateSummary(accumulators)
    assert "No response-time data" in summary
