---
name: harness-engineering
description: "Run the project Harness Engineering workflow: brainstorming, design review, implementation, implementation review, security review, fixes, commit, PR review, push/PR, and docs/memory updates."
---

# Harness Engineering Workflow

Use this internal orchestration skill when the user invokes the `/harness` command or asks to run the full Harness Engineering workflow.

This skill coordinates the workflow. It does not replace Superpowers skills. Planning must still use:

1. `superpowers:brainstorming`
2. `superpowers:writing-plans`

Before claiming completion, committing, or creating a PR, use `superpowers:verification-before-completion` and record fresh verification evidence in `REVIEW.md`.

Implementation may start only after the design and implementation plan are approved.

## Source Of Truth

Harness does not use a separate state file. Progress is derived from durable artifacts and git history:

- `docs/<task-slug>/DESIGN.md` - planning, alternatives, decisions, design review, and user approval.
- `docs/<task-slug>/IMPLEMENTATION.md` - approved implementation plan, expected files, validation, risks, and rollback.
- `docs/<task-slug>/REVIEW.md` - implementation review, security review, fix notes, validation evidence, PR review notes, and remaining follow-ups.
- Git commits and PR status - final record of staged, committed, pushed, and reviewed work.

If an artifact is missing, resume at the earliest step that needs it. Do not infer approval from intent alone; record `Status: approved` in the relevant artifact before advancing.

An approved artifact pair means a single `docs/<task-slug>/` directory contains both `DESIGN.md` and `IMPLEMENTATION.md`, and both files contain `Status: approved`.

## Execution Protocol

Do not merely describe this workflow. Execute the next incomplete step until blocked by an approval gate, missing prerequisite, failed validation, or scope divergence.

At the start of every run:

1. Determine the requested task and derive a short `task-slug`.
2. Look for `docs/<task-slug>/DESIGN.md`, `IMPLEMENTATION.md`, and `REVIEW.md`.
3. Resume from the earliest incomplete step based on those artifacts.
4. Announce the current step and next action.

When blocked:

- Update the relevant artifact before stopping.
- State the exact gate that blocked progress.
- Tell the user the exact next response needed, such as approving the design, approving the implementation plan, approving the stage list, or approving push/PR creation.
- When the user says "continue", "next", "proceed", "approved", or repeats `/harness` for the same task, read the artifacts and resume from the blocked step.

Never skip ahead. If Step 1 or Step 2 is incomplete, do not edit implementation files.

## Hard Gates

- Do not implement until `DESIGN.md` records `Status: approved`.
- Do not implement until `IMPLEMENTATION.md` records `Status: approved`.
- Do not edit implementation files through Edit, Write, or obvious Bash file-write commands until an approved artifact pair exists.
- Do not continue if implementation scope diverges from the approved plan. Stop, summarize the divergence, and update the plan first.
- Do not run `git add`, `git commit`, `git push`, or `gh pr create` without explicit user approval.
- Do not stage unrelated user changes. Stage only files explicitly included in the approved change set.

## Workflow

1. **Planning**
   - Use `superpowers:brainstorming`.
   - Treat `docs/<task-slug>/DESIGN.md` as the Harness override for the brainstorming design/spec location.
   - Explore context, clarify requirements, compare approaches, and present the design.
   - Save the planning draft to `docs/<task-slug>/DESIGN.md` using `templates/design.md`.
   - Record `Status: draft` unless Step 2 has already completed the critical review loop.

2. **Design Review**
   - Open `docs/<task-slug>/DESIGN.md`.
   - Review the design from an objective and critical perspective.
   - Look for unclear goals, weak success criteria, hidden assumptions, oversized scope, missing alternatives, unresolved tradeoffs, implementation ambiguity, and operational risk.
   - Record findings and required changes in `DESIGN.md`.
   - If findings exist, record `Status: changes_requested`, revise the design, and run the design review again.
   - Repeat review and revision until `Blocking findings remaining: no`.
   - Record `Status: approved` only when the re-review has no blocking findings.

3. **Implementation**
   - Use `superpowers:writing-plans` to produce the implementation plan.
   - Save the approved plan to `docs/<task-slug>/IMPLEMENTATION.md` using `templates/implementation.md`.
   - Record `Status: approved` only after the user approves the implementation plan.
   - Open `docs/<task-slug>/DESIGN.md` and `IMPLEMENTATION.md` before editing.
   - Implement only the approved plan and keep edits scoped.
   - Use `superpowers:test-driven-development` for feature and bugfix work.
   - For each feature unit, write the failing test first, confirm it fails for the expected reason, implement the minimal change, and run the targeted test until it passes.
   - If a test fails unexpectedly or the root cause is unclear, use `superpowers:systematic-debugging` before changing code.
   - After all feature units pass, run the approved full flow validation and record the results in `REVIEW.md`.

4. **Implementation Review**
   - Use the `harness-review` skill.
   - Use `superpowers:verification-before-completion` before claiming the implementation is complete or passing.
   - Compare the diff against `IMPLEMENTATION.md`.
   - Run the implementation review first. Review regression risk, validation coverage, API or state contract drift, docs impact, unrelated changes, reproducible bugs, unused code, and duplicate code.
   - Save implementation review findings to `docs/<task-slug>/REVIEW.md` using `templates/review.md`.
   - Then continue directly into the security review without waiting for a new user prompt. Common prompts include `방금 구현한 거 코드 리뷰해줘` and `보안 취약점 체크해줘`.
   - Run the security review second. Review secrets and sensitive data handling, auth or authorization assumptions, input validation, configuration exposure, dependency risk, and risky code paths adjacent to the change.
   - Save security review findings to `docs/<task-slug>/REVIEW.md` under the `Security Review` section.
   - Treat reproducible bugs and high-severity security vulnerabilities as blocking findings. Record lower-severity unused code, duplicate code, and security concerns in `REVIEW.md` and affected `TODO.md` files when follow-up is sufficient.

5. **Fix And Improve**
   - Address implementation review and security review findings.
   - Re-run relevant validation.
   - Record fix notes, remaining risk, and follow-ups in `REVIEW.md` and affected `TODO.md` files when meaningful.

6. **Add And Commit**
   - Use `superpowers:verification-before-completion` before asking to commit.
   - Show dirty worktree and intended staged files first.
   - Ask for approval before `git add`.
   - Stage only approved files.
   - Ask for approval before `git commit`.
   - Commit implementation separately from planning-only changes when both exist.

7. **PR Review**
   - Use `superpowers:verification-before-completion` before drafting or claiming PR readiness.
   - Review the final diff and draft PR content.
   - Record PR review notes and proposed PR summary in `REVIEW.md`.
   - Use `templates/pr-body.md` only when a separate PR body is useful.

8. **Push And PR**
   - Ask for approval before `git push` and before `gh pr create`.
   - Confirm `gh auth status` before PR creation.
   - Record push/PR status in `REVIEW.md`.

9. **Docs And Memory**
   - Use the `harness-docs` skill.
   - Update only documents that changed in meaning.
   - Update memory only for durable, non-obvious user preferences or project decisions.
   - Record docs and memory decisions in `REVIEW.md`.

## Step Completion Rules

- Step 1 is complete when `DESIGN.md` exists and contains a planning draft.
- Step 2 is complete when `DESIGN.md` records objective and critical review results, `Blocking findings remaining: no`, and `Status: approved`.
- Step 3 is complete when `IMPLEMENTATION.md` contains `Status: approved`, implementation edits match the plan, TDD evidence is recorded in `REVIEW.md`, targeted tests pass, and full flow validation is recorded.
- Step 4 is complete when `REVIEW.md` records both the implementation review and the security review.
- Step 5 is complete when implementation review and security review findings are fixed or recorded as follow-ups.
- Step 6 is complete when the approved files are committed or the user explicitly skips commit.
- Step 7 is complete when `REVIEW.md` contains final PR review notes.
- Step 8 is complete when push/PR status is recorded or the user explicitly skips push/PR.
- Step 9 is complete when docs, TODO, and memory decisions are recorded.

## Blocked Output Format

When stopping at a gate, use this concise shape:

```txt
Harness paused at Step <n>: <step name>
Reason: <approval, missing prerequisite, failed check, or scope divergence>
Artifact updated: docs/<task-slug>/<DESIGN.md|IMPLEMENTATION.md|REVIEW.md>
Next response needed: <specific user action>
```

## Minimal Documentation Change Path

For small documentation-only requests, such as updating `README.md`, use the shortest valid Harness path:

- Run a concise `superpowers:brainstorming` pass and record the planning draft in `DESIGN.md` with `Status: draft`.
- Run an objective and critical design review. If findings exist, revise and re-review until `Blocking findings remaining: no`, then record `Status: approved`.
- Run a concise `superpowers:writing-plans` pass and record the approved plan in `IMPLEMENTATION.md` with `Status: approved`.
- Use `superpowers:test-driven-development` for feature or bugfix documentation logic when applicable; skip TDD only for pure documentation edits and record the reason in `REVIEW.md`.
- Edit only the approved documentation files.
- No build or lint is required unless the documentation references generated content.
- Still review the diff, run the Step 4 implementation review and security review, request `git add` and commit approval, and record validation/docs decisions in `REVIEW.md`.

## Documentation Rules

- Root `CLAUDE.md`: project-wide direction and rules only.
- Code-folder `CLAUDE.md`: update only when contracts, constraints, or local operating rules change.
- Code-folder `TODO.md`: update for active tasks, review findings, and follow-ups.
- `docs/<task-slug>/`: official task artifacts.
- Memory: durable context that cannot be derived from code, docs, or git history.

## Windows Notes

- Use `npm.cmd`, not `npm`, in PowerShell.
- Confirm `gh auth status` before PR creation.
- Confirm git safe directory is configured if git reports dubious ownership.
