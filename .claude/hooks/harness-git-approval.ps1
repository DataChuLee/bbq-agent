$raw = [Console]::In.ReadToEnd()
try {
    $event = $raw | ConvertFrom-Json
} catch {
    exit 0
}

$command = ""
if ($event.tool_input -and $event.tool_input.command) {
    $command = [string]$event.tool_input.command
}

if (-not $command) {
    exit 0
}

function Split-CommandTokens {
    param([string]$Value)

    $matches = [regex]::Matches($Value, '"[^"]*"|''[^'']*''|\S+')
    $tokens = @()
    foreach ($match in $matches) {
        $token = $match.Value.Trim()
        if ($token.Length -ge 2) {
            $first = $token.Substring(0, 1)
            $last = $token.Substring($token.Length - 1, 1)
            if (($first -eq '"' -and $last -eq '"') -or ($first -eq "'" -and $last -eq "'")) {
                $token = $token.Substring(1, $token.Length - 2)
            }
        }
        if ($token) {
            $tokens += $token
        }
    }
    return $tokens
}

function Requires-GitApproval {
    param([string[]]$Tokens)

    $gitOptionsWithValue = @(
        "-c",
        "-C",
        "--config",
        "--work-tree",
        "--git-dir",
        "--namespace",
        "--exec-path",
        "--super-prefix",
        "--html-path"
    )
    $gitOptionsWithoutValue = @(
        "--no-pager",
        "--paginate",
        "--bare",
        "--no-replace-objects",
        "--literal-pathspecs",
        "--glob-pathspecs",
        "--noglob-pathspecs",
        "--icase-pathspecs",
        "--no-optional-locks"
    )
    $gitOptionsWithInlineValue = @(
        "-c*",
        "-C*",
        "--config=*",
        "--work-tree=*",
        "--git-dir=*",
        "--namespace=*",
        "--exec-path=*",
        "--super-prefix=*",
        "--html-path=*"
    )

    for ($i = 0; $i -lt $Tokens.Count; $i++) {
        $tool = [System.IO.Path]::GetFileName($Tokens[$i]).ToLowerInvariant()

        if ($tool -in @("git", "git.exe")) {
            $j = $i + 1
            while ($j -lt $Tokens.Count) {
                $rawArg = $Tokens[$j]
                $arg = $rawArg.ToLowerInvariant()

                if ($arg -in @("add", "commit", "push")) {
                    return $true
                }

                if ($gitOptionsWithValue -contains $rawArg) {
                    $j += 2
                    continue
                }

                if ($gitOptionsWithoutValue -contains $arg) {
                    $j += 1
                    continue
                }

                $isInlineValueOption = $false
                foreach ($pattern in $gitOptionsWithInlineValue) {
                    if ($rawArg -like $pattern) {
                        $isInlineValueOption = $true
                        break
                    }
                }
                if ($isInlineValueOption) {
                    $j += 1
                    continue
                }

                break
            }
        }

        if ($tool -in @("gh", "gh.exe")) {
            if (($i + 2) -lt $Tokens.Count) {
                $first = $Tokens[$i + 1].ToLowerInvariant()
                $second = $Tokens[$i + 2].ToLowerInvariant()
                if ($first -eq "pr" -and $second -eq "create") {
                    return $true
                }
            }
        }
    }

    return $false
}

$requiresApproval = Requires-GitApproval -Tokens (Split-CommandTokens -Value $command)

if ($requiresApproval) {
    @{
        hookSpecificOutput = @{
            hookEventName = "PreToolUse"
            permissionDecision = "ask"
            permissionDecisionReason = "Harness gate: git add, commit, push, and PR creation require explicit user approval. Stage only the approved file list."
        }
    } | ConvertTo-Json -Depth 5 -Compress
}
