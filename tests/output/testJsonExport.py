import json
from logana.analytics.accumulatorSet import AccumulatorSet
from logana.output.jsonExport import exportToJson
from helpers.eventFactory import buildLogEvent, buildQuarantineEntry


def test_jsonExportStructure():
    accumulators = AccumulatorSet()
    accumulators.ingest(buildLogEvent(lineNumber=1, responseTimeMs=120.0, logLevel="INFO"))
    accumulators.ingest(buildLogEvent(lineNumber=2, responseTimeMs=350.0, logLevel="ERROR", urlPath="/api/login", message="DB Timeout"))
    accumulators.ingest(buildQuarantineEntry(lineNumber=3))

    data = json.loads(exportToJson(accumulators))
    assert data["summary"]["totalEvents"] == 2
    assert data["summary"]["totalQuarantined"] == 1
    assert data["latency"]["min"] == 120.0
    assert any(e["endpoint"] == "/api/login" for e in data["endpoints"])
    assert data["latency"]["available"] is True
