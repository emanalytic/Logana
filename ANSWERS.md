# ANSWERS.md

 Full setup and architecture: [README.md](README.md).

---

## 1. How to run

**You need:** Python 3.11 or newer and [Poetry](https://python-poetry.org/docs/#installation).

**Install once:**

```bash
git clone https://github.com/emanalytic/Logana
cd Log-Analyzer
poetry lock
poetry install
```

**Run on the sample log:**

```bash
poetry run logana app.log --log-timezone Asia/Karachi
poetry run logana app.log --log-timezone Asia/Karachi --format dashboard
poetry run logana app.log --log-timezone Asia/Karachi --format json > report.json
```

`--log-timezone` matters for `app.log` because many lines use local time with `+0500` or no offset. Pick the zone where the servers wrote the log (here: `Asia/Karachi`).

**Old syslog files with no year** (see `tests/fixtures/Linux_2k.log`):

```bash
poetry run logana tests/fixtures/Linux_2k.log --reference-date 2004-06-15
```

**Tests:**

```bash
poetry run pytest -q
```

**If something breaks:**

| Problem | Try this |
|---------|----------|
| `poetry` not found | Install Poetry and restart the terminal |
| Wrong Python version | `poetry env use python3.12`, then `poetry install` |
| `No module named logana` | From the project folder: `poetry install`, then `poetry run logana` |
| Command still points at old code | `poetry lock`, then `poetry install` |

---

## 2. Stack choice

**What I built:** a Python command-line tool that analyzes one log file per run.

**Why Python**

- The job is to read one file, parse messy lines, and update counts as you go.
- I had time to add several parsers and tests.
- Only three extra packages: `click`, `rich`, and `tzdata`.

**What I did not build**

| Idea | Why I skipped it |
|------|------------------|
| Web upload app | Same result, but more setup for reviewers |
| Splunk / ELK | Built for large fleets and search — not “analyze this one file” |
| Loading the whole file with pandas | RAM grows with file size |
| C++ / Rust | I am still a beginner in those languages |

**Tradeoff:** the tool is fast enough on a laptop, but some formats need `--log-timezone` or `--reference-date`.

---

## 3. Real edge cases

Two situations that often appear in production logs and shaped how logana was built.

### A 

Application crashes and stack traces rarely fit on a single line. The first line usually has the timestamp and error message. Follow-up lines (`at …`, `Caused by:`, indented details) belong to the same failure but often have **no timestamp of their own**.
If the tool treated every physical line as a separate event, you would get extra rows with missing times, wrong volume counts, and a misleading rejected rate.
**What I did:** Before parsing, related lines are grouped into one chunk (stack continuations, indented blocks, and JSON objects that span multiple lines).
**Limitation:** Only the header line typically has a trustworthy time. Follow-up lines may still be marked as rejected even though they belong to the same exception. Error stats on the header remain useful. See section 5.

---

### B 
A single outage is often visible in several shapes at once: access-style lines (failure in the HTTP status), JSON gateway lines (a soft level like WARN but status 5xx), syslog or load-balancer lines, and `key=value` application logs. A parser built for only one format would under-count the same incident.
**What I did:** Detect the format per chunk, parse with the matching handler, normalize to the same eight fields, and fill gaps with a backup scan over the line when needed. For metrics, a row counts as an error if the log level indicates failure **or** the HTTP status is 500 or higher, so access logs and JSON gateways are judged the same way.
**Limitation:** A line can legitimately say WARN while the status is 200; that should not count as an error. Only a bad level **or** status 5xx triggers the error bucket.

---

## 4. AI usage

I used **[Cursor](https://cursor.com)** as a coding assistant while building logana. It did **not** design the project. I chose the architecture, folder layout, pipeline stages, and coding style first. AI helped mainly with implementation speed then i reviewed and changed anything that did not fit.

AI sped up typing and debugging. **Architecture, structure, and product choices are mine.** I read diffs, ran tests, and removed or rewrote suggestions that were wrong or too generic

---

## 5. Honest gaps

	
- Inflated rejected % (stacks), login ERROR lines not counted, checkout latency 0 on CLF-heavy paths, historical syslog needs --reference-date.
- Text logs only; one file per run; a wrong timezone flag produces wrong charts; XML and CEF in fixtures are expected to fail parsing.

---

## Quick copy-paste

```bash
poetry install
poetry run logana app.log --log-timezone Asia/Karachi
poetry run pytest -q
```
