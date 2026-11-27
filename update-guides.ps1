param(
    [string]$Save,
    [string]$Exe,
    [double]$ChickenCycleSeconds,
    [switch]$Open,
    [switch]$Watch
)
$ErrorActionPreference = 'Stop'
$pythonPath = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw 'Set up the environment as described in tools/character_state/README.md.'
}
$scriptArgs = @('-X', 'utf8', '-I', (Join-Path $PSScriptRoot 'tools\character_state\update_guides.py'))
if ($Save) { $scriptArgs += @('--save', $Save) }
if ($Exe) { $scriptArgs += @('--exe', $Exe) }
if ($PSBoundParameters.ContainsKey('ChickenCycleSeconds')) {
    $scriptArgs += @('--chicken-cycle-seconds', $ChickenCycleSeconds.ToString([System.Globalization.CultureInfo]::InvariantCulture))
}
if ($Open) { $scriptArgs += '--open' }
if ($Watch) { $scriptArgs += '--watch' }
& $pythonPath @scriptArgs
exit $LASTEXITCODE
