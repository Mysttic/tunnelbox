<#
.SYNOPSIS
    Szkic posta Buy Me a Coffee o wydaniu Tunnelboxa jako wpis w kalendarzu Notion „🎸 Zadania” (issue #16).

.DESCRIPTION
    Buy Me a Coffee nie ma API do postów, więc post publikuje autor, przenosząc tekst z wpisu w kalendarzu. Skrypt
    bierze wydanie vX.Y.Z z GitHuba i część CHANGELOG.md tej wersji, a w bazie Notion tworzy jeden wpis z Typem
    „Post BMC”: tytuł „Post BMC: Tunnelbox X.Y.Z”, Status „Planowany”, Termin według reguły odstępu, Link do
    wydania i opis z rodzajem wersji, widocznością w BMC i kategorią. W treści wpisu jest instrukcja publikacji, tekst
    posta do skopiowania i zwinięty pełny changelog wersji. Wzór: post-bmc.ps1 z Chatt (a ten z MystticRock).

    CHANGELOG.md jest cały po angielsku, więc tekst posta powstaje wprost z części wersji: tytuł „Tunnelbox X.Y.Z: ”
    z początkiem pierwszego zdania wstępu do dwukropka, akapit wstępu (tekst przed pierwszym nagłówkiem), „What
    changed” z pogrubionych początków wpisów, skąd pobrać Tunnelboxa (Docker Hub, czyli jego sklep, i strona
    projektu z paczką), zdanie o niezależności od Fortinetu i podziękowanie. Nawiasy z numerami issues znikają.
    Zdanie albo początek wpisu z kodem, nazwą pliku albo numerem issue nie trafia do posta (zasady treści z #16):
    instrukcja publikacji wymienia je do przeredagowania. Gdy pierwsze zdanie wstępu odpada albo wstępu nie ma,
    tytuł bierze pierwszy początek wpisu, który został.

    Termin to najwcześniej jutro (dzień w Polsce) i co najmniej 3 dni po najpóźniejszym Terminie wpisów „Post BMC”
    wszystkich projektów. Wpis „Post BMC” z tym samym Link albo tytułem znaczy, że wersja ma już wpis: drugi bieg
    niczego nie dodaje. Wydania wstępne i szkice nie dostają wpisu. Błąd (Notion, GitHub, brak sekretu) nie kończy
    skryptu porażką, bo wydanie już stoi: skrypt wypisuje ostrzeżenie Actions i zdanie w podsumowaniu joba.

    Sekrety przychodzą w zmiennych NOTION_TOKEN i NOTION_CALENDAR_DATA_SOURCE_ID i nie trafiają do logu.

.EXAMPLE
    ./.github/scripts/post-bmc.ps1 -Version 1.0.1 -DryRun
#>
[CmdletBinding()]
param(
    # Numer wersji X.Y.Z; wydanie vX.Y.Z jest już na GitHubie
    [Parameter(Mandatory)]
    [string]$Version,

    # Tylko podgląd: wypisuje wpis i Termin bez zapisu (z sekretami pyta Notion o duplikat i ostatni Termin)
    [switch]$DryRun,

    # Dane wydania z pliku JSON (pola url, isDraft i isPrerelease jak z gh release view --json); bez niego z GitHuba
    [string]$ReleaseJson,

    # Historia zmian, domyślnie CHANGELOG.md w katalogu repozytorium
    [string]$Changelog,

    # Repozytorium wydania dla gh, domyślnie to, w którym biegnie workflow
    [string]$Repository,

    # Adres API Notion; test podstawia atrapę na localhost
    [string]$ApiBase = 'https://api.notion.com/v1',

    # Dzisiejsza data RRRR-MM-DD do reguły Terminu, domyślnie dziś w Polsce
    [string]$Today
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

# Wersja API ta sama co w MystticRock i Chatt (sprawdzona w dokumentacji Notion 25.11.2026)
$NotionVersion = '2026-03-11'
$PostType = 'Post BMC'
$Project = 'Tunnelbox'
$Category = 'Tunnelbox'
# Skąd pobrać Tunnelboxa: Docker Hub jest jego sklepem, a strona projektu daje paczkę ZIP i opis instalacji
$DockerHubUrl = 'https://hub.docker.com/r/mysttic/tunnelbox'
$PageUrl = 'https://mysttic.github.io/Mysttic/tunnelbox/'
# Zdanie, które stoi w każdym poście o Tunnelboxie (#16); w akapicie wstępu nie powtarza się
$Disclaimer = 'Tunnelbox is an independent project, not affiliated with or endorsed by Fortinet.'
$GapDays = 3
# Notion przyjmuje do 2000 znaków w jednym kawałku tekstu i do 100 elementów w jednej tablicy
$MaxText = 2000
$MaxItems = 100
$MaxChanges = 50
$MaxOmitted = 40
# Kropka po skrócie nie kończy zdania
$Abbreviations = 'e.g', 'i.e', 'etc', 'vs', 'cf', 'approx'

function Write-Summary([string[]]$Lines) {
    if (-not $env:GITHUB_STEP_SUMMARY) { return }
    $text = ($Lines -join "`n") + "`n"
    [System.IO.File]::AppendAllText($env:GITHUB_STEP_SUMMARY, $text, [System.Text.UTF8Encoding]::new($false))
}

function Write-Note([string]$Text) {
    Write-Host $Text
    Write-Summary $Text
}

# Polecenie przepływu pracy w jednej linii: %, CR i LF trzeba zakodować
function ConvertTo-CommandData([string]$Text) {
    $Text.Replace('%', '%25').Replace("`r", '%0D').Replace("`n", '%0A')
}

# Identyfikator bazy w każdej postaci (z kreskami i bez), bo Notion pisze go w błędach po swojemu
function Get-SecretForm {
    $id = ("$env:NOTION_CALENDAR_DATA_SOURCE_ID" -replace '^collection://', '').Trim()
    $plain = $id -replace '-', ''
    $forms = @($env:NOTION_TOKEN, $id, $plain)
    if ($plain -match '^[0-9a-fA-F]{32}$') { $forms += $plain -replace '^(.{8})(.{4})(.{4})(.{4})(.{12})$', '$1-$2-$3-$4-$5' }
    $forms | Where-Object { $_ } | Select-Object -Unique
}

function Hide-Secret([string]$Text) {
    foreach ($form in @(Get-SecretForm)) {
        $Text = [regex]::Replace($Text, [regex]::Escape($form), '***', 'IgnoreCase')
    }
    $Text
}

function Get-Release {
    if ($ReleaseJson) { return (Get-Content -LiteralPath $ReleaseJson -Raw -Encoding UTF8 | ConvertFrom-Json) }
    $repo = if ($Repository) { $Repository } elseif ($env:GITHUB_REPOSITORY) { $env:GITHUB_REPOSITORY } else { 'Mysttic/tunnelbox' }
    $json = gh release view "v$Version" --repo $repo --json 'url,isDraft,isPrerelease'
    if ($LASTEXITCODE -ne 0) { throw "gh release view v$($Version): kod wyjścia $LASTEXITCODE (czy wydanie v$Version istnieje?)" }
    ($json -join "`n") | ConvertFrom-Json
}

# Część CHANGELOG.md spod nagłówka „## [X.Y.Z]” (dawne części mają numer bez nawiasów) do następnego nagłówka
# drugiego stopnia, bez definicji odnośników z dołu pliku („[1.0.0]: https://…”), które dostałaby ostatnia część
function Get-ChangelogSection([string]$Path) {
    $lines = @(Get-Content -LiteralPath $Path -Encoding UTF8)
    $heading = "^## \[?$([regex]::Escape($Version))\]?(\s|$)"
    $start = -1
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match $heading) { $start = $i; break }
    }
    if ($start -lt 0) { throw "CHANGELOG.md nie ma części ## [$Version]" }
    $end = $lines.Count
    for ($i = $start + 1; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match '^## ') { $end = $i; break }
    }
    $body = ''
    if ($end -gt $start + 1) {
        $body = (@($lines[($start + 1)..($end - 1)] | Where-Object { $_ -notmatch '^\[[^\]]+\]:\s*\S' }) -join "`n").Trim()
    }
    if (-not $body) { throw "część ## [$Version] w CHANGELOG.md jest pusta" }
    $body
}

# Bloki Markdown: nagłówki, punkty z wierszami ciągu dalszego i akapity
function Split-Markdown([string]$Text) {
    $blocks = New-Object System.Collections.Generic.List[object]
    $current = $null
    foreach ($raw in ($Text -split '\r?\n')) {
        $line = $raw.Trim()
        if (-not $line) { $current = $null; continue }
        if ($line -match '^#{1,6}\s+(.*)$') {
            $current = $null
            $blocks.Add([pscustomobject]@{ Kind = 'Heading'; Text = $Matches[1].Trim() })
            continue
        }
        if ($line -match '^[-*] ') {
            $current = [pscustomobject]@{ Kind = 'Item'; Text = $line.Substring(2).Trim() }
            $blocks.Add($current)
            continue
        }
        if ($current) { $current.Text += ' ' + $line }
        else {
            $current = [pscustomobject]@{ Kind = 'Text'; Text = $line }
            $blocks.Add($current)
        }
    }
    $blocks.ToArray()
}

# Bez numerów issues i PR-ów (zasady treści z #16: czytelnik posta nie szuka ich w repozytorium): nawias z numerem,
# np. „(issue #91)”, „(#80)” albo „(Windows only, issue #94)”, znika w całości
function Remove-IssueReference([string]$Text) {
    ($Text -replace '\s*\([^()]*#\d+[^()]*\)', '').Trim()
}

function Remove-Markdown([string]$Text) {
    $Text = ($Text -replace '\[([^\]]+)\]\([^)]*\)', '$1').Replace('`', '').Replace('**', '')
    $Text -replace '(?<![\w*])\*([^*\s][^*]*)\*(?![\w*])', '$1'
}

# Zdania tekstu: koniec to kropka, wykrzyknik albo pytajnik (z cudzysłowem albo nawiasem za nim) przed odstępem
# i początkiem następnego zdania; kropka po skrócie zdania nie kończy. Typograficzne cudzysłowy są we wzorcu kodami
# “, ”, „, ‘ i ’, bo PowerShell bierze dwa ostatnie za koniec napisu w apostrofach
function Split-Sentence([string]$Text) {
    $sentences = New-Object System.Collections.Generic.List[string]
    $at = 0
    foreach ($match in [regex]::Matches($Text, '[.!?]["\u201D\u2019)]*(?=\s+["\u201C\u201E\u2018(\[*`\p{Lu}\p{N}])')) {
        if ($match.Value.StartsWith('.')) {
            $word = [regex]::Match($Text.Substring(0, $match.Index), '[\p{L}.]+$').Value.ToLowerInvariant()
            if ($Abbreviations -contains $word) { continue }
        }
        $end = $match.Index + $match.Length
        $sentence = $Text.Substring($at, $end - $at).Trim()
        if ($sentence) { $sentences.Add($sentence) }
        $at = $end
    }
    $rest = $Text.Substring($at).Trim()
    if ($rest) { $sentences.Add($rest) }
    $sentences.ToArray()
}

# Początek zdania do pierwszego dwukropka, bez kropki na końcu: krótki tytuł posta
function Get-Lead([string]$Sentence) {
    $colon = [regex]::Match($Sentence, ':(?=\s|$)')
    $text = if ($colon.Success) { $Sentence.Substring(0, $colon.Index) } else { $Sentence }
    $text.Trim().TrimEnd('.', ',', ';').Trim()
}

# Pogrubiony początek wpisu, a bez pogrubienia jego pierwsze zdanie; bez nawiasów z numerami issues
function Get-EntryTitle([string]$Text) {
    $bold = [regex]::Match($Text, '^\*\*(.+?)\*\*')
    $title = if ($bold.Success) { $bold.Groups[1].Value } else { @(Split-Sentence $Text) | Select-Object -First 1 }
    (Remove-IssueReference "$title").TrimEnd('.', ':', ',', ';').Trim()
}

# Czego tekst posta nie może mieć (zasady treści z #16): kodu, poleceń, zmiennych, nazw plików i numerów issues lub
# PR-ów. Ścieżki i polecenia CHANGELOG.md pisze w `kodzie`, więc łapie je pierwszy warunek. Zwraca powód do instrukcji
# publikacji albo pusty tekst
function Get-OmitReason([string]$Text) {
    if ($Text.Contains('`') -or $Text -match '(?<![\w-])--\w' -or $Text -cmatch '\b[A-Z][A-Z0-9]*_[A-Z0-9_]*[A-Z0-9]\b') { return 'kod' }
    if ($Text -match '\b[\w.-]+\.(py|md|ya?ml|ps1|json|txt|sh|bat|exe|zip|gz|tar|enc|js|html|css|toml|conf|ini|log)\b') { return 'nazwa pliku' }
    if ($Text -match '#\d') { return 'numer issue' }
    ''
}

# Tekst posta: akapity wstępu sprzed pierwszego nagłówka (po zdaniu) i pogrubione początki wszystkich wpisów; to, co
# odpada według Get-OmitReason, idzie do listy pominiętych z powodem
function Get-PostText($Blocks) {
    $omitted = New-Object System.Collections.Generic.List[object]
    $paragraphs = New-Object System.Collections.Generic.List[string]
    $lead = ''
    $first = $true
    foreach ($block in $Blocks) {
        if ($block.Kind -eq 'Heading') { break }
        if ($block.Kind -ne 'Text') { continue }
        $kept = New-Object System.Collections.Generic.List[string]
        foreach ($sentence in @(Split-Sentence (Remove-IssueReference $block.Text))) {
            # zdanie o Fortinecie post ma na końcu, więc we wstępie byłoby drugi raz
            if ((Remove-Markdown $sentence).Trim() -eq $Disclaimer) { continue }
            $reason = Get-OmitReason $sentence
            if ($reason) { $omitted.Add([pscustomobject]@{ Reason = $reason; Text = $sentence }) }
            else {
                $plain = Remove-Markdown $sentence
                $kept.Add($plain)
                if ($first) { $lead = Get-Lead $plain }
            }
            $first = $false
        }
        if ($kept.Count) { $paragraphs.Add($kept -join ' ') }
    }
    $items = New-Object System.Collections.Generic.List[string]
    foreach ($block in @($Blocks | Where-Object { $_.Kind -eq 'Item' })) {
        $title = Get-EntryTitle $block.Text
        if (-not $title) { continue }
        $reason = Get-OmitReason $title
        if ($reason) { $omitted.Add([pscustomobject]@{ Reason = $reason; Text = $title }) }
        else { $items.Add((Remove-Markdown $title)) }
    }
    if (-not $lead -and $items.Count) { $lead = $items[0] }
    [pscustomobject]@{ Lead = $lead; Paragraphs = $paragraphs.ToArray(); Items = $items.ToArray(); Omitted = $omitted.ToArray() }
}

# Rodzaj wersji i widoczność posta w BMC: X.0.0 dla wszystkich, X.Y.0 dla dwóch poziomów wsparcia, X.Y.Z (Z > 0)
# tylko dla All Updates Supporter. Dla wersji 0.x reguła nie jest ustalona (Tunnelbox ich nie ma; gałąź zostaje jak
# we wzorze z Chatt, żeby poprawki przenosiły się między projektami bez zmian)
function Get-VersionKind {
    $numbers = @($Version.Split('.') | ForEach-Object { [int]$_ })
    $name = if ($numbers[2] -gt 0) { 'Patch' } elseif ($numbers[1] -gt 0) { 'Minor' } else { 'Major' }
    if ($numbers[0] -eq 0) {
        return [pscustomobject]@{ Name = $name; Visibility = 'Do decyzji'; Hint = 'do decyzji, reguła dla wersji 0.x nie jest ustalona' }
    }
    switch ($name) {
        'Patch' { [pscustomobject]@{ Name = $name; Visibility = 'All Updates Supporter'; Hint = 'Members only, poziom All Updates Supporter' } }
        'Minor' { [pscustomobject]@{ Name = $name; Visibility = 'Release Supporter i All Updates Supporter'; Hint = 'Members only, poziomy Release Supporter i All Updates Supporter' } }
        default { [pscustomobject]@{ Name = $name; Visibility = 'Public'; Hint = 'Public' } }
    }
}

function Add-TextPart($Parts, [string]$Content, [bool]$Bold, [bool]$Code, [string]$Link) {
    for ($i = 0; $i -lt $Content.Length; $i += $MaxText) {
        $text = [ordered]@{ content = $Content.Substring($i, [Math]::Min($MaxText, $Content.Length - $i)) }
        if ($Link) { $text.link = [ordered]@{ url = $Link } }
        $part = [ordered]@{ type = 'text'; text = $text }
        if ($Bold -or $Code) {
            $annotations = [ordered]@{}
            if ($Bold) { $annotations.bold = $true }
            if ($Code) { $annotations.code = $true }
            $part.annotations = $annotations
        }
        $Parts.Add($part)
    }
}

# Tekst Notion z Markdown w jednej linii: `kod`, **pogrubienie** i odnośniki http(s) (inne odnośniki zostają samym
# tekstem), w kawałkach do 2000 znaków
function ConvertTo-RichText([string]$Text, [switch]$Bold) {
    $parts = New-Object System.Collections.Generic.List[object]
    $at = 0
    foreach ($match in [regex]::Matches($Text, '`([^`]+)`|\*\*([^*]+)\*\*|\[([^\]]+)\]\(([^)\s]+)\)')) {
        if ($match.Index -gt $at) { Add-TextPart $parts $Text.Substring($at, $match.Index - $at) $Bold.IsPresent $false '' }
        if ($match.Groups[1].Success) { Add-TextPart $parts $match.Groups[1].Value $Bold.IsPresent $true '' }
        elseif ($match.Groups[2].Success) { Add-TextPart $parts $match.Groups[2].Value $true $false '' }
        else {
            $url = $match.Groups[4].Value
            if ($url -notmatch '^https?://') { $url = '' }
            Add-TextPart $parts $match.Groups[3].Value $Bold.IsPresent $false $url
        }
        $at = $match.Index + $match.Length
    }
    if ($at -lt $Text.Length) { Add-TextPart $parts $Text.Substring($at) $Bold.IsPresent $false '' }
    if ($parts.Count -gt $MaxItems) {
        $parts.Clear()
        Add-TextPart $parts (Remove-Markdown $Text) $Bold.IsPresent $false ''
    }
    $parts.ToArray()
}

# Blok Notion; dzieci jako tablica, bo @() na List[object] rzuca w Windows PowerShell 5.1 „Argument types do not match”
function New-Block([string]$Type, $RichText, [object[]]$Children) {
    $content = [ordered]@{ rich_text = @($RichText | Where-Object { $null -ne $_ }) }
    if ($null -ne $Children -and $Children.Count -gt 0) { $content.children = $Children }
    [ordered]@{ object = 'block'; type = $Type; $Type = $content }
}

function ConvertTo-NotionBlock($Block) {
    $type = switch ($Block.Kind) { 'Heading' { 'heading_3' } 'Item' { 'bulleted_list_item' } default { 'paragraph' } }
    New-Block $type (ConvertTo-RichText $Block.Text)
}

# Odnośnik Markdown z adresem bez https:// jako tekstem, jak w README.md: adres widać też po wklejeniu samego tekstu
function Format-Link([string]$Url) { '[{0}]({1})' -f ($Url -replace '^https://', ''), $Url }

# Skąd pobrać Tunnelboxa: obraz na Docker Hub (jego sklep) i strona projektu z paczką ZIP i opisem instalacji
function New-DownloadBlock {
    New-Block 'bulleted_list_item' (ConvertTo-RichText "The image on Docker Hub: $(Format-Link $DockerHubUrl)")
    New-Block 'bulleted_list_item' (ConvertTo-RichText "The package for Windows, macOS and Linux, with the install steps: $(Format-Link $PageUrl)")
}

# Treść wpisu: instrukcja publikacji, tekst posta do skopiowania i zwinięty pełny changelog wersji (bez zmian)
function New-PageContent($Post, $Kind, $Blocks) {
    $notes = New-Object System.Collections.Generic.List[object]
    $notes.Add((New-Block 'bulleted_list_item' (ConvertTo-RichText "Widoczność: $($Kind.Hint) (wersja $($Kind.Name)).")))
    $notes.Add((New-Block 'bulleted_list_item' (ConvertTo-RichText "Kategoria: $Category.")))
    $notes.Add((New-Block 'bulleted_list_item' (ConvertTo-RichText 'Zdjęcie: poziomy zrzut angielskiego panelu z nowością tej wersji; gotowe zrzuty są w docs/img/en.')))
    $notes.Add((New-Block 'bulleted_list_item' (ConvertTo-RichText 'Tekst: prosty angielski, bez kodu, poleceń, ścieżek, nazw plików, zmiennych i numerów issue; zdanie o Fortinecie zostaje. Gdy BMC odrzuci zapis („Something went wrong”), przeredaguj zdanie, które go blokuje.')))
    $omitted = @($Post.Omitted)
    if ($omitted.Count) {
        $notes.Add((New-Block 'bulleted_list_item' (ConvertTo-RichText 'Pominięte w tekście posta (przeredaguj, jeśli mają w nim być):')))
        foreach ($part in @($omitted | Select-Object -First $MaxOmitted)) {
            $notes.Add((New-Block 'bulleted_list_item' (@(ConvertTo-RichText "$($part.Reason): ") + @(ConvertTo-RichText $part.Text))))
        }
        if ($omitted.Count -gt $MaxOmitted) {
            $notes.Add((New-Block 'bulleted_list_item' (ConvertTo-RichText "I jeszcze $($omitted.Count - $MaxOmitted), wszystkie są w zwiniętym changelogu.")))
        }
    }
    $callout = New-Block 'callout' (ConvertTo-RichText 'Instrukcja publikacji (nie kopiować)' -Bold) $notes.ToArray()
    $callout.callout.icon = [ordered]@{ type = 'emoji'; emoji = [char]::ConvertFromUtf32(0x1F4CC) }
    $callout.callout.color = 'gray_background'
    $callout

    New-Block 'heading_2' (ConvertTo-RichText 'Treść do skopiowania')
    $title = if ($Post.Lead) { "$Project $($Version): $($Post.Lead)" } else { "$Project $Version" }
    New-Block 'heading_3' (ConvertTo-RichText $title)
    foreach ($paragraph in @($Post.Paragraphs)) { New-Block 'paragraph' (ConvertTo-RichText $paragraph) }
    if (@($Post.Items).Count) {
        New-Block 'paragraph' (ConvertTo-RichText 'What changed:' -Bold)
        foreach ($item in @($Post.Items | Select-Object -First $MaxChanges)) { New-Block 'bulleted_list_item' (ConvertTo-RichText $item) }
    }
    New-Block 'paragraph' (ConvertTo-RichText "Get $($Project):" -Bold)
    New-DownloadBlock
    New-Block 'paragraph' (ConvertTo-RichText $Disclaimer)
    New-Block 'paragraph' (ConvertTo-RichText 'Thank you for supporting my work!')

    $full = @($Blocks | ForEach-Object { ConvertTo-NotionBlock $_ })
    if ($full.Count -gt $MaxItems) {
        $full = @($full[0..($MaxItems - 2)]) + @(New-Block 'paragraph' (ConvertTo-RichText 'Reszta części wersji jest w CHANGELOG.md.'))
    }
    New-Block 'toggle' (ConvertTo-RichText 'Pełny changelog') $full
}

# Podgląd treści w logu: tekst bloków z wcięciem dla bloków zagnieżdżonych
function Format-Block($Blocks, [string]$Indent) {
    $number = 0
    foreach ($block in @($Blocks)) {
        $content = $block[$block.type]
        $text = (@($content.rich_text) | ForEach-Object { $_.text.content }) -join ''
        if ($block.type -eq 'numbered_list_item') { $number++ } else { $number = 0 }
        $prefix = switch ($block.type) {
            'heading_2' { '## ' }
            'heading_3' { '### ' }
            'bulleted_list_item' { '- ' }
            'numbered_list_item' { "$number. " }
            'callout' { '[ramka] ' }
            'toggle' { '[zwinięte] ' }
            default { '' }
        }
        "$Indent$prefix$text"
        if ($content.Contains('children')) { Format-Block $content.children ($Indent + '    ') }
    }
}

function Get-HttpStatus($ErrorRecord) {
    $exception = $ErrorRecord.Exception
    if ($exception.PSObject.Properties['Response'] -and $exception.Response) { return [int]$exception.Response.StatusCode }
    0
}

function Get-RetryAfter($ErrorRecord) {
    $seconds = 2
    try {
        $headers = $ErrorRecord.Exception.Response.Headers
        $value = if ($headers -is [System.Net.WebHeaderCollection]) { $headers['Retry-After'] } else { $headers.RetryAfter.Delta.TotalSeconds }
        if ($value) { $seconds = [int][Math]::Ceiling([double]$value) }
    }
    catch { }
    [Math]::Max(1, [Math]::Min($seconds, 30))
}

# Treść odpowiedzi z błędem: pwsh daje ją w ErrorDetails, Windows PowerShell 5.1 tylko w strumieniu odpowiedzi
function Get-ErrorBody($ErrorRecord) {
    if ($ErrorRecord.ErrorDetails -and $ErrorRecord.ErrorDetails.Message) { return $ErrorRecord.ErrorDetails.Message }
    $exception = $ErrorRecord.Exception
    if ($exception.PSObject.Properties['Response'] -and $exception.Response -and $exception.Response.PSObject.Methods['GetResponseStream']) {
        try { return (New-Object System.IO.StreamReader($exception.Response.GetResponseStream(), [System.Text.Encoding]::UTF8)).ReadToEnd() }
        catch { }
    }
    ''
}

function Get-NotionError($ErrorRecord, [int]$Status, [string]$What) {
    $detail = $ErrorRecord.Exception.Message
    $body = Get-ErrorBody $ErrorRecord
    if ($body) {
        $detail = $body
        try {
            $json = $body | ConvertFrom-Json
            $detail = "$($json.code): $($json.message)"
        }
        catch { }
    }
    $answer = if ($Status) { "HTTP $Status" } else { 'bez odpowiedzi' }
    "Notion, $What ($answer): $detail"
}

# Zapytanie POST do API Notion; limit zapytań (HTTP 429) czeka i ponawia, inne błędy idą wyżej z opisem bez adresu
function Invoke-Notion([string]$Path, $Body, [string]$What) {
    $headers = @{ Authorization = "Bearer $env:NOTION_TOKEN"; 'Notion-Version' = $NotionVersion }
    $bytes = [System.Text.Encoding]::UTF8.GetBytes((ConvertTo-Json -InputObject $Body -Depth 32 -Compress))
    for ($attempt = 1; ; $attempt++) {
        try {
            return Invoke-RestMethod -Method Post -Uri "$ApiBase/$Path" -Headers $headers -ContentType 'application/json; charset=utf-8' -Body $bytes -TimeoutSec 60
        }
        catch {
            $status = Get-HttpStatus $_
            if ($status -eq 429 -and $attempt -lt 3) {
                $wait = Get-RetryAfter $_
                Write-Host "Notion ogranicza liczbę zapytań (HTTP 429), ponowienie za $wait s."
                Start-Sleep -Seconds $wait
                continue
            }
            throw (Get-NotionError $_ $status $What)
        }
    }
}

# Wpis tej wersji: Typ „Post BMC” i ten sam Link (adres wydania) albo ten sam tytuł, gdyby Link zmienił się na
# adres posta w BMC
function Find-Existing([string]$DataSource, [string]$Link, [string]$Title) {
    $body = [ordered]@{
        filter = [ordered]@{
            and = @(
                [ordered]@{ property = 'Typ'; select = [ordered]@{ equals = $PostType } },
                [ordered]@{
                    or = @(
                        [ordered]@{ property = 'Link'; url = [ordered]@{ equals = $Link } },
                        [ordered]@{ property = 'Zadanie'; title = [ordered]@{ equals = $Title } }
                    )
                }
            )
        }
        page_size = 1
    }
    $response = Invoke-Notion "data_sources/$DataSource/query" $body 'sprawdzenie, czy wpis już jest'
    @($response.results) | Select-Object -First 1
}

function ConvertTo-Day($Value) {
    if ($Value -is [datetime]) { return $Value.Date }
    [datetime]::ParseExact(([string]$Value).Substring(0, 10), 'yyyy-MM-dd', [System.Globalization.CultureInfo]::InvariantCulture)
}

# Najpóźniejszy dzień wśród Terminów wpisów „Post BMC” wszystkich projektów (koniec zakresu, gdy Termin ma zakres)
function Get-LatestTermin([string]$DataSource) {
    $body = [ordered]@{
        filter = [ordered]@{
            and = @(
                [ordered]@{ property = 'Typ'; select = [ordered]@{ equals = $PostType } },
                [ordered]@{ property = 'Termin'; date = [ordered]@{ is_not_empty = $true } }
            )
        }
        sorts = @([ordered]@{ property = 'Termin'; direction = 'descending' })
        page_size = 10
    }
    $response = Invoke-Notion "data_sources/$DataSource/query" $body 'ostatni Termin postów'
    $latest = $null
    foreach ($page in @($response.results)) {
        $date = $page.properties.Termin.date
        if (-not $date) { continue }
        foreach ($value in @($date.start, $date.end)) {
            if (-not $value) { continue }
            $day = ConvertTo-Day $value
            if ($null -eq $latest -or $day -gt $latest) { $latest = $day }
        }
    }
    $latest
}

function Get-Today {
    if ($Today) { return [datetime]::ParseExact($Today, 'yyyy-MM-dd', [System.Globalization.CultureInfo]::InvariantCulture) }
    foreach ($zone in 'Europe/Warsaw', 'Central European Standard Time') {
        try { return [TimeZoneInfo]::ConvertTimeBySystemTimeZoneId([datetime]::UtcNow, $zone).Date } catch { }
    }
    [datetime]::UtcNow.Date
}

function Format-Day([datetime]$Day) { $Day.ToString('yyyy-MM-dd', [System.Globalization.CultureInfo]::InvariantCulture) }

function Invoke-Main {
    if ($Version -notmatch '^\d+\.\d+\.\d+$') { throw "numer wersji ma postać X.Y.Z, np. 1.0.1 (podano '$Version')" }

    $release = Get-Release
    if ($release.isDraft) { Write-Note "Wydanie v$Version jest szkicem, więc nie dostaje posta BMC."; return }
    if ($release.isPrerelease) { Write-Note "Wydanie v$Version jest wstępne, więc nie dostaje posta BMC."; return }
    $link = [string]$release.url
    if ($link -notmatch '^https://') { throw "wydanie v$Version nie ma adresu (url: '$link')" }

    $path = if ($Changelog) { $Changelog } else { Join-Path $PSScriptRoot '../../CHANGELOG.md' }
    $blocks = @(Split-Markdown (Get-ChangelogSection $path))
    $post = Get-PostText $blocks
    $kind = Get-VersionKind
    $title = "Post BMC: $Project $Version"
    $description = "Rodzaj: $($kind.Name). Widoczność: $($kind.Visibility). Kategoria: $Category."

    $dataSource = ("$env:NOTION_CALENDAR_DATA_SOURCE_ID" -replace '^collection://', '').Trim()
    $notion = [bool]$env:NOTION_TOKEN -and [bool]$dataSource
    if (-not $notion -and -not $DryRun) { throw 'brak sekretu NOTION_TOKEN albo NOTION_CALENDAR_DATA_SOURCE_ID' }
    if ($notion -and $env:GITHUB_ACTIONS -eq 'true') {
        foreach ($form in @(Get-SecretForm)) { if ($form -ne $env:NOTION_TOKEN) { Write-Host "::add-mask::$form" } }
    }

    $latest = $null
    if ($notion) {
        $existing = Find-Existing $dataSource $link $title
        if ($existing) { Write-Note ('Wpis „{0}” już jest w kalendarzu ({1}), drugiego nie dodaję.' -f $title, $existing.url); return }
        $latest = Get-LatestTermin $dataSource
    }
    else { Write-Host 'Bez sekretów Notion: podgląd bez sprawdzenia duplikatu i ostatniego Terminu.' }

    $tomorrow = (Get-Today).AddDays(1)
    $termin = $tomorrow
    if ($null -ne $latest -and $latest.AddDays($GapDays) -gt $termin) { $termin = $latest.AddDays($GapDays) }
    $day = Format-Day $termin
    $why = if (-not $notion) { 'jutro, bez sprawdzenia kalendarza' }
    elseif ($null -eq $latest) { 'jutro, w kalendarzu nie ma innych postów BMC' }
    elseif ($termin -eq $tomorrow) { "jutro, ostatni post BMC ma Termin $(Format-Day $latest)" }
    else { "$GapDays dni po ostatnim poście BMC z $(Format-Day $latest)" }

    $children = @(New-PageContent $post $kind $blocks)
    $preview = @(
        "Zadanie:     $title"
        "Typ:         $PostType"
        'Status:      Planowany'
        "Termin:      $day ($why)"
        "Link:        $link"
        "Description: $description"
        'Treść:'
    ) + @(Format-Block $children '    ')

    if ($DryRun) {
        Write-Host 'Podgląd wpisu w kalendarzu Notion (bez zapisu):'
        $preview | ForEach-Object { Write-Host $_ }
        $heading = 'Podgląd wpisu „{0}” w kalendarzu Notion (bez zapisu), Termin {1} ({2}):' -f $title, $day, $why
        Write-Summary (@($heading, '', '```text') + $preview + '```')
        return
    }

    $body = [ordered]@{
        parent = [ordered]@{ type = 'data_source_id'; data_source_id = $dataSource }
        properties = [ordered]@{
            Zadanie = [ordered]@{ title = @(ConvertTo-RichText $title) }
            Typ = [ordered]@{ select = [ordered]@{ name = $PostType } }
            Status = [ordered]@{ status = [ordered]@{ name = 'Planowany' } }
            Termin = [ordered]@{ date = [ordered]@{ start = $day } }
            Link = [ordered]@{ url = $link }
            Description = [ordered]@{ rich_text = @(ConvertTo-RichText $description) }
        }
        children = $children
    }
    $page = Invoke-Notion 'pages' $body 'nowy wpis'
    $preview | ForEach-Object { Write-Host $_ }
    Write-Note ('Szkic posta BMC w kalendarzu Notion: „{0}”, Termin {1} ({2}): {3}' -f $title, $day, $why, $page.url)
}

# Windows PowerShell 5.1 bez tego może próbować starszego TLS, którego Notion nie przyjmuje
[Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
try {
    Invoke-Main
}
catch {
    $message = Hide-Secret "Szkic posta BMC o wersji $Version nie powstał: $($_.Exception.Message)"
    Write-Host (Hide-Secret "$($_.ScriptStackTrace)")
    Write-Host "::warning::$(ConvertTo-CommandData $message)"
    Write-Summary $message
}
exit 0
