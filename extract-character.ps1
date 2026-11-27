param(
    [string]$Save,
    [string]$Exe,
    [string]$Output
)
$ErrorActionPreference = 'Stop'
$pythonPath = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw 'Set up the environment: python -m venv .venv; .\.venv\Scripts\python.exe -m pip install -r tools\character_state\requirements.txt'
}
$scriptArgs = @('-X', 'utf8', '-I', (Join-Path $PSScriptRoot 'tools\character_state\extract.py'))
if ($Save) { $scriptArgs += @('--save', $Save) }
if ($Exe) { $scriptArgs += @('--exe', $Exe) }
if ($Output) { $scriptArgs += @('--output', $Output) }
& $pythonPath @scriptArgs
exit $LASTEXITCODE
