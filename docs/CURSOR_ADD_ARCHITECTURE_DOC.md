# Cursor: add master architecture doc

## What to add

1. **Create** (or keep) the canonical architecture document at:

   **`docs/MASTER_ARCHITECTURE.md`**

   This is the single **master readout** for engineers: PUBLIC EYE vs FRAME naming, four products, monorepo map, **signing algorithm + the “not in signing body = decoration” rule**, current article pipeline (revisions, contextual brief, drift, dig deeper), drift summary, data sources table, env vars by priority, deployment warnings, five-step onboarding ending on the signing rule, and a sharper “what this is not” section.

2. **Reference this file** from:

   - **`docs/CONTEXT.md`** — In **“Before touching any code in a new session”** (or the **REPOS AND DEPLOYMENT** / intro area), add a bullet to read **`docs/MASTER_ARCHITECTURE.md`** for full stack architecture and signing semantics.

   - **`README.md`** — After the intro paragraph (or in **Run it locally**), add one line linking to **`docs/MASTER_ARCHITECTURE.md`** for engineers onboarding to the repo.

## Commit

After the two reference updates and `docs/MASTER_ARCHITECTURE.md` are in place:

```bash
git add docs/MASTER_ARCHITECTURE.md docs/CURSOR_ADD_ARCHITECTURE_DOC.md docs/CONTEXT.md README.md
git commit -m "docs: add MASTER_ARCHITECTURE (signing slice, article pipeline, onboarding)"
```

Adjust the commit message if only a subset of files changed.

## Drop-in for Cursor chats

Attach:

- **`docs/MASTER_ARCHITECTURE.md`**
- **`docs/CURSOR_ADD_ARCHITECTURE_DOC.md`** (this file)

so the model knows where the doc lives and which entry points were updated.
