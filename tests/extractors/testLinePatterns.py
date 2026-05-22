from logana.extractors.linePatterns import TIME_KV_RE, _parseTimeKv
from logana.extractors.linePatterns import applyLinePatterns
from logana.models.fieldState import isKnown
from logana.parsers.fieldKit import ParserFieldKit


def test_openstackLineExtractsStatusAndTime():
    line = (
        "2017-07-03 23:34:19.392 257 INFO nova.compute "
        "[req-abc] status: 200 time: 0.2477829"
    )
    kit = ParserFieldKit()
    fields = kit.emptyStandardFields()
    applyLinePatterns(fields, kit, line)
    assert isKnown(fields["statusCode"])
    assert fields["statusCode"].value == 200
    assert isKnown(fields["responseTimeMs"])
    assert abs(fields["responseTimeMs"].value - 247.78) < 1.0


def test_timeKvBare500TreatedAsMilliseconds():
    match = TIME_KV_RE.search("status: 200 duration_ms: 500")
    assert match is not None
    parsed = _parseTimeKv(match)
    assert parsed is not None
    assert parsed[0] == 500.0


def test_timeKvBareSecondsForTimeKey():
    match = TIME_KV_RE.search("status: 200 time: 0.24")
    assert match is not None
    parsed = _parseTimeKv(match)
    assert parsed is not None
    assert abs(parsed[0] - 240.0) < 1.0


def test_httpInlineRequest():
    line = '127.0.0.1 - - [04/Dec/2005:13:30:00] "GET /index.html HTTP/1.1" 200'
    kit = ParserFieldKit()
    fields = kit.emptyStandardFields()
    applyLinePatterns(fields, kit, line)
    assert isKnown(fields["httpMethod"])
    assert fields["httpMethod"].value == "GET"
    assert isKnown(fields["urlPath"])
    assert fields["urlPath"].value == "/index.html"
