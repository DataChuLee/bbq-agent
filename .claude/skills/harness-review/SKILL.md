---
name: harness-review
description: "Review implementation changes for the Harness workflow, focusing on regressions, bugs, unused or duplicate code, security risk, missing validation, PR readiness, and documentation impact."
---

# Harness Review

Use this skill during Harness step 4 and step 7.

## Review Stance

Prioritize concrete findings over summaries. Look for:

- Behavioral regressions
- Reproducible bugs
- Incorrect or incomplete implementation against the approved plan
- Missing validation or unrun planned checks
- API, schema, or state contract drift
- Error handling gaps
- Unused code, dead branches, or duplicate logic introduced by the change
- Security vulnerabilities or risky assumptions around secrets, auth, input validation, configuration exposure, or dependencies
- Unintended changes or unrelated files
- Documentation and TODO updates that are required but missing

## Implementation Review Checklist

1. Compare the diff against `docs/<task-slug>/IMPLEMENTATION.md`.
2. Confirm the changed files match the approved scope.
3. Inspect risky paths manually for regressions and reproducible bugs.
4. Check for unused code, duplicate logic, dead branches, or stale helpers introduced by the change.
5. Verify planned checks were run or failures were recorded.
6. Identify follow-up tasks that should go into the relevant `TODO.md`.

## Security Review Checklist

1. Inspect changed code and adjacent configuration for secrets or sensitive data exposure.
2. Check auth and authorization assumptions, including missing permission boundaries.
3. Check input validation, data handling, and error paths for obvious abuse cases.
4. Check configuration exposure and dependency risk relevant to the change, and note when no scanner or audit command was run.
5. Mark high-severity security findings as blocking and lower-severity issues as follow-ups when appropriate.

## PR Review Checklist

1. Confirm the PR body describes the actual diff.
2. Confirm tests/checks are listed with pass/fail status.
3. Confirm docs updates are listed.
4. Confirm known risks and follow-ups are explicit.
5. Confirm no unrelated user changes are included.

## Output Format

For Step 4, use this order:

1. Implementation review findings, ordered by severity, with file references when available.
2. Security review findings, ordered by severity, with file references when available.
3. Open questions or assumptions.
4. Required fixes.
5. Validation status.

For Step 7, keep PR review findings first, then open questions or assumptions, required fixes, and validation status.

If there are no findings in a section, state that clearly and mention any residual risk.
