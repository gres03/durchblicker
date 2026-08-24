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

    Write-Host ""
    Write-Host "Optional: Gemini-API-Schluessel fuer die automatische Dokumentenerkennung"
    Write-Host "in der Web-Oberflaeche (webapp_starten). Kostenloses Kontingent, kein"
    Write-Host "Zahlungsmittel noetig -- siehe https://aistudio.google.com/apikey"
    Write-Host "Leer lassen und Enter druecken, um das jetzt zu ueberspringen (kann"
    Write-Host "spaeter jederzeit in .env nachgetragen werden -- dann funktioniert nur"
    Write-Host "der manuelle claude.ai-Weg aus ANLEITUNG.md nicht die Web-Oberflaeche)."
    $geminiKey = Read-Host "  Gemini-API-Schluessel (optional)"

    @"
DURCHBLICKER_URL=https://durchblicker.at/
DURCHBLICKER_USER=$benutzer
DURCHBLICKER_PASS=$passwort
GEMINI_API_KEY=$geminiKey
"@ | Set-Content -Path ".env" -Encoding utf8

    Write-Host "`n.env angelegt."
} else {
    Write-Host "`n.env existiert bereits, wird nicht ueberschrieben."
}

Write-Host "`nSetup abgeschlossen. Aktivieren mit: .\.venv\Scripts\Activate.ps1"
Write-Host "Web-Oberflaeche starten mit: .\Webapp_starten.bat"
Write-Host "Login testen mit: python login.py"
