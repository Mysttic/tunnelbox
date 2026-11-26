<#
.SYNOPSIS
    Test skryptu post-bmc.ps1 bez Notion i bez GitHuba: atrapa API Notion na localhost i dane wydań z plików.

.DESCRIPTION
    Uruchamia post-bmc.ps1 w osobnym procesie tego samego PowerShella (Windows PowerShell 5.1 albo pwsh) na części
    3.0.0 z CHANGELOG.md i na próbnych częściach 3.1.0 i 3.0.1. Atrapa odpowiada jak API Notion: Terminy wpisów
    „Post BMC” jak w kalendarzu 26.11.2026 (najpóźniejszy 2026-12-06), wpis już istniejący, błąd serwera
    z identyfikatorem bazy i limit zapytań. Test sprawdza właściwości i treść wpisu, Termin, pominięcie wydania
    wstępnego i szkicu, duplikat, ostrzeżenie z kodem wyjścia 0 przy błędzie, tekst posta bez kodu, nazw plików
    i numerów issues, skąd pobrać (Docker Hub i strona projektu), zdanie o Fortinecie raz, przed podziękowaniem,
    oraz to, że sekrety nie trafiają do logu. Kończy się kodem 1, gdy któreś sprawdzenie nie przejdzie. Wzór:
    post-bmc-test.ps1 z Chatt (a ten z MystticRock).

.EXAMPLE
    powershell -File .github\scripts\post-bmc-test.ps1
#>
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$script = Join-Path $PSScriptRoot 'post-bmc.ps1'
$shell = (Get-Process -Id $PID).Path
$work = Join-Path ([System.IO.Path]::GetTempPath()) "post-bmc-test-$([guid]::NewGuid().ToString('N'))"
New-Item -ItemType Directory -Path $work | Out-Null

$token = 'atrapa-tokenu-notion'
$dataSource = '0123456789abcdef0123456789abcdef'
$dataSourceDashed = '01234567-89ab-cdef-0123-456789abcdef'
$dockerHubUrl = 'https://hub.docker.com/r/programistticsolutions/tunnelbox'
$pageUrl = 'https://mysttic.github.io/Mysttic/tunnelbox/'
$disclaimer = 'Tunnelbox is an independent project, not affiliated with or endorsed by Fortinet.'
$failures = New-Object System.Collections.Generic.List[string]
$savedEnvironment = @{}
foreach ($name in 'GITHUB_STEP_SUMMARY', 'GITHUB_ACTIONS', 'NOTION_TOKEN', 'NOTION_CALENDAR_DATA_SOURCE_ID') {
    $savedEnvironment[$name] = [Environment]::GetEnvironmentVariable($name)
}
# Bez maskowania Actions: skrypt wypisałby wtedy formy identyfikatora bazy w poleceniach ::add-mask::
$env:GITHUB_ACTIONS = $null

function Write-Utf8([string]$Path, [string]$Text) {
    [System.IO.File]::WriteAllText($Path, $Text, [System.Text.UTF8Encoding]::new($false))
}

function New-Release([string]$Name, [string]$Version, [bool]$Prerelease = $false, [bool]$Draft = $false) {
    $path = Join-Path $work "$Name.json"
    $flags = $Draft.ToString().ToLowerInvariant(), $Prerelease.ToString().ToLowerInvariant()
    Write-Utf8 $path ('{{"url":"https://github.com/Mysttic/tunnelbox/releases/tag/v{0}","isDraft":{1},"isPrerelease":{2}}}' -f $Version, $flags[0], $flags[1])
    $path
}

function New-PageJson([string]$Url, [string]$Start, [string]$End) {
    $endJson = if ($End) { '"' + $End + '"' } else { 'null' }
    '{{"object":"page","url":"{0}","properties":{{"Termin":{{"id":"x","type":"date","date":{{"start":"{1}","end":{2},"time_zone":null}}}}}}}}' -f $Url, $Start, $endJson
}

$calendar = '[' + ((New-PageJson 'https://www.notion.so/mystticrock-1-0-1' '2026-12-06'), (New-PageJson 'https://www.notion.so/chatt-1-0-1' '2026-12-03'), (New-PageJson 'https://www.notion.so/mysttrainings' '2026-12-01') -join ',') + ']'
$state = [hashtable]::Synchronized(@{
        Scenario = 'ok'
        Calendar = $calendar
        Existing = '[]'
        DataSource = $dataSourceDashed
        Requests = [System.Collections.ArrayList]::Synchronized((New-Object System.Collections.ArrayList))
    })

# Atrapa API Notion: zapytanie z „or” to szukanie duplikatu, inne zapytanie to ostatnie Terminy, POST /v1/pages zapis
$serve = {
    param($Listener, $State)
    while ($Listener.IsListening) {
        try { $context = $Listener.GetContext() } catch { break }
        try {
            $request = $context.Request
            $body = (New-Object System.IO.StreamReader($request.InputStream, [System.Text.Encoding]::UTF8)).ReadToEnd()
            $path = $request.Url.AbsolutePath
            [void]$State.Requests.Add([pscustomobject]@{
                    Method = $request.HttpMethod
                    Path = $path
                    NotionVersion = $request.Headers['Notion-Version']
                    Authorization = $request.Headers['Authorization']
                    Body = $body
                })
            $status = 200
            $retryAfter = $null
            if ($State.Scenario -eq 'blad') {
                $status = 500
                $json = '{"object":"error","status":500,"code":"internal_server_error","message":"Atrapa: baza ' + $State.DataSource + ' nie odpowiada."}'
            }
            elseif ($State.Scenario -eq 'limit' -and $State.Requests.Count -eq 1) {
                $status = 429
                $retryAfter = '1'
                $json = '{"object":"error","status":429,"code":"rate_limited","message":"Atrapa: limit zapytań."}'
            }
            elseif ($path -match '^/v1/data_sources/[^/]+/query$') {
                $results = if ($body -match '"or"') { $State.Existing } else { $State.Calendar }
                $json = '{"object":"list","results":' + $results + ',"has_more":false,"next_cursor":null}'
            }
            elseif ($path -eq '/v1/pages' -and $request.HttpMethod -eq 'POST') {
                $json = '{"object":"page","id":"atrapa","url":"https://www.notion.so/atrapa-wpisu"}'
            }
            else {
                $status = 404
                $json = '{"object":"error","status":404,"code":"object_not_found","message":"Atrapa: nie ma ' + $path + '."}'
            }
            $bytes = [System.Text.Encoding]::UTF8.GetBytes($json)
            $context.Response.StatusCode = $status
            $context.Response.ContentType = 'application/json; charset=utf-8'
            if ($retryAfter) { $context.Response.AddHeader('Retry-After', $retryAfter) }
            $context.Response.OutputStream.Write($bytes, 0, $bytes.Length)
        }
        finally { $context.Response.Close() }
    }
}

function Invoke-PostBmc([string]$Name, [string[]]$Arguments, [string]$Scenario = 'ok', [bool]$Secrets = $true) {
    Write-Host "Przypadek: $Name"
    $state.Scenario = $Scenario
    $state.Requests.Clear()
    $summary = Join-Path $work "podsumowanie-$([guid]::NewGuid().ToString('N')).md"
    Write-Utf8 $summary ''
    $env:GITHUB_STEP_SUMMARY = $summary
    $env:NOTION_TOKEN = if ($Secrets) { $token } else { $null }
    $env:NOTION_CALENDAR_DATA_SOURCE_ID = if ($Secrets) { $dataSource } else { $null }
    $ErrorActionPreference = 'Continue'
    $output = & $shell -NoProfile -ExecutionPolicy Bypass -File $script -ApiBase $api -Today '2026-11-26' @Arguments 2>&1 | Out-String
    $code = $LASTEXITCODE
    $ErrorActionPreference = 'Stop'
    $requests = @($state.Requests.ToArray())
    [pscustomobject]@{
        Output = $output
        Code = $code
        Summary = [System.IO.File]::ReadAllText($summary, [System.Text.Encoding]::UTF8)
        Requests = $requests
        Pages = @($requests | Where-Object { $_.Path -eq '/v1/pages' })
    }
}

function Test-That([string]$Name, [bool]$Condition) {
    if ($Condition) { Write-Host "  OK    $Name" }
    else {
        Write-Host "  BŁĄD  $Name"
        $failures.Add($Name)
    }
}

# Wynik przypadku: kod 0 (błąd nie oznacza wydania jako nieudanego), log bez tokenu i identyfikatora bazy; po błędzie
# sprawdzenia cały log skryptu dla diagnozy
function Test-Run($Run, [int]$FailuresBefore) {
    Test-That 'kod wyjścia 0' ($Run.Code -eq 0)
    $secretInLog = $Run.Output.Contains($token) -or $Run.Output.Contains($dataSource) -or $Run.Output.Contains($dataSourceDashed)
    $secretInSummary = $Run.Summary.Contains($token) -or $Run.Summary.Contains($dataSource) -or $Run.Summary.Contains($dataSourceDashed)
    Test-That 'sekrety poza logiem i podsumowaniem' (-not $secretInLog -and -not $secretInSummary)
    if ($failures.Count -gt $FailuresBefore) { Write-Host $Run.Output }
}

# Treść zapisanego wpisu z zapytania POST /v1/pages albo $null (i błąd sprawdzenia), gdy zapisu nie było
function Get-WrittenPage($Run) {
    Test-That 'jeden zapis wpisu' ($Run.Pages.Count -eq 1)
    if ($Run.Pages.Count -ne 1) { return $null }
    $Run.Pages[0].Body | ConvertFrom-Json
}

function Get-BlockText($Block) {
    $content = $Block.($Block.type)
    (@($content.rich_text) | ForEach-Object { $_.text.content }) -join ''
}

function Get-Children($Block) {
    $content = $Block.($Block.type)
    if ($content.PSObject.Properties['children']) { return @($content.children) }
    @()
}

function Get-PageText($Blocks) {
    @($Blocks | ForEach-Object { '{0}: {1}' -f $_.type, (Get-BlockText $_) })
}

# Adresy odnośników w tekście bloku
function Get-LinkUrl($Block) {
    $content = $Block.($Block.type)
    @(@($content.rich_text) | Where-Object { $_.text.PSObject.Properties['link'] } | ForEach-Object { $_.text.link.url })
}

# Teksty instrukcji publikacji: punkty w ramce na początku wpisu
function Get-Notes($Blocks) {
    $callout = @($Blocks)[0]
    @(Get-Children $callout | ForEach-Object { Get-BlockText $_ })
}

# Tekst posta do skopiowania: bloki od nagłówka „Treść do skopiowania” do zwiniętego changelogu, z dziećmi
function Get-PostLines($Blocks) {
    $lines = New-Object System.Collections.Generic.List[string]
    $inside = $false
    foreach ($block in @($Blocks)) {
        if ($block.type -eq 'heading_2') { $inside = $true; continue }
        if ($block.type -eq 'toggle') { break }
        if (-not $inside) { continue }
        $lines.Add((Get-BlockText $block))
        foreach ($child in @(Get-Children $block)) { $lines.Add((Get-BlockText $child)) }
    }
    $lines.ToArray()
}

# Punkty „What changed”: wszystkie punkty posta bez dwóch o tym, skąd pobrać
function Get-Changes($Text) {
    @($Text -like 'bulleted_list_item:*' | Where-Object { $_ -notmatch ': The (image on Docker Hub|package for Windows)' })
}

# Zasady treści z #16: w tekście posta nie ma kodu, nazw plików ani numerów issues
function Test-PostClean($Blocks) {
    $dirty = @(Get-PostLines $Blocks | Where-Object { $_ -match '`|#\d|\b[\w-]+\.(py|md|ya?ml|json|txt|ps1|sh|bat|zip|enc)\b' })
    Test-That 'tekst posta bez kodu, nazw plików i numerów issues' ($dirty.Count -eq 0)
    foreach ($line in $dirty) { Write-Host "        $line" }
}

# Skąd pobrać: Docker Hub (sklep Tunnelboxa) i strona projektu z paczką; na końcu zdanie o Fortinecie, raz,
# i podziękowanie
function Test-Download($Blocks) {
    $get = @($Blocks | Where-Object { (Get-BlockText $_) -eq 'Get Tunnelbox:' })
    Test-That 'Get Tunnelbox pogrubione' ($get.Count -eq 1 -and $get[0].type -eq 'paragraph' -and $get[0].paragraph.rich_text[0].annotations.bold)
    $hub = @($Blocks | Where-Object { (Get-BlockText $_) -like 'The image on Docker Hub:*' })
    Test-That 'Docker Hub: odnośnik' ($hub.Count -eq 1 -and (@(Get-LinkUrl $hub[0]) -join ' ') -eq $dockerHubUrl -and (Get-BlockText $hub[0]) -eq 'The image on Docker Hub: hub.docker.com/r/programistticsolutions/tunnelbox')
    $package = @($Blocks | Where-Object { (Get-BlockText $_) -like 'The package for Windows*' })
    Test-That 'paczka: odnośnik do strony projektu' ($package.Count -eq 1 -and (@(Get-LinkUrl $package[0]) -join ' ') -eq $pageUrl -and (Get-BlockText $package[0]) -eq 'The package for Windows, macOS and Linux, with the install steps: mysttic.github.io/Mysttic/tunnelbox/')
    $lines = @(Get-PostLines $Blocks)
    $fortinet = @($lines | Where-Object { $_ -like '*not affiliated with or endorsed by Fortinet*' })
    Test-That 'zdanie o Fortinecie raz, przed podziękowaniem' ($fortinet.Count -eq 1 -and $lines.Count -ge 2 -and $lines[$lines.Count - 2] -eq $disclaimer -and $lines[$lines.Count - 1] -eq 'Thank you for supporting my work!')
}

$probe = New-Object System.Net.Sockets.TcpListener([System.Net.IPAddress]::Loopback, 0)
$probe.Start()
$port = $probe.LocalEndpoint.Port
$probe.Stop()
$listener = New-Object System.Net.HttpListener
$listener.Prefixes.Add("http://localhost:$port/")
$listener.Start()
$server = [powershell]::Create()
[void]$server.AddScript($serve).AddArgument($listener).AddArgument($state)
$handle = $server.BeginInvoke()
$api = "http://localhost:$port/v1"

try {
    $release300 = New-Release 'wydanie-3.0.0' '3.0.0'
    $link300 = 'https://github.com/Mysttic/tunnelbox/releases/tag/v3.0.0'
    $title300 = 'heading_3: Tunnelbox 3.0.0: FortiVPN 2 is now Tunnelbox'

    $before = $failures.Count
    $run = Invoke-PostBmc '3.0.0, podgląd z kalendarzem' @('-Version', '3.0.0', '-DryRun', '-ReleaseJson', $release300)
    Test-That 'bez ostrzeżenia' ($run.Output -notmatch '::warning::')
    Test-That 'dwa zapytania do bazy, bez zapisu' ($run.Requests.Count -eq 2 -and $run.Pages.Count -eq 0)
    Test-That 'Termin 3 dni po najpóźniejszym poście (2026-12-06)' ($run.Output -match 'Termin:\s+2026-12-09')
    Test-That 'nagłówek Notion-Version 2026-03-11' (@($run.Requests | Where-Object { $_.NotionVersion -ne '2026-03-11' }).Count -eq 0)
    Test-That 'token w nagłówku Authorization' (@($run.Requests | Where-Object { $_.Authorization -ne "Bearer $token" }).Count -eq 0)
    Test-That 'zapytania do tej bazy' (@($run.Requests | Where-Object { $_.Path -ne "/v1/data_sources/$dataSource/query" }).Count -eq 0)
    if ($run.Requests.Count -eq 2) {
        $query = $run.Requests[0].Body | ConvertFrom-Json
        Test-That 'duplikat: Typ Post BMC' ($query.filter.and[0].property -eq 'Typ' -and $query.filter.and[0].select.equals -eq 'Post BMC')
        Test-That 'duplikat: ten sam Link albo tytuł' ($query.filter.and[1].or[0].url.equals -eq $link300 -and $query.filter.and[1].or[1].title.equals -eq 'Post BMC: Tunnelbox 3.0.0')
        $query = $run.Requests[1].Body | ConvertFrom-Json
        Test-That 'ostatni Termin: Typ Post BMC, sortowanie malejąco' ($query.filter.and[0].select.equals -eq 'Post BMC' -and $query.sorts[0].property -eq 'Termin' -and $query.sorts[0].direction -eq 'descending')
    }
    Test-That 'podsumowanie: tytuł i opis wpisu' ($run.Summary.Contains('Post BMC: Tunnelbox 3.0.0') -and $run.Summary.Contains('Rodzaj: Major. Widoczność: Public. Kategoria: Tunnelbox.'))
    Test-That 'podsumowanie: tytuł posta' ($run.Summary.Contains('### Tunnelbox 3.0.0: FortiVPN 2 is now Tunnelbox'))
    Test-That 'podsumowanie: Docker Hub' ($run.Summary.Contains('- The image on Docker Hub: hub.docker.com/r/programistticsolutions/tunnelbox'))
    Test-Run $run $before

    $before = $failures.Count
    $run = Invoke-PostBmc '3.0.0, zapis' @('-Version', '3.0.0', '-ReleaseJson', $release300)
    Test-That 'bez ostrzeżenia' ($run.Output -notmatch '::warning::')
    Test-That 'jeden zapis wpisu po dwóch zapytaniach' ($run.Requests.Count -eq 3 -and $run.Pages.Count -eq 1)
    Test-That 'log z adresem wpisu' ($run.Output.Contains('https://www.notion.so/atrapa-wpisu'))
    $page = Get-WrittenPage $run
    if ($page) {
        Test-That 'rodzic: data source z sekretu' ($page.parent.type -eq 'data_source_id' -and $page.parent.data_source_id -eq $dataSource)
        Test-That 'Zadanie' ($page.properties.Zadanie.title[0].text.content -eq 'Post BMC: Tunnelbox 3.0.0')
        Test-That 'Typ' ($page.properties.Typ.select.name -eq 'Post BMC')
        Test-That 'Status' ($page.properties.Status.status.name -eq 'Planowany')
        Test-That 'Termin' ($page.properties.Termin.date.start -eq '2026-12-09')
        Test-That 'Link' ($page.properties.Link.url -eq $link300)
        Test-That 'Description' ($page.properties.Description.rich_text[0].text.content -eq 'Rodzaj: Major. Widoczność: Public. Kategoria: Tunnelbox.')
        $blocks = @($page.children)
        $text = Get-PageText $blocks
        Test-That 'ramka z instrukcją publikacji' ($blocks[0].type -eq 'callout' -and (Get-BlockText $blocks[0]) -eq 'Instrukcja publikacji (nie kopiować)')
        $notes = Get-Notes $blocks
        Test-That 'instrukcja: widoczność, kategoria, zdjęcie, zasady tekstu' ($notes -contains 'Widoczność: Public (wersja Major).' -and $notes -contains 'Kategoria: Tunnelbox.' -and @($notes -like 'Zdjęcie:*').Count -eq 1 -and @($notes -like 'Tekst:*Fortinecie*').Count -eq 1)
        Test-That 'instrukcja: nic pominiętego' ($notes.Count -eq 4)
        Test-That 'nagłówek treści do skopiowania' ($text -contains 'heading_2: Treść do skopiowania')
        $at = [array]::IndexOf($text, $title300)
        Test-That 'tytuł z pierwszego wpisu, bez akapitu wstępu' ($at -ge 0 -and $text[$at + 1] -eq 'paragraph: What changed:')
        $changes = @(Get-Changes $text)
        $expected = 'FortiVPN 2 is now Tunnelbox', 'A new update channel', 'Ready-made images in a registry', 'Dependabot', "FortiVPN 2's downloads"
        Test-That 'What changed: 22 pogrubione początki wpisów' ($changes.Count -eq 22 -and @($expected | Where-Object { $changes -notcontains "bulleted_list_item: $_" }).Count -eq 0)
        Test-Download $blocks
        Test-PostClean $blocks
        $toggle = $blocks[$blocks.Count - 1]
        $full = Get-PageText (Get-Children $toggle)
        $code = @(Get-Children $toggle | ForEach-Object { $_.($_.type).rich_text } | Where-Object { $_.PSObject.Properties['annotations'] -and $_.annotations.PSObject.Properties['code'] -and $_.text.content -eq 'ghcr.io/mysttic/tunnelbox' })
        Test-That 'zwinięty pełny changelog: 26 bloków bez zmian, `kod` jako kod' ((Get-BlockText $toggle) -eq 'Pełny changelog' -and $full.Count -eq 26 -and $full -contains 'heading_3: Security' -and $code.Count -eq 1)
    }
    Test-That 'podsumowanie z adresem wpisu' ($run.Summary.Contains('https://www.notion.so/atrapa-wpisu'))
    Test-Run $run $before

    $before = $failures.Count
    $state.Existing = '[' + (New-PageJson 'https://www.notion.so/istniejacy-wpis' '2026-12-09') + ']'
    $run = Invoke-PostBmc 'drugi bieg dla tej samej wersji' @('-Version', '3.0.0', '-ReleaseJson', $release300)
    $state.Existing = '[]'
    Test-That 'tylko szukanie duplikatu, bez zapisu' ($run.Requests.Count -eq 1 -and $run.Pages.Count -eq 0)
    Test-That 'log i podsumowanie wskazują istniejący wpis' ($run.Output.Contains('https://www.notion.so/istniejacy-wpis') -and $run.Summary.Contains('już jest w kalendarzu'))
    Test-That 'bez ostrzeżenia' ($run.Output -notmatch '::warning::')
    Test-Run $run $before

    $before = $failures.Count
    $run = Invoke-PostBmc 'wydanie wstępne' @('-Version', '3.0.0', '-ReleaseJson', (New-Release 'wydanie-wstepne' '3.0.0' -Prerelease $true))
    Test-That 'bez zapytań do Notion' ($run.Requests.Count -eq 0)
    Test-That 'podsumowanie: wydanie wstępne' ($run.Summary.Contains('Wydanie v3.0.0 jest wstępne'))
    Test-Run $run $before

    $before = $failures.Count
    $run = Invoke-PostBmc 'szkic wydania' @('-Version', '3.0.0', '-ReleaseJson', (New-Release 'wydanie-szkic' '3.0.0' -Draft $true))
    Test-That 'bez zapytań do Notion' ($run.Requests.Count -eq 0)
    Test-That 'podsumowanie: szkic' ($run.Summary.Contains('Wydanie v3.0.0 jest szkicem'))
    Test-Run $run $before

    $before = $failures.Count
    $run = Invoke-PostBmc 'błąd serwera Notion' @('-Version', '3.0.0', '-ReleaseJson', $release300) 'blad'
    Test-That 'ostrzeżenie Actions z HTTP 500' ($run.Output -match '::warning::Szkic posta BMC o wersji 3\.0\.0 nie powsta.*Notion, .*HTTP 500')
    Test-That 'zdanie w podsumowaniu' ($run.Summary.Contains('nie powstał') -and $run.Summary.Contains('internal_server_error'))
    Test-That 'identyfikator bazy z komunikatu Notion zamaskowany' ($run.Output.Contains('Atrapa: baza *** nie odpowiada'))
    Test-That 'bez zapisu' ($run.Pages.Count -eq 0)
    Test-Run $run $before

    $before = $failures.Count
    $run = Invoke-PostBmc 'limit zapytań Notion' @('-Version', '3.0.0', '-ReleaseJson', $release300) 'limit'
    Test-That 'ponowienie po HTTP 429 i zapis' ($run.Requests.Count -eq 4 -and $run.Pages.Count -eq 1 -and $run.Output.Contains('HTTP 429'))
    Test-That 'bez ostrzeżenia' ($run.Output -notmatch '::warning::')
    Test-Run $run $before

    $before = $failures.Count
    $run = Invoke-PostBmc 'zapis bez sekretów' @('-Version', '3.0.0', '-ReleaseJson', $release300) 'ok' $false
    Test-That 'ostrzeżenie o sekretach' ($run.Output -match '::warning::.*NOTION_TOKEN')
    Test-That 'bez zapytań do Notion' ($run.Requests.Count -eq 0)
    Test-Run $run $before

    $before = $failures.Count
    $run = Invoke-PostBmc 'podgląd bez sekretów' @('-Version', '3.0.0', '-DryRun', '-ReleaseJson', $release300) 'ok' $false
    Test-That 'Termin jutro, bez kalendarza' ($run.Output -match 'Termin:\s+2026-11-27')
    Test-That 'bez zapytań i bez ostrzeżenia' ($run.Requests.Count -eq 0 -and $run.Output -notmatch '::warning::')
    Test-Run $run $before

    $before = $failures.Count
    $state.Calendar = '[' + (New-PageJson 'https://www.notion.so/stary' '2026-11-20') + ']'
    $run = Invoke-PostBmc 'kalendarz bez bliskich postów' @('-Version', '3.0.0', '-DryRun', '-ReleaseJson', $release300)
    Test-That 'Termin jutro' ($run.Output -match 'Termin:\s+2026-11-27')
    Test-Run $run $before

    $before = $failures.Count
    $state.Calendar = '[' + ((New-PageJson 'https://www.notion.so/a' '2026-12-06'), (New-PageJson 'https://www.notion.so/zakres' '2026-12-01' '2026-12-08') -join ',') + ']'
    $run = Invoke-PostBmc 'Termin z zakresem dni' @('-Version', '3.0.0', '-DryRun', '-ReleaseJson', $release300)
    $state.Calendar = $calendar
    Test-That 'Termin 3 dni po końcu zakresu (2026-12-08)' ($run.Output -match 'Termin:\s+2026-12-11')
    Test-Run $run $before

    $changelog = Join-Path $work 'CHANGELOG.md'
    Write-Utf8 $changelog ((
            '# Changelog', '', '## [3.1.0] - 2026-12-10', '',
            "Updates now come straight from the project's own releases (issue #20). Panels of 3.0.0",
            'still look in the old place. The panel reads `app/updates.py` now.',
            "Settings live in vault.enc as before. $disclaimer", '',
            '### Changed',
            "- **Updates come from the project's own releases** (issue #20). The panel asks GitHub.",
            '- **The [project page](https://mysttic.github.io/Mysttic/tunnelbox/) links to',
            '  Docker Hub** (issues #21 and #22).', '',
            '## [3.0.1] - 2026-12-01', '',
            '### Fixed',
            '- **A tunnel that drops reconnects on its own** (issue #30). It waited for a click.',
            '- A gateway with a long realm name connects (#31). The name was cut.',
            '- **`TUNNELBOX_DATA` with spaces works** (issue #32).',
            '- **Release notes in PR #33 read better**.', '',
            '[3.1.0]: https://github.com/Mysttic/tunnelbox/compare/v3.0.1...v3.1.0',
            '[3.0.1]: https://github.com/Mysttic/tunnelbox/compare/v3.0.0...v3.0.1') -join "`n")

    $before = $failures.Count
    $run = Invoke-PostBmc 'próbna 3.1.0: wstęp z kodem, nazwą pliku i zdaniem o Fortinecie' @('-Version', '3.1.0', '-ReleaseJson', (New-Release 'wydanie-3.1.0' '3.1.0'), '-Changelog', $changelog)
    $page = Get-WrittenPage $run
    if ($page) {
        $blocks = @($page.children)
        $text = Get-PageText $blocks
        $notes = Get-Notes $blocks
        Test-That 'Description: Minor' ($page.properties.Description.rich_text[0].text.content -eq 'Rodzaj: Minor. Widoczność: Release Supporter i All Updates Supporter. Kategoria: Tunnelbox.')
        Test-That 'instrukcja: Members only, dwa poziomy' ($notes -contains 'Widoczność: Members only, poziomy Release Supporter i All Updates Supporter (wersja Minor).')
        Test-That 'tytuł posta bez issue' ($text -contains "heading_3: Tunnelbox 3.1.0: Updates now come straight from the project's own releases")
        Test-That 'akapit wstępu bez issue, kodu, nazwy pliku i bez powtórzonego zdania o Fortinecie' ($text -contains "paragraph: Updates now come straight from the project's own releases. Panels of 3.0.0 still look in the old place.")
        $changes = @(Get-Changes $text)
        Test-That 'What changed: odnośnik jako sam tekst' ($changes.Count -eq 2 -and $changes -contains "bulleted_list_item: Updates come from the project's own releases" -and $changes -contains 'bulleted_list_item: The project page links to Docker Hub')
        Test-That 'instrukcja: zdanie z kodem i zdanie z nazwą pliku' ($notes -contains 'kod: The panel reads app/updates.py now.' -and $notes -contains 'nazwa pliku: Settings live in vault.enc as before.')
        Test-Download $blocks
        Test-PostClean $blocks
    }
    Test-Run $run $before

    $before = $failures.Count
    $run = Invoke-PostBmc 'próbna 3.0.1: bez wstępu, ostatnia część' @('-Version', '3.0.1', '-ReleaseJson', (New-Release 'wydanie-3.0.1' '3.0.1'), '-Changelog', $changelog)
    $page = Get-WrittenPage $run
    if ($page) {
        $blocks = @($page.children)
        $text = Get-PageText $blocks
        $notes = Get-Notes $blocks
        Test-That 'Description: Patch' ($page.properties.Description.rich_text[0].text.content -eq 'Rodzaj: Patch. Widoczność: All Updates Supporter. Kategoria: Tunnelbox.')
        Test-That 'instrukcja: Members only, poziom All Updates Supporter' ($notes -contains 'Widoczność: Members only, poziom All Updates Supporter (wersja Patch).')
        $at = [array]::IndexOf($text, 'heading_3: Tunnelbox 3.0.1: A tunnel that drops reconnects on its own')
        Test-That 'tytuł z pierwszego wpisu, bez akapitu wstępu' ($at -ge 0 -and $text[$at + 1] -eq 'paragraph: What changed:')
        $changes = @(Get-Changes $text)
        Test-That 'What changed: pogrubiony początek i pierwsze zdanie wpisu bez pogrubienia' ($changes.Count -eq 2 -and $changes -contains 'bulleted_list_item: A tunnel that drops reconnects on its own' -and $changes -contains 'bulleted_list_item: A gateway with a long realm name connects')
        Test-That 'instrukcja: zmienna i numer PR' ($notes -contains 'kod: TUNNELBOX_DATA with spaces works' -and $notes -contains 'numer issue: Release notes in PR #33 read better')
        $full = Get-PageText (Get-Children $blocks[-1])
        Test-That 'pełny changelog bez odnośników z dołu pliku' ($full.Count -eq 5 -and @($full -like '*compare/v3.0*').Count -eq 0)
        Test-Download $blocks
        Test-PostClean $blocks
    }
    Test-Run $run $before

    $before = $failures.Count
    $run = Invoke-PostBmc 'wersja bez części w CHANGELOG.md' @('-Version', '9.9.9', '-ReleaseJson', (New-Release 'wydanie-9.9.9' '9.9.9'))
    Test-That 'ostrzeżenie o braku części' ($run.Output -match '::warning::.*## \[9\.9\.9\]')
    Test-That 'bez zapytań do Notion' ($run.Requests.Count -eq 0)
    Test-Run $run $before

    $before = $failures.Count
    $run = Invoke-PostBmc 'zły numer wersji' @('-Version', '3.0', '-ReleaseJson', $release300)
    Test-That 'ostrzeżenie o postaci X.Y.Z' ($run.Output -match '::warning::.*X\.Y\.Z')
    Test-Run $run $before
}
finally {
    $listener.Stop()
    $listener.Close()
    try { [void]$server.EndInvoke($handle) } catch { }
    $server.Dispose()
    foreach ($name in $savedEnvironment.Keys) { [Environment]::SetEnvironmentVariable($name, $savedEnvironment[$name]) }
    Remove-Item -LiteralPath $work -Recurse -Force
}

if ($failures.Count) {
    Write-Host "Nie przeszło: $($failures.Count) ($($failures -join '; '))."
    exit 1
}
Write-Host 'Wszystkie sprawdzenia przeszły.'
exit 0
