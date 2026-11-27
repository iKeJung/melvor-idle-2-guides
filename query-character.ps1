param(
    [Parameter(Mandatory=$true)][string]$Skill,
    [string]$Stat,
    [string]$Component,
    [string]$Type,
    [switch]$Cache,
    [string]$Save,
    [string]$Exe,
    [string]$Output
)
$ErrorActionPreference = 'Stop'
$pythonPath = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw 'Set up the environment as described in tools/character_state/README.md.'
}
$scriptArgs = @('-X', 'utf8', '-I', (Join-Path $PSScriptRoot 'tools\character_state\query.py'), '--skill', $Skill)
if ($Stat) { $scriptArgs += @('--stat', $Stat) }
if ($Component) { $scriptArgs += @('--component', $Component) }
if ($Type) { $scriptArgs += @('--type', $Type) }
if ($Cache) { $scriptArgs += '--cache' }
if ($Save) { $scriptArgs += @('--save', $Save) }
if ($Exe) { $scriptArgs += @('--exe', $Exe) }
if ($Output) { $scriptArgs += @('--output', $Output) }
& $pythonPath @scriptArgs
exit $LASTEXITCODE
