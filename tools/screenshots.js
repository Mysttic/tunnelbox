#!/usr/bin/env node
// Generuje zrzuty ekranu do docs/MANUAL.md i docs/MANUAL.pl.md.
//
//   node tools/screenshots.js
//
// Skrypt serwuje app/static, podstawia odpowiedzi API (żeby nie trzeba było mieć
// działającego VPN-a ani sejfu) i zapisuje pliki do docs/img/<język>. Dzięki temu po
// każdej zmianie w interfejsie zrzuty odświeża się jednym poleceniem, zamiast klikać
// i wycinać ręcznie — a instrukcja nie zostaje w tyle za panelem.
//
// Panel jest dwujęzyczny, więc każdy zrzut powstaje po angielsku i po polsku:
// docs/MANUAL.md pokazuje img/en, docs/MANUAL.pl.md — img/pl.
//
// Playwright bierzemy z tests/e2e (tam już jest zainstalowany):
//   cd tests/e2e && npm install && npx playwright install chromium

const fs = require("fs");
const http = require("http");
const path = require("path");

const ROOT = path.join(__dirname, "..");
const STATIC = path.join(ROOT, "app", "static");
const OUT = path.join(ROOT, "docs", "img");
const JEZYKI = ["en", "pl"];
const PORT = 8098;

const { chromium } = require(path.join(ROOT, "tests", "e2e", "node_modules", "playwright"));

// --- dane pokazywane na zrzutach ---

const WERSJA = fs.readFileSync(path.join(ROOT, "VERSION"), "utf8").trim();

// Przykładowe dane po angielsku i po polsku — zrzut ma wyglądać jak panel,
// który użytkownik zobaczy u siebie, razem z nazwami maszyn.
const SLOWA = {
  en: {
    alfa: "Client Alfa", beta: "Client Beta", gamma: "Client Gamma",
    rdp: "RDP server", sql: "SQL database", files: "File server", web: "https panel",
    blad: "Sign-in rejected — check the username, password or token.",
    cert: "The VPN server presented an unknown certificate. Check that the gateway "
      + "address is right, then click “Trust the certificate and connect”.",
  },
  pl: {
    alfa: "Klient Alfa", beta: "Klient Beta", gamma: "Klient Gamma",
    rdp: "Serwer RDP", sql: "Baza SQL", files: "Serwer plików", web: "Panel https",
    blad: "Logowanie odrzucone — sprawdź login, hasło i token.",
    cert: "Serwer przedstawił nieznany certyfikat. Sprawdź, czy adres bramy się zgadza, "
      + "i kliknij „Zaufaj certyfikatowi i połącz”.",
  },
};

const ALFA = {
  id: "a1",
  name: "alfa",
  vpn_type: "ssl",
  host: "vpn.alfa.pl",
  port: 443,
  realm: "",
  username: "jkowalski",
  password: "example-password",
  token_mode: "none",
  requires_token: false,
  trusted_certs: [],
  forwards: [
    { label: "rdp", ip: "10.10.10.11", remote_port: 3389, local_port: 13391 },
    { label: "sql", ip: "10.10.10.20", remote_port: 1433, local_port: 13392 },
  ],
};

const BETA = {
  id: "b1",
  name: "beta",
  vpn_type: "ipsec",
  host: "brama.beta.pl",
  port: 443,
  realm: "",
  username: "jkowalski",
  password: "example-password",
  token_mode: "none",
  requires_token: false,
  trusted_certs: [],
  ipsec_auth: "ikev1-psk-xauth",
  ipsec_psk: "KluczWspoldzielony2026",
  ipsec_local_id: "grupa-vpn",
  ipsec_remote_id: "",
  ipsec_remote_ts: "10.20.0.0/16",
  ipsec_aggressive: true,
  forwards: [
    { label: "files", ip: "10.20.0.15", remote_port: 445, local_port: 13393 },
  ],
};

const GAMMA = {
  id: "c1",
  name: "gamma",
  vpn_type: "ssl",
  host: "vpn.gamma.pl",
  port: 443,
  realm: "",
  username: "jkowalski",
  password: "example-password",
  token_mode: "code",
  requires_token: true,
  trusted_certs: [],
  forwards: [{ label: "web", ip: "10.30.0.8", remote_port: 9443, local_port: 13394 }],
};

// Etykiety maszyn trzymamy jako klucze — tłumaczy je dopiero zrzut dla danego języka.
const przetlumacz = (profil, lang) => ({
  ...profil,
  name: SLOWA[lang][profil.name] || profil.name,
  forwards: profil.forwards.map((f) => ({ ...f, label: SLOWA[lang][f.label] || f.label })),
});

const ZAKRES_PORTOW = [13391, 13449];
const ustawienia = (lang) => ({ fast_rdp: true, check_updates: true, lang });

const stan = (profiles, connections = {}) => ({
  profiles,
  connections,
  port_range: ZAKRES_PORTOW,
  settings: null,          // język dokłada zrzut() — te same dane, dwa katalogi
});

// Teksty zależne od języka podstawiamy dopiero przy robieniu zrzutu.
function nalang(wartosc, lang) {
  if (Array.isArray(wartosc)) return wartosc.map((x) => nalang(x, lang));
  if (wartosc && typeof wartosc === "object") {
    const kopia = {};
    for (const [k, v] of Object.entries(wartosc)) kopia[k] = nalang(v, lang);
    return kopia;
  }
  if (typeof wartosc === "string" && SLOWA[lang][wartosc]) return SLOWA[lang][wartosc];
  return wartosc;
}

const polaczony = (forwards) => ({
  state: "connected",
  forwards: forwards.map((f) => ({ local_port: f.local_port, alive: true })),
});

const BEZ_AKTUALIZACJI = {
  enabled: true,
  ok: true,
  current: WERSJA,
  latest: WERSJA,
  available: false,
  install: "package",     // paczka ZIP: pasek z przyciskami, nie polecenie dla rejestru
  page: "https://mysttic.github.io/Mysttic/tunnelbox/",
};

// „nowsza wersja" na zrzucie liczona od bieżącej — wpisana na sztywno zestarzałaby się
// przy pierwszym podbiciu VERSION i pasek namawiałby na wersję starszą niż zainstalowana
const [MAJ, MIN] = WERSJA.split(".").map(Number);
const NOWSZA = `${MAJ}.${MIN + 1}.0`;

const JEST_AKTUALIZACJA = {
  ...BEZ_AKTUALIZACJI,
  current: WERSJA,
  latest: NOWSZA,
  available: true,
  asset: `tunnelbox-${NOWSZA}.zip`,
  download:
    `https://github.com/Mysttic/tunnelbox/releases/download/v${NOWSZA}/tunnelbox-${NOWSZA}.zip`,
  size: 147 * 1024 * 1024,
  published_at: "2026-09-20T09:00:00Z",
};

// --- serwer plików statycznych ---

function serwuj() {
  const typy = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
  };
  const server = http.createServer((req, res) => {
    let p = decodeURIComponent(req.url.split("?")[0]);
    if (p === "/") p = "/index.html";
    const file = path.join(STATIC, p);
    if (!file.startsWith(STATIC) || !fs.existsSync(file)) {
      res.writeHead(404);
      return res.end("nie ma");
    }
    res.writeHead(200, { "Content-Type": typy[path.extname(file)] || "application/octet-stream" });
    fs.createReadStream(file).pipe(res);
  });
  return new Promise((ok) => server.listen(PORT, () => ok(server)));
}

// --- pojedynczy zrzut ---

async function zrzut(context, lang, opcje) {
  const {
    nazwa,
    szerokosc = 1000,
    wysokosc = 560,   // tylko ramka: zrzut całej strony i tak rośnie do wysokości treści
    vault = { exists: true, unlocked: true, version: WERSJA },
    token = true,
    state = stan([]),
    update = BEZ_AKTUALIZACJI,
    przygotuj,
    element,
  } = opcje;

  const page = await context.newPage();
  await page.setViewportSize({ width: szerokosc, height: wysokosc });
  const dane = { ...nalang(state, lang), settings: ustawienia(lang) };
  await page.addInitScript((mock) => {
    if (mock.token) sessionStorage.setItem("vpn_token", "demo");
    // ekran hasła głównego rysuje się, zanim panel odczyta ustawienia z sejfu
    localStorage.setItem("vpn_lang", mock.lang);
    window.fetch = async (url) => {
      const u = String(url);
      const dane = u.includes("/api/state")
        ? mock.state
        : u.includes("/api/update")
          ? mock.update
          : u.includes("/api/vault")
            ? mock.vault
            : {};
      return { ok: true, status: 200, json: async () => dane };
    };
  }, { token, vault, state: dane, update, lang });

  await page.goto(`http://localhost:${PORT}/`);
  await page.waitForFunction(() => typeof window.openEditor === "function");
  await page.waitForTimeout(200);           // showAuth()/loadUpdate() są asynchroniczne
  await page.evaluate(() => clearInterval(pollTimer));

  if (przygotuj) await przygotuj(page, lang);
  await page.waitForTimeout(150);           // dialogi mają animację wejścia

  const plik = path.join(OUT, lang, `${nazwa}.png`);
  if (element) await page.locator(element).screenshot({ path: plik });
  else await page.screenshot({ path: plik, fullPage: true });

  await page.close();
  const { width, height } = rozmiar(plik);
  console.log(`  ${lang}/${nazwa}.png  ${width}x${height}`);
}

function rozmiar(plik) {
  const raw = fs.readFileSync(plik);
  return { width: raw.readUInt32BE(16), height: raw.readUInt32BE(20) };
}

// --- lista zrzutów ---

const ZRZUTY = [
  {
    nazwa: "01-haslo-glowne",
    vault: { exists: false, unlocked: false, version: WERSJA },
    token: false,
    wysokosc: 560,
  },
  {
    nazwa: "02-odblokowanie",
    vault: { exists: true, unlocked: false, version: WERSJA },
    token: false,
    wysokosc: 500,
  },
  { nazwa: "03-lista-pusta", wysokosc: 300 },
  {
    nazwa: "04-formularz-pusty",
    element: "#editor",
    wysokosc: 1700,
    przygotuj: (page) => page.evaluate(() => openEditor(null)),
  },
  {
    nazwa: "05-formularz-wypelniony",
    element: "#editor",
    wysokosc: 1900,
    state: stan([ALFA]),
    przygotuj: (page, lang) => page.evaluate((p) => openEditor(p), przetlumacz(ALFA, lang)),
  },
  {
    nazwa: "06-formularz-ipsec",
    element: "#editor",
    wysokosc: 2100,
    state: stan([BETA]),
    przygotuj: (page, lang) => page.evaluate((p) => openEditor(p), przetlumacz(BETA, lang)),
  },
  {
    nazwa: "07-token",
    element: "#otp-dialog",
    state: stan([GAMMA]),
    przygotuj: (page, lang) => page.evaluate((p) => connectProfile(p), przetlumacz(GAMMA, lang)),
  },
  {
    nazwa: "08-certyfikat",
    element: ".card",
    state: stan([ALFA], {
      a1: {
        state: "need_trust",
        detail: "cert",
      },
    }),
  },
  {
    nazwa: "09-polaczony",
    element: ".card",
    state: stan([ALFA], { a1: polaczony(ALFA.forwards) }),
  },
  {
    nazwa: "10-menu-akcji",
    wysokosc: 300,
    state: stan([ALFA], { a1: polaczony(ALFA.forwards) }),
    przygotuj: (page) => page.locator(".fwd-menu-btn").first().click(),
  },
  {
    nazwa: "11-dodaj-maszyne",
    element: "#add-fwd-dialog",
    state: stan([ALFA], { a1: polaczony(ALFA.forwards) }),
    przygotuj: (page, lang) => page.evaluate((p) => openAddForward(p), przetlumacz(ALFA, lang)),
  },
  {
    nazwa: "12-kilka-polaczen",
    wysokosc: 300,
    state: stan([ALFA, BETA, GAMMA], {
      a1: polaczony(ALFA.forwards),
      b1: polaczony(BETA.forwards),
      c1: { state: "error", detail: "blad" },
    }),
  },
  {
    nazwa: "13-podglad-aktywnego",
    element: "#editor",
    wysokosc: 1900,
    state: stan([ALFA], { a1: polaczony(ALFA.forwards) }),
    przygotuj: (page, lang) => page.evaluate((p) => openEditor(p, true), przetlumacz(ALFA, lang)),
  },
  {
    nazwa: "14-ustawienia",
    element: "#settings-dialog",
    wysokosc: 800,
    state: stan([ALFA]),
    przygotuj: (page) => page.click("#settings-btn"),
  },
  {
    nazwa: "15-aktualizacja",
    wysokosc: 300,
    state: stan([ALFA], { a1: polaczony(ALFA.forwards) }),
    update: JEST_AKTUALIZACJA,
    przygotuj: (page) =>
      // przycisk instalatora jest tylko na Windows, a zrzuty robimy tam, gdzie akurat
      // stoi przeglądarka — pokazujemy go zawsze, bo taki widzi użytkownik
      page.evaluate(() => $("update-install").classList.remove("hidden")),
  },
];

// --- start ---

(async () => {
  for (const lang of JEZYKI) fs.mkdirSync(path.join(OUT, lang), { recursive: true });
  const server = await serwuj();
  const browser = await chromium.launch();

  console.log(`Zrzuty dla wersji ${WERSJA} -> docs/img`);
  try {
    for (const lang of JEZYKI) {
      const context = await browser.newContext({
        deviceScaleFactor: 2,
        locale: lang === "pl" ? "pl-PL" : "en-GB",
      });
      for (const opcje of ZRZUTY) await zrzut(context, lang, opcje);
      await context.close();
    }
  } finally {
    await browser.close();
    server.close();
  }
  console.log("Gotowe.");
})();
