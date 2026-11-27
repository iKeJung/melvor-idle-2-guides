param(
    [string]$Save,
    [string]$Exe,
    [string]$Saida
)
$ErrorActionPreference = 'Stop'
$pythonPath = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw 'Prepare o ambiente: python -m venv .venv; .\.venv\Scripts\python.exe -m pip install -r ferramentas\estado_personagem\requirements.txt'
}
$scriptArgs = @('-X', 'utf8', '-I', (Join-Path $PSScriptRoot 'ferramentas\estado_personagem\extrair.py'))
if ($Save) { $scriptArgs += @('--save', $Save) }
if ($Exe) { $scriptArgs += @('--exe', $Exe) }
if ($Saida) { $scriptArgs += @('--saida', $Saida) }
& $pythonPath @scriptArgs
exit $LASTEXITCODE
