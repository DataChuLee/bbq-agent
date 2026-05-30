$raw = [Console]::In.ReadToEnd()
try {
    $event = $raw | ConvertFrom-Json
} catch {
    exit 0
}

$filePath = ""
if ($event.tool_input -and $event.tool_input.file_path) {
    $filePath = [string]$event.tool_input.file_path
}

if (-not $filePath) {
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

$normalized = $filePath.Replace('\', '/')
$isCodeOrConfig = $normalized -match '\.(py|ts|tsx|js|jsx|json|toml|yaml|yml|css|mjs|cjs)$'
$isHarnessPlanning = $normalized -match '/docs/[^/]+/(DESIGN|IMPLEMENTATION|REVIEW|PRD|PR|API|ARCHITECTURE)\.md$'
$isClaudeHarness = $normalized -match '/\.claude/(commands|skills|hooks)/'

if ($isCodeOrConfig -and -not $isHarnessPlanning -and -not $isClaudeHarness) {
    $projectDir = Get-ProjectDir
    if (-not (Has-ApprovedArtifactPair -ProjectDir $projectDir)) {
        @{
            hookSpecificOutput = @{
                hookEventName = "PreToolUse"
                permissionDecision = "ask"
                permissionDecisionReason = "Harness gate: implementation edits require a docs/<task>/DESIGN.md and IMPLEMENTATION.md pair with Status: approved."
            }
        } | ConvertTo-Json -Depth 5 -Compress
    }
}
