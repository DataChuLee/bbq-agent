$message = @"
Harness stop checklist:
- Confirm DESIGN.md records the approved design when planning was part of this task.
- Confirm IMPLEMENTATION.md records the approved implementation plan before implementation edits.
- Confirm REVIEW.md records both implementation review and security review, plus validation evidence, PR notes, and docs/memory decisions when applicable.
- Confirm reproducible bugs and high-severity security findings blocked progress, and lower-severity review follow-ups were recorded in REVIEW.md or TODO.md when applicable.
- Confirm superpowers:verification-before-completion was used before completion, commit, or PR readiness claims.
- Confirm affected TODO.md files include remaining follow-ups.
- Confirm git add, commit, push, and PR gates were not bypassed.
"@

@{
    systemMessage = $message
    suppressOutput = $false
} | ConvertTo-Json -Depth 4 -Compress
