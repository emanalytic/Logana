from logana.pipeline.formatProbe import probeFormat, FormatHint, hasConsistentDelimiter

def test_probe_json():
    hint, conf = probeFormat('{"timestamp": "2024-01-01T00:00:00Z"}')
    assert hint == FormatHint.JSON
    assert conf >= 0.9

def test_probe_syslog():
    hint, conf = probeFormat("<34>Oct 11 22:14:15 host msg")
    assert hint == FormatHint.SYSLOG
    assert conf >= 0.8

def test_probe_clf():
    line = '127.0.0.1 - - [10/Oct/2000:13:55:36 -0700] "GET / HTTP/1.1" 200 2326'
    hint, conf = probeFormat(line)
    assert hint == FormatHint.CLF
    assert conf >= 0.8

def test_probe_kv():
    line = 'time=2024-01-01T00:00:00Z level=info msg=ok ip=1.2.3.4 status=200'
    hint, conf = probeFormat(line)
    assert hint == FormatHint.KV
    assert conf >= 0.7

def test_probe_delimited_two_separators():
    line = "2024-01-01|10.0.0.1|GET"
    assert hasConsistentDelimiter(line) is True
    hint, conf = probeFormat(line)
    assert hint == FormatHint.DELIMITED

def test_probe_unknown():
    hint, conf = probeFormat("totally unstructured text")
    assert hint == FormatHint.UNKNOWN
    assert conf == 0.0
