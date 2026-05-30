---
name: harness-docs
description: "Update Harness workflow documentation, TODO files, official task docs, and durable memory with minimal churn."
---

# Harness Docs

Use this skill during Harness step 9 or whenever a Harness run needs documentation cleanup.

## Update Policy

Minimize documentation churn. Update only when information changed in meaning.

- `TODO.md`: update for active status, completed tasks, review findings, and follow-ups.
- `CLAUDE.md`: update only for rules, contracts, ownership, constraints, or important caveats.
- `docs/<task-slug>/`: update official artifacts such as DESIGN, IMPLEMENTATION, REVIEW, API, ARCHITECTURE, and PR notes.
- Memory: save only durable, non-obvious context that is useful in future conversations and cannot be derived from code, docs, or git.

## Required Checks

1. Identify directly changed code folders.
2. For each changed folder, decide whether its `TODO.md` needs a status or follow-up update.
3. Update folder `CLAUDE.md` only if the change alters local rules or contracts.
4. Update `docs/<task-slug>/REVIEW.md` with validation, PR, docs, and memory decisions.
5. Update `docs/<task-slug>/DESIGN.md` or `IMPLEMENTATION.md` only when the approved design or plan changed.
6. Do not add memory for normal implementation details, file paths, or code patterns already documented elsewhere.

## Final State

At the end of a Harness run, docs should answer:

- What was planned?
- What was implemented?
- What was checked?
- What remains?
- What PR or commit contains the work?
