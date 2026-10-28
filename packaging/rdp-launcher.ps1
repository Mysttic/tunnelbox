# Helper protokołu tunnelbox-rdp:// — wywoływany przez Windows po kliknięciu
# „Połącz przez RDP" w panelu. Uruchamia pulpit zdalny wprost adresem
# (mstsc /v:), bez pośrednictwa pliku .rdp.
#
# Dlaczego bez pliku: aktualizacja zabezpieczeń Windows z kwietnia 2026
# (CVE-2026-26151) pokazuje ostrzeżenie „nieznany wydawca" przy KAŻDYM otwarciu
# niepodpisanego pliku .rdp — bez opcji „nie pytaj ponownie" — i przy okazji
# wyłącza wszystkie przekierowania (schowek, drukarki) na czas jednej sesji.
# Połączenia startowanego adresem ta zmiana nie dotyczy: okno się nie pokazuje,
# a ustawienia biorą się z Default.rdp użytkownika, więc schowek działa od razu.
# Zapamiętane hasła zostają bez zmian — Menedżer poświadczeń trzyma je pod
# TERMSRV/<adres>, a każda maszyna ma własny adres pętli zwrotnej (localHost()
# w app.js), więc dalej są rozdzielone per maszyna.
#
# Format adresu:
#   tunnelbox-rdp://connect?host=127.0.0.2&port=13391&name=Klient%20Alfa%20-%20Serwer%20RDP
#
# Dane z adresu pochodzą ze strony WWW, więc są tu ściśle walidowane:
# host tylko z pętli zwrotnej, port liczbowy. Nazwa jest opcjonalna i służy już
# tylko do komunikatu o błędzie (bez pliku nie ma czego nazywać).

param([Parameter(Position = 0)][string]$Url)

$ErrorActionPreference = 'Stop'

# Tryb diagnostyczny: nie uruchamia pulpitu zdalnego i nie pokazuje okienek —
# wypisuje na konsolę polecenie, które by poszło. Używany przy testowaniu skryptu.
#   $env:TUNNELBOX_RDP_TEST = '1'
$Quiet = $env:TUNNELBOX_RDP_TEST -eq '1'

function Show-Error([string]$Message) {
    if ($Quiet) {
        Write-Host "ERROR: $Message"
        exit 1
    }
    try {
        Add-Type -AssemblyName System.Windows.Forms -ErrorAction SilentlyContinue
        [System.Windows.Forms.MessageBox]::Show($Message, 'Tunnelbox — RDP', 'OK', 'Error') | Out-Null
    } catch {
        Write-Host $Message
    }
    exit 1
}

if (-not $Url) { Show-Error 'No connection address.' }

# --- rozbiór adresu ---
$query = $Url -replace '^[^?]*\??', ''
$params = @{}
foreach ($pair in ($query -split '&')) {
    $kv = $pair -split '=', 2
    if ($kv.Count -eq 2 -and $kv[0]) {
        $params[$kv[0]] = [Uri]::UnescapeDataString($kv[1].Replace('+', ' '))
    }
}

$targetHost = [string]$params['host']
$targetPort = [string]$params['port']
$name       = [string]$params['name']

# --- walidacja (dane pochodzą ze strony — nie ufamy im) ---
if ($targetHost -notmatch '^127\.0\.0\.(?:[2-9]|[1-9]\d|1\d\d|2[0-4]\d|25[0-4])$') {
    Show-Error "Invalid machine address: $targetHost"
}
if ($targetPort -notmatch '^\d{1,5}$' -or [int]$targetPort -lt 1 -or [int]$targetPort -gt 65535) {
    Show-Error "Invalid port: $targetPort"
}

# nazwa trafia tylko do komunikatu o błędzie — czyścimy ze znaków sterujących
$safeName = ($name -replace '[\x00-\x1F]', '').Trim()
if ($safeName.Length -gt 100) { $safeName = $safeName.Substring(0, 100).Trim() }

# --- uruchom pulpit zdalny ---
# Bez /f: tryb ekranu, przekierowania i reszta biorą się z Default.rdp, czyli
# z tego, co użytkownik sam ustawił w pulpicie zdalnym.
$target = "${targetHost}:${targetPort}"

if ($Quiet) {
    Write-Host "OK: mstsc.exe /v:$target"
    exit 0
}
try {
    Start-Process -FilePath 'mstsc.exe' -ArgumentList "/v:$target"
} catch {
    $what = if ($safeName) { "$safeName ($target)" } else { $target }
    Show-Error "Could not start Remote Desktop (mstsc).`n`nMachine: $what"
}
