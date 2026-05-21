# Test fixtures (LogHub only)

All files here are **2,000-line samples** from the public [LogHub](https://github.com/logpai/loghub) dataset — real production-style logs, not synthetic samples.

**Evaluation write-up:** [LOGHUB.md](LOGHUB.md) — parse rates, error detection, and what works vs what does not.

| File | Run hint |
|------|----------|
| `OpenStack_2k.log` | `poetry run logana tests/fixtures/OpenStack_2k.log --log-timezone UTC` |
| `Linux_2k.log` | add `--reference-date 2004-06-15` |
| `Apache_2k.log` | add `--reference-date 2005-12-04` |
| `OpenSSH_2k.log` | `--log-timezone UTC` |
| `HDFS_2k.log`, `Hadoop_2k.log`, `HealthApp_2k.log` | `--log-timezone UTC` |

Re-run the benchmark table:

```bash
poetry run python scripts/benchmark_fixtures.py
```

Tests: `tests/integration/testLoghubCorpus.py`
