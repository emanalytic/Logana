# ANSWERS.md

Submission Q&A for **logana**. Full setup and CLI details are in [README.md](README.md).

---

## 1. How to run

### Requirements

- **Python 3.11+**
- **[Poetry](https://python-poetry.org/docs/#installation)** (recommended)

Runtime dependencies (via Poetry): `click`, `rich`, `tzdata`. Dev: `pytest`, `pytest-cov`, `pytest-asyncio`.

### Install (one time)

```bash
git clone <repo-url>
cd Log-Analyzer
poetry lock
poetry install
```

### Analyze a log

```bash
# Text report (default)
poetry run logana app.log --log-timezone Asia/Karachi

# Live terminal dashboard
poetry run logana app.log --log-timezone Asia/Karachi --format dashboard

# JSON export
poetry run logana app.log --log-timezone Asia/Karachi --format json > report.json
```

**Why `--log-timezone`?** The sample `app.log` uses `+0500` and naive local-style timestamps. Setting the zone keeps naive times aligned with how the log was written (see README → Timestamps).

**Syslog without a year** (e.g. fixture corpus):

```bash
poetry run logana tests/fixtures/Linux_2k.log --reference-date 2004-06-15
```

### Tests

```bash
poetry run pytest -q
```

Optional coverage:

```bash
poetry run pytest --cov=logana --cov-report=term-missing
```

### If install fails

| Problem | Fix |
|---------|-----|
| `poetry: command not found` | Install Poetry, open a new shell |
| Wrong Python version | `poetry env use python3.12` then `poetry install` |
| `ModuleNotFoundError: logana` | Run from project root: `poetry install` then `poetry run logana` |
| Stale CLI entry after pull | `poetry lock && poetry install` (script: `logana.cli.cliMain:main` in `pyproject.toml`) |

---

## 2. Stack choice

**Choice: Python 3.11+ CLI** (`click` + `rich` + stdlib `json` / `re` / `dataclasses`).

### Why this fits the problem

The assignment is: **read one messy file on disk and summarize it in one pass** — error rate, latency tails, top paths, quarantine reasons — without loading the whole file into RAM. That is a **local, streaming analytics** problem, not a multi-tenant log platform.

Python was the right tradeoff because I could spend time on:

- Multiple format parsers (JSON, CLF, syslog, key=value, delimited) with a shared extractor layer
- **Uncertainty per field** (`Known` / `Unknown` / `Absent`) and a quarantine gate
- Timezone normalization (`tzdata`, naive vs explicit offsets, syslog year inference)
- Bounded streaming metrics (t-digest, MAD spikes, capped endpoint table)
- A large pytest suite against fixture logs

…with **three small dependencies** and no database, Docker stack, or frontend build for a grader to stand up.

### What I did not build (on purpose)

| Alternative | Why not |
|-------------|---------|
| **Web app** | Needs upload UI, API, storage, and auth for the same one-shot analysis. More moving parts for reviewers, little extra insight into parsing design. |
| **ELK / Splunk-style stack** | Solves search and retention at fleet scale. Not a reasonable “build it yourself” scope; also hides the streaming + quarantine story this project is meant to show. |
| **C++ / Rust** | Faster per byte, but I would burn the timeline on I/O and build plumbing instead of multi-format parsers, tests, and the live dashboard. |
| **Pandas / full in-memory load** | Simple for small files; breaks the streaming memory story on multi-GB logs. |

### Tradeoffs I accept

- Throughput is “laptop good” (~10k+ lines/sec), not SIMD log-shipping speed.
- Parsers are **heuristic** — odd vendor layouts may quarantine until flags like `--log-timezone` or `--reference-date` are set.
- **Single file per run** — no cross-file history store.

---

## 3. One real edge case

### Problem: WARN/INFO text while the request actually failed (HTTP 5xx)

In production, access logs and JSON gateways often record a **soft log level** (`WARN`, `INFO`) on lines that are still **failed requests** because the HTTP status is **502/503/500**. During an outage, counting only `level=ERROR` would **under-report** the incident.

**Real examples in `app.log`:**

| Line | What it looks like | Why it matters |
|------|-------------------|----------------|
| 3–4 | Apache CLF: `POST ... checkout` → **502** / **503** (no `level` field) | Classic access log — failure is in **status**, not text level |
| 9 | JSON: `"level":"WARN"` but `"status":502` | Gateway logged a warning for an upstream timeout |
| 28–29 | Syslog/haproxy: backend lines with **502** / **503** | Same checkout failure, different format |

Counter-example (should **not** count as error): line 13 — `level=warn` with `status=200` (refresh token warning on a successful call).

### Handling

`src/logana/analytics/errorSeverity.py` — an event is an error if **either**:

1. Log level is in `{ERROR, FATAL, CRITICAL, …}`, **or**
2. HTTP status is **≥ 500** (when that field is confidently parsed)

```9:20:src/logana/analytics/errorSeverity.py
def isErrorEvent(event: LogEvent) -> bool:
    """True when log level indicates failure or HTTP status is 5xx."""
    if isinstance(event.logLevel, Known):
        if str(event.logLevel.value).upper() in _ERROR_LEVELS:
            return True

    if isinstance(event.statusCode, Known):
        code = event.statusCode.value
        if isinstance(code, int) and code >= 500:
            return True

    return False
```

### Without this rule

Error rate, error clusters, and endpoint error % would miss most of the checkout failure in `app.log` (many lines are CLF or `WARN` + 5xx).

### With this rule

CLF, JSON, logfmt, and syslog/haproxy lines all feed the **same** error metrics — closer to how ops asks “was this request bad?” not “did someone type ERROR in the string?”

---

## 4. AI usage

I used **Cursor** as an assistant while building and submitting. Below is an honest split of what AI helped with vs what I owned.

| Area | AI helped with | What I kept / changed |
|------|----------------|------------------------|
| **Sample data** | Drafting mixed-format `app.log` | Kept CLF + JSON + logfmt + stack trace + syslog mix; **removed `#` comment lines** AI added — they inflated junk-line counts |
| **Debugging packaging** | Hint to run `poetry lock` when `logana` failed to import | Real fix: **Poetry-native** `[tool.poetry.scripts]` → `logana.cli.cliMain:main` (old `cli.app` shim was stale in the venv) |
| **Docs** | First drafts of README / ANSWERS | **Rewrote** for accuracy, shorter grading path, and alignment with actual CLI flags |
| **Exploration** | “Why is quarantine high?” style questions | Used answers to tune thresholds and document stack-trace behavior in section 5 |

### Concrete example (packaging)

- **Symptom:** `poetry run logana` → `ModuleNotFoundError: logana.cli.app`
- **AI suggestion:** run `poetry lock`
- **Actual fix:** point the console script at `cliMain.py` and reinstall; lock alone did not remove the old entry-point target in the virtualenv.

### Not AI-generated (written and tested during implementation)

Streaming pipeline (`streamReader` → `lineBoundary` → `parserDispatch` → `quarantineGate` → `accumulatorSet`), parsers, extractors, field-state model, analytics trackers, JSON/summary/dashboard output, and the pytest suite under `tests/`.

**Verification:** `poetry run pytest -q` on the fixture corpus; manual runs on `app.log` and `tests/fixtures/complex.log`.

---

## 5. Honest gaps

### Primary gap: stack trace continuation lines quarantine separately

**What happens:** The header line parses as an event, e.g. in `app.log`:

```text
2025-05-21 09:00:13 [ERROR] payment-svc — Connection pool exhausted
```

Following `at com.shop...` / `Caused by:` lines are grouped with the trace (see `lineBoundary.py`) but often **lack their own timestamp**, so `quarantineGate` rejects them with a “missing timestamp” reason.

**Impact:** Error clustering and error rate on the **header** are still correct; **quarantine %** looks higher than a human expects for “one exception.”

**Next step (if I had more time):** Reuse the parent group’s timestamp for known stack continuations (same idea as multi-line JSON grouping), or tag `at ` / `Caused by` lines so they do not count as full quarantine rows in the summary.

### Secondary gaps

| Gap | Notes |
|-----|--------|
| **Vendor-specific binary / XML / CEF** | Text-first design; fixtures like `sample4.log` quarantine XML/CEF by design |
| **Cross-run history** | One file per invocation — compare two JSON exports yourself |
| **Git history granularity** | Large feature chunks; would split pipeline / parsers / analytics / tests into smaller commits before a final review |
| **Perfect timezone guessing** | Wrong `--log-timezone` still produces wrong UTC charts for naive timestamps — flags are required |

---

## Quick reference

```bash
poetry install
poetry run logana app.log --log-timezone Asia/Karachi
poetry run logana app.log --format dashboard
poetry run pytest -q
```
