$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

if (-not (Test-Path ".venv")) {
    python -m venv .venv
}
& ".\.venv\Scripts\Activate.ps1"

python -m pip install --upgrade pip
pip install -r requirements.txt
playwright install chromium

if (-not (Test-Path ".env")) {
    Write-Host ""
    Write-Host "Zugangsdaten fuer durchblicker.at (werden nur lokal in .env gespeichert, nie committed):"
    $benutzer = Read-Host "  E-Mail"
    $passwortSicher = Read-Host "  Passwort" -AsSecureString
    $passwort = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
        [Runtime.InteropServices.Marshal]::SecureStringToBSTR($passwortSicher)
    )

    @"
DURCHBLICKER_URL=https://durchblicker.at/
DURCHBLICKER_USER=$benutzer
DURCHBLICKER_PASS=$passwort
"@ | Set-Content -Path ".env" -Encoding utf8

    Write-Host "`n.env angelegt."
} else {
    Write-Host "`n.env existiert bereits, wird nicht ueberschrieben."
}

Write-Host "`nSetup abgeschlossen. Aktivieren mit: .\.venv\Scripts\Activate.ps1"
Write-Host "Login testen mit: python login.py"
