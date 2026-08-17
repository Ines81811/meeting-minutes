$backendDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $backendDir

$python = Join-Path $backendDir ".venv\Scripts\python.exe"
$logFile = Join-Path $backendDir "logs\server.log"

& $python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 *> $logFile
