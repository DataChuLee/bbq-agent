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

$normalized = $filePath.Replace('\', '/')
if ($normalized -match '\.(py|ts|tsx|js|jsx|css|json|mjs|cjs)$') {
    @{
        systemMessage = "Harness reminder: after code edits, update REVIEW.md, relevant TODO.md files, and official docs only if meaningfully affected."
        suppressOutput = $true
    } | ConvertTo-Json -Depth 4 -Compress
}
