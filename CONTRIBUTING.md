# Contributing

PUBLIC EYE is a solo project in active development. If you want to contribute, here's how things work.

---

## Before you open a PR

File an issue first and describe what you want to change and why. The codebase is moving fast and a lot of things that look like they should be fixed are actually intentional or already being changed. An issue saves everyone time.

---

## What's most useful right now

- Bug reports with reproduction steps
- Performance issues with specific analysis runs (slow? timing out?)
- LLM adapter contributions (new providers for `llm_client.py`)
- New adapter modules for data sources (court records, financial disclosures, etc.)
- Test coverage for the signing pipeline

---

## What's not useful right now

- Rewrites or large refactors of `main.py` — the monolith is intentional for now
- New UI frameworks or frontend overhauls — the server-rendered approach is deliberate
- Feature requests without a specific use case

---

## Code style

- Python: no type annotation requirements, just don't make it unreadable
- No linter enforcement yet — use your judgment
- If you add a file, add a docstring at the top explaining what it is and how to use it
- Test signing-related changes against actual receipts, not just unit tests

---

## Running tests

```bash
# TypeScript
npm test

# End-to-end (requires running API)
bash scripts/e2e-test.sh http://localhost:8000

# Python JCS self-test
python3 apps/api/jcs_canonicalize.py

# Python receipt versioning self-test
python3 apps/api/receipt_versioning.py
```

---

## Commit messages

Plain English. Say what changed and why in one line. If it needs more explanation, add a body after a blank line. No emoji, no ticket numbers.

Good:
```
fix verify-receipt snake_case field normalization
add global perspectives to analyze-article pipeline
remove Node subprocess from JCS signing path
```

Not useful:
```
fix stuff
update code
WIP
```

---

## The stance

PUBLIC EYE's core principle is receipts, not verdicts. Any contribution that edges toward "and then it tells you who's right" is out of scope. The tool surfaces what the record shows and makes explicit what's missing. It doesn't score credibility, assign bias ratings, or determine truth.

If you're not sure whether something fits that principle, ask in an issue.
