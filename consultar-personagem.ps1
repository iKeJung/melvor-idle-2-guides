param(
    [Parameter(Mandatory=$true)][string]$Habilidade,
    [string]$Stat,
    [string]$Componente,
    [string]$Tipo,
    [switch]$Cache,
    [string]$Save,
    [string]$Exe,
    [string]$Saida
)
$ErrorActionPreference = 'Stop'
$pythonPath = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw 'Prepare o ambiente conforme ferramentas/estado_personagem/README.md.'
}
$scriptArgs = @('-X', 'utf8', '-I', (Join-Path $PSScriptRoot 'ferramentas\estado_personagem\consultar.py'), '--skill', $Habilidade)
if ($Stat) { $scriptArgs += @('--stat', $Stat) }
if ($Componente) { $scriptArgs += @('--componente', $Componente) }
if ($Tipo) { $scriptArgs += @('--tipo', $Tipo) }
if ($Cache) { $scriptArgs += '--cache' }
if ($Save) { $scriptArgs += @('--save', $Save) }
if ($Exe) { $scriptArgs += @('--exe', $Exe) }
if ($Saida) { $scriptArgs += @('--saida', $Saida) }
& $pythonPath @scriptArgs
exit $LASTEXITCODE
