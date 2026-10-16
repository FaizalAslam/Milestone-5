$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$taskPython = Join-Path $PSScriptRoot '.venv312\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $taskPython)) {
    throw 'Create .venv312 and install requirements.txt using the README first.'
}
& $taskPython -m streamlit run app.py --server.address 127.0.0.1 --server.port 8502
