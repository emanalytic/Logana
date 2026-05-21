# LogHub benchmark results

This document explains how **logana** performs on real log files from the public [LogHub](https://github.com/logpai/loghub) dataset. Each fixture file contains 2,000 lines from a different system (Apache, Linux syslog, OpenStack, Zookeeper, Spark, and others).

The purpose of these tests is **evaluation**, not a promise to parse every format perfectly.

---

## How to reproduce the numbers

```bash
poetry run python scripts/benchmarkFixtures.py
poetry run pytest -q tests/integration/testLoghubCorpus.py
```

The benchmark script runs with default settings:

- **`--profile pragmatic`** — a line is accepted if it has a usable timestamp. Weak guesses on optional fields (HTTP status, latency, and so on) do not cause rejection.
- **Automatic reference-year detection** — the pipeline reads the first ~400 lines and infers a year when syslog-style lines omit one.

---

## How logana parses these files

logana does not maintain a custom parser for each LogHub filename. Instead it uses a small set of **format families** that apply across many systems:

| Component | What it does |
|-----------|----------------|
| **Structured parsers** | When a line clearly matches JSON, Apache Combined Log Format (CLF), syslog, key=value (logfmt), or tab/comma-separated fields, a dedicated parser runs first. |
| **Token scanner** | For everything else, the tool splits the line into tokens and looks for timestamps, IP addresses, HTTP methods, status codes, and similar fields. |
| **Line patterns** | On the full line text, it also looks for common patterns such as `status: 200`, `time: 0.24`, `level: ERROR`, and quoted HTTP requests like `"GET /path HTTP/1.1"`. |
| **Timestamp rules** | Explicit patterns cover ISO dates, CLF dates, syslog without a year, HDFS-style `YYMMDD`, compact pipe timestamps (`20171223-22:15:29:606`), bracket wall-clock times (`[10.30 16:49:06]`), and short Java-style dates (`17/06/09`). A fuzzy date parser is used only after those rules. |
| **Quarantine gate** | Lines without a confident timestamp are stored separately with a written reason. Optional fields can be missing without rejecting the line (under the pragmatic profile). |

**What its optimize for:** one pass over the file, bounded memory, and logs that look like web access logs, syslog, JSON lines, or API-style text (for example OpenStack nova).

**What it do not claim:** full semantic understanding of every vendor-specific layout (mobile app pipes, proxy column tables, and similar formats may parse partially or with wrong inferred years).

---

## Results (pragmatic profile, automatic year detection)

| Log file | Lines accepted | Lines quarantined | Error rate* | Assessment |
|----------|---------------:|------------------:|------------:|------------|
| **OpenStack_2k.log** | 100% | 0% | ~0% | **Strong fit** — API-style lines; over 1,000 latency samples from `time:` fields |
| **Apache_2k.log** | 100% | 0% | ~30% | **Strong fit** — bracketed Apache error log; year inferred from file content |
| **Linux_2k.log** | 100% | 0% | ~27% | **Strong fit** — syslog and key=value lines |
| **OpenSSH_2k.log** | 100% | 0% | ~55% | **Strong fit** — many failed logins are counted as errors by design |
| **Hadoop_2k.log** | 100% | 0% | ~8% | **Strong fit** |
| **Zookeeper_2k.log** | 100% | 0% | ~1% | **Strong fit** — Java `YYYY-MM-DD HH:MM:SS,mmm` prefix; WARN-heavy quorum logs |
| **HDFS_2k.log** | 100% | 0% | ~0% | **Strong fit** — HDFS `YYMMDD` timestamps |
| **Spark_2k.log** | 100% | 0% | ~1% | **Partial** — timestamps parse via `YY/MM/DD`; Spark-specific fields are not modeled |
| **Proxifier_2k.log** | 100% | 0% | ~7% | **Partial** — bracket timestamps parse; inferred calendar year can be wrong |
| **HealthApp_2k.log** | ~79% | ~21% | ~0% | **Mixed** — most lines use compact pipe timestamps; the remainder lack a parseable time |

\* **Error rate** is calculated only over **accepted** lines, not over quarantined lines.

Run `poetry run python scripts/benchmarkFixtures.py` after code changes to refresh these figures on your machine.

---

## What the assessment labels mean

- **Strong fit** — The log shape matches what the tool was designed for. Metrics such as error rate and time span are meaningful for that file.
- **Partial** — Most lines are accepted and receive a timestamp, but the tool does not fully represent that system’s semantics. Treat time ranges and endpoint labels as approximate, especially when year inference is uncertain.
- **Mixed** — A noticeable share of lines still cannot be timed. Inspect quarantine reasons in the summary output to see why.

A high **error rate** on OpenSSH does not mean parsing failed. It means many lines describe authentication failures, which the error classifier flags intentionally.

---

## Quarantine profiles

You can change how strict acceptance is with `--profile`:

| Profile | Behavior |
|---------|----------|
| **pragmatic** (default) | Reject a line only when the timestamp is missing or too uncertain. |
| **strict** | Also reject when optional fields have low confidence, or when average field confidence falls below the threshold. |
| **forensics** | Same as pragmatic for field rules, but assigns a low-confidence “ingestion time” when no timestamp is found so more lines enter analytics. |

Examples:

```bash
poetry run logana tests/fixtures/HealthApp_2k.log --profile strict
poetry run logana tests/fixtures/Spark_2k.log --profile forensics
```

---

## Practical guidance

| Goal | Suggested approach |
|------|-------------------|
| Compare logana to another tool fairly | Separate **strong fit** files from **partial** or **mixed** ones; do not expect one parse percentage across all fixture files. |
| Tighten data quality | Use `--profile strict` or raise `--quarantine-threshold`. |
| Accept more lines for exploration | Use `--profile forensics` and read the summary warnings about synthetic timestamps. |
| Fix syslog years | Pass `--reference-date YYYY-MM-DD`, or rely on automatic sniffing plus anchors learned while reading the file. |
| Support a new log shape | Add one parser or extractor for a **class** of lines (for example “bracket wall clock without year”), not a regex named after a single LogHub file. |

---

## Example commands

```bash
poetry run logana tests/fixtures/OpenStack_2k.log --log-timezone UTC
poetry run logana tests/fixtures/Zookeeper_2k.log --log-timezone UTC
poetry run logana tests/fixtures/Linux_2k.log --reference-date 2004-06-15
poetry run python scripts/benchmarkFixtures.py
```

---

## Automated tests

`tests/integration/testLoghubCorpus.py` checks minimum acceptance rates and quarantine ceilings for in-scope files (including Zookeeper). Tests for Spark and Proxifier only verify that the pipeline processes all 2,000 lines without crashing—they do not require 100% quarantine, because generic timestamp rules may accept those lines.
