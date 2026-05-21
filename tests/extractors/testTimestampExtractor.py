import pytest
from datetime import datetime, timezone
from logana.models.fieldState import Known, Unknown, Absent
from logana.extractors.timestamp import TimestampExtractor


def test_iso8601Utc():
    res = TimestampExtractor().extract("2024-03-15T14:23:01Z")
    assert isinstance(res, Known)
    assert res.value == datetime(2024, 3, 15, 14, 23, 1, tzinfo=timezone.utc)
    assert res.meta["timestampSource"] == "explicit_offset"


def test_clfTimestamp():
    res = TimestampExtractor().extract("[10/Oct/2000:13:55:36 -0700]")
    assert isinstance(res, Known)
    assert res.value.year == 2000
    assert res.value.tzinfo is not None


def test_syslogInferredYear():
    res = TimestampExtractor().extract("Oct 11 13:14:15")
    assert isinstance(res, Known)
    assert res.meta["timestampSource"] == "syslog_inferred"


def test_invalidToken():
    assert isinstance(TimestampExtractor().extract("not-a-timestamp"), Absent)


def test_outOfRangeYearIsUnknown():
    assert isinstance(TimestampExtractor().extract("2099-03-15T14:23:01Z"), Unknown)
