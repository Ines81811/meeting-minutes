$backendDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$logFile = Join-Path $backendDir "logs\tunnel.log"
$cloudflared = "C:\Program Files (x86)\cloudflared\cloudflared.exe"

# Give the server a head start so the tunnel doesn't come up before there's
# anything listening on :8000.
Start-Sleep -Seconds 8

& $cloudflared tunnel --url http://localhost:8000 *> $logFile
