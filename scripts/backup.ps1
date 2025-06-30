# backup.ps1
Write-Host " Начало резервного копирования..." -ForegroundColor Green
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
Write-Host "Backup timestamp: $timestamp"
