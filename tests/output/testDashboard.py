from logana.analytics.accumulatorSet import AccumulatorSet
from logana.output.dashboard import Dashboard
from helpers.eventFactory import buildLogEvent


def test_dashboardLayoutRenders():
    accumulators = AccumulatorSet()
    accumulators.ingest(buildLogEvent(responseTimeMs=45.0))
    dashboard = Dashboard(accumulators)
    dashboard.redrawInterval = 0.0
    dashboard.update()
    assert dashboard.layout["header"] is not None
    assert dashboard.layout["alerts"] is not None
    assert dashboard.layout["snapshot"] is not None
    assert dashboard.layout["byVolume"] is not None
    assert dashboard.layout["footer"] is not None


def test_dashboardReusesTablesWhenDataIsUnchanged():
    accumulators = AccumulatorSet()
    accumulators.ingest(
        buildLogEvent(
            logLevel="ERROR",
            message="boom",
            urlPath="/api/very/long/path/that/should/not/be/manual/truncated",
            responseTimeMs=120.0,
        )
    )
    dashboard = Dashboard(accumulators)
    dashboard.redrawInterval = 0.0

    dashboard.update()
    error_table = dashboard._errorTableRenderable
    volume_table = dashboard._endpointVolumeRenderable
    error_endpoint_table = dashboard._endpointErrorsRenderable

    dashboard.update()

    assert dashboard._errorTableRenderable is error_table
    assert dashboard._endpointVolumeRenderable is volume_table
    assert dashboard._endpointErrorsRenderable is error_endpoint_table
