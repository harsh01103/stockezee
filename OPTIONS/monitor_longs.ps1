while ($true) {
    Clear-Host
    Write-Host "=== ACTIVE LONG POSITIONS ===" -ForegroundColor Cyan
    
    try {
        $ledger = Invoke-RestMethod -Uri "http://localhost:4000/api/ledger" -UseBasicParsing
        $openLongs = $ledger.trades | Where-Object { $_.status -eq "OPEN" -and $_.action -eq "BUY" }
        
        if ($openLongs) {
            $openLongs | Select-Object `
                @{Name="Symbol"; Expression={$_.contractSymbol}},
                @{Name="Qty"; Expression={$_.qty}},
                @{Name="Entry Price"; Expression={"{0:N2}" -f $_.entryPrice}},
                @{Name="Current LTP"; Expression={"{0:N2}" -f $_.currentLtp}},
                @{Name="PnL (Rs)"; Expression={"{0:N2}" -f (($_.currentLtp - $_.entryPrice) * $_.qty)}} | 
                Format-Table -AutoSize
        } else {
            Write-Host "No open long positions currently." -ForegroundColor Yellow
        }
    } catch {
        Write-Host "Waiting for backend to connect..." -ForegroundColor DarkGray
    }
    
    Start-Sleep -Seconds 3
}
