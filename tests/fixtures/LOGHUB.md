# LogHub evaluation results

This is the **official evaluation report** for logana. All numbers come from real logs in this folder

**Source:** [logpai/loghub](https://github.com/logpai/loghub) — 2,000-line samples per system.  
**How to reproduce:**

```bash
poetry run python scripts/benchmarkFixtures.py
poetry run pytest -q tests/integration/testLoghubCorpus.py
```

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


