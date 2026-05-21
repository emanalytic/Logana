import pytest
from datetime import datetime, timezone
from logana.models.fieldState import Known, Unknown, Absent, isKnown
from logana.models.logEvent import LogEvent
from logana.models.quarantineEntry import QuarantineEntry
from logana.parsers.parserBase import ParseResult
from logana.parsers.jsonParser import JsonParser
from logana.parsers.clfParser import ClfParser
from logana.parsers.syslogParser import SyslogParser
from logana.parsers.kvParser import KvParser
from logana.parsers.delimitedParser import DelimitedParser
from logana.parsers.tokenExtractor import TokenExtractor
from logana.pipeline.parserDispatch import ParserDispatch
from logana.pipeline.quarantineGate import QuarantineGate

def test_json_parser():
    parser = JsonParser()
    text = '{"timestamp": "2024-03-15T14:23:01Z", "ip": "192.168.1.42", "method": "GET", "path": "/api/users", "status": 200, "duration": "142ms", "level": "info", "msg": "Success"}'
    res = parser.parse(text, 1)
    
    assert res.parserId == "json"
    assert res.lineNumber == 1
    assert isKnown(res.fields["timestamp"])
    assert isKnown(res.fields["ipAddress"])
    assert res.fields["ipAddress"].value == "192.168.1.42"
    assert res.fields["statusCode"].value == 200
    assert res.fields["responseTimeMs"].value == 142.0
    assert res.fields["logLevel"].value == "INFO"

def test_json_parser_accepts_prefixed_payload():
    parser = JsonParser()
    text = 'TIEBREAKER_TAG: {"timestamp": "2024-03-15T14:23:01Z", "logLevel": "ERROR", "message": "Tagged JSON"}'
    res = parser.parse(text, 1)

    assert res.parserId == "json"
    assert isKnown(res.fields["timestamp"])
    assert res.fields["logLevel"].value == "ERROR"
    assert res.fields["message"].value == "Tagged JSON"
    assert "Ignored non-JSON prefix" in res.warnings[0]

def test_clf_parser():
    parser = ClfParser()
    # Combined Log Format
    text = '127.0.0.1 - frank [10/Oct/2000:13:55:36 -0700] "GET /api/users HTTP/1.1" 200 2326 "http://referer.com" "Mozilla/5.0"'
    res = parser.parse(text, 2)
    
    assert res.parserId == "clf"
    assert res.fields["ipAddress"].value == "127.0.0.1"
    assert res.fields["httpMethod"].value == "GET"
    assert res.fields["urlPath"].value == "/api/users"
    assert res.fields["statusCode"].value == 200

def test_syslog_parser():
    parser = SyslogParser()
    # RFC 3164
    text = '<34>Oct 11 22:14:15 mymachine su: pam_unix(su:auth): authentication failure'
    res = parser.parse(text, 3)
    
    assert res.parserId == "syslog"
    assert res.fields["logLevel"].value == "CRITICAL"  # 34 % 8 = 2 -> CRITICAL
    assert res.fields["message"].value == "su: pam_unix(su:auth): authentication failure"

    # RFC 5424
    text = '<165>1 2003-10-11T22:14:15.003Z mymachine.example.com evtsys - ID47 [exampleSDID@32473] An error occurred'
    res = parser.parse(text, 4)
    assert res.fields["logLevel"].value == "INFO"
    assert res.fields["message"].value == "An error occurred"

def test_kv_parser():
    parser = KvParser()
    text = 'time=2024-03-15T14:23:01Z level=error msg="Database unavailable" ip=10.0.0.1 status=503 duration=50ms'
    res = parser.parse(text, 5)
    
    assert res.parserId == "kv"
    assert res.fields["ipAddress"].value == "10.0.0.1"
    assert res.fields["statusCode"].value == 503
    assert res.fields["responseTimeMs"].value == 50.0
    assert res.fields["logLevel"].value == "ERROR"

def test_delimited_parser():
    parser = DelimitedParser()
    # Pipe separated
    text = '2024-03-15T14:23:01Z | 192.168.1.100 | GET | /health | 200 | 4.2ms | INFO'
    
    # First parse initializes the column mapping
    res = parser.parse(text, 6)
    assert res.parserId == "delimited"
    assert res.fields["ipAddress"].value == "192.168.1.100"
    assert res.fields["statusCode"].value == 200
    assert res.fields["responseTimeMs"].value == 4.2
    assert res.fields["logLevel"].value == "INFO"

def test_delimited_parser_reinfers_changed_schema():
    parser = DelimitedParser()
    first = '2024-03-15T14:23:01Z | 192.168.1.100 | GET | /health | 200 | 4.2ms | INFO'
    second = 'INFO | 9.5ms | 201 | /users | POST | 10.0.0.5 | 2024-03-15T14:24:01Z'

    parser.parse(first, 1)
    res = parser.parse(second, 2)

    assert res.fields["timestamp"].value.isoformat().startswith("2024-03-15T14:24:01")
    assert res.fields["ipAddress"].value == "10.0.0.5"
    assert res.fields["httpMethod"].value == "POST"
    assert res.fields["urlPath"].value == "/users"
    assert res.fields["statusCode"].value == 201
    assert res.fields["responseTimeMs"].value == 9.5

def test_token_extractor():
    parser = TokenExtractor()
    text = '2024-03-15T14:23:01Z 192.168.1.42 GET /api/users 200 142ms'
    res = parser.parse(text, 7)
    
    assert res.parserId == "tokenExtractor"
    assert res.fields["ipAddress"].value == "192.168.1.42"
    assert res.fields["httpMethod"].value == "GET"
    assert res.fields["urlPath"].value == "/api/users"
    assert res.fields["statusCode"].value == 200
    # responseTimeMs is Unknown because it's extracted from "142ms" or similar.
    # Wait, "142ms" has unit, so ResponseTimeExtractor extracts it as Known!
    assert res.fields["responseTimeMs"].value == 142.0

def test_parser_dispatch():
    dispatcher = ParserDispatch(quarantineThreshold=0.3)
    
    # 1. Valid JSON should parse directly with JsonParser
    res = dispatcher.dispatch('{"timestamp": "2024-03-15T14:23:01Z", "ip": "192.168.1.42", "level": "info", "msg": "hello"}', 8)
    assert res.parserId == "json"
    
    # 2. Ambiguous text should fall back to token extractor
    res = dispatcher.dispatch('2024-03-15T14:23:01Z 192.168.1.42 GET /api/users 200', 9)
    assert res.parserId == "tokenExtractor"

def test_quarantine_gate():
    gate = QuarantineGate(quarantineThreshold=0.3)
    
    # Valid parse result
    validFields = {
        "timestamp": Known(datetime.now(), 0.9, "now"),
        "statusCode": Known(200, 0.9, "200")
    }
    validRes = gate.route(ParseResult("test", validFields, "raw line", 10))
    assert isinstance(validRes, LogEvent)
    
    # Missing timestamp
    invalidFields = {
        "statusCode": Known(200, 0.9, "200")
    }
    quarantineRes = gate.route(ParseResult("test", invalidFields, "raw line", 11))
    assert isinstance(quarantineRes, QuarantineEntry)
    assert "Missing or invalid timestamp" in quarantineRes.reason

    # Low confidence status code
    lowConfFields = {
        "timestamp": Known(datetime.now(), 0.9, "now"),
        "statusCode": Known(200, 0.1, "200") # below 0.3 threshold
    }
    quarantineRes2 = gate.route(ParseResult("test", lowConfFields, "raw line", 12))
    assert isinstance(quarantineRes2, QuarantineEntry)
    assert "confidence" in quarantineRes2.reason

    lowConfUnknownFields = {
        "timestamp": Known(datetime.now(), 0.9, "now"),
        "statusCode": Unknown("ambiguous status", 700, 0.1)
    }
    quarantineRes3 = gate.route(ParseResult("test", lowConfUnknownFields, "raw line", 13))
    assert isinstance(quarantineRes3, QuarantineEntry)
    assert "confidence" in quarantineRes3.reason
