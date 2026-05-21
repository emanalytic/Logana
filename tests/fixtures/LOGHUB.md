# LogHub evaluation results

This is the **official evaluation report** for logana. All numbers come from real logs in this folder

**Source:** [logpai/loghub](https://github.com/logpai/loghub) — 2,000-line samples per system.  
**How to reproduce:**

```bash
poetry run python scripts/benchmarkFixtures.py
poetry run pytest -q tests/integration/testLoghubCorpus.py
```

Benchmark date: run locally after LogHub-only fixture set (Poetry env, default quarantine threshold `0.3`).

---

## Summary table

| Log file | Lines | Accepted | Quarantine | Error rate* | Latency n | Verdict |
|----------|------:|---------:|-----------:|--------------:|----------:|---------|
| **OpenStack_2k.log** | 2000 | **100%** | 0% | 0% | 0† | **Excellent** — best overall fit |
| **Apache_2k.log** | 2000 | **100%** | 0% | 30% | 0 | **Strong** — errors clustered; use `--reference-date 2005-12-04` |
| **Linux_2k.log** | 2000 | **96%** | 4% | 24% | 0 | **Strong** — syslog + kv; use `--reference-date 2004-06-15` |
| **OpenSSH_2k.log** | 2000 | **94%** | 6% | 53% | 0 | **Strong** — auth failures surfaced clearly |
| **Hadoop_2k.log** | 2000 | **83%** | 17% | 9% | 0 | **Good** — mixed YARN text + delimited |
| **HDFS_2k.log** | 2000 | **52%** | 49% | 0.2% | 0 | **Partial** — HDFS date works; many block lines low confidence |
| **HealthApp_2k.log** | 2000 | **39%** | 61% | 0.3% | 0 | **Weak** — pipe format; timestamp gaps |
| **Spark_2k.log** | 2000 | **0%** | 100% | — | 0 | **Fail** — `17/06/09` date style not implemented |
| **Proxifier_2k.log** | 2000 | **0%** | 100% | — | 0 | **Fail** — Proxifier table layout not implemented |

\* Error rate = share of **accepted** events flagged as errors (log level or HTTP 5xx).  
† OpenStack lines include `time: 0.24…` in text but not mapped to `responseTimeMs` yet.

---

## Per-file notes (what we checked)

### OpenStack_2k.log — **Excellent**

- **Format:** Nova API (`nova-api.log…` + ISO timestamp + HTTP request + `status:` + `time:`).
- **Parser path:** `tokenExtractor` on all 2,000 lines; timestamps and URL paths extracted reliably.
- **Quarantine:** 0% — every line accepted.
- **Useful metrics:** Busiest path `/v2/…/servers/detail` (~698 hits); log span ~15 minutes wall time.
- **Gap:** `time:` seconds in log text not promoted to latency digest (no structured `duration` field).

```bash
poetry run logana tests/fixtures/OpenStack_2k.log --log-timezone UTC --format dashboard
```

### Apache_2k.log — **Strong**

- **Format:** Apache httpd error log `[Sun Dec 04 … 2005] [error] …`.
- **Quarantine:** 0%; **error rate ~30%** matches visible `[error]` / mod_jk noise.
- **Clusters:** 8 templates (e.g. mod_jk child worker errors).
- **CLI:** `--reference-date 2005-12-04` keeps syslog-style years stable.

### Linux_2k.log — **Strong**

- **Format:** Linux syslog (2004) + some `key=value` segments.
- **Quarantine:** ~4%; format drift detected mid-file (kv → token).
- **Error rate ~24%** (e.g. `authentication failure`, ftpd).
- **CLI:** `--reference-date 2004-06-15`.

### OpenSSH_2k.log — **Strong**

- **Format:** OpenSSH/PAM auth logs.
- **Quarantine:** ~6%; **error rate ~53%** — expected for failed logins.
- **Top pattern:** `pam_unix(sshd:auth): authentication failure` (~384×).
- Good demo for **security / auth** log review.

### Hadoop_2k.log — **Good**

- **Format:** YARN/MapReduce (`2015-10-18 … ERROR [RMCommunicator …]`).
- **Accepted:** ~83%; quarantine mostly **field confidence below threshold** on noisy tails.
- **Error rate ~9%**; 6 error clusters.
- Delimited + token fallback carries most structure.

### HDFS_2k.log — **Partial**

- **Format:** `081109 203615 148 INFO dfs.DataNode$…` (YYMMDD HHMMSS).
- **Accepted:** ~52%; half quarantined on short/terminating block lines.
- **Timestamps:** HDFS regex + token scan work on INFO lines; span ~2 days 2008.
- **Errors:** Very low rate (0.2%) — datanode INFO-heavy file.

### HealthApp_2k.log — **Weak**

- **Format:** `20171223-22:15:29:606|…|…|…` pipe-delimited mobile app logs.
- **Accepted:** ~39%; **61% quarantine** — mostly missing/invalid timestamp on continuation lines.
- Delimited parser hits ~776 lines; not enough for latency/HTTP analytics.

### Spark_2k.log — **Fail (known gap)**

- **Format:** `17/06/09 20:10:40 INFO executor.…` (two-digit year path).
- **100% quarantine** — no timestamp parser for this layout yet.
- **Next fix:** add Spark/Java log date pattern to `timestamp.py`.

### Proxifier_2k.log — **Fail (known gap)**

- **Format:** Windows Proxifier connection table (not syslog/CLF/JSON).
- **100% quarantine** — no dedicated profile.
- **Next fix:** optional Proxifier column parser or skip in docs.

---

## Overall assessment

| Capability | On LogHub corpus |
|------------|------------------|
| Streaming 2k lines/sec | Yes (~1.4k–4.1k lines/s in benchmark) |
| Zero-quarantine parse | **OpenStack**, **Apache** |
| High quarantine visibility | Yes — reasons tracked (timestamp, confidence) |
| Error clustering (Drain3) | Strong on Apache, Linux, OpenSSH, Hadoop |
| HTTP path / endpoint stats | Strong on **OpenStack**; weak on non-HTTP logs |
| Latency percentiles | **Not shown** on LogHub set (no consistent `duration` field) |
| Mixed format in one repo folder | N/A — one file per format; drift seen inside Linux |

**Bottom line:** logana is **production-useful** on **OpenStack, Apache, Linux, and OpenSSH** LogHub samples. It is **exploratory / partial** on HDFS and HealthApp, and **not ready** for Spark or Proxifier without new parsers.

---

## Recommended commands

```bash
# Best first run (0% quarantine)
poetry run logana tests/fixtures/OpenStack_2k.log --log-timezone UTC

# Error-heavy security log
poetry run logana tests/fixtures/OpenSSH_2k.log --log-timezone UTC

# Historical syslog
poetry run logana tests/fixtures/Linux_2k.log --reference-date 2004-06-15

# Full table
poetry run python scripts/benchmark_fixtures.py
```
