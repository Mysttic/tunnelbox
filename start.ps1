# Uruchamia panel Tunnelbox (ze źródeł) i otwiera go w przeglądarce.
# Najprościej: dwuklik start.bat. Można też: prawy klik -> "Uruchom w programie PowerShell".

Set-Location $PSScriptRoot

# Konfiguruje szybkie łączenie RDP: rejestruje protokół tunnelbox-rdp:// dla bieżącego
# użytkownika (HKCU, bez uprawnień administratora), dzięki czemu kliknięcie „Połącz
# przez RDP" w panelu od razu otwiera pulpit zdalny. Zapisuje tylko przy zmianie.
# Sam przycisk w panelu można przełączyć w Ustawieniach (Szybkie łączenie RDP).
function Enable-FastRdp {
    param([string]$LauncherSource)

    if (-not (Test-Path -LiteralPath $LauncherSource)) { return $false }

    $home2 = Join-Path $env:LOCALAPPDATA 'Tunnelbox'
    $dest = Join-Path $home2 'rdp-launcher.ps1'
    New-Item -ItemType Directory -Force -Path $home2 | Out-Null

    $needCopy = -not (Test-Path -LiteralPath $dest) -or
        (Get-FileHash -LiteralPath $LauncherSource).Hash -ne (Get-FileHash -LiteralPath $dest).Hash
    if ($needCopy) { Copy-Item -LiteralPath $LauncherSource -Destination $dest -Force }

    $psExe = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
    $command = "`"$psExe`" -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$dest`" `"%1`""

    $key = "HKCU:\Software\Classes\tunnelbox-rdp"
    $cmdKey = Join-Path $key 'shell\open\command'
    $current = (Get-ItemProperty -Path $cmdKey -Name '(default)' -ErrorAction SilentlyContinue).'(default)'
    if ($current -eq $command) { return $false }   # już skonfigurowane

    New-Item -Path $cmdKey -Force | Out-Null
    Set-ItemProperty -Path $key -Name '(default)' -Value 'URL:Tunnelbox RDP'
    Set-ItemProperty -Path $key -Name 'URL Protocol' -Value ''
    Set-ItemProperty -Path $cmdKey -Name '(default)' -Value $command
    return $true
}

# Czy docker jest w PATH?
try { $null = Get-Command docker -ErrorAction Stop } catch {
    Write-Host "Docker not found. Install Docker Desktop: https://www.docker.com/products/docker-desktop/" -ForegroundColor Red
    Read-Host "Press Enter to close"
    exit 1
}

# Czy silnik Dockera działa? (cmd /c pochłania stderr, więc EAP nie przerywa skryptu)
cmd /c "docker info >nul 2>nul"
if ($LASTEXITCODE -ne 0) {
    Write-Host "Docker is not running. Start Docker Desktop and try again." -ForegroundColor Red
    Read-Host "Press Enter to close"
    exit 1
}

Write-Host "Starting the Tunnelbox panel (the first run can take a few minutes)..."
docker compose -f docker-compose.yml -f docker-compose.build.yml up -d --build
if ($LASTEXITCODE -ne 0) {
    Write-Host "Could not start the panel. Details above." -ForegroundColor Red
    Read-Host "Press Enter to close"
    exit 1
}

try {
    if (Enable-FastRdp (Join-Path $PSScriptRoot 'packaging\rdp-launcher.ps1')) {
        Write-Host "Enabled fast RDP connect (clicking in the panel opens Remote Desktop)." -ForegroundColor Green
    }
} catch {
    Write-Host "Warning: could not set up fast RDP connect ($($_.Exception.Message))." -ForegroundColor Yellow
}

Start-Process "http://tunnelbox.localhost:25263"
Write-Host "The panel is running at http://tunnelbox.localhost:25263" -ForegroundColor Green
