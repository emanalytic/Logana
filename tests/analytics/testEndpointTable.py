from logana.analytics.endpointTable import EndpointTable
from helpers.eventFactory import buildLogEvent


def test_endpointVolumeAndErrorSorting():
    table = EndpointTable()
    for _ in range(10):
        table.ingest(buildLogEvent(urlPath="/api/users", responseTimeMs=20.0))
    for _ in range(5):
        table.ingest(buildLogEvent(urlPath="/api/login", responseTimeMs=100.0, logLevel="ERROR"))

    assert table.getSortedEndpoints(sortBy="volume")[0].endpoint == "/api/users"
    assert table.getSortedEndpoints(sortBy="errorRate")[0].errorRate == 1.0
