# Helper protokołu tunnelbox-update:// — wywoływany przez Windows po kliknięciu
# „Zaktualizuj" w panelu. Robi dokładnie to, co użytkownik robiłby ręcznie: pobiera
# paczkę ze strony wydań, rozpakowuje ją i uruchamia jej start.ps1 (a ten wczytuje
# obraz, sprząta po poprzedniej wersji i przenosi zapisane połączenia).
#
# Format adresu:
#   tunnelbox-update://install?version=3.0.0
#
# Ze strony przychodzi WYŁĄCZNIE numer wersji — adres pliku do pobrania helper
# ustala sam, odpytując stronę wydań. Dzięki temu panel nie ma jak podsunąć
# niczego innego do ściągnięcia, nawet gdyby ktoś podłożył mu spreparowaną
# odpowiedź. Adres pliku jest dodatkowo sprawdzany pod kątem pochodzenia.
#
# Kontrakt (tag wydania i nazwa pliku) musi zgadzać się z app/updates.py —
# pilnuje tego test w tests/test_packaging.py.

param([Parameter(Position = 0)][string]$Url)

$ErrorActionPreference = 'Stop'
# Pasek postępu Invoke-WebRequest potrafi spowolnić pobieranie kilkukrotnie.
$ProgressPreference = 'SilentlyContinue'

# Tryb diagnostyczny: sprawdza tylko rozbiór adresu, nie rusza sieci ani Dockera.
#   $env:TUNNELBOX_UPDATE_TEST = '1'
$Quiet = $env:TUNNELBOX_UPDATE_TEST -eq '1'

# Strona wydań to hub Mysttic/Mysttic: trzyma wydania kilku programów, ten ma prefiks tagu.
$HubApi = 'https://api.github.com/repos/Mysttic/Mysttic/releases?per_page=100'
$TagPrefix = 'tunnelbox-v'
$DownloadPrefix = 'https://github.com/Mysttic/Mysttic/releases/download/'
$PageUrl = 'https://mysttic.github.io/Mysttic/tunnelbox/'
$PanelApi = 'http://127.0.0.1:25263/api/vault'

$AppHome = Join-Path $env:LOCALAPPDATA 'Tunnelbox'
$VersionsDir = Join-Path $AppHome 'versions'

function Stop-WithError([string]$Message) {
    Write-Host ""
    Write-Host $Message -ForegroundColor Red
    Write-Host "You can always download the package manually: $PageUrl" -ForegroundColor Yellow
    if (-not $Quiet) { Read-Host "Press Enter to close" }
    exit 1
}

# --- rozbiór adresu (dane ze strony — nie ufamy im) ---

if (-not $Url) { Stop-WithError 'No version number to install.' }

$query = $Url -replace '^[^?]*\??', ''
$version = $null
foreach ($pair in ($query -split '&')) {
    $kv = $pair -split '=', 2
    if ($kv.Count -eq 2 -and $kv[0] -eq 'version') {
        $version = [Uri]::UnescapeDataString($kv[1].Replace('+', ' ')).Trim()
    }
}
if ($version -notmatch '^\d+\.\d+\.\d+$') {
    Stop-WithError "Invalid version number: $version"
}

if ($Quiet) { Write-Host "OK: $version"; exit 0 }

$tag = "$TagPrefix$version"
$assetName = "tunnelbox-$version.zip"

Write-Host "Tunnelbox — updating to version $version" -ForegroundColor Cyan
Write-Host ""

# Windows PowerShell 5.1 na starszych systemach domyślnie próbuje TLS 1.0 —
# GitHub takie połączenie odrzuca.
try {
    [Net.ServicePointManager]::SecurityProtocol =
        [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
} catch { }

# --- gdzie leży paczka ---

Write-Host "Looking for the package on the releases page..."
try {
    $releases = Invoke-RestMethod -Uri $HubApi -TimeoutSec 20 -UseBasicParsing -Headers @{
        'Accept' = 'application/vnd.github+json'
        'User-Agent' = 'Tunnelbox-Panel'
    }
} catch {
    Stop-WithError "Could not connect to the releases page.`n$($_.Exception.Message)"
}

$release = @($releases) |
    Where-Object { $_.tag_name -eq $tag -and -not $_.draft -and -not $_.prerelease } |
    Select-Object -First 1
if (-not $release) { Stop-WithError "Release $tag was not found on the releases page." }

$asset = @($release.assets) | Where-Object { $_.name -eq $assetName } | Select-Object -First 1
if (-not $asset) { Stop-WithError "Release $tag does not contain the file $assetName." }

# Właściciel i nazwa repozytorium w ścieżce GitHuba nie rozróżniają wielkości liter,
# a API zwraca je w postaci kanonicznej, więc prefiks porównujemy bez rozróżniania
# wielkości liter.
$downloadUrl = [string]$asset.browser_download_url
if (-not $downloadUrl.StartsWith($DownloadPrefix, [StringComparison]::OrdinalIgnoreCase)) {
    Stop-WithError "The file address does not come from the releases page:`n$downloadUrl"
}

# --- pobranie ---

New-Item -ItemType Directory -Force -Path $VersionsDir | Out-Null
$zip = Join-Path $AppHome $assetName
$megabytes = if ($asset.size) { [math]::Round($asset.size / 1MB) } else { 0 }

Write-Host "Downloading $assetName ($megabytes MB) — this will take a while..."
try {
    Invoke-WebRequest -Uri $downloadUrl -OutFile $zip -TimeoutSec 1800 -UseBasicParsing
} catch {
    Stop-WithError "Could not download the package.`n$($_.Exception.Message)"
}

if ($asset.size -and (Get-Item -LiteralPath $zip).Length -ne [int64]$asset.size) {
    Remove-Item -LiteralPath $zip -Force -ErrorAction SilentlyContinue
    Stop-WithError "The downloaded file is incomplete — please try again."
}

# --- rozpakowanie ---

$target = Join-Path $VersionsDir "tunnelbox-$version"
if (Test-Path -LiteralPath $target) {
    Remove-Item -LiteralPath $target -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host "Unpacking..."
try {
    Expand-Archive -LiteralPath $zip -DestinationPath $VersionsDir -Force
} catch {
    Stop-WithError "Could not unpack the package.`n$($_.Exception.Message)"
}
Remove-Item -LiteralPath $zip -Force -ErrorAction SilentlyContinue

$start = Join-Path $target 'start.ps1'
if (-not (Test-Path -LiteralPath $start)) {
    Stop-WithError "The package does not contain start.ps1 — install it manually: $VersionsDir"
}

# --- instalacja (to samo, co dwuklik w start.bat) ---

Write-Host ""
& $start

# --- sprzątanie: dopiero gdy nowa wersja faktycznie wstała ---

$running = $false
$deadline = (Get-Date).AddSeconds(60)
while ((Get-Date) -lt $deadline) {
    try {
        $status = Invoke-RestMethod -Uri $PanelApi -TimeoutSec 3
        if ($status.version -eq $version) { $running = $true; break }
    } catch { }
    Start-Sleep -Seconds 2
}

Write-Host ""
if ($running) {
    Write-Host "Done — the panel is running version $version." -ForegroundColor Green
    # Kasujemy wyłącznie starsze paczki z NASZEGO katalogu wersji. Folder, do którego
    # użytkownik sam rozpakował poprzednią wersję, zostaje nietknięty.
    Get-ChildItem -LiteralPath $VersionsDir -Directory -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -match '^tunnelbox-\d+\.\d+\.\d+$' -and $_.FullName -ne $target } |
        ForEach-Object { Remove-Item -LiteralPath $_.FullName -Recurse -Force -ErrorAction SilentlyContinue }
} else {
    Write-Host "Could not confirm that the new version is running." -ForegroundColor Yellow
    Write-Host "Run start.bat from the folder: $target" -ForegroundColor Yellow
    Read-Host "Press Enter to close"
}
