"use strict";

// Teksty panelu po angielsku (domyślnie) i po polsku.
//
// Wybór języka zapada w Ustawieniach i jedzie do sejfu razem z resztą ustawień —
// dzięki temu wędruje z eksportem konfiguracji i wraca po przeniesieniu na inny
// komputer. Kopię trzymamy dodatkowo w localStorage, bo ekran hasła głównego rysuje
// się, zanim panel zdąży cokolwiek odczytać z sejfu (a sejf bywa zablokowany).
//
// W znacznikach: data-i18n (tekst), data-i18n-html (tekst ze znacznikami),
// data-i18n-ph (placeholder), data-i18n-title, data-i18n-aria. Wartości w HTML są
// po angielsku, więc nawet gdyby ten plik się nie wczytał, panel zostaje czytelny.

const LANGS = { en: "English", pl: "Polski" };
const DEFAULT_LANG = "en";
const LANG_KEY = "vpn_lang";

const STRINGS = {
  en: {
    "header.settings": "⚙ Settings",
    "header.changePass": "Change master password",
    "header.lock": "Lock panel",

    "auth.createTitle": "Welcome! Set a master password",
    "auth.createIntro":
      "This password encrypts every VPN profile you save. Remember it — it cannot be recovered.",
    "auth.createPass": "Master password (min. 4 characters)",
    "auth.repeatPass": "Repeat password",
    "auth.createBtn": "Create vault",
    "auth.unlockTitle": "Unlock the panel",
    "auth.unlockIntro": "Enter your master password to reach your VPN profiles.",
    "auth.unlockPass": "Master password",
    "auth.unlockBtn": "Unlock",
    "auth.configFile": "Configuration file",
    "auth.export": "⬇️ Export",
    "auth.import": "⬆️ Import",
    "auth.showPass": "Show password",
    "auth.hidePass": "Hide password",
    "auth.showKey": "Show key",
    "auth.passTooShort": "The password needs at least 4 characters.",
    "auth.passMismatch": "The passwords are not identical.",

    "main.connections": "VPN connections",
    "main.add": "＋ Add connection",
    "main.empty":
      "No connections yet. Click “Add connection”, fill in the form and you are done.",

    "update.install": "⬆️ Update",
    "update.download": "⬇️ Download package",
    "update.whatsNew": "What's new",
    "update.later": "Later",
    "update.registryHint": "Installed from the registry — in the folder with docker-compose.yml run:",
    "update.available": "Version {version} is available",
    "update.haveVersion": "you have {version}",
    "update.released": "released {date}",
    "update.startedTitle": "Starting the installer",
    "update.startedText":
      "A separate window shows the progress. The panel disappears for a moment — " +
      "after the update it opens again, with the same connections.",
    "update.failedTitle": "The installer did not open",
    "update.failedText":
      "One-click updates need the panel to be started through start.bat. You can " +
      "download the package and unpack it yourself — saved connections move across " +
      "just the same.",
    "update.checking": "Checking…",
    "update.checkFailed": "Could not check — try again.",
    "update.disabled": "Update checks are turned off.",
    "update.offline": "No connection to the releases page — try again later.",
    "update.foundNewer":
      "Version {version} is available. The update bar is waiting above your connections.",
    "update.upToDate": "You have the latest version ({version}).",

    "editor.titleNew": "New connection",
    "editor.titleEdit": "Edit connection",
    "editor.titleView": "Connection settings",
    "editor.readonly":
      "🔒 This connection is active — read-only preview. Disconnect it first to change anything.",
    "editor.intro":
      "Enter the credentials for the client's VPN (you get them from the client or their " +
      "administrator), then list the machines you need to reach. The panel handles the rest.",
    "editor.name": "Connection name",
    "editor.nameHint": "anything you like, so you recognise it in the list",
    "editor.namePh": "e.g. Client X",
    "editor.vpnType": "Connection type",
    "editor.vpnTypeHint":
      "pick what the client's administrator told you. SSL-VPN is the ordinary Forti tunnel " +
      "over port 443; you can spot IPsec by the <strong>pre-shared key (PSK)</strong> you were given",
    "editor.typeSsl": "SSL-VPN (Forti) — default",
    "editor.typeIpsec": "IPsec",
    "editor.host": "VPN server address",
    "editor.hostHint":
      "you can paste the whole address from Forti (e.g. https://vpn.client.com:443/myrealm) — we will split it up",
    "editor.hostPh": "e.g. vpn.client.com or 10.10.10.10",
    "editor.port": "Port",
    "editor.portHint": "usually 443",
    "editor.realm": "Realm / path (optional)",
    "editor.realmHint":
      "the part of the Forti address after the slash, e.g. <code>myrealm</code> — leave empty if there is none",
    "editor.realmPh": "e.g. myrealm",
    "editor.ipsecAuth": "How the gateway authenticates you",
    "editor.ipsecAuthHint":
      "if you are not sure, leave the first option — that is how most FortiGate dial-ups work",
    "editor.authXauth": "IKEv1: PSK + username and password (XAuth)",
    "editor.authIkev1": "IKEv1: PSK only",
    "editor.authIkev2": "IKEv2: PSK only",
    "editor.psk": "Pre-shared key (PSK)",
    "editor.pskHint":
      "the same string on both ends of the tunnel — you get it from the client's administrator",
    "editor.localId": "Local identifier (optional)",
    "editor.localIdHint": "group name / “peer ID”, if the client gave you one",
    "editor.localIdPh": "e.g. vpn-group",
    "editor.remoteId": "Gateway identifier (optional)",
    "editor.remoteIdHint": "leave empty if you do not have one",
    "editor.remoteIdPh": "e.g. vpn.client.com",
    "editor.remoteTs": "Networks behind the VPN (optional)",
    "editor.remoteTsHint":
      "the client's networks, comma separated, e.g. <code>10.10.0.0/16, 192.168.5.0/24</code> " +
      "— empty means “everything through the tunnel”",
    "editor.remoteTsPh": "e.g. 10.10.0.0/16",
    "editor.aggressive": "Aggressive mode",
    "editor.aggressiveHint":
      "Tick this only when the client's administrator says so — it is sometimes required when " +
      "the gateway recognises you by the local identifier. IKEv1 only.",
    "editor.username": "Username",
    "editor.password": "Password",
    "editor.token": "This connection needs a token (two-factor authentication)",
    "editor.tokenCode": "I type a one-time code (from SMS or an app)",
    "editor.tokenPush": "I approve the sign-in in a phone app (push)",
    "editor.machines": "Machines in the client's network",
    "editor.machinesIntro":
      "List the computers or servers you need to reach once connected. For each one give its " +
      "IP address in the client's network and the service port (e.g. 3389 for remote desktop). " +
      "After connecting, the panel shows a local shortcut such as <code>127.0.0.2:13391</code> " +
      "— you type that in your RDP/SSH client instead of the real address. Nothing else to set up.",
    "editor.addMachine": "＋ Add machine",
    "editor.cancel": "Cancel",
    "editor.close": "Close",
    "editor.save": "Save",
    "editor.machineName": "Machine name (optional)",
    "editor.machineNameHint": "type RDP, SSH, VNC or https — the port fills itself in",
    "editor.machineNamePh": "e.g. RDP server",
    "editor.machineIp": "IP address in the client's network",
    "editor.machineIpPh": "e.g. 10.10.10.11",
    "editor.machinePort": "Service port",
    "editor.machinePortPh": "e.g. 3389",
    "editor.remove": "Remove",
    "editor.needPsk": "IPsec needs a pre-shared key (PSK) — ask the client's administrator for it.",
    "editor.needIpPort": "Fill in the IP address and service port for machine no. {row}.",
    "editor.badRowPort": "Invalid service port for machine no. {row} (1–65535).",
    "editor.portsHint":
      "Common ports: 3389 = RDP, 22 = SSH, 5900 = VNC, 443 = web. The local address " +
      "(e.g. 127.0.0.2:13391) is assigned by the panel once you connect.",

    "otp.title": "Enter your token",
    "otp.hint": "“{name}” needs a one-time code (token).",
    "otp.ph": "One-time code",
    "otp.connect": "Connect",
    "otp.missing": "Enter the token to connect.",

    "settings.title": "Settings",
    "settings.language": "Language",
    "settings.languageHint": "Applies to the whole panel, including messages from connections.",
    "settings.fastRdp": "Fast RDP connect",
    "settings.fastRdpHint":
      "On: <strong>“Connect over RDP”</strong> opens remote desktop straight away — no file " +
      "saved and no Windows warning on every connection.<br>" +
      "Off: you get <strong>“Download .rdp file”</strong> instead — the file lands in Downloads " +
      "and you open it with a double click.",
    "settings.checkUpdates": "Check for updates",
    "settings.checkUpdatesHint":
      "On: once a day the panel asks the releases page whether a newer version exists and shows " +
      "a bar above your connections. It sends none of your data.<br>" +
      "Off: the panel connects to nothing except your own VPN tunnels.",
    "settings.checkNow": "🔄 Check now",
    "settings.configFile": "Configuration file",
    "settings.configHint":
      "Export writes every connection into one encrypted file (still protected by your master " +
      "password) — good for a backup or for moving to another computer. Import replaces the " +
      "current configuration; the previous one stays beside it as a <code>.bak</code> copy, and " +
      "active connections are disconnected.",
    "settings.export": "⬇️ Export configuration",
    "settings.import": "⬆️ Import configuration",
    "settings.cancel": "Cancel",
    "settings.save": "Save",

    "addFwd.title": "Add machine",
    "addFwd.hint":
      "The machine will be added to “{name}” and made available right away — without dropping the VPN.",
    "addFwd.needIpPort": "Enter the IP address and the service port.",
    "addFwd.badPort": "Invalid service port (1–65535).",
    "addFwd.cancel": "Cancel",
    "addFwd.save": "Add",

    "changePass.title": "Change master password",
    "changePass.intro":
      "Enter your current password and the new one. Every saved connection is re-encrypted with the new password.",
    "changePass.current": "Current master password",
    "changePass.new": "New password (min. 4 characters)",
    "changePass.repeat": "Repeat the new password",
    "changePass.cancel": "Cancel",
    "changePass.save": "Change password",
    "changePass.needCurrent": "Enter your current password.",
    "changePass.done": "The master password has been changed.",

    "import.title": "Import configuration",
    "import.intro":
      "Pick the <code>.enc</code> file saved earlier by the export and give the master password that protects it.",
    "import.warning":
      "⚠️ The current configuration will be replaced and active connections dropped. " +
      "The previous version is saved beside it as a <code>.bak</code> copy.",
    "import.file": "Configuration file",
    "import.pass": "Master password for that file",
    "import.cancel": "Cancel",
    "import.save": "Import",
    "import.needFile": "Pick the configuration file.",
    "import.needPass": "Enter the master password for that file.",
    "import.readFailed": "Could not read the file.",

    "status.disconnected": "Disconnected",
    "status.connecting": "Connecting…",
    "status.connected": "Connected",
    "status.disconnecting": "Disconnecting…",
    "status.need_trust": "Unknown certificate",
    "status.error": "Error",

    "card.connect": "Connect",
    "card.disconnect": "Disconnect",
    "card.trust": "Trust the certificate and connect",
    "card.retry": "Connect again",
    "card.addMachine": "＋ Add machine",
    "card.addMachineHint": "Add a machine without disconnecting",
    "card.edit": "Edit",
    "card.editHint": "Edit this connection",
    "card.preview": "Preview",
    "card.previewHint": "Look at the settings (without disconnecting)",
    "card.delete": "Delete",
    "card.confirmDelete": "Delete the connection “{name}”?",
    "card.afterConnect": "available once connected",
    "card.dead": "not working — check the IP and port",
    "card.showLog": "Show connection log",
    "card.menuHint": "Actions for this address",

    "menu.rdpConnect": "🖥️ Connect over RDP",
    "menu.rdpDownload": "⬇️ Download .rdp file",
    "menu.ssh": "🔌 Connect over SSH",
    "menu.vnc": "🖥️ Connect over VNC",
    "menu.browser": "🌐 Open in browser",
    "menu.copyAddr": "📋 Copy address",
    "menu.copyCmd": "📋 Copy command",
    "menu.sshUser": "user",

    "rdp.failedTitle": "Remote desktop did not open",
    "rdp.failedText":
      "Fast RDP connect is not set up on this computer. Run start.bat again, or download the connection file.",
    "rdp.failedTextRegistry":
      "Fast RDP connect is not set up on this computer — the docker compose install does not register it. " +
      "Download the connection file, or turn off ⚙ Settings → Fast RDP connect.",
    "rdp.download": "⬇️ Download .rdp file",
    "rdp.settings": "⚙ Settings",
    "toast.close": "Close",

    "err.generic": "Something went wrong — try again.",
    "err.field": "Check the field: {field} ({message}).",
    "err.invalidValue": "invalid value",
    "err.locked": "The vault is locked",

    "field.name": "name",
    "field.host": "server address",
    "field.username": "username",
    "field.password": "password",
    "field.port": "port",
    "field.ip": "remote IP",
    "field.remote_port": "remote port",
    "field.local_port": "local port",
    "field.otp": "token",
    "field.trusted_certs": "certificate",
    "field.ipsec_psk": "pre-shared key (PSK)",
    "field.ipsec_remote_ts": "networks behind the VPN",
    "field.data": "data",
  },

  pl: {
    "header.settings": "⚙ Ustawienia",
    "header.changePass": "Zmień hasło główne",
    "header.lock": "Zablokuj panel",

    "auth.createTitle": "Witaj! Ustaw hasło główne",
    "auth.createIntro":
      "Tym hasłem będą zaszyfrowane wszystkie Twoje profile VPN. Zapamiętaj je — nie da się go odzyskać.",
    "auth.createPass": "Hasło główne (min. 4 znaki)",
    "auth.repeatPass": "Powtórz hasło",
    "auth.createBtn": "Utwórz sejf",
    "auth.unlockTitle": "Odblokuj panel",
    "auth.unlockIntro": "Podaj hasło główne, aby uzyskać dostęp do profili VPN.",
    "auth.unlockPass": "Hasło główne",
    "auth.unlockBtn": "Odblokuj",
    "auth.configFile": "Plik konfiguracji",
    "auth.export": "⬇️ Eksportuj",
    "auth.import": "⬆️ Importuj",
    "auth.showPass": "Pokaż hasło",
    "auth.hidePass": "Ukryj hasło",
    "auth.showKey": "Pokaż klucz",
    "auth.passTooShort": "Hasło musi mieć co najmniej 4 znaki.",
    "auth.passMismatch": "Hasła nie są identyczne.",

    "main.connections": "Połączenia VPN",
    "main.add": "＋ Dodaj połączenie",
    "main.empty":
      "Nie masz jeszcze żadnych połączeń. Kliknij „Dodaj połączenie”, wypełnij formularz i gotowe.",

    "update.install": "⬆️ Zaktualizuj",
    "update.download": "⬇️ Pobierz paczkę",
    "update.whatsNew": "Co nowego",
    "update.later": "Później",
    "update.registryHint": "Zainstalowano z rejestru — w folderze z docker-compose.yml uruchom:",
    "update.available": "Dostępna nowa wersja {version}",
    "update.haveVersion": "masz {version}",
    "update.released": "wydana {date}",
    "update.startedTitle": "Uruchamiam instalator",
    "update.startedText":
      "W osobnym oknie zobaczysz postęp. Panel na chwilę zniknie — po aktualizacji " +
      "otworzy się sam, z tymi samymi połączeniami.",
    "update.failedTitle": "Instalator się nie otworzył",
    "update.failedText":
      "Aktualizacja jednym kliknięciem wymaga uruchomienia panelu przez start.bat. " +
      "Możesz pobrać paczkę i rozpakować ją samodzielnie — zapisane połączenia " +
      "zostaną przeniesione tak samo.",
    "update.checking": "Sprawdzam…",
    "update.checkFailed": "Nie udało się sprawdzić — spróbuj ponownie.",
    "update.disabled": "Sprawdzanie aktualizacji jest wyłączone.",
    "update.offline": "Brak połączenia ze stroną wydań — spróbuj później.",
    "update.foundNewer":
      "Jest nowsza wersja: {version}. Pasek z aktualizacją czeka nad listą połączeń.",
    "update.upToDate": "Masz najnowszą wersję ({version}).",

    "editor.titleNew": "Nowe połączenie",
    "editor.titleEdit": "Edytuj połączenie",
    "editor.titleView": "Ustawienia połączenia",
    "editor.readonly":
      "🔒 Połączenie jest aktywne — podgląd tylko do odczytu. Aby zmienić ustawienia, najpierw je rozłącz.",
    "editor.intro":
      "Wpisz dane dostępowe do VPN klienta (dostajesz je od klienta lub administratora), " +
      "a niżej wskaż maszyny, do których chcesz się dostać. Resztą zajmie się panel.",
    "editor.name": "Nazwa połączenia",
    "editor.nameHint": "dowolna, żebyś rozpoznał to połączenie na liście",
    "editor.namePh": "np. Klient X",
    "editor.vpnType": "Typ połączenia",
    "editor.vpnTypeHint":
      "wybierz to, co podał administrator klienta. SSL-VPN to zwykły tunel Forti przez " +
      "przeglądarkowy port 443; IPsec rozpoznasz po tym, że dostałeś " +
      "<strong>klucz współdzielony (PSK)</strong>",
    "editor.typeSsl": "SSL-VPN (Forti) — domyślny",
    "editor.typeIpsec": "IPsec",
    "editor.host": "Adres serwera VPN",
    "editor.hostHint":
      "możesz wkleić cały adres z Forti (np. https://vpn.klient.pl:443/myrealm) — rozłożymy go na pola",
    "editor.hostPh": "np. vpn.klient.pl lub 10.10.10.10",
    "editor.port": "Port",
    "editor.portHint": "zwykle 443",
    "editor.realm": "Realm / ścieżka (opcjonalnie)",
    "editor.realmHint":
      "część adresu z Forti po ukośniku, np. <code>myrealm</code> — zostaw puste, jeśli jej nie ma",
    "editor.realmPh": "np. myrealm",
    "editor.ipsecAuth": "Sposób logowania do bramy",
    "editor.ipsecAuthHint":
      "jeśli nie wiesz, zostaw pierwszą pozycję — tak działa większość dial-upów FortiGate",
    "editor.authXauth": "IKEv1: klucz PSK + login i hasło (XAuth)",
    "editor.authIkev1": "IKEv1: sam klucz PSK",
    "editor.authIkev2": "IKEv2: sam klucz PSK",
    "editor.psk": "Klucz współdzielony (PSK)",
    "editor.pskHint":
      "ten sam ciąg znaków po obu stronach tunelu — dostajesz go od administratora klienta",
    "editor.localId": "Identyfikator lokalny (opcjonalnie)",
    "editor.localIdHint": "nazwa grupy / „peer ID”, jeśli klient ją podał",
    "editor.localIdPh": "np. grupa-vpn",
    "editor.remoteId": "Identyfikator bramy (opcjonalnie)",
    "editor.remoteIdHint": "zostaw puste, jeśli nie masz",
    "editor.remoteIdPh": "np. vpn.klient.pl",
    "editor.remoteTs": "Sieci za VPN-em (opcjonalnie)",
    "editor.remoteTsHint":
      "adresy sieci klienta po przecinku, np. <code>10.10.0.0/16, 192.168.5.0/24</code> " +
      "— puste oznacza „wszystko przez tunel”",
    "editor.remoteTsPh": "np. 10.10.0.0/16",
    "editor.aggressive": "Tryb agresywny (aggressive mode)",
    "editor.aggressiveHint":
      "Zaznacz tylko wtedy, gdy administrator klienta tak powiedział — bywa wymagany, " +
      "gdy brama rozpoznaje klienta po identyfikatorze lokalnym. Dotyczy wyłącznie IKEv1.",
    "editor.username": "Login",
    "editor.password": "Hasło",
    "editor.token": "Połączenie wymaga tokena (uwierzytelnianie dwuskładnikowe)",
    "editor.tokenCode": "Wpisuję kod jednorazowy (z SMS-a lub aplikacji)",
    "editor.tokenPush": "Zatwierdzam logowanie w aplikacji na telefonie (push)",
    "editor.machines": "Maszyny w sieci klienta",
    "editor.machinesIntro":
      "Wskaż komputery/serwery, do których chcesz się dostać po połączeniu. Dla każdego " +
      "podaj jego adres IP w sieci klienta i port usługi (np. 3389 dla pulpitu zdalnego). " +
      "Po połączeniu panel pokaże dla każdej maszyny lokalny skrót typu " +
      "<code>127.0.0.2:13391</code> — ten adres wpiszesz w kliencie RDP/SSH zamiast " +
      "prawdziwego. Nie musisz nic więcej ustawiać.",
    "editor.addMachine": "＋ Dodaj maszynę",
    "editor.cancel": "Anuluj",
    "editor.close": "Zamknij",
    "editor.save": "Zapisz",
    "editor.machineName": "Nazwa maszyny (opcjonalnie)",
    "editor.machineNameHint": "wpisz np. RDP, SSH, VNC lub https — port uzupełni się sam",
    "editor.machineNamePh": "np. Serwer RDP",
    "editor.machineIp": "Adres IP w sieci klienta",
    "editor.machineIpPh": "np. 10.10.10.11",
    "editor.machinePort": "Port usługi",
    "editor.machinePortPh": "np. 3389",
    "editor.remove": "Usuń",
    "editor.needPsk": "IPsec wymaga klucza współdzielonego (PSK) — poproś o niego administratora klienta.",
    "editor.needIpPort": "Uzupełnij adres IP i port usługi w maszynie nr {row}.",
    "editor.badRowPort": "Nieprawidłowy port usługi w maszynie nr {row} (1–65535).",
    "editor.portsHint":
      "Częste porty: 3389 = RDP, 22 = SSH, 5900 = VNC, 443 = WWW. " +
      "Adres lokalny (np. 127.0.0.2:13391) panel nada automatycznie po połączeniu.",

    "otp.title": "Podaj token",
    "otp.hint": "Połączenie „{name}” wymaga kodu jednorazowego (tokena).",
    "otp.ph": "Kod jednorazowy",
    "otp.connect": "Połącz",
    "otp.missing": "Podaj token, żeby się połączyć.",

    "settings.title": "Ustawienia",
    "settings.language": "Język",
    "settings.languageHint": "Dotyczy całego panelu, łącznie z komunikatami połączeń.",
    "settings.fastRdp": "Szybkie łączenie RDP",
    "settings.fastRdpHint":
      "Włączone: przycisk <strong>„Połącz przez RDP”</strong> od razu otwiera pulpit " +
      "zdalny — bez zapisywania pliku i bez ostrzeżenia Windows przy każdym połączeniu.<br>" +
      "Wyłączone: zamiast tego pokaże się <strong>„Pobierz plik .rdp”</strong> — " +
      "plik trafi do „Pobranych” i otworzysz go dwuklikiem.",
    "settings.checkUpdates": "Sprawdzaj aktualizacje",
    "settings.checkUpdatesHint":
      "Włączone: raz na dobę panel pyta stronę z wydaniami, czy jest nowsza wersja, " +
      "i pokazuje pasek nad listą połączeń. Nie wysyła przy tym żadnych Twoich danych.<br>" +
      "Wyłączone: panel nie łączy się z niczym poza Twoimi tunelami VPN.",
    "settings.checkNow": "🔄 Sprawdź teraz",
    "settings.configFile": "Plik konfiguracji",
    "settings.configHint":
      "Eksport zapisuje wszystkie połączenia do jednego zaszyfrowanego pliku (nadal " +
      "chronionego hasłem głównym) — dobre na kopię zapasową albo przeniesienie na " +
      "inny komputer. Import zastępuje obecną konfigurację; poprzednia zostaje obok " +
      "jako kopia <code>.bak</code>, a aktywne połączenia są rozłączane.",
    "settings.export": "⬇️ Eksportuj konfigurację",
    "settings.import": "⬆️ Importuj konfigurację",
    "settings.cancel": "Anuluj",
    "settings.save": "Zapisz",

    "addFwd.title": "Dodaj maszynę",
    "addFwd.hint":
      "Maszyna zostanie dodana do „{name}” i od razu udostępniona — bez rozłączania VPN.",
    "addFwd.needIpPort": "Podaj adres IP i port usługi.",
    "addFwd.badPort": "Nieprawidłowy port usługi (1–65535).",
    "addFwd.cancel": "Anuluj",
    "addFwd.save": "Dodaj",

    "changePass.title": "Zmień hasło główne",
    "changePass.intro":
      "Podaj obecne hasło i nowe. Wszystkie zapisane połączenia zostaną ponownie zaszyfrowane nowym hasłem.",
    "changePass.current": "Obecne hasło główne",
    "changePass.new": "Nowe hasło (min. 4 znaki)",
    "changePass.repeat": "Powtórz nowe hasło",
    "changePass.cancel": "Anuluj",
    "changePass.save": "Zmień hasło",
    "changePass.needCurrent": "Podaj obecne hasło.",
    "changePass.done": "Hasło główne zostało zmienione.",

    "import.title": "Importuj konfigurację",
    "import.intro":
      "Wskaż plik <code>.enc</code> zapisany wcześniej przez eksport i podaj hasło główne, którym był chroniony.",
    "import.warning":
      "⚠️ Obecna konfiguracja zostanie zastąpiona, a aktywne połączenia rozłączone. " +
      "Poprzednia wersja zostanie zapisana obok jako kopia <code>.bak</code>.",
    "import.file": "Plik konfiguracji",
    "import.pass": "Hasło główne do tego pliku",
    "import.cancel": "Anuluj",
    "import.save": "Importuj",
    "import.needFile": "Wskaż plik konfiguracji.",
    "import.needPass": "Podaj hasło główne do tego pliku.",
    "import.readFailed": "Nie udało się odczytać pliku.",

    "status.disconnected": "Rozłączony",
    "status.connecting": "Łączenie…",
    "status.connected": "Połączony",
    "status.disconnecting": "Rozłączanie…",
    "status.need_trust": "Nieznany certyfikat",
    "status.error": "Błąd",

    "card.connect": "Połącz",
    "card.disconnect": "Rozłącz",
    "card.trust": "Zaufaj certyfikatowi i połącz",
    "card.retry": "Połącz ponownie",
    "card.addMachine": "＋ Dodaj maszynę",
    "card.addMachineHint": "Dołóż maszynę bez rozłączania",
    "card.edit": "Edytuj",
    "card.editHint": "Edytuj połączenie",
    "card.preview": "Podgląd",
    "card.previewHint": "Podejrzyj ustawienia (bez rozłączania)",
    "card.delete": "Usuń",
    "card.confirmDelete": "Usunąć połączenie „{name}”?",
    "card.afterConnect": "dostępne po połączeniu",
    "card.dead": "nie działa — sprawdź IP/port",
    "card.showLog": "Pokaż log połączenia",
    "card.menuHint": "Akcje dla tego adresu",

    "menu.rdpConnect": "🖥️ Połącz przez RDP",
    "menu.rdpDownload": "⬇️ Pobierz plik .rdp",
    "menu.ssh": "🔌 Połącz przez SSH",
    "menu.vnc": "🖥️ Połącz przez VNC",
    "menu.browser": "🌐 Otwórz w przeglądarce",
    "menu.copyAddr": "📋 Kopiuj adres",
    "menu.copyCmd": "📋 Kopiuj komendę",
    "menu.sshUser": "użytkownik",

    "rdp.failedTitle": "Pulpit zdalny się nie otworzył",
    "rdp.failedText":
      "Szybkie łączenie RDP nie jest skonfigurowane na tym komputerze. " +
      "Uruchom ponownie start.bat albo pobierz plik połączenia.",
    "rdp.failedTextRegistry":
      "Szybkie łączenie RDP nie jest skonfigurowane na tym komputerze — instalacja przez docker compose go nie rejestruje. " +
      "Pobierz plik połączenia albo wyłącz ⚙ Ustawienia → Szybkie łączenie RDP.",
    "rdp.download": "⬇️ Pobierz plik .rdp",
    "rdp.settings": "⚙ Ustawienia",
    "toast.close": "Zamknij",

    "err.generic": "Coś poszło nie tak — spróbuj ponownie.",
    "err.field": "Sprawdź pole: {field} ({message}).",
    "err.invalidValue": "nieprawidłowa wartość",
    "err.locked": "Sejf zablokowany",

    "field.name": "nazwa",
    "field.host": "adres serwera",
    "field.username": "login",
    "field.password": "hasło",
    "field.port": "port",
    "field.ip": "IP zdalne",
    "field.remote_port": "port zdalny",
    "field.local_port": "port lokalny",
    "field.otp": "token",
    "field.trusted_certs": "certyfikat",
    "field.ipsec_psk": "klucz współdzielony (PSK)",
    "field.ipsec_remote_ts": "sieci za VPN-em",
    "field.data": "dane",
  },
};

// --- stan ---

function storedLang() {
  try {
    const saved = localStorage.getItem(LANG_KEY);
    if (saved && STRINGS[saved]) return saved;
  } catch (e) { /* prywatne okno albo zablokowane ciasteczka — trudno */ }
  return DEFAULT_LANG;
}

let lang = storedLang();

const currentLang = () => lang;
const localeTag = () => (lang === "pl" ? "pl-PL" : "en-GB");

// Brakujący klucz nie może wywrócić panelu: wracamy do angielskiego, a w ostateczności
// pokazujemy sam klucz — od razu widać, czego brakuje w katalogu.
function t(key, params) {
  let text = STRINGS[lang][key];
  if (text === undefined) text = STRINGS[DEFAULT_LANG][key];
  if (text === undefined) return key;
  if (!params) return text;
  return text.replace(/\{(\w+)\}/g, (m, name) => (name in params ? params[name] : m));
}

function applyTranslations(root = document) {
  const set = (attr, fn) => {
    for (const node of root.querySelectorAll(`[${attr}]`)) fn(node, t(node.getAttribute(attr)));
  };
  set("data-i18n", (node, text) => { node.textContent = text; });
  set("data-i18n-html", (node, text) => { node.innerHTML = text; });
  set("data-i18n-ph", (node, text) => { node.placeholder = text; });
  set("data-i18n-title", (node, text) => { node.title = text; });
  set("data-i18n-aria", (node, text) => { node.setAttribute("aria-label", text); });
  if (root === document) document.documentElement.lang = lang;
}

// Zmiana języka przerysowuje panel bez przeładowania strony — formularze zostają
// wypełnione tym, co użytkownik już wpisał.
function setLang(code) {
  if (!STRINGS[code] || code === lang) return false;
  lang = code;
  try { localStorage.setItem(LANG_KEY, code); } catch (e) { /* jak wyżej */ }
  applyTranslations();
  return true;
}
