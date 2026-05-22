from logana.analytics.accumulatorSet import AccumulatorSet
from logana.output.dashboard import _overview, _weakest_fields
from helpers.eventFactory import buildLogEvent, buildQuarantineEntry


def test_overview_matches_event_counter():
    acc = AccumulatorSet()
    acc.ingest(buildLogEvent(lineNumber=1))
    acc.ingest(buildLogEvent(lineNumber=2))
    acc.ingest(buildQuarantineEntry(lineNumber=3, reason="Missing timestamp"))

    ov = _overview(acc)
    assert ov.lines == 3
    assert ov.accepted == 2
    assert ov.quarantined == 1
    assert abs(ov.accept_pct - 200 / 3) < 0.1
    assert abs(ov.quarantine_pct - 100 / 3) < 0.1
    assert abs(ov.accept_pct + ov.quarantine_pct - 100.0) < 0.1


def test_weakest_fields_sorted_by_known_rate():
    acc = AccumulatorSet()
    acc.ingest(buildLogEvent(urlPath="/a", responseTimeMs=None))
    acc.ingest(buildLogEvent(urlPath="/b", statusCode=500, logLevel="ERROR"))

    weak = _weakest_fields(acc, limit=3)
    rates = [rate for _, rate in weak]
    assert rates == sorted(rates)
    assert len(weak) == 3
