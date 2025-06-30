# backup_supabase.ps1
param(
    [string]$BackupDir = "C:\VendHub\backup"
)

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupFile = "$BackupDir\vendhub_backup_$timestamp.sql"
$compressedFile = "$backupFile.gz"

Write-Host "Creating Supabase backup: $backupFile"

# Используем pg_dump для подключения к Supabase
$env:PGPASSWORD = "Shx5WM+#8Sh4uUq"
& "C:\Program Files\PostgreSQL\15\bin\pg_dump.exe" `
    -h "db.kyqmdazuzzynpcdbopjn.supabase.co" `
    -p 5432 `
    -U "postgres" `
    -d "postgres" `
    -f $backupFile `
    --no-owner `
    --no-privileges

# Сжатие файла
if (Test-Path $backupFile) {
    & "C:\Program Files\7-Zip\7z.exe" a -tgzip $compressedFile $backupFile
    Remove-Item $backupFile
    Write-Host "Backup completed: $compressedFile" -ForegroundColor Green
    
    # Размер файла
    $size = (Get-Item $compressedFile).Length / 1MB
    Write-Host "Backup size: $([math]::Round($size, 2)) MB" -ForegroundColor Cyan
}

# Удаление старых бэкапов (старше 30 дней)
Get-ChildItem -Path $BackupDir -Filter "*.sql.gz" | 
    Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-30) } | 
    Remove-Item -Force
