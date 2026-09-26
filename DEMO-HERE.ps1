<#
Launch the local virtual-cell demo from any working directory.

First run on a new Windows checkout: .\DEMO-HERE.ps1 -Install
Later runs:                         .\DEMO-HERE.ps1
Preflight without serving:          .\DEMO-HERE.ps1 -CheckOnly
#>
[CmdletBinding()]
param(
    [switch] $Install,
    [switch] $CheckOnly,
    [ValidateRange(1, 65535)] [int] $BoardPort = 8765,
    [ValidateRange(1, 65535)] [int] $PlaygroundPort = 8766,
    [string] $EngineCli
)

$repoRoot = $PSScriptRoot
$python = Join-Path $repoRoot '.venv\Scripts\python.exe'
$launcher = Join-Path $repoRoot 'tools\start_live_demo.py'

if (-not (Test-Path -LiteralPath $launcher -PathType Leaf)) {
    throw "Demo launcher is missing: $launcher"
}
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    if ($CheckOnly -or -not $Install) {
        throw 'The demo environment is missing. Run .\DEMO-HERE.ps1 -Install from the repository root.'
    }
    Write-Host 'Creating the local Python 3.12 environment...'
    & py -3.12 -m venv (Join-Path $repoRoot '.venv')
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the Python 3.12 environment.' }
}
if ($Install) {
    Write-Host 'Installing the pinned demo dependencies, including Ocura OSS...'
    & $python -m pip install -r (Join-Path $repoRoot 'requirements-hackathon.txt')
    if ($LASTEXITCODE -ne 0) { throw 'Demo dependency installation failed.' }
}

$launchArgs = @($launcher, '--board-port', [string]$BoardPort,
                '--playground-port', [string]$PlaygroundPort)
if ($CheckOnly) { $launchArgs += '--check-only' }
if ($EngineCli) { $launchArgs += @('--engine-cli', $EngineCli) }

Push-Location -LiteralPath $repoRoot
try {
    if (-not $CheckOnly) {
        Write-Host "Board:      http://127.0.0.1:$BoardPort/"
        Write-Host "Playground: http://127.0.0.1:$PlaygroundPort/"
        Write-Host "Campaign:   http://127.0.0.1:$PlaygroundPort/campaign"
        Write-Host 'Keep this window open during the demo. Press Ctrl+C to stop services started by this launcher.'
    }
    & $python @launchArgs
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} finally {
    Pop-Location
}
