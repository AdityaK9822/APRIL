# EXPERIENCE.md — Global Lesson Library

This file is the root-level lesson library for the APRIL Harness² engine. After a
harness is adopted, the engine appends a lesson entry here so future runs can
reuse the hard-won tweak.

Entries are append-only Markdown table rows. Do not edit or remove prior rows;
corrections are recorded as new rows with an updated `Status`.

## Entry format

Each adopted harness contributes one row:

| Task ID | Domain | Adopted | Lesson | Cue | Evidence | Confidence | Status |
|---|---|---|---|---|---|---|---|
| `task-001` | `accounting` | `agg1` (run `demo-001/ledger-1/agg1`) | Include both signs when summing in `scripts/summarize.py`. | Ledger includes credits and debits. | `scripts/summarize.py` row: dropping the positive-only filter changed the probe total to include credits. | high | adopted |

### Field notes

- **Task ID** — stable identifier of the originating task (`<domain>/<task>` or `task-NNN`).
- **Domain** — the component/domain family the lesson applies to.
- **Adopted** — the adopted harness id plus the run path that produced it.
- **Lesson** — the transferable instruction for future harness authors.
- **Cue** — the trigger condition under which the lesson applies.
- **Evidence** — the concrete observation that supports the lesson.
- **Confidence** — `high` / `medium` / `low` for the observed contrast.
- **Status** — `adopted`, `superseded`, or `retracted`.

## Writing

The Harness engine opens this file in append mode and adds new rows plus an optional
short prose section in the style of the per-harness `EXPERIENCE.md` files. Keep this
header and the table legend intact so automated parsers can locate the schema.
