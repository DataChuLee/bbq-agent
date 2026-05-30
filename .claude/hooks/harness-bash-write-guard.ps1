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

function Get-ProjectDir {
    if ($env:CLAUDE_PROJECT_DIR) {
        return $env:CLAUDE_PROJECT_DIR
    }
    return (Get-Location).Path
}

function Has-ApprovedArtifactPair {
    param([string]$ProjectDir)

    $docsDir = Join-Path $ProjectDir "docs"
    if (-not (Test-Path -LiteralPath $docsDir)) {
        return $false
    }

    $approvedPattern = '(?im)^\s*-?\s*Status:\s*approved\s*$'
    $taskDirs = Get-ChildItem -LiteralPath $docsDir -Directory -ErrorAction SilentlyContinue
    foreach ($taskDir in $taskDirs) {
        $designPath = Join-Path $taskDir.FullName "DESIGN.md"
        $implementationPath = Join-Path $taskDir.FullName "IMPLEMENTATION.md"
        if ((Test-Path -LiteralPath $designPath) -and (Test-Path -LiteralPath $implementationPath)) {
            $design = Get-Content -Raw -Encoding UTF8 -LiteralPath $designPath
            $implementation = Get-Content -Raw -Encoding UTF8 -LiteralPath $implementationPath
            if (($design -match $approvedPattern) -and ($implementation -match $approvedPattern)) {
                return $true
            }
        }
    }

    return $false
}

function Has-ExplicitFileWrite {
    param([string]$Value)

    $writeCommandPattern = '(?i)(^|[\s;|&])(Set-Content|Add-Content|Out-File|New-Item|Remove-Item|Move-Item|Copy-Item)\b'
    if ($Value -match $writeCommandPattern) {
        return $true
    }

    $redirectionPattern = '(?<![<>=])>>?(?![>=])'
    if ($Value -match $redirectionPattern) {
        return $true
    }

    return $false
}

if (Has-ExplicitFileWrite -Value $command) {
    $projectDir = Get-ProjectDir
    if (-not (Has-ApprovedArtifactPair -ProjectDir $projectDir)) {
        @{
            hookSpecificOutput = @{
                hookEventName = "PreToolUse"
                permissionDecision = "ask"
                permissionDecisionReason = "Harness gate: Bash file writes require a docs/<task>/DESIGN.md and IMPLEMENTATION.md pair with Status: approved."
            }
        } | ConvertTo-Json -Depth 5 -Compress
    }
}
