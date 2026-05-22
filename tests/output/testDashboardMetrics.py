from logana.analytics.accumulatorSet import AccumulatorSet
from logana.output.dashboard import _Glyphs, _overview, _weakest_fields, Dashboard
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


def test_glyphsUseUnicodeSparklineWhenEncodingSupportsIt(monkeypatch):
    class DummyStdout:
        encoding = "utf-8"

    monkeypatch.setattr("sys.stdout", DummyStdout())

    glyphs = _Glyphs.for_stdout()

    assert glyphs.spark == "▁▂▃▄▅▆▇█"


def test_endpointTableUsesRichOverflowForPaths():
    acc = AccumulatorSet()
    dashboard = Dashboard(acc)
    table = dashboard._endpoint_table(
        [
            type(
                "Stat",
                (),
                {
                    "endpoint": "/api/very/long/path/that/should/not/be/manual/truncated",
                    "count": 10,
                    "errorRate": 0.2,
                    "p99Latency": 120.0,
                    "trend": "STABLE",
                },
            )()
        ],
        "empty",
    )

    assert table.columns[0].overflow == "ellipsis"
