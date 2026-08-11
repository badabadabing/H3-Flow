param(
    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot)
)

$ErrorActionPreference = 'Stop'
$forbiddenExtensions = @('.safetensors', '.ckpt', '.pt', '.pth', '.mp4', '.mov', '.mkv', '.avi', '.wav', '.flac', '.mp3')
$forbiddenNames = @('.env', 'config.local.json')
$issues = [System.Collections.Generic.List[string]]::new()

Get-ChildItem -LiteralPath $ProjectRoot -File -Recurse | ForEach-Object {
    if ($forbiddenExtensions -contains $_.Extension.ToLowerInvariant()) {
        $issues.Add("Forbidden binary/media file: $($_.FullName)")
    }
    if ($forbiddenNames -contains $_.Name.ToLowerInvariant()) {
        $issues.Add("Forbidden local configuration: $($_.FullName)")
    }
}

$textFiles = Get-ChildItem -LiteralPath $ProjectRoot -File -Recurse | Where-Object {
    $_.FullName -ne $PSCommandPath -and
    $_.Extension.ToLowerInvariant() -in @('.py', '.js', '.html', '.css', '.md', '.json', '.yml', '.yaml', '.ps1', '.txt')
}
$patterns = @(
    'C:\\Users\\',
    'D:\\Desktop\\vibe coding',
    'github_pat_',
    'gho_',
    'sk-[A-Za-z0-9_-]{16,}',
    'AKIA[0-9A-Z]{16}',
    'BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY'
)
foreach ($pattern in $patterns) {
    $matches = $textFiles | Select-String -Pattern $pattern -CaseSensitive
    foreach ($match in $matches) {
        $issues.Add("Sensitive pattern in $($match.Path):$($match.LineNumber)")
    }
}

if ($issues.Count) {
    $issues | ForEach-Object { Write-Error $_ }
    throw "Privacy check failed with $($issues.Count) issue(s)."
}

[pscustomobject]@{ Status = 'pass'; FilesScanned = @($textFiles).Count; Root = (Resolve-Path -LiteralPath $ProjectRoot).Path }
