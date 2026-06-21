# ポート 8861 / 8760 / 8761 を使用しているプロセスを強制終了
$ports = @(8861, 8760, 8761)

foreach ($port in $ports) {
    $p = (Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue).OwningProcess
    if ($p) {
        Write-Host "Port $port is used by PID: $p"
        Stop-Process -Id $p -Force -ErrorAction SilentlyContinue
        Write-Host "Process $p has been terminated."
    } else {
        Write-Host "Port $port is not currently in use."
    }
}

Write-Host "Done."
