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

**Run on a real LogHub log:**

```bash
poetry run logana tests/fixtures/OpenStack_2k.log --log-timezone UTC
poetry run logana tests/fixtures/OpenStack_2k.log --log-timezone UTC --format dashboard
poetry run logana tests/fixtures/OpenStack_2k.log --log-timezone UTC --format json > report.json
```

**Evaluation results:** [tests/fixtures/LOGHUB.md](tests/fixtures/LOGHUB.md)

**Old syslog files with no year** (see `tests/fixtures/Linux_2k.log`):

```bash
poetry run logana tests/fixtures/Linux_2k.log --reference-date 2004-06-15
```

**Tests:**

```bash
poetry run pytest -q
```

**If something breaks:**

| Problem                          | Try this                                                            |
| -------------------------------- | ------------------------------------------------------------------- |
| `poetry` not found               | Install Poetry and restart the terminal                             |
| Wrong Python version             | `poetry env use python3.12`, then `poetry install`                  |
| `No module named logana`         | From the project folder: `poetry install`, then `poetry run logana` |
| Command still points at old code | `poetry lock`, then `poetry install`                                |

---

## 2. Stack choice

**What I built:** a Python command-line tool that analyzes one log file per run.

**Why Python**

- The job is to read one file, parse messy lines, and update counts as you go.
- I had time to add several parsers and tests.
- Only three extra packages: `click`, `rich`, and `tzdata`.

**What I did not build**

| Idea                               | Why I skipped it                                                |
| ---------------------------------- | --------------------------------------------------------------- |
| Web upload app                     | Same result, but more setup for reviewers                       |
| Splunk / ELK                       | Built for large fleets and search — not “analyze this one file” |
| Loading the whole file with pandas | RAM grows with file size                                        |
| C++ / Rust                         | I am still a beginner in those languages                        |

**Tradeoff:** the tool is fast enough on a laptop, but some formats need `--log-timezone` or `--reference-date`.

---

## 3. Edge cases

These are the real edge cases that shaped the parser and the dashboard.

### A. Multiline stack traces

In `app.log`, one payment failure expands into a Java stack trace. The first line has the timestamp, but the follow-up `at ...` and `Caused by:` lines do not.
If I counted each physical line as a separate event, the file would look much noisier than it really is.
**What I do:** `lineBoundary` groups the stack trace into one logical chunk before parsing.
**Tradeoff:** the stack trace tail may still be quarantined separately if it does not carry its own timestamp, but the main error line still counts and still helps the error-rate charts.

### B. Mixed formats in one file

The synthetic mixed log and the real sample both contain CLF, JSON, logfmt, pipe-delimited rows, syslog, and plain text in the same file.
A parser that expects only one shape would miss a lot of useful rows.
**What I do:** `formatProbe` picks the best parser per chunk, and `parserDispatch` falls back to token scanning when the chunk is only partly structured.
**Tradeoff:** heuristic parsing is flexible, but it can still be wrong on unusual vendor logs, so the tool prefers conservative quarantine over guessing too much.

### C. Bare latency values

In JSON logs, `duration_ms: 142` is safe because the field name says the unit.
But a bare value like `duration: 3.2` is not automatically safe, because the same number could mean milliseconds, seconds, or something else in another file.
**What I do:** explicit ms-style aliases count as latency samples, while ambiguous bare numbers stay `Unknown` unless a source-specific rule says otherwise.
**Tradeoff:** this avoids false precision, but it means some logs need a custom alias mapping before their latency shows up in the dashboard.

### D. Syslog without a year

Older syslog lines often look like `May 21 09:01:12 ...` with no year at all.
If I guessed the year blindly, January logs near a year boundary could be wrong.
**What I do:** `sniffReferenceYear` and `--reference-date` provide a year anchor, and the parser only accepts a learned year when there is enough evidence.
**Tradeoff:** the tool may quarantine or under-confidence some old syslog lines rather than inventing the wrong year.

---

## 4. AI usage

I used **[Cursor](https://cursor.com)** as a coding assistant while building logana. It did **not** design the project. I chose the architecture, folder layout, pipeline stages, and coding style first. AI helped mainly with implementation speed then i reviewed and changed anything that did not fit.

AI sped up typing and debugging. **Architecture, structure, and product choices are mine.** I read diffs, ran tests, and removed or rewrote suggestions that were wrong or too generic

---

## 5. Honest gaps

- Multiline stack traces can still raise the rejected rate because the header line has the real timestamp, but the continuation lines often do not.
- Latency is only counted when the field name or source makes the unit clear; a bare value like `duration: 3.2` stays ambiguous unless I add a rule for that source.
- Old syslog files with no year still need `--reference-date` or a strong year hint, otherwise the year can be wrong near a boundary.
- The tool is still one file at a time and only supports text logs; XML, CEF, and similar formats are expected to fail unless I add a parser for them.
- A wrong `--log-timezone` or `--naive-timestamps` choice can shift timestamps and make the charts look correct even when the assumption is wrong.
- Ai integration will be helpful for ambiguous or unknown fields clusters. But i will add this later
---

## Quick copy-paste

```bash
poetry install
poetry run logana tests/fixtures/OpenStack_2k.log --log-timezone UTC
poetry run pytest -q
```
