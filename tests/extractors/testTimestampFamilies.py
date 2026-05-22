
from logana.extractors.timestamp import TimestampExtractor
from logana.models.fieldState import isKnown
from logana.pipeline.timeContext import PipelineTimeContext
from logana.utils.timeUtils import resolveLocalTimezone


def _extract(line: str, *, year: int | None = None):
    ctx = PipelineTimeContext(default_tz=resolveLocalTimezone(), reference_year=year)
    return TimestampExtractor(ctx).extract(line)


def test_compactPipeTimestamp():
    result = _extract("20171223-22:15:29:606 | com.test App")
    assert isKnown(result)
    assert result.value.year == 2017
    assert result.value.month == 12
    assert result.value.day == 23


def test_bracketWallTimestampUsesReferenceYear():
    result = _extract("[10.30 16:49:06] host open", year=2016)
    assert isKnown(result)
    assert result.value.year == 2016
    assert result.value.month == 10
    assert result.value.day == 30


def test_shortSlashYearTimestamp():
    result = _extract("17/06/09 20:10:00 INFO spark.Executor")
    assert isKnown(result)
    assert result.value.year == 2017
    assert result.value.month == 6
    assert result.value.day == 9
