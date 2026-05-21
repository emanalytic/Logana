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
    assert dashboard.layout["footer"] is not None
