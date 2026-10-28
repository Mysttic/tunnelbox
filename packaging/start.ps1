# Uruchamia panel Tunnelbox z obrazu dołączonego do paczki.
# Najprościej: dwuklik start.bat.
#
# Aktualizacja działa sama: skrypt wykrywa poprzednią wersję, przenosi z niej
# zapisane połączenia (vault.enc), usuwa stary kontener i stare obrazy, po czym
# uruchamia nową wersję. Nie trzeba nic robić ręcznie ani rozpakowywać w konkretne
# miejsce — dane użytkownika leżą poza folderem programu.
#
# Ten skrypt uruchamia też helper aktualizacji z panelu (update-launcher.ps1), który
# po nim czeka na nową wersję pod http://127.0.0.1:25263. Panel musi więc wstać pod
# tym samym adresem przed końcem skryptu, a na tej ścieżce nie może być pytań do
# użytkownika.

Set-Location $PSScriptRoot

# Helper aktualizacji ma $ErrorActionPreference = 'Stop', a wywołany skrypt tę
# zmienną dziedziczy. Windows PowerShell 5.1 zamienia wtedy każdy wpis dockera na
# stderr (np. „No such object" dla nieistniejącego kontenera — nawet przy 2>$null)
# w błąd przerywający i instalacja urwałaby się w połowie. Wyniki dockera
# sprawdzamy sami przez $LASTEXITCODE.
$ErrorActionPreference = 'Continue'

# Katalog z danymi użytkownika (sejf z połączeniami). Trzymany poza folderem
# programu, żeby rozpakowanie nowej paczki gdziekolwiek indziej niczego nie gubiło.
$AppHome = Join-Path $env:LOCALAPPDATA 'Tunnelbox'
$DataDir = Join-Path $AppHome 'data'
$ContainerName = 'tunnelbox'
$ImageRepository = 'tunnelbox'
# Katalog roboczy na czas instalacji — kasowany dopiero po potwierdzeniu, że
# konfiguracja wczytała się do nowej wersji.
$StagingDir = Join-Path $env:TEMP 'Tunnelbox-migration'

# Rejestruje protokół dla bieżącego użytkownika (HKCU, bez uprawnień administratora)
# i kopiuje helper do katalogu programu. Dzięki temu kliknięcie w panelu potrafi
# uruchomić coś na komputerze. Wywoływane przy każdym starcie, ale zapisuje tylko
# wtedy, gdy czegoś brakuje lub coś się zmieniło.
function Register-Handler {
    param(
        [string]$Key,            # pełna ścieżka klucza w HKCU
        [string]$Title,
        [string]$LauncherSource,
        [switch]$Hidden          # helper bez własnego okna
    )

    if (-not (Test-Path -LiteralPath $LauncherSource)) { return $false }

    $dest = Join-Path $AppHome (Split-Path -Leaf $LauncherSource)
    New-Item -ItemType Directory -Force -Path $AppHome | Out-Null

    $needCopy = -not (Test-Path -LiteralPath $dest) -or
        (Get-FileHash -LiteralPath $LauncherSource).Hash -ne (Get-FileHash -LiteralPath $dest).Hash
    if ($needCopy) { Copy-Item -LiteralPath $LauncherSource -Destination $dest -Force }

    $psExe = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
    $style = if ($Hidden) { ' -WindowStyle Hidden' } else { '' }
    $command = "`"$psExe`" -NoProfile -ExecutionPolicy Bypass$style -File `"$dest`" `"%1`""

    $cmdKey = Join-Path $Key 'shell\open\command'
    $current = (Get-ItemProperty -Path $cmdKey -Name '(default)' -ErrorAction SilentlyContinue).'(default)'
    if ($current -eq $command) { return $false }   # już skonfigurowane

    New-Item -Path $cmdKey -Force | Out-Null
    Set-ItemProperty -Path $Key -Name '(default)' -Value $Title
    Set-ItemProperty -Path $Key -Name 'URL Protocol' -Value ''
    Set-ItemProperty -Path $cmdKey -Name '(default)' -Value $command
    return $true
}

# Szybkie łączenie RDP: kliknięcie „Połącz przez RDP" w panelu od razu otwiera pulpit
# zdalny. Sam przycisk można przełączyć w Ustawieniach (Szybkie łączenie RDP).
function Enable-FastRdp {
    param([string]$LauncherSource)
    return Register-Handler -Key "HKCU:\Software\Classes\tunnelbox-rdp" `
                            -Title 'URL:Tunnelbox RDP' `
                            -LauncherSource $LauncherSource -Hidden
}

# Aktualizacja z panelu: kliknięcie „Zaktualizuj" pobiera nową paczkę i ją instaluje.
# Bez -Hidden — instalator ma pokazać okno z postępem, bo pobieranie trwa.
function Enable-Updates {
    param([string]$LauncherSource)
    return Register-Handler -Key "HKCU:\Software\Classes\tunnelbox-update" `
                            -Title 'URL:Tunnelbox update' `
                            -LauncherSource $LauncherSource
}

# Obraz, który ma być uruchomiony (źródłem prawdy jest docker-compose.yml paczki).
function Get-DesiredImage {
    $match = Select-String -Path (Join-Path $PSScriptRoot 'docker-compose.yml') `
                           -Pattern '^\s*image:\s*(\S+)' | Select-Object -First 1
    if ($match) { return $match.Matches[0].Groups[1].Value }
    return $null
}

# Numer wersji z tagu obrazu: „tunnelbox:3.0.0" -> 3.0.0.
function Get-ImageVersion {
    param([string]$Image)
    if ($Image -match ':(\d+\.\d+\.\d+)$') { return [version]$Matches[1] }
    return $null
}

# Obraz kontenera o podanej nazwie; $null, gdy takiego kontenera nie ma.
# --type container: bez tego docker inspect znalazłby też OBRAZ o tej nazwie
# (np. tunnelbox:latest zbudowany kiedyś ręcznie).
function Get-ContainerImage {
    param([string]$Name)
    $img = docker inspect --type container $Name --format '{{.Config.Image}}' 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $img) { return $null }
    return ([string]($img | Select-Object -First 1)).Trim()
}

# Ścieżka do danych, których używała poprzednia wersja (mogła stać w innym folderze).
# Uwaga: szablon nie może zawierać cudzysłowów — PowerShell zjada je przy przekazywaniu
# argumentu do docker.exe i szablon Go się nie parsuje. Dlatego bierzemy całe .Mounts
# jako JSON i filtrujemy już po stronie PowerShella.
function Get-ContainerDataPath {
    param([string]$Name)
    $json = docker inspect --type container $Name --format '{{json .Mounts}}' 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $json) { return $null }
    try { $mounts = ($json | Out-String) | ConvertFrom-Json } catch { return $null }
    $mount = @($mounts) | Where-Object { $_.Destination -eq '/data' } | Select-Object -First 1
    if (-not $mount) { return $null }
    return ([string]$mount.Source).Trim()
}

# Folder paczki, z której compose utworzył kontener (etykieta compose; ten sam
# powód co wyżej, że bez cudzysłowów w szablonie). $null, gdy kontener powstał
# inaczej (np. docker run).
function Get-ContainerFolder {
    param([string]$Name)
    $json = docker inspect --type container $Name --format '{{json .Config.Labels}}' 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $json) { return $null }
    try { $labels = ($json | Out-String) | ConvertFrom-Json } catch { return $null }
    if (-not $labels) { return $null }
    $folder = [string]$labels.'com.docker.compose.project.working_dir'
    if (-not $folder) { return $null }
    return $folder.Trim()
}

# Stare obrazy programu. Kasujemy wyłącznie tagi wyglądające jak wersja (X.Y.Z)
# z podanego repozytorium, żeby nie ruszyć np. obrazu zbudowanego lokalnie ze
# źródeł (:dev, :latest) ani obrazu z rejestru (ghcr.io/..., inne repozytorium).
function Remove-OldImages {
    param(
        [string]$Repository,
        [string]$Keep            # tag, który ma zostać (ten z paczki)
    )
    docker images $Repository --format '{{.Repository}}:{{.Tag}}' 2>$null | ForEach-Object {
        $tag = ([string]$_).Trim()
        if ($tag -and $tag -ne $Keep -and $tag -match ':\d+\.\d+\.\d+$') {
            docker rmi $tag 2>$null | Out-Null
        }
    }
}

# Wszystkie miejsca, w których może leżeć sejf poprzedniej instalacji — od
# najpewniejszego. Kontener starej wersji bywa już usunięty (np. przez
# „docker compose down"), dlatego szukamy też w folderach obok tej paczki:
# ZIP rozpakowuje się do katalogu z numerem wersji, więc poprzednia wersja zwykle
# stoi jako katalog sąsiedni.
function Get-VaultCandidates {
    $dirs = @()

    $dirs += $DataDir                                  # konfiguracja bieżącej instalacji

    $fromContainer = Get-ContainerDataPath $ContainerName
    if ($fromContainer) { $dirs += $fromContainer }

    $dirs += (Join-Path $PSScriptRoot 'data')          # nadpisanie w tym samym folderze

    $parent = Split-Path -Parent $PSScriptRoot
    if ($parent -and (Test-Path -LiteralPath $parent)) {
        $dirs += (Join-Path $parent 'data')            # dane obok folderu paczki
        # sąsiednie instalacje — najświeższy sejf pierwszy
        $siblings = Get-ChildItem -LiteralPath $parent -Directory -ErrorAction SilentlyContinue |
            Where-Object { $_.FullName -ne $PSScriptRoot } |
            ForEach-Object { Join-Path $_.FullName 'data' } |
            Where-Object { Test-Path -LiteralPath (Join-Path $_ 'vault.enc') } |
            Sort-Object { (Get-Item (Join-Path $_ 'vault.enc')).LastWriteTime } -Descending
        $dirs += $siblings
    }
    return $dirs
}

# KROK 1 — zabezpieczenie konfiguracji przed instalacją.
# Kopiujemy istniejący sejf do katalogu roboczego. Kopia jest kasowana dopiero wtedy,
# gdy po instalacji potwierdzimy, że konfiguracja wczytała się do nowej wersji.
function Backup-VaultToStaging {
    foreach ($dir in (Get-VaultCandidates)) {
        if (-not $dir) { continue }
        $source = Join-Path $dir 'vault.enc'
        if (-not (Test-Path -LiteralPath $source)) { continue }

        New-Item -ItemType Directory -Force -Path $StagingDir | Out-Null
        $staged = Join-Path $StagingDir 'vault.enc'
        Copy-Item -LiteralPath $source -Destination $staged -Force
        return [pscustomobject]@{ File = $staged; Source = $dir }
    }
    return $null
}

# Czeka, aż nowa wersja panelu odpowie, i mówi, czy widzi konfigurację.
function Get-PanelVaultStatus {
    param([int]$TimeoutSeconds = 60)

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            return Invoke-RestMethod -Uri 'http://127.0.0.1:25263/api/vault' -TimeoutSec 3
        } catch {
            Start-Sleep -Seconds 1
        }
    }
    return $null
}

# KROK 2 — po instalacji: wczytanie konfiguracji do nowej wersji i weryfikacja.
# Zwraca 'ok' | 'brak-panelu' | 'niepotwierdzone'.
function Restore-VaultFromStaging {
    param([string]$StagedFile)

    $target = Join-Path $DataDir 'vault.enc'
    $status = Get-PanelVaultStatus
    if (-not $status) { return 'brak-panelu' }

    if (-not $status.exists) {
        Copy-Item -LiteralPath $StagedFile -Destination $target -Force
        $status = Get-PanelVaultStatus -TimeoutSeconds 20
    }

    # Potwierdzenie: panel widzi sejf ORAZ plik jest identyczny z kopią roboczą.
    if ($status -and $status.exists -and (Test-Path -LiteralPath $target) -and
        (Get-FileHash -LiteralPath $target).Hash -eq (Get-FileHash -LiteralPath $StagedFile).Hash) {
        return 'ok'
    }
    return 'niepotwierdzone'
}

# --- wymagania ---

try { $null = Get-Command docker -ErrorAction Stop } catch {
    Write-Host "Docker not found. Install Docker Desktop: https://www.docker.com/products/docker-desktop/" -ForegroundColor Red
    Read-Host "Press Enter to close"
    exit 1
}

cmd /c "docker info >nul 2>nul"
if ($LASTEXITCODE -ne 0) {
    Write-Host "Docker is not running. Start Docker Desktop and try again." -ForegroundColor Red
    Read-Host "Press Enter to close"
    exit 1
}

# --- ochrona przed cofnięciem wersji ---

# Aktualizacja z panelu rozpakowuje nową wersję do własnego katalogu, więc folder ze
# starą paczką (a często i skrót do jej start.bat) zostaje na dysku. Uruchomiony przez
# przypadek zainstalowałby z powrotem starszą wersję — pytamy, zanim to zrobimy.
# Pytanie pada tylko wtedy, gdy działa NOWSZA wersja; zwykła aktualizacja przechodzi
# bez zatrzymania.
$runningImage = Get-ContainerImage $ContainerName
$desiredVersion = Get-ImageVersion (Get-DesiredImage)
$runningVersion = Get-ImageVersion $runningImage
if ($desiredVersion -and $runningVersion -and $runningVersion -gt $desiredVersion) {
    Write-Host "A newer version is already running on this computer: $runningVersion." -ForegroundColor Yellow
    Write-Host "This package is version $desiredVersion." -ForegroundColor Yellow
    if ((Read-Host "Install the older version anyway? [y/N]") -notmatch '^[yYtT]') {
        Write-Host "Keeping the newer version — opening the panel." -ForegroundColor Green
        docker start $ContainerName 2>$null | Out-Null
        Start-Process "http://tunnelbox.localhost:25263"
        exit 0
    }
}

# --- dane użytkownika i ewentualna migracja z poprzedniej wersji ---

New-Item -ItemType Directory -Force -Path $DataDir | Out-Null
$env:TUNNELBOX_DATA = ($DataDir -replace '\\', '/')

# KROK 1: zanim cokolwiek ruszymy — kopia robocza istniejącej konfiguracji.
$staged = Backup-VaultToStaging
if ($staged) {
    Write-Host "Saved your current configuration for the duration of the install." -ForegroundColor DarkGray
    Write-Host "  source: $($staged.Source)" -ForegroundColor DarkGray
}

# --- wczytanie nowego obrazu ---

$imageTar = Get-ChildItem -Path $PSScriptRoot -Filter "tunnelbox-image-*.tar.gz" | Select-Object -First 1
if (-not $imageTar) {
    Write-Host "Image file (tunnelbox-image-*.tar.gz) not found in this folder." -ForegroundColor Red
    Write-Host "Make sure you extracted the whole ZIP package." -ForegroundColor Yellow
    Read-Host "Press Enter to close"
    exit 1
}

Write-Host "Loading the Tunnelbox image into Docker (the first run takes a while)..."
docker load -i $imageTar.FullName
if ($LASTEXITCODE -ne 0) {
    Write-Host "Could not load the image. Check that the file is not damaged." -ForegroundColor Red
    Read-Host "Press Enter to close"
    exit 1
}

# --- usunięcie poprzedniej wersji (tylko gdy to faktycznie aktualizacja) ---

$desiredImage = Get-DesiredImage
$currentImage = Get-ContainerImage $ContainerName
if ($currentImage -and $desiredImage -and $currentImage -ne $desiredImage) {
    Write-Host "Found the previous version ($currentImage) — removing it..."
    docker rm -f $ContainerName 2>$null | Out-Null
    Remove-OldImages -Repository $ImageRepository -Keep $desiredImage
} elseif ($currentImage -and (Get-ContainerFolder $ContainerName) -ne $PSScriptRoot) {
    # Ta sama wersja, ale uruchomiona z innego folderu (np. paczka rozpakowana drugi
    # raz). Compose nie przejmie kontenera z innego folderu, bo zgłosiłby konflikt
    # nazwy, więc tworzymy go od nowa stąd.
    Write-Host "The panel was started from another folder — recreating it from this one..."
    docker rm -f $ContainerName 2>$null | Out-Null
}

# --- uruchomienie ---

docker compose up -d
if ($LASTEXITCODE -ne 0) {
    Write-Host "Could not start the panel. Details above." -ForegroundColor Red
    Read-Host "Press Enter to close"
    exit 1
}

# KROK 2: konfiguracja do nowej wersji + potwierdzenie. Kopię roboczą kasujemy
# dopiero po potwierdzeniu — inaczej zostaje na dysku razem ze ścieżką na ekranie.
if ($staged) {
    switch (Restore-VaultFromStaging $staged.File) {
        'ok' {
            Write-Host "Configuration moved to the new version and confirmed." -ForegroundColor Green
            Remove-Item -LiteralPath $StagingDir -Recurse -Force -ErrorAction SilentlyContinue
        }
        'brak-panelu' {
            Write-Host "The panel did not respond — cannot confirm that the configuration was moved." -ForegroundColor Yellow
            Write-Host "A backup copy is waiting in: $($staged.File)" -ForegroundColor Yellow
        }
        default {
            Write-Host "Could not confirm that the configuration was moved." -ForegroundColor Yellow
            Write-Host "A backup copy is waiting in: $($staged.File)" -ForegroundColor Yellow
            Write-Host "To restore it: close the panel and copy this file to $DataDir" -ForegroundColor Yellow
        }
    }
}

try {
    if (Enable-Updates (Join-Path $PSScriptRoot 'update-launcher.ps1')) {
        Write-Host "Enabled updating from the panel (the 'Update' button downloads the new version)." -ForegroundColor Green
    }
} catch {
    Write-Host "Warning: could not set up updating from the panel ($($_.Exception.Message))." -ForegroundColor Yellow
    Write-Host "The panel works normally — you can always download a newer package manually." -ForegroundColor Yellow
}

try {
    if (Enable-FastRdp (Join-Path $PSScriptRoot 'rdp-launcher.ps1')) {
        Write-Host "Enabled fast RDP connect (clicking in the panel opens Remote Desktop)." -ForegroundColor Green
    }
} catch {
    Write-Host "Warning: could not set up fast RDP connect ($($_.Exception.Message))." -ForegroundColor Yellow
    Write-Host "The panel works normally — use 'Download .rdp file' in the machine menu." -ForegroundColor Yellow
}

Start-Process "http://tunnelbox.localhost:25263"
Write-Host "The panel is running at http://tunnelbox.localhost:25263" -ForegroundColor Green
Write-Host "Your connections are stored in: $DataDir" -ForegroundColor DarkGray
