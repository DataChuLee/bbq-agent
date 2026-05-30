---
description: Run the Harness Engineering workflow for a requested task.
---

Use the `harness-engineering` skill for the following request.

The workflow uses three task artifacts under `docs/<task-slug>/`:

- `DESIGN.md`
- `IMPLEMENTATION.md`
- `REVIEW.md`

Use those artifacts, git history, and PR status as the workflow record.

During Step 4, Harness reviews the implementation first, records bug, unused code, and duplicate code findings in `REVIEW.md`, then continues directly into a security review and records security findings in the same artifact.

Common review prompts include:

- `방금 구현한 거 코드 리뷰해줘`
- `보안 취약점 체크해줘`

$ARGUMENTS
