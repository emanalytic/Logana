# LogHub evaluation results

Real-world **benchmark corpus** for logana — not a checklist of parsers to implement.

**Source:** [logpai/loghub](https://github.com/logpai/loghub) (2,000 lines per system).

```bash
poetry run python scripts/benchmarkFixtures.py
poetry run pytest -q tests/integration/testLoghubCorpus.py
```

Default run uses **`--profile pragmatic`** (timestamp required; optional fields do not drive quarantine) and **auto reference-year sniffing** from the first ~400 lines (no per-file CLI tables in the benchmark script).

---

## How to read these numbers (important)

We **do not** add a dedicated parser every time a LogHub file scores poorly. That would never end.

logana is built around a **small set of format families**:

| Layer | Role |
|-------|------|
| **JSON / CLF / syslog / logfmt / delimited** | Structured parsers when the line shape matches |
| **tokenExtractor + linePatterns** | Generic `status:`, `time:`, `level:`, HTTP request snippets on the full line |
| **timestamp families** | ISO, CLF, syslog, HDFS, compact pipe, bracket wall clock, short `YY/MM/DD`, dateutil fallback |
| **quarantineGate** | Profile-controlled: pragmatic = **timestamp only** |

LogHub files are **evaluation targets**. A low score usually means “outside the design center,” not “add Spark_2k regex tomorrow.”

**Design center:** one pass, bounded RAM, HTTP-ish and ops text logs (access logs, syslog, JSON lines, OpenStack-style API logs).

---

## Summary table (pragmatic profile, auto year sniff)

| Log file | Accepted | Quarantine | Error rate* | Verdict |
|----------|----------:|-----------:|--------------:|---------|
| **OpenStack_2k.log** | 100% | 0% | ~0% | **In scope** — `status:` / `time:` line patterns; 1k+ latency samples |
| **Apache_2k.log** | 100% | 0% | ~30% | **In scope** — bracketed error log (year sniffed) |
| **Linux_2k.log** | 100% | 0% | ~27% | **In scope** — syslog/kv |
| **OpenSSH_2k.log** | 100% | 0% | ~55% | **In scope** — auth failures (high error % is real) |
| **Hadoop_2k.log** | 100% | 0% | ~8% | **In scope** |
| **HDFS_2k.log** | 100% | 0% | ~0% | **In scope** — `YYMMDD` family |
| **Spark_2k.log** | 100% | 0% | ~1% | **Partial** — `YY/MM/DD` family accepts lines; not full Spark semantics |
| **Proxifier_2k.log** | 100% | 0% | ~7% | **Partial** — bracket wall-clock family; year inference can be wrong |
| **HealthApp_2k.log** | ~79% | ~21% | ~0% | **Mixed** — compact pipe timestamps on most lines |

\* Error rate is over **accepted** events only.

Re-run `benchmarkFixtures.py` after changes; numbers above are from the current tree.

---

## Profiles

| Profile | Behavior |
|---------|----------|
| **pragmatic** (default) | Quarantine only on missing/weak **timestamp** |
| **strict** | Also quarantine on low-confidence optional fields and low mean confidence |
| **forensics** | Like pragmatic, but enables synthetic ingestion timestamps when time is missing |

```bash
poetry run logana tests/fixtures/HealthApp_2k.log --profile strict
poetry run logana tests/fixtures/Spark_2k.log --profile forensics
```

---

## What to do instead of per-file parsers

| If you need… | Do this |
|--------------|---------|
| **Fair benchmark** | Report in-scope vs partial vs unsupported semantics |
| **Stricter quality bar** | `--profile strict` |
| **Maximum line count** | `--profile forensics` (understand synthetic time) |
| **Syslog year** | `--reference-date` or rely on sniff + anchors in stream |
| **New format family** | One extractor/parser for a **class** of lines — not per LogHub filename |

---

## Recommended commands

```bash
poetry run logana tests/fixtures/OpenStack_2k.log --log-timezone UTC
poetry run logana tests/fixtures/Linux_2k.log --reference-date 2004-06-15
poetry run python scripts/benchmarkFixtures.py
```

---

## Tests

`tests/integration/testLoghubCorpus.py` — bounds for in-scope files; Spark/Proxifier tests only assert the pipeline runs (no “must quarantine 100%” goal).
