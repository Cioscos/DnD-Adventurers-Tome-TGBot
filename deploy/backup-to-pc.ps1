# Backup del Pi sul PC: istantanea coerente del database (anche a servizio acceso, anche con WAL) + file caricati
# (mappe, vocali, silhouette, lore, atlante), in un solo archivio datato. Si lancia da Windows:
#   pwsh deploy\backup-to-pc.ps1
# Ripristino: estrarre l'archivio in data/ sul Pi a servizi fermi (dentro c'è già dnd_bot.db).
param(
    [string]$Dest = 'D:\backup_dnd_bot',
    [string]$SshHost = 'rpi',
    [int]$Keep = 14  # archivi conservati; i più vecchi vengono cancellati
)
$ErrorActionPreference = 'Stop'

# Sul Pi: python3 al posto della CLI sqlite3, che può non essere installata. L'ultima riga stampata è la cartella temporanea.
$remote = @'
set -e
cd /home/cioscospi/Programs/dnd_bot_revamped
T=$(mktemp -d)
python3 -c "import sqlite3,sys; s=sqlite3.connect('data/dnd_bot.db'); d=sqlite3.connect(sys.argv[1]); s.backup(d); d.close()" "$T/dnd_bot.db"
tar czf "$T/backup.tgz" --exclude='./dnd_bot.db*' -C data . -C "$T" dnd_bot.db
echo "$T"
'@ -replace "`r", ''

New-Item -ItemType Directory -Force $Dest | Out-Null
$tmp = ($remote | ssh $SshHost 'bash -s' | Select-Object -Last 1)
if ($LASTEXITCODE -ne 0 -or $tmp -notmatch '^/tmp/tmp\.\w+$') { throw "Backup sul Pi fallito: $tmp" }
try {
    $file = Join-Path $Dest ("dnd_bot_{0:yyyy-MM-dd_HHmmss}.tgz" -f (Get-Date))
    scp -q "${SshHost}:$tmp/backup.tgz" $file
    if ($LASTEXITCODE -ne 0 -or (Get-Item $file).Length -eq 0) { throw "Copia sul PC fallita: $file" }
} finally {
    ssh $SshHost "rm -rf '$tmp'"
}

Get-ChildItem $Dest -Filter 'dnd_bot_*.tgz' | Sort-Object Name -Descending | Select-Object -Skip $Keep | Remove-Item
"{0}  ({1:N0} KB)" -f $file, ((Get-Item $file).Length / 1KB)
