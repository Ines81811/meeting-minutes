# The quick-tunnel URL changes every time the tunnel restarts (new login,
# reboot, crash). Run this script any time to see the current public URL.
$backendDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$logFile = Join-Path $backendDir "logs\tunnel.log"

if (-not (Test-Path $logFile)) {
    Write-Host "找不到 tunnel.log，tunnel 可能還沒啟動過。"
    exit 1
}

$match = Select-String -Path $logFile -Pattern "https://[a-z0-9-]+\.trycloudflare\.com" | Select-Object -Last 1
if ($match) {
    Write-Host $match.Matches[0].Value
} else {
    Write-Host "還沒找到網址，tunnel 可能還在啟動中，稍後再試一次。"
}
