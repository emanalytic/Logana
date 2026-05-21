from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from logana.extractors.timestamp import TimestampExtractor
from logana.pipeline.timeContext import PipelineTimeContext, utcTimeContext
from logana.models.fieldState import Known
from logana.utils.timeUtils import (
    TimestampNormalizer,
    TIMESTAMP_SOURCE_EXPLICIT,
    TIMESTAMP_SOURCE_LOCAL,
)

@pytest.fixture
def chicago_context():
    try:
        tz = ZoneInfo("America/Chicago")
    except Exception:
        pytest.skip("tzdata not available for America/Chicago")
    return PipelineTimeContext(default_tz=tz, naive_policy="local")

def test_iso_z_stays_utc(chicago_context):
    ext = TimestampExtractor(chicago_context)
    res = ext.extract("2024-03-15T14:23:01Z")
    assert isinstance(res, Known)
    assert res.value.tzinfo is not None
    assert res.value.tzinfo == timezone.utc
    assert res.meta["timestampSource"] == TIMESTAMP_SOURCE_EXPLICIT

def test_naive_plain_uses_local_timezone(chicago_context):
    ext = TimestampExtractor(chicago_context)
    res = ext.extract("2024-03-15 14:23:03")
    assert isinstance(res, Known)
    assert res.meta["timestampSource"] == TIMESTAMP_SOURCE_LOCAL
    assert res.value.tzinfo == timezone.utc
    # 14:23 America/Chicago (CDT, UTC-5) -> 19:23 UTC
    assert res.value.hour == 19
    assert res.value.minute == 23

def test_naive_as_utc_policy():
    ctx = utcTimeContext()
    ext = TimestampExtractor(ctx)
    res = ext.extract("2024-03-15 14:23:03")
    assert isinstance(res, Known)
    assert res.value == datetime(2024, 3, 15, 14, 23, 3, tzinfo=timezone.utc)

def test_java_bracket_timestamp(chicago_context):
    ext = TimestampExtractor(chicago_context)
    res = ext.extract("[2024-03-15 14:23:03,456] ERROR msg")
    assert isinstance(res, Known)
    assert res.meta["timestampSource"] == TIMESTAMP_SOURCE_LOCAL

def test_clf_offset_is_explicit(chicago_context):
    ext = TimestampExtractor(chicago_context)
    res = ext.extract("[10/Oct/2000:13:55:36 -0700]")
    assert isinstance(res, Known)
    assert res.meta["timestampSource"] == TIMESTAMP_SOURCE_EXPLICIT
    assert res.value.tzinfo is not None

def test_syslog_uses_default_tz_not_utc(chicago_context):
    ctx = PipelineTimeContext(
        default_tz=chicago_context.default_tz,
        naive_policy="local",
        reference_year=2024,
    )
    ext = TimestampExtractor(ctx)
    res = ext.extract("Oct 11 13:14:15")
    assert isinstance(res, Known)
    assert res.meta["timestampSource"] == "syslog_inferred"
    assert res.value.tzinfo == timezone.utc
    assert res.value.year == 2024

def test_apache_error_log_timestamp(chicago_context):
    ext = TimestampExtractor(chicago_context)
    res = ext.extract("[Sun Dec 04 04:47:44 2005] [error] mod_jk child workerEnv in error state 6")
    assert isinstance(res, Known)
    assert res.value.year == 2005
    assert res.value.month == 12
    assert res.value.day == 4
    assert res.meta["timestampSource"] == TIMESTAMP_SOURCE_LOCAL


def test_hdfs_compact_timestamp():
    ext = TimestampExtractor(utcTimeContext())
    res = ext.extract("081109 203615 148 INFO dfs.DataNode$PacketResponder: terminating")
    assert isinstance(res, Known)
    assert res.value == datetime(2008, 11, 9, 20, 36, 15, tzinfo=timezone.utc)


def test_normalizer_never_returns_naive(chicago_context):
    normalizer = TimestampNormalizer(chicago_context)
    naive = datetime(2024, 6, 1, 12, 0, 0)
    utc_dt, _, source = normalizer.normalize(naive, TIMESTAMP_SOURCE_LOCAL, 0.9)
    assert utc_dt.tzinfo is not None
    assert source == TIMESTAMP_SOURCE_LOCAL
