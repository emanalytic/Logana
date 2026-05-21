# Test fixtures

| File | Format | Notes |
|------|--------|-------|
| `complex.log` | Mixed (CLF, JSON, syslog, logfmt, stack trace) | Primary integration sample |
| `sample1.log` | Mixed app logs | Similar to `complex.log` |
| `sample2.log` | CLF access log (synthetic) | Best for endpoint/latency dashboard checks |
| `sample3.log` | Format edge cases | Multi-line JSON, TSV, epoch, bracketed logs |
| `sample4.log` | IIS W3C + XML + CEF | IIS lines parse; XML/CEF are expected quarantine |
| `Apache_2k.log` | Apache error log (2005) | Use `--reference-date 2005-12-04` if syslog year drifts |
| `Linux_2k.log` | Linux syslog (2004) | Use `--reference-date 2004-06-15` for correct years |

Example:

```bash
poetry run logana tests/fixtures/sample2.log --format dashboard
poetry run logana tests/fixtures/Linux_2k.log --reference-date 2004-06-15
```
