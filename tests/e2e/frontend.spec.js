const { test, expect } = require("@playwright/test");
const fs = require("fs");

// Testy zachowania interfejsu (bez backendu — stan wstrzykiwany, jak w realnym renderze).

const SAMPLE = {
  id: "a1", name: "Klient Alfa", host: "vpn.alfa.pl", requires_token: false, token_mode: "none",
  forwards: [
    { label: "Serwer RDP", ip: "10.10.10.11", remote_port: 3389, local_port: 13391 },
    { label: "SSH brama", ip: "10.10.10.12", remote_port: 22, local_port: 13392 },
  ],
};

// Panel mówi domyślnie po angielsku, a język da się przełączyć — testy pilnują więc
// zachowania, a brzmienie tekstów biorą z katalogu tłumaczeń.
const tekst = (page, klucz) => page.evaluate((k) => t(k), klucz);

async function toMain(page) {
  await page.goto("/");
  await page.waitForFunction(() => typeof window.openEditor === "function");
  await page.evaluate(() => {
    if (typeof pollTimer !== "undefined") clearInterval(pollTimer);
    state = { profiles: [], connections: {}, port_range: [13391, 13449] };
    show("main");
  });
}

test("tryby tokena: checkbox odsłania opcje, zapis wysyła token_mode=push", async ({ page }) => {
  await toMain(page);
  await page.evaluate(() => openEditor(null));

  await expect(page.locator("#token-modes")).toBeHidden();
  await page.check("#f-token");
  await expect(page.locator("#token-modes")).toBeVisible();
  await page.check('input[name="token-mode"][value="push"]');

  // przechwyć treść zapisu
  await page.evaluate(() => {
    window.__captured = null;
    window.fetch = async (url, opts) => {
      if (opts && opts.method === "POST" && String(url).includes("/api/profiles")) {
        window.__captured = JSON.parse(opts.body);
      }
      return { ok: true, status: 200, json: async () => ({ id: "x" }) };
    };
  });

  await page.fill("#f-name", "Test");
  await page.fill("#f-host", "vpn.test.pl");
  await page.fill("#f-username", "u");
  await page.fill("#f-password", "haslo");
  await page.click("#editor-save");

  const captured = await page.evaluate(() => window.__captured);
  expect(captured).not.toBeNull();
  expect(captured.token_mode).toBe("push");
});

test("wklejony adres bramy rozkłada się na host/port/realm", async ({ page }) => {
  await toMain(page);
  await page.evaluate(() => openEditor(null));
  await page.fill("#f-host", "https://vpn.klient.pl:443/myrealm");
  await page.evaluate(() => splitGatewayField());
  await expect(page.locator("#f-host")).toHaveValue("vpn.klient.pl");
  await expect(page.locator("#f-port")).toHaveValue("443");
  await expect(page.locator("#f-realm")).toHaveValue("myrealm");
});

test("auto-uzupełnianie portu usługi z nazwy maszyny", async ({ page }) => {
  await toMain(page);
  await page.evaluate(() => openEditor(null));

  const cases = { "Serwer RDP": "3389", "Brama SSH": "22", "Konsola VNC": "5900" };
  for (const [name, port] of Object.entries(cases)) {
    await page.fill(".fwd-edit .f-label", "");
    await page.fill(".fwd-edit .f-rport", "");
    await page.fill(".fwd-edit .f-label", name);
    await expect(page.locator(".fwd-edit .f-rport")).toHaveValue(port);
  }
});

test("menu akcji ⋮ pokazuje akcję RDP i kopiowanie", async ({ page }) => {
  await toMain(page);
  await page.evaluate((p) => {
    state = {
      profiles: [p],
      connections: { a1: { state: "connected", detail: "",
        forwards: [{ local_port: 13391, alive: true }, { local_port: 13392, alive: true }], log: [] } },
      port_range: [13391, 13449],
    };
    render();
  }, SAMPLE);

  await page.locator(".fwd-menu-btn").first().click();
  const menu = page.locator("#action-menu");
  await expect(menu).toBeVisible();
  const items = (await menu.locator(".menu-item").allTextContents()).join(" | ");
  expect(items).toContain("RDP");
  expect(items).toContain(await tekst(page, "menu.copyAddr"));
});

test("plik .rdp zawiera nazwę połączenia i maszyny", async ({ page }) => {
  await toMain(page);
  await page.evaluate((p) => {
    state = {
      profiles: [p],
      connections: { a1: { state: "connected", detail: "",
        forwards: [{ local_port: 13391, alive: true }, { local_port: 13392, alive: true }], log: [] } },
      port_range: [13391, 13449],
      settings: { fast_rdp: false },   // przycisk pobierania pliku
    };
    render();
  }, SAMPLE);
  await page.locator(".fwd-menu-btn").first().click();
  const [download] = await Promise.all([
    page.waitForEvent("download"),
    page.locator("#action-menu .menu-item",
                 { hasText: await tekst(page, "menu.rdpDownload") }).click(),
  ]);
  expect(download.suggestedFilename()).toBe("Klient Alfa - Serwer RDP.rdp");
});

test("szybkie łączenie RDP używa protokołu tunnelbox-rdp z adresem i nazwą", async ({ page }) => {
  await toMain(page);
  await page.evaluate((p) => {
    state = {
      profiles: [p],
      connections: { a1: { state: "connected", detail: "",
        forwards: [{ local_port: 13391, alive: true }, { local_port: 13392, alive: true }], log: [] } },
      port_range: [13391, 13449],
    };
    render();
  }, SAMPLE);

  // domyślnie (fast_rdp) menu pokazuje szybkie łączenie
  await page.locator(".fwd-menu-btn").first().click();
  const items = (await page.locator("#action-menu .menu-item").allTextContents()).join(" | ");
  expect(items).toContain(await tekst(page, "menu.rdpConnect"));

  // adres protokołu budowany dla tej maszyny
  const url = await page.evaluate(
    (p) => rdpProtocolUrl(p.forwards[0], p.name), SAMPLE);
  expect(url).toContain("tunnelbox-rdp://connect?");
  expect(url).toContain("host=127.0.0.2");
  expect(url).toContain("port=13391");
  // spacje kodowane jako '+' (helper rdp-launcher.ps1 zamienia je z powrotem)
  expect(url).toContain("name=Klient+Alfa+-+Serwer+RDP");
});

test("gdy protokół RDP nie jest zarejestrowany, panel podpowiada i daje pobranie pliku", async ({ page }) => {
  await toMain(page);
  await page.evaluate((p) => {
    state = {
      profiles: [p],
      connections: { a1: { state: "connected", detail: "",
        forwards: [{ local_port: 13391, alive: true }, { local_port: 13392, alive: true }], log: [] } },
      port_range: [13391, 13449],
      settings: { fast_rdp: true },
    };
    render();
  }, SAMPLE);

  // strona zachowuje fokus = nic się nie uruchomiło (protokół niezarejestrowany)
  await page.bringToFront();
  await page.evaluate((p) => scheduleRdpFallbackHint(p.forwards[0], p.name, 10), SAMPLE);

  const toast = page.locator("#toast");
  await expect(toast).toBeVisible();
  await expect(toast).toContainText(await tekst(page, "rdp.failedTitle"));

  // przycisk w podpowiedzi realnie pobiera plik
  const [download] = await Promise.all([
    page.waitForEvent("download"),
    toast.locator("button", { hasText: await tekst(page, "rdp.download") }).click(),
  ]);
  expect(download.suggestedFilename()).toBe("Klient Alfa - Serwer RDP.rdp");
  await expect(toast).toBeHidden();
});

test("instalacja z rejestru: podpowiedź RDP nie odsyła do start.bat, którego tam nie ma", async ({ page }) => {
  await toMain(page);
  await page.evaluate((p) => {
    state = {
      profiles: [p],
      connections: { a1: { state: "connected", detail: "",
        forwards: [{ local_port: 13391, alive: true }], log: [] } },
      port_range: [13391, 13449],
      settings: { fast_rdp: true },
    };
    render();
  }, SAMPLE);
  await page.bringToFront();

  // sposób instalacji ze stanu (zawsze wczytany), nawet gdy /api/update jeszcze nie odpowiedziało
  for (const [install, klucz] of [["registry", "rdp.failedTextRegistry"], ["package", "rdp.failedText"]]) {
    await page.evaluate((i) => { state.install = i; updateInfo = null; hideToast(); }, install);
    await page.evaluate((p) => scheduleRdpFallbackHint(p.forwards[0], p.name, 10), SAMPLE);
    await expect(page.locator("#toast")).toContainText(await tekst(page, klucz));
  }
  // starszy backend bez pola w stanie: zapasem jest odpowiedź /api/update
  for (const [install, klucz] of [["registry", "rdp.failedTextRegistry"], ["package", "rdp.failedText"]]) {
    await page.evaluate((i) => { delete state.install; updateInfo = { install: i }; hideToast(); }, install);
    await page.evaluate((p) => scheduleRdpFallbackHint(p.forwards[0], p.name, 10), SAMPLE);
    await expect(page.locator("#toast")).toContainText(await tekst(page, klucz));
  }
  expect(await tekst(page, "rdp.failedTextRegistry")).not.toContain("start.bat");
});

test("podpowiedź nie pojawia się, gdy pulpit zdalny przejął fokus", async ({ page }) => {
  await toMain(page);
  // symulacja: mstsc wystartował i zabrał fokus przeglądarce
  await page.evaluate(() => { document.hasFocus = () => false; });
  await page.evaluate((p) => scheduleRdpFallbackHint(p.forwards[0], p.name, 10), SAMPLE);
  await page.waitForTimeout(120);
  await expect(page.locator("#toast")).toBeHidden();
});

test("każda maszyna dostaje własny adres pętli zwrotnej", async ({ page }) => {
  await toMain(page);
  await page.evaluate((p) => {
    state = {
      profiles: [p],
      connections: { a1: { state: "connected", detail: "",
        forwards: [{ local_port: 13391, alive: true }, { local_port: 13392, alive: true }], log: [] } },
      port_range: [13391, 13449],
    };
    render();
  }, SAMPLE);

  // Wspólny „localhost" sprawiał, że Windows nadpisywał poświadczenia RDP —
  // klucz TERMSRV/<adres> nie zawiera portu.
  expect(await page.locator(".fwd-addr").allTextContents())
    .toEqual(["127.0.0.2:13391", "127.0.0.3:13392"]);
});

test("plik .rdp ma własny adres maszyny i korzysta z zapisanych poświadczeń", async ({ page }) => {
  await toMain(page);
  await page.evaluate((p) => {
    state = {
      profiles: [p],
      connections: { a1: { state: "connected", detail: "",
        forwards: [{ local_port: 13391, alive: true }, { local_port: 13392, alive: true }], log: [] } },
      port_range: [13391, 13449],
      settings: { fast_rdp: false },   // przycisk pobierania pliku
    };
    render();
  }, SAMPLE);
  await page.locator(".fwd-menu-btn").first().click();
  const [download] = await Promise.all([
    page.waitForEvent("download"),
    page.locator("#action-menu .menu-item",
                 { hasText: await tekst(page, "menu.rdpDownload") }).click(),
  ]);
  const content = fs.readFileSync(await download.path(), "utf8");
  expect(content).toContain("full address:s:127.0.0.2:13391");
  expect(content).toContain("prompt for credentials:i:0");
});

test("podgląd aktywnego połączenia jest tylko do odczytu", async ({ page }) => {
  await toMain(page);
  await page.evaluate((p) => {
    state = {
      profiles: [p],
      connections: { a1: { state: "connected", detail: "",
        forwards: [{ local_port: 13391, alive: true }, { local_port: 13392, alive: true }], log: [] } },
      port_range: [13391, 13449],
    };
    render();
  }, SAMPLE);
  await page.getByRole("button", { name: await tekst(page, "card.preview") }).click();
  await expect(page.locator("#editor-readonly-note")).toBeVisible();
  await expect(page.locator("#f-name")).toBeDisabled();
  await expect(page.locator("#f-host")).toBeDisabled();
  await expect(page.locator(".fwd-edit .f-ip").first()).toBeDisabled();
  await expect(page.locator("#editor-save")).toBeHidden();
  await expect(page.locator("#editor-cancel")).toHaveText(await tekst(page, "editor.close"));
});

test("akcja 'otwórz w przeglądarce' rozpoznana z nazwy (https na nietypowym porcie)", async ({ page }) => {
  await toMain(page);
  const WEB = {
    id: "a1", name: "Klient Alfa", host: "vpn.alfa.pl", requires_token: false, token_mode: "none",
    forwards: [{ label: "Panel https", ip: "10.10.10.30", remote_port: 9443, local_port: 13395 }],
  };
  await page.evaluate((p) => {
    state = { profiles: [p], connections: { a1: { state: "connected", detail: "",
      forwards: [{ local_port: 13395, alive: true }], log: [] } }, port_range: [13391, 13449] };
    render();
  }, WEB);
  await page.locator(".fwd-menu-btn").first().click();
  const items = (await page.locator("#action-menu .menu-item").allTextContents()).join(" | ");
  expect(items).toContain(await tekst(page, "menu.browser"));
});

test("dokładanie maszyny do działającego połączenia", async ({ page }) => {
  await toMain(page);
  await page.evaluate((p) => {
    state = { profiles: [p], connections: { a1: { state: "connected", detail: "",
      forwards: [{ local_port: 13391, alive: true }, { local_port: 13392, alive: true }], log: [] } },
      port_range: [13391, 13449] };
    render();
  }, SAMPLE);

  await page.getByRole("button", { name: await tekst(page, "card.addMachine") }).click();
  await expect(page.locator("#add-fwd-dialog")).toBeVisible();

  // auto-port z nazwy
  await page.fill("#af-label", "Konsola VNC");
  await expect(page.locator("#af-rport")).toHaveValue("5900");

  // przechwyć wysyłkę
  await page.evaluate(() => {
    window.__sent = null;
    window.fetch = async (url, opts) => {
      if (opts && opts.method === "POST" && String(url).includes("/forwards")) {
        window.__sent = { url: String(url), body: JSON.parse(opts.body) };
      }
      return { ok: true, status: 200, json: async () => ({ local_port: 13393 }) };
    };
  });
  await page.fill("#af-ip", "10.10.10.30");
  await page.click("#af-save");

  const sent = await page.evaluate(() => window.__sent);
  expect(sent).not.toBeNull();
  expect(sent.url).toContain("/api/profiles/a1/forwards");
  expect(sent.body).toMatchObject({ ip: "10.10.10.30", remote_port: 5900, label: "Konsola VNC" });
});

test("ustawienie fast_rdp decyduje, który przycisk pokazuje menu ⋮", async ({ page }) => {
  await toMain(page);
  const setStateWith = (fastRdp) => page.evaluate(({ p, fast }) => {
    state = {
      profiles: [p],
      connections: { a1: { state: "connected", detail: "",
        forwards: [{ local_port: 13391, alive: true }, { local_port: 13392, alive: true }], log: [] } },
      port_range: [13391, 13449],
      settings: { fast_rdp: fast },
    };
    render();
  }, { p: SAMPLE, fast: fastRdp });

  // włączone -> szybkie łączenie
  await setStateWith(true);
  await page.locator(".fwd-menu-btn").first().click();
  let items = (await page.locator("#action-menu .menu-item").allTextContents()).join(" | ");
  expect(items).toContain(await tekst(page, "menu.rdpConnect"));
  expect(items).not.toContain(await tekst(page, "menu.rdpDownload"));
  await page.keyboard.press("Escape");

  // wyłączone -> pobieranie pliku
  await setStateWith(false);
  await page.locator(".fwd-menu-btn").first().click();
  items = (await page.locator("#action-menu .menu-item").allTextContents()).join(" | ");
  expect(items).toContain(await tekst(page, "menu.rdpDownload"));
  expect(items).not.toContain(await tekst(page, "menu.rdpConnect"));
});

test("dialog ustawień zapisuje przełącznik szybkiego RDP", async ({ page }) => {
  await toMain(page);
  await page.evaluate(() => { state.settings = { fast_rdp: true, check_updates: true, lang: "en" }; });

  await page.click("#settings-btn");
  await expect(page.locator("#settings-dialog")).toBeVisible();
  await expect(page.locator("#set-fast-rdp")).toBeChecked();
  await expect(page.locator("#set-check-updates")).toBeChecked();

  await page.evaluate(() => {
    window.__put = null;
    window.fetch = async (url, opts) => {
      if (opts && opts.method === "PUT" && String(url).includes("/api/settings")) {
        window.__put = JSON.parse(opts.body);
      }
      return { ok: true, status: 200, json: async () => ({ fast_rdp: false }) };
    };
  });
  await page.uncheck("#set-fast-rdp");
  await page.click("#settings-save");

  expect(await page.evaluate(() => window.__put))
    .toEqual({ lang: "en", fast_rdp: false, check_updates: true });
});

test("zmiana hasła: walidacja niezgodnych haseł", async ({ page }) => {
  await toMain(page);
  await page.click("#change-pass-btn");
  await expect(page.locator("#change-pass-dialog")).toBeVisible();
  await page.fill("#cp-current", "stare");
  await page.fill("#cp-new", "noweHaslo");
  await page.fill("#cp-new2", "inne");
  await page.click("#cp-save");
  await expect(page.locator("#cp-error")).toBeVisible();
  await expect(page.locator("#cp-error")).toHaveText(await tekst(page, "auth.passMismatch"));
});

test("przyciski eksportu/importu są w ustawieniach i na ekranie logowania", async ({ page }) => {
  await page.goto("/");
  await page.waitForFunction(() => typeof window.openEditor === "function");

  // ekran logowania
  await page.evaluate(() => { show("auth"); });
  await expect(page.locator("#auth-export")).toBeVisible();
  await expect(page.locator("#auth-import")).toBeVisible();

  // ustawienia
  await page.evaluate(() => {
    if (typeof pollTimer !== "undefined") clearInterval(pollTimer);
    state = { profiles: [], connections: {}, port_range: [13391, 13449], settings: {} };
    show("main");
  });
  await page.click("#settings-btn");
  await expect(page.locator("#settings-export")).toBeVisible();
  await expect(page.locator("#settings-import")).toBeVisible();

  // „Importuj" w ustawieniach otwiera okno importu
  await page.click("#settings-import");
  await expect(page.locator("#import-dialog")).toBeVisible();
});

test("blokada panelu czyści listę połączeń z widoku", async ({ page }) => {
  await page.goto("/");
  await page.waitForFunction(() => typeof window.lockPanel === "function");
  await page.evaluate((p) => {
    if (typeof pollTimer !== "undefined") clearInterval(pollTimer);
    state = { profiles: [p], connections: { a1: { state: "connected", forwards: [], log: [] } },
              port_range: [13391, 13449], settings: {} };
    show("main");
    render();
    // panel zablokowany po stronie serwera
    window.fetch = async () => ({ ok: true, status: 200, json: async () => ({ exists: true }) });
  }, SAMPLE);
  await expect(page.locator(".card")).toHaveCount(1);

  await page.evaluate(() => lockPanel());
  await expect(page.locator("#unlock-view")).toBeVisible();
  await expect(page.locator("#profiles")).toBeEmpty();
  await expect(page.locator(".card")).toHaveCount(0);
});

test("brak menu ⋮ przy rozłączonym połączeniu", async ({ page }) => {
  await toMain(page);
  await page.evaluate((p) => {
    state = { profiles: [p], connections: { a1: { state: "disconnected", forwards: [], log: [] } },
              port_range: [13391, 13449] };
    render();
  }, SAMPLE);
  await expect(page.locator(".fwd-menu-btn")).toHaveCount(0);
  await expect(page.locator(".fwd-row").first()).toContainText(await tekst(page, "card.afterConnect"));
});

test("typ IPsec odsłania własne pola i chowa te od SSL-VPN", async ({ page }) => {
  await toMain(page);
  await page.evaluate(() => openEditor(null));

  // domyślnie SSL-VPN: pola IPsec ukryte, port i realm widoczne
  await expect(page.locator("#ipsec-fields")).toBeHidden();
  await expect(page.locator("#f-port-wrap")).toBeVisible();
  await expect(page.locator("#f-realm-wrap")).toBeVisible();

  await page.selectOption("#f-vpn-type", "ipsec");
  await expect(page.locator("#ipsec-fields")).toBeVisible();
  await expect(page.locator("#f-port-wrap")).toBeHidden();
  await expect(page.locator("#f-realm-wrap")).toBeHidden();
  // IPsec nie zna zatwierdzania na telefonie
  await expect(page.locator("#token-push-wrap")).toBeHidden();
  // domyślny tryb pyta o użytkownika, więc login i hasło zostają
  await expect(page.locator("#creds-row")).toBeVisible();
});

test("tryb IPsec na sam klucz PSK chowa login, hasło i token", async ({ page }) => {
  await toMain(page);
  await page.evaluate(() => openEditor(null));
  await page.selectOption("#f-vpn-type", "ipsec");

  await page.selectOption("#f-ipsec-auth", "ikev2-psk");
  await expect(page.locator("#creds-row")).toBeHidden();
  await expect(page.locator("#token-block")).toBeHidden();
  // tryb agresywny dotyczy tylko IKEv1
  await expect(page.locator("#f-aggressive-wrap")).toBeHidden();

  await page.selectOption("#f-ipsec-auth", "ikev1-psk");
  await expect(page.locator("#f-aggressive-wrap")).toBeVisible();
});

test("zapis profilu IPsec wysyła komplet pól", async ({ page }) => {
  await toMain(page);
  await page.evaluate(() => openEditor(null));
  await page.selectOption("#f-vpn-type", "ipsec");

  await page.evaluate(() => {
    window.__captured = null;
    window.fetch = async (url, opts) => {
      if (opts && opts.method === "POST" && String(url).includes("/api/profiles")) {
        window.__captured = JSON.parse(opts.body);
      }
      return { ok: true, status: 200, json: async () => ({ id: "x" }) };
    };
  });

  await page.fill("#f-name", "Klient IPsec");
  await page.fill("#f-host", "vpn.klient.pl");
  await page.fill("#f-username", "jkowalski");
  await page.fill("#f-password", "haslo");
  await page.fill("#f-ipsec-psk", "KluczWspoldzielony");
  await page.fill("#f-ipsec-local-id", "grupa-vpn");
  await page.fill("#f-ipsec-remote-ts", "10.10.0.0/16");
  await page.check("#f-ipsec-aggressive");
  await page.click("#editor-save");

  const captured = await page.evaluate(() => window.__captured);
  expect(captured).not.toBeNull();
  expect(captured.vpn_type).toBe("ipsec");
  expect(captured.ipsec_auth).toBe("ikev1-psk-xauth");
  expect(captured.ipsec_psk).toBe("KluczWspoldzielony");
  expect(captured.ipsec_local_id).toBe("grupa-vpn");
  expect(captured.ipsec_remote_ts).toBe("10.10.0.0/16");
  expect(captured.ipsec_aggressive).toBe(true);
});

test("IPsec bez klucza PSK nie idzie do zapisu", async ({ page }) => {
  await toMain(page);
  await page.evaluate(() => openEditor(null));
  await page.selectOption("#f-vpn-type", "ipsec");

  await page.evaluate(() => {
    window.__calls = 0;
    window.fetch = async () => {
      window.__calls++;
      return { ok: true, status: 200, json: async () => ({ id: "x" }) };
    };
  });

  await page.fill("#f-name", "Bez klucza");
  await page.fill("#f-host", "vpn.klient.pl");
  await page.fill("#f-username", "u");
  await page.fill("#f-password", "haslo");
  await page.click("#editor-save");

  await expect(page.locator("#editor-error")).toBeVisible();
  await expect(page.locator("#editor-error")).toContainText("PSK");
  expect(await page.evaluate(() => window.__calls)).toBe(0);
});

test("karta połączenia IPsec ma znacznik typu, SSL-VPN nie", async ({ page }) => {
  await toMain(page);
  await page.evaluate((sample) => {
    state.profiles = [
      { ...sample, id: "s1", name: "Klient SSL" },
      { ...sample, id: "i1", name: "Klient IPsec", vpn_type: "ipsec" },
    ];
    render();
  }, SAMPLE);

  const karty = page.locator(".card");
  await expect(karty).toHaveCount(2);
  await expect(karty.nth(0).locator(".type-badge")).toHaveCount(0);
  await expect(karty.nth(1).locator(".type-badge")).toHaveText("IPsec");
});

// --- pasek aktualizacji ---

const NOWA_WERSJA = {
  enabled: true,
  ok: true,
  current: "2.7.0",
  latest: "2.8.0",
  available: true,
  asset: "tunnelbox-2.8.0.zip",
  download: "https://github.com/Mysttic/tunnelbox/releases/download/v2.8.0/tunnelbox-2.8.0.zip",
  size: 147 * 1024 * 1024,
  published_at: "2026-09-01T10:00:00Z",
  page: "https://mysttic.github.io/Mysttic/tunnelbox/",
};

async function pokazPasek(page, info) {
  await toMain(page);
  await page.evaluate((data) => {
    sessionStorage.removeItem("vpn_update_skip");
    updateInfo = data;
    renderUpdateBar();
  }, info);
}

test("pasek aktualizacji pokazuje numer wersji i adresy do pobrania", async ({ page }) => {
  await pokazPasek(page, NOWA_WERSJA);

  await expect(page.locator("#update-bar")).toBeVisible();
  await expect(page.locator("#update-title")).toHaveText(/2\.8\.0/);
  await expect(page.locator("#update-note")).toContainText("2.7.0");
  await expect(page.locator("#update-note")).toContainText("147 MB");
  await expect(page.locator("#update-download")).toHaveAttribute("href", NOWA_WERSJA.download);
  await expect(page.locator("#update-page")).toHaveAttribute("href", NOWA_WERSJA.page);
});

test("bez nowszej wersji paska nie ma", async ({ page }) => {
  await pokazPasek(page, { ...NOWA_WERSJA, available: false });
  await expect(page.locator("#update-bar")).toBeHidden();
});

test("„Później” chowa pasek, ale kolejna wersja pokaże go znowu", async ({ page }) => {
  await pokazPasek(page, NOWA_WERSJA);
  await page.click("#update-later");

  await expect(page.locator("#update-bar")).toBeHidden();
  expect(await page.evaluate(() => sessionStorage.getItem("vpn_update_skip"))).toBe("2.8.0");

  await page.evaluate(() => renderUpdateBar());
  await expect(page.locator("#update-bar")).toBeHidden();

  await page.evaluate(() => {
    updateInfo = { ...updateInfo, latest: "2.9.0" };
    renderUpdateBar();
  });
  await expect(page.locator("#update-bar")).toBeVisible();
});

test("instalator dostaje sam numer wersji", async ({ page }) => {
  await toMain(page);
  // Ze strony nie może wyjść nic poza numerem — adres pliku instalator ustala sam.
  const adres = await page.evaluate(() => updateProtocolUrl("2.8.0"));
  expect(adres).toBe("tunnelbox-update://install?version=2.8.0");
  expect(await page.evaluate(() => updateProtocolUrl("2.8.0 & rm -rf /")))
    .toBe("tunnelbox-update://install?version=2.8.0%20%26%20rm%20-rf%20%2F");
});

test("aktualizacja jednym kliknięciem jest tylko na Windows", async ({ page }) => {
  await pokazPasek(page, NOWA_WERSJA);
  // instalator to helper dla Windows; gdzie indziej zostaje pobranie paczki
  const windows = await page.evaluate(() => isWindows());
  if (windows) {
    await expect(page.locator("#update-install")).toBeVisible();
  } else {
    await expect(page.locator("#update-install")).toBeHidden();
  }
  await expect(page.locator("#update-download")).toBeVisible();
});

test("„Zaktualizuj” mówi, co się właśnie dzieje", async ({ page }) => {
  await pokazPasek(page, NOWA_WERSJA);
  // poza Windows przycisku nie ma — tu sprawdzamy samo zachowanie kliknięcia
  await page.evaluate(() => $("update-install").classList.remove("hidden"));
  await page.click("#update-install");

  await expect(page.locator("#toast")).toBeVisible();
  await expect(page.locator("#toast .toast-title"))
    .toHaveText(await tekst(page, "update.startedTitle"));
});

// Odpowiedź /api/update podstawiona tak, jak przyszłaby z backendu — przez loadUpdate(),
// a nie wpisana prosto do updateInfo. Udajemy przy tym Windows: tam przycisk instalatora
// normalnie jest widoczny, więc widać, że chowa go dopiero instalacja z rejestru.
async function pasekZApi(page, info) {
  await toMain(page);
  await page.evaluate(async (data) => {
    sessionStorage.removeItem("vpn_update_skip");
    Object.defineProperty(navigator, "userAgentData", { value: { platform: "Windows" } });
    window.fetch = async (url) => ({
      ok: true,
      status: 200,
      json: async () => (String(url).includes("/api/update") ? data : {}),
    });
    await loadUpdate();
  }, info);
}

test("instalacja z rejestru: zamiast przycisków pasek podaje polecenie docker compose", async ({ page }) => {
  await pasekZApi(page, { ...NOWA_WERSJA, install: "registry" });

  await expect(page.locator("#update-bar")).toBeVisible();
  await expect(page.locator("#update-title")).toHaveText(/2\.8\.0/);
  // paczka ani instalator nic tu nie dadzą — obraz podmienia docker compose pull
  await expect(page.locator("#update-install")).toBeHidden();
  await expect(page.locator("#update-download")).toBeHidden();
  const podpowiedz = page.locator("#update-registry");
  await expect(podpowiedz).toBeVisible();
  await expect(podpowiedz).toContainText(await tekst(page, "update.registryHint"));
  // dwa osobne polecenia — „&&" nie działa w Windows PowerShell 5.1
  await expect(podpowiedz.locator("code")).toHaveText(["docker compose pull", "docker compose up -d"]);
  // „Co nowego” zostaje — opis wydania przyda się niezależnie od sposobu instalacji
  await expect(page.locator("#update-page")).toBeVisible();
});

test("instalacja z paczki (albo starszy backend bez pola install) nie pokazuje polecenia", async ({ page }) => {
  for (const info of [{ ...NOWA_WERSJA, install: "package" }, NOWA_WERSJA]) {
    await pasekZApi(page, info);

    await expect(page.locator("#update-bar")).toBeVisible();
    await expect(page.locator("#update-registry")).toBeHidden();
    await expect(page.locator("#update-install")).toBeVisible();
    await expect(page.locator("#update-download")).toBeVisible();
    await expect(page.locator("#update-download")).toHaveAttribute("href", NOWA_WERSJA.download);
  }
});

// --- język panelu ---

test("panel startuje po angielsku", async ({ page }) => {
  await toMain(page);
  await expect(page.locator("#settings-btn")).toHaveText("⚙ Settings");
  await expect(page.locator(".toolbar h2")).toHaveText("VPN connections");
  expect(await page.evaluate(() => document.documentElement.lang)).toBe("en");
});

test("wybór polskiego przerysowuje panel bez przeładowania", async ({ page }) => {
  await toMain(page);
  await page.evaluate((sample) => {
    state.profiles = [sample];
    state.connections = {};
    render();
  }, SAMPLE);

  await page.evaluate(() => setLang("pl"));
  await page.evaluate(() => render());

  await expect(page.locator("#settings-btn")).toHaveText("⚙ Ustawienia");
  await expect(page.locator(".toolbar h2")).toHaveText("Połączenia VPN");
  await expect(page.locator(".card .status")).toHaveText("Rozłączony");
  await expect(page.locator(".card-actions button").first()).toHaveText("Połącz");
  expect(await page.evaluate(() => document.documentElement.lang)).toBe("pl");

  // wybór zostaje na następne wejście do panelu — ekran hasła zna go, zanim
  // cokolwiek odczytamy z sejfu
  expect(await page.evaluate(() => localStorage.getItem("vpn_lang"))).toBe("pl");
});

test("ustawienie z sejfu przestawia język panelu", async ({ page }) => {
  await toMain(page);
  await page.evaluate(() => setLang("en"));
  await page.evaluate(() => {
    state.settings = { fast_rdp: true, check_updates: true, lang: "pl" };
    syncLang();
    render();
  });
  await expect(page.locator("#settings-btn")).toHaveText("⚙ Ustawienia");
});
