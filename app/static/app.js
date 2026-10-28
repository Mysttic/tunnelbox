"use strict";

let token = sessionStorage.getItem("vpn_token");
let state = null;          // ostatni stan z /api/state
let pollTimer = null;
let editingId = null;      // id profilu w edytorze (null = nowy)
let editorReadOnly = false; // podgląd aktywnego połączenia — bez edycji/zapisu
const inflight = new Set(); // profile z trwającym connect/trust (blokada dwukliku)

const $ = (id) => document.getElementById(id);

// Etykieta stanu bierze się z katalogu tłumaczeń przy każdym renderze — dzięki temu
// zmiana języka nie wymaga przeładowania strony.
const STATUS = {
  disconnected:  { cls: "st-off" },
  connecting:    { cls: "st-wait" },
  connected:     { cls: "st-on" },
  disconnecting: { cls: "st-wait" },
  need_trust:    { cls: "st-warn" },
  error:         { cls: "st-err" },
};

// Nazwa pola w komunikacie walidacji — backend podaje nazwę techniczną.
const FIELD_KEYS = [
  "name", "host", "username", "password", "port", "ip", "remote_port",
  "local_port", "otp", "trusted_certs", "ipsec_psk", "ipsec_remote_ts",
];

// słowo w nazwie maszyny -> port usługi (auto-uzupełnianie, #4)
const SERVICE_PORTS = {
  rdp: 3389, pulpit: 3389, zdalny: 3389,
  ssh: 22, sftp: 22, vnc: 5900,
  http: 80, www: 80, https: 443,
  ftp: 21, smb: 445, telnet: 23,
  mysql: 3306, mariadb: 3306, postgres: 5432, postgresql: 5432,
  mssql: 1433, sql: 1433, winrm: 5985,
};
// port usługi -> rodzaj (menu akcji, #5)
const PORT_SERVICE = {
  3389: "rdp", 22: "ssh", 5900: "vnc", 80: "http", 443: "https",
  8080: "http", 8000: "http", 8443: "https",
  3306: "sql", 5432: "sql", 1433: "sql", 445: "smb", 21: "ftp", 23: "telnet",
};

// rodzaj usługi z NAZWY (priorytet) lub z portu — nazwa typu „Panel https" ma dać
// akcję „otwórz w przeglądarce" także na niestandardowym porcie
function detectService(fwd) {
  const label = (fwd.label || "").toLowerCase();
  if (/https/.test(label)) return "https";
  if (/http|www|strona|panel web/.test(label)) return "http";
  if (/rdp|pulpit/.test(label)) return "rdp";
  if (/ssh|sftp/.test(label)) return "ssh";
  if (/vnc/.test(label)) return "vnc";
  return PORT_SERVICE[fwd.remote_port];
}

// Każde przekierowanie ma własny adres pętli zwrotnej: 13391 -> 127.0.0.2,
// 13392 -> 127.0.0.3, ... Windows zapisuje poświadczenia RDP pod kluczem
// TERMSRV/<adres> BEZ portu, więc gdyby wszystkie maszyny siedziały na
// „localhost", dzieliłyby jeden wpis i nadpisywały się nawzajem.
// Przypisanie musi pokrywać się z mapowaniem portów w docker-compose.yml.
const LOOPBACK_FIRST = 2;

function localHost(localPort) {
  const min = (state && state.port_range && state.port_range[0]) || 13391;
  return `127.0.0.${localPort - min + LOOPBACK_FIRST}`;
}

function localAddr(localPort) {
  return `${localHost(localPort)}:${localPort}`;
}

// ustawienia panelu (z /api/state); domyślnie włączone, gdy stan jeszcze nie dotarł
const DEFAULT_SETTINGS = { fast_rdp: true, check_updates: true, lang: DEFAULT_LANG };

function settingEnabled(name) {
  return Boolean(settingValue(name));
}

function settingValue(name) {
  const s = (state && state.settings) || {};
  return name in s ? s[name] : DEFAULT_SETTINGS[name];
}

// --- API ---

function formatDetail(detail) {
  if (typeof detail === "string") return detail;
  // obiekt z kodem: backend dołącza go tam, gdzie panel ma rozpoznać konkretny przypadek
  if (detail && typeof detail === "object" && !Array.isArray(detail) && detail.message) {
    return detail.message;
  }
  if (Array.isArray(detail) && detail.length) {
    const first = detail[0];
    const loc = (first.loc || []).filter((x) => typeof x === "string");
    const field = loc[loc.length - 1];
    const label = FIELD_KEYS.includes(field) ? t(`field.${field}`) : (field || t("field.data"));
    return t("err.field", { field: label, message: first.msg || t("err.invalidValue") });
  }
  return t("err.generic");
}

async function api(path, method = "GET", body = null) {
  const res = await fetch("/api" + path, {
    method,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { "X-Auth": token } : {}),
    },
    body: body ? JSON.stringify(body) : null,
  });
  if (res.status === 401) {
    token = null;
    sessionStorage.removeItem("vpn_token");
    showAuth();
    throw new Error(t("err.locked"));
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = new Error(formatDetail(data.detail));
    // kod z backendu (np. "already_active") — treść komunikatu zależy od języka,
    // więc panel rozpoznaje przypadki po kodzie, a nie po tekście
    err.code = (data.detail && data.detail.code) || "";
    throw err;
  }
  return data;
}

// --- widoki ---

function show(view) {
  $("unlock-view").classList.toggle("hidden", view !== "auth");
  $("main-view").classList.toggle("hidden", view !== "main");
  $("lock-btn").classList.toggle("hidden", view !== "main");
  $("change-pass-btn").classList.toggle("hidden", view !== "main");
  $("settings-btn").classList.toggle("hidden", view !== "main");
}

async function showAuth() {
  clearInterval(pollTimer);
  closeMenu();
  $("editor").close();
  $("otp-dialog").close();
  $("change-pass-dialog").close();
  $("add-fwd-dialog").close();
  $("settings-dialog").close();
  $("import-dialog").close();
  hideToast();
  $("create-pass").value = "";
  $("create-pass2").value = "";
  $("unlock-pass").value = "";
  ["cp-current", "cp-new", "cp-new2"].forEach((id) => { $(id).value = ""; });
  show("auth");
  const status = await fetch("/api/vault").then((r) => r.json());
  $("auth-create").classList.toggle("hidden", status.exists);
  $("auth-unlock").classList.toggle("hidden", !status.exists);
  $("auth-error").classList.add("hidden");
  (status.exists ? $("unlock-pass") : $("create-pass")).focus();
}

function showMain() {
  show("main");
  refresh();
  loadUpdate();
  clearInterval(pollTimer);
  pollTimer = setInterval(refresh, 2000);
}

// Numer wersji w nagłówku. /api/vault jest publiczne, więc plakietka jest też
// na ekranie logowania — a brak numeru nie może wywrócić panelu.
async function loadVersion() {
  try {
    const { version } = await fetch("/api/vault").then((r) => r.json());
    if (version) $("app-version").textContent = `v${version}`;
  } catch (e) { /* trudno, panel działa dalej */ }
}

// Język zapisany jest w sejfie, więc dowiadujemy się o nim dopiero ze stanu panelu.
// setLang() odświeża teksty statyczne; dynamiczne odrysuje render() tuż poniżej.
function syncLang() {
  const wanted = state && state.settings && state.settings.lang;
  if (wanted && setLang(wanted) && updateInfo) renderUpdateBar();
}

async function refresh() {
  try {
    state = await api("/state");
    syncLang();
    render();
  } catch (e) {
    /* 401 obsłużone w api() */
  }
}

// --- renderowanie ---

function el(tag, cls, text) {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text !== undefined) node.textContent = text;
  return node;
}

function render() {
  const box = $("profiles");

  // #2 — zapamiętaj stan logów (otwarty + pozycja przewijania) przed przebudową
  const logState = {};
  for (const d of box.querySelectorAll("details")) {
    const pre = d.querySelector(".log");
    const atBottom = pre
      ? pre.scrollHeight - pre.scrollTop - pre.clientHeight < 8
      : true;
    logState[d.dataset.pid] = { open: d.open, top: pre ? pre.scrollTop : 0, atBottom };
  }

  box.innerHTML = "";
  $("empty-hint").classList.toggle("hidden", state.profiles.length > 0);
  for (const profile of state.profiles) {
    box.appendChild(renderCard(profile, logState[profile.id]));
  }

  // #2 — przywróć przewijanie: trzymaj się dołu (najnowsze), chyba że user odjechał w górę
  for (const d of box.querySelectorAll("details")) {
    const pre = d.querySelector(".log");
    if (!pre) continue;
    const s = logState[d.dataset.pid];
    pre.scrollTop = !s || s.atBottom ? pre.scrollHeight : s.top;
  }
}

function renderCard(profile, logSt) {
  const conn = state.connections[profile.id] || { state: "disconnected" };
  const stateName = STATUS[conn.state] ? conn.state : "disconnected";
  const st = STATUS[stateName];
  const active = ["connecting", "connected", "disconnecting"].includes(conn.state);
  const connected = conn.state === "connected";
  const aliveByPort = {};
  for (const f of conn.forwards || []) aliveByPort[f.local_port] = f.alive;

  const card = el("div", "card");

  const head = el("div", "card-head");
  const titleBox = el("div");
  titleBox.appendChild(el("div", "card-title", profile.name));
  const sub = el("div", "muted small", profile.host);
  // typ pokazujemy tylko przy IPsec — SSL-VPN jest domyślny i etykieta na każdej
  // karcie byłaby tylko szumem
  if (profile.vpn_type === "ipsec") sub.appendChild(el("span", "type-badge", "IPsec"));
  titleBox.appendChild(sub);
  head.appendChild(titleBox);
  head.appendChild(el("span", "status " + st.cls, t(`status.${stateName}`)));
  card.appendChild(head);

  if (conn.detail && ["error", "need_trust"].includes(conn.state)) {
    card.appendChild(el("p", "error", conn.detail));
  }

  // przekierowania
  if (profile.forwards.length) {
    const list = el("div", "forwards");
    for (const fwd of profile.forwards) {
      const row = el("div", "fwd-row" + (connected ? "" : " fwd-inactive"));
      row.appendChild(el("span", "fwd-label", fwd.label || fwd.ip));
      const addr = localAddr(fwd.local_port);
      if (connected) {
        const dead = aliveByPort[fwd.local_port] === false;
        row.appendChild(el("span", "fwd-addr" + (dead ? " fwd-dead" : ""), addr));
        if (dead) {
          row.appendChild(el("span", "fwd-warn", t("card.dead")));
        } else {
          const menuBtn = el("button", "btn btn-mini fwd-menu-btn", "⋮");
          menuBtn.title = t("card.menuHint");
          menuBtn.onclick = (e) => { e.stopPropagation(); openMenu(menuBtn, fwd, profile.name); };
          row.appendChild(menuBtn);
        }
      } else {
        row.appendChild(el("span", "fwd-addr", addr));
        row.appendChild(el("span", "muted small", t("card.afterConnect")));
      }
      list.appendChild(row);
    }
    card.appendChild(list);
  }

  // akcje
  const actions = el("div", "card-actions");
  if (conn.state === "need_trust") {
    const trust = el("button", "btn btn-warn", t("card.trust"));
    trust.disabled = inflight.has(profile.id);
    trust.onclick = () => trustAndConnect(profile);
    actions.appendChild(trust);
    const retry = el("button", "btn btn-ghost", t("card.retry"));
    retry.disabled = inflight.has(profile.id);
    retry.onclick = () => connectProfile(profile);
    actions.appendChild(retry);
  } else if (active) {
    const btn = el("button", "btn btn-danger", t("card.disconnect"));
    btn.disabled = conn.state === "disconnecting";
    btn.onclick = () => api(`/profiles/${profile.id}/disconnect`, "POST", {}).then(refresh);
    actions.appendChild(btn);
  } else {
    const btn = el("button", "btn btn-success", t("card.connect"));
    btn.disabled = inflight.has(profile.id);
    btn.onclick = () => connectProfile(profile);
    actions.appendChild(btn);
  }
  if (connected) {
    const addFwd = el("button", "btn btn-ghost", t("card.addMachine"));
    addFwd.title = t("card.addMachineHint");
    addFwd.onclick = () => openAddForward(profile);
    actions.appendChild(addFwd);
  }
  const edit = el("button", "btn btn-ghost", t(active ? "card.preview" : "card.edit"));
  edit.title = t(active ? "card.previewHint" : "card.editHint");
  edit.onclick = () => openEditor(profile, active);
  actions.appendChild(edit);
  const del = el("button", "btn btn-ghost", t("card.delete"));
  del.disabled = active;
  del.onclick = async () => {
    if (!confirm(t("card.confirmDelete", { name: profile.name }))) return;
    try { await api(`/profiles/${profile.id}`, "DELETE"); refresh(); }
    catch (e) { alert(e.message); }
  };
  actions.appendChild(del);
  card.appendChild(actions);

  // log
  if (conn.log && conn.log.length) {
    const details = el("details");
    details.dataset.pid = profile.id;
    if (logSt ? logSt.open : false) details.open = true;
    details.appendChild(el("summary", "muted small", t("card.showLog")));
    details.appendChild(el("pre", "log", conn.log.join("\n")));
    card.appendChild(details);
  }

  return card;
}

// --- menu akcji „3 kropki" (#5) ---

function rdpFileContent(port) {
  return [
    // własny adres na maszynę — patrz localHost(); dzięki temu Windows trzyma
    // osobne poświadczenia dla każdej maszyny zamiast jednego wpisu na localhost
    `full address:s:${localAddr(port)}`,
    // 0 = użyj zapisanych poświadczeń. Przy 1 mstsc pytał o dane nawet wtedy,
    // gdy były już zapamiętane.
    "prompt for credentials:i:0",
    "administrative session:i:0",
    "screen mode id:i:2",
    "use multimon:i:0",
  ].join("\r\n") + "\r\n";
}

function rdpFileName(fwd, profileName) {
  // „<połączenie> - <maszyna>" — kilka połączeń może mieć maszynę „Serwer RDP"
  const parts = [profileName, fwd.label].filter((x) => x && x.trim());
  return (parts.join(" - ") || `maszyna-${fwd.local_port}`)
    .replace(/[\\/:*?"<>|]+/g, "-")
    .trim();
}

// Szybkie łączenie: lokalny helper (packaging/rdp-launcher.ps1) uruchamia pulpit
// zdalny wprost adresem (mstsc /v:). Bez pliku .rdp, bo Windows od aktualizacji
// z kwietnia 2026 ostrzega przed każdym otwarciem niepodpisanego pliku .rdp.
function rdpProtocolUrl(fwd, profileName) {
  const q = new URLSearchParams({
    host: localHost(fwd.local_port),
    port: String(fwd.local_port),
    name: rdpFileName(fwd, profileName),
  });
  return `tunnelbox-rdp://connect?${q.toString()}`;
}

function showToast(title, text, actions = []) {
  const box = $("toast");
  box.innerHTML = "";
  box.appendChild(el("div", "toast-title", title));
  box.appendChild(el("div", "toast-text", text));
  const row = el("div", "toast-actions");
  for (const a of actions) {
    const btn = el("button", a.primary ? "btn btn-mini btn-primary" : "btn btn-mini btn-ghost", a.label);
    btn.onclick = () => { hideToast(); a.fn(); };
    row.appendChild(btn);
  }
  const close = el("button", "btn btn-mini btn-ghost", t("toast.close"));
  close.onclick = hideToast;
  row.appendChild(close);
  box.appendChild(row);
  box.classList.remove("hidden");
  clearTimeout(showToast._t);
  showToast._t = setTimeout(hideToast, 20000);
}

function hideToast() {
  clearTimeout(showToast._t);
  $("toast").classList.add("hidden");
}

// Zabezpieczenie: gdy protokół tunnelbox-rdp:// nie jest zarejestrowany, przeglądarka
// po cichu ignoruje kliknięcie. Jeśli po chwili nadal mamy fokus (pulpit zdalny by go
// zabrał), podpowiadamy co zrobić i dajemy pobranie pliku od ręki.
function scheduleRdpFallbackHint(fwd, profileName, delay = 1800) {
  clearTimeout(scheduleRdpFallbackHint._t);
  scheduleRdpFallbackHint._t = setTimeout(() => {
    if (!document.hasFocus()) return;   // coś przejęło fokus — pulpit zdalny wystartował
    // instalacja z rejestru nie ma start.bat, który zarejestrowałby protokół; sposób
    // instalacji bierzemy ze stanu (wczytany zawsze), a /api/update jest zapasem
    const install = (state && state.install) || (updateInfo && updateInfo.install);
    const registry = install === "registry";
    showToast(
      t("rdp.failedTitle"),
      t(registry ? "rdp.failedTextRegistry" : "rdp.failedText"),
      [
        { label: t("rdp.download"), primary: true, fn: () => downloadRdp(fwd, profileName) },
        { label: t("rdp.settings"), fn: () => $("settings-btn").click() },
      ],
    );
  }, delay);
}

function connectRdp(fwd, profileName) {
  location.href = rdpProtocolUrl(fwd, profileName);
  scheduleRdpFallbackHint(fwd, profileName);
}

function downloadRdp(fwd, profileName) {
  const base = rdpFileName(fwd, profileName);
  const blob = new Blob([rdpFileContent(fwd.local_port)], { type: "application/x-rdp" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `${base}.rdp`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 2000);
}

// --- aktualizacje ---

// Ostatnia odpowiedź /api/update. null = nie wiemy (np. sejf zablokowany).
let updateInfo = null;

const isWindows = () =>
  /win/i.test(
    (navigator.userAgentData && navigator.userAgentData.platform) || navigator.platform || "",
  );

function formatSize(bytes) {
  if (!bytes) return "";
  const mb = bytes / (1024 * 1024);
  return mb >= 1 ? `${mb.toFixed(mb < 10 ? 1 : 0)} MB` : `${Math.round(bytes / 1024)} kB`;
}

function formatDate(iso) {
  const d = new Date(iso);
  return Number.isNaN(d.getTime())
    ? ""
    : d.toLocaleDateString(localeTag(), { year: "numeric", month: "short", day: "numeric" });
}

// Sprawdzenie wersji nie może wywrócić panelu — gdy się nie uda, paska po prostu nie ma.
async function loadUpdate(force = false) {
  try {
    updateInfo = force ? await api("/update/check", "POST") : await api("/update");
  } catch (e) {
    updateInfo = null;
  }
  renderUpdateBar();
  return updateInfo;
}

function renderUpdateBar() {
  const info = updateInfo;
  const skipped = sessionStorage.getItem("vpn_update_skip");
  const visible = Boolean(info && info.available && info.latest && skipped !== info.latest);
  $("update-bar").classList.toggle("hidden", !visible);
  if (!visible) return;

  $("update-title").textContent = t("update.available", { version: info.latest });
  const bits = [t("update.haveVersion", { version: info.current })];
  if (info.published_at) bits.push(t("update.released", { date: formatDate(info.published_at) }));
  if (info.size) bits.push(formatSize(info.size));
  $("update-note").textContent = bits.filter(Boolean).join(" · ");

  // Instalacja z rejestru (docker-compose.yml z obrazem ghcr.io): paczka ani instalator
  // nic tu nie dadzą — nowy obraz ściąga „docker compose pull”, więc zamiast przycisków
  // pokazujemy to polecenie.
  const registry = info.install === "registry";
  $("update-registry").classList.toggle("hidden", !registry);

  // Aktualizacja jednym kliknięciem to helper dla Windows — gdzie indziej zostaje
  // pobranie paczki i ręczne rozpakowanie (start.sh zrobi resztę tak samo).
  $("update-install").classList.toggle("hidden", registry || !isWindows());
  const download = $("update-download");
  download.href = info.download || info.page;
  download.classList.toggle("hidden", registry || !info.download);
  $("update-page").href = info.page;
}

// Aktualizacja jednym kliknięciem: lokalny helper (packaging/update-launcher.ps1)
// pobiera paczkę ze strony wydań, rozpakowuje i uruchamia — czyli robi dokładnie to,
// co użytkownik robi ręcznie. Przekazujemy sam numer wersji: adres pliku helper
// ustala sam, więc ze strony nie da się mu podstawić czegokolwiek do pobrania.
function updateProtocolUrl(version) {
  return `tunnelbox-update://install?version=${encodeURIComponent(version)}`;
}

function installUpdate() {
  if (!updateInfo || !updateInfo.latest) return;
  location.href = updateProtocolUrl(updateInfo.latest);
  showToast(
    t("update.startedTitle"),
    t("update.startedText"),
  );
  scheduleUpdateFallbackHint();
}

// To samo zabezpieczenie co przy RDP: gdy protokół nie jest zarejestrowany,
// przeglądarka ignoruje kliknięcie po cichu.
function scheduleUpdateFallbackHint(delay = 2500) {
  clearTimeout(scheduleUpdateFallbackHint._t);
  scheduleUpdateFallbackHint._t = setTimeout(() => {
    if (!document.hasFocus()) return;   // instalator wystartował i zabrał fokus
    showToast(
      t("update.failedTitle"),
      t("update.failedText"),
      [{ label: t("update.download"), primary: true, fn: () => $("update-download").click() }],
    );
  }, delay);
}

async function checkUpdatesNow() {
  const btn = $("settings-check-now");
  const hint = $("settings-update-info");
  btn.disabled = true;
  hint.textContent = t("update.checking");
  try {
    const info = await loadUpdate(true);
    if (!info) hint.textContent = t("update.checkFailed");
    else if (!info.enabled) hint.textContent = t("update.disabled");
    else if (!info.ok) hint.textContent = t("update.offline");
    else if (info.available) hint.textContent = t("update.foundNewer", { version: info.latest });
    else hint.textContent = t("update.upToDate", { version: info.current });
  } finally {
    btn.disabled = false;
  }
}

function commandFor(fwd) {
  const svc = detectService(fwd);
  const p = fwd.local_port;
  if (svc === "rdp") return `mstsc /v:${localAddr(p)}`;
  if (svc === "ssh") return `ssh -p ${p} ${t("menu.sshUser")}@${localHost(p)}`;
  return localAddr(p);
}

function serviceActions(fwd, profileName) {
  const addr = localAddr(fwd.local_port);
  const svc = detectService(fwd);
  const actions = [];
  if (svc === "rdp") {
    // o tym, który przycisk widzi użytkownik, decyduje ustawienie panelu
    if (settingEnabled("fast_rdp")) {
      actions.push({ label: t("menu.rdpConnect"), fn: () => connectRdp(fwd, profileName) });
    } else {
      actions.push({ label: t("menu.rdpDownload"), fn: () => downloadRdp(fwd, profileName) });
    }
  } else if (svc === "ssh") {
    actions.push({ label: t("menu.ssh"), fn: () => { location.href = `ssh://${addr}`; } });
  } else if (svc === "vnc") {
    actions.push({ label: t("menu.vnc"), fn: () => { location.href = `vnc://${addr}`; } });
  } else if (svc === "http") {
    actions.push({ label: t("menu.browser"), fn: () => window.open(`http://${addr}`, "_blank") });
  } else if (svc === "https") {
    actions.push({ label: t("menu.browser"), fn: () => window.open(`https://${addr}`, "_blank") });
  }
  actions.push({ label: t("menu.copyAddr"), fn: () => navigator.clipboard.writeText(addr) });
  actions.push({ label: t("menu.copyCmd"), fn: () => navigator.clipboard.writeText(commandFor(fwd)) });
  return actions;
}

function openMenu(btn, fwd, profileName) {
  const menu = $("action-menu");
  menu.innerHTML = "";
  const head = [profileName, fwd.label || localAddr(fwd.local_port)].filter(Boolean).join(" — ");
  menu.appendChild(el("div", "menu-head", head));
  for (const a of serviceActions(fwd, profileName)) {
    const item = el("button", "menu-item", a.label);
    item.onclick = () => { try { a.fn(); } catch (e) { /* ignoruj */ } closeMenu(); };
    menu.appendChild(item);
  }
  menu.classList.remove("hidden");
  const r = btn.getBoundingClientRect();
  const w = menu.offsetWidth || 240;
  let left = r.right + window.scrollX - w;
  if (left < 8) left = 8;
  menu.style.top = `${r.bottom + window.scrollY + 4}px`;
  menu.style.left = `${left}px`;
}

function closeMenu() {
  $("action-menu").classList.add("hidden");
}

// --- łączenie ---

function profileTokenMode(p) {
  if (["none", "code", "push"].includes(p.token_mode)) return p.token_mode;
  return p.requires_token ? "code" : "none";
}

function connectProfile(profile) {
  if (inflight.has(profile.id)) return;
  const mode = profileTokenMode(profile);
  if (mode === "code") {
    $("otp-hint").textContent =
      t("otp.hint", { name: profile.name });
    $("otp-error").classList.add("hidden");
    $("otp-input").value = "";
    const dialog = $("otp-dialog");
    dialog.dataset.pid = profile.id;
    dialog.showModal();
    $("otp-input").focus();
  } else {
    // push: openfortivpn wyśle powiadomienie do aplikacji — zatwierdź na telefonie
    doConnect(profile.id, null);
  }
}

async function doConnect(profileId, otp) {
  if (inflight.has(profileId)) return;
  inflight.add(profileId);
  render();
  try {
    await api(`/profiles/${profileId}/connect`, "POST", { otp });
  } catch (e) {
    if (e.code !== "already_active") alert(e.message);
  } finally {
    inflight.delete(profileId);
    await refresh();
  }
}

async function trustAndConnect(profile) {
  if (inflight.has(profile.id)) return;
  inflight.add(profile.id);
  render();
  try {
    await api(`/profiles/${profile.id}/trust`, "POST", {});
  } catch (e) {
    inflight.delete(profile.id);
    await refresh();
    alert(e.message);
    return;
  }
  inflight.delete(profile.id);
  await refresh();
  connectProfile(profile);
}

// --- dokładanie maszyny do działającego połączenia ---

function openAddForward(profile) {
  const d = $("add-fwd-dialog");
  d.dataset.pid = profile.id;
  $("af-hint").textContent = t("addFwd.hint", { name: profile.name });
  $("af-label").value = "";
  $("af-ip").value = "";
  $("af-rport").value = "";
  delete $("af-rport").dataset.auto;
  $("af-error").classList.add("hidden");
  d.showModal();
  $("af-label").focus();
}

async function submitAddForward(event) {
  event.preventDefault();
  const err = $("af-error");
  const showErr = (m) => { err.textContent = m; err.classList.remove("hidden"); };
  const label = $("af-label").value.trim();
  const ip = $("af-ip").value.trim();
  const rportRaw = $("af-rport").value.trim();
  if (!ip || !rportRaw) return showErr(t("addFwd.needIpPort"));
  const rport = parseInt(rportRaw, 10);
  if (Number.isNaN(rport) || rport < 1 || rport > 65535) {
    return showErr(t("addFwd.badPort"));
  }
  const pid = $("add-fwd-dialog").dataset.pid;
  try {
    await api(`/profiles/${pid}/forwards`, "POST",
              { label, ip, remote_port: rport, local_port: null });
    $("add-fwd-dialog").close();
    await refresh();
  } catch (e) {
    showErr(e.message);
  }
}

// --- edytor profilu ---

function forwardRow(fwd = {}) {
  const row = el("div", "fwd-edit");
  const fields = el("div", "fwd-fields");

  const field = (labelText, cls, inputCls, ph, val, type = "text") => {
    const wrap = el("label", cls, labelText);
    const input = el("input", inputCls);
    input.placeholder = ph;
    input.value = val ?? "";
    input.type = type;
    wrap.appendChild(input);
    return wrap;
  };

  const name = field(t("editor.machineName"), "grow", "f-label",
                     t("editor.machineNamePh"), fwd.label);
  const ip = field(t("editor.machineIp"), "grow", "f-ip",
                   t("editor.machineIpPh"), fwd.ip);
  const port = field(t("editor.machinePort"), "w-port", "f-rport",
                     t("editor.machinePortPh"), fwd.remote_port, "number");

  const nameInput = name.querySelector(".f-label");
  const portInput = port.querySelector(".f-rport");
  portInput.min = "1"; portInput.max = "65535"; portInput.step = "1";
  portInput.inputMode = "numeric";
  portInput.addEventListener("input", () => {
    let v = portInput.value.replace(/[^\d]/g, "");
    if (v !== "") v = String(Math.min(parseInt(v, 10), 65535));
    portInput.value = v;
    portInput.dataset.auto = "";  // ręczna zmiana kasuje auto
  });

  // #4 — auto-uzupełnij port usługi na podstawie nazwy maszyny
  nameInput.addEventListener("input", () => {
    const manual = portInput.value.trim() && portInput.dataset.auto !== "1";
    if (manual) return;
    const words = (nameInput.value.toLowerCase().match(/[a-ząćęłńóśźż]+/g) || []);
    for (const w of words) {
      if (SERVICE_PORTS[w]) {
        portInput.value = SERVICE_PORTS[w];
        portInput.dataset.auto = "1";
        return;
      }
    }
  });

  const rm = el("button", "btn btn-mini btn-ghost fwd-remove", `✕ ${t("editor.remove")}`);
  rm.type = "button";
  rm.onclick = () => row.remove();

  fields.append(name, ip, port, rm);
  row.appendChild(fields);
  row.appendChild(el("p", "hint", t("editor.portsHint")));
  return row;
}

function setEditorReadOnly(ro) {
  editorReadOnly = ro;
  const form = $("editor-form");
  form.querySelectorAll("input, select, textarea, .fwd-remove, #add-forward")
    .forEach((elm) => { elm.disabled = ro; });
  $("editor-save").classList.toggle("hidden", ro);
  $("editor-cancel").textContent = t(ro ? "editor.close" : "editor.cancel");
  $("editor-readonly-note").classList.toggle("hidden", !ro);
}

// Formularz jest wspólny dla obu typów tuneli — pokazujemy tylko te pola, które
// naprawdę dotyczą wybranego połączenia, żeby nie straszyć IPsec-iem kogoś, kto
// wpisuje zwykły SSL-VPN.
function updateVpnTypeUi() {
  const ipsec = $("f-vpn-type").value === "ipsec";
  const auth = $("f-ipsec-auth").value;
  // login i hasło są potrzebne zawsze poza IPsec-em na sam klucz PSK
  const needsCreds = !ipsec || auth === "ikev1-psk-xauth";
  $("ipsec-fields").classList.toggle("hidden", !ipsec);
  $("f-port-wrap").classList.toggle("hidden", ipsec);
  $("f-realm-wrap").classList.toggle("hidden", ipsec);
  $("f-aggressive-wrap").classList.toggle("hidden", !auth.startsWith("ikev1"));
  $("creds-row").classList.toggle("hidden", !needsCreds);
  $("token-block").classList.toggle("hidden", !needsCreds);
  $("f-username").required = needsCreds;
  $("f-password").required = needsCreds;
  // IPsec nie zna zatwierdzania na telefonie — zostaje kod jednorazowy albo brak tokena
  $("token-push-wrap").classList.toggle("hidden", ipsec);
  const radios = [...document.getElementsByName("token-mode")];
  if (ipsec && radios.find((r) => r.value === "push")?.checked) {
    radios.find((r) => r.value === "code").checked = true;
  }
}

function openEditor(profile, readOnly = false) {
  editingId = profile ? profile.id : null;
  $("editor-title").textContent = readOnly
    ? t("editor.titleView")
    : t(profile ? "editor.titleEdit" : "editor.titleNew");
  $("f-name").value = profile?.name || "";
  $("f-vpn-type").value = profile?.vpn_type === "ipsec" ? "ipsec" : "ssl";
  $("f-host").value = profile?.host || "";
  $("f-port").value = profile?.port || 443;
  $("f-realm").value = profile?.realm || "";
  $("f-username").value = profile?.username || "";
  $("f-password").value = profile?.password || "";

  const auth = profile?.ipsec_auth || "";
  $("f-ipsec-auth").value =
    [...$("f-ipsec-auth").options].some((o) => o.value === auth) ? auth : "ikev1-psk-xauth";
  $("f-ipsec-psk").value = profile?.ipsec_psk || "";
  $("f-ipsec-local-id").value = profile?.ipsec_local_id || "";
  $("f-ipsec-remote-id").value = profile?.ipsec_remote_id || "";
  $("f-ipsec-remote-ts").value = profile?.ipsec_remote_ts || "";
  $("f-ipsec-aggressive").checked = !!profile?.ipsec_aggressive;

  const mode = profile ? profileTokenMode(profile) : "none";
  $("f-token").checked = mode !== "none";
  $("token-modes").classList.toggle("hidden", mode === "none");
  for (const r of document.getElementsByName("token-mode")) {
    r.checked = r.value === (mode === "push" ? "push" : "code");
  }

  $("editor").dataset.certs = JSON.stringify(profile?.trusted_certs || []);
  const box = $("forwards");
  box.innerHTML = "";
  for (const fwd of profile?.forwards || []) box.appendChild(forwardRow(fwd));
  if (!profile) box.appendChild(forwardRow());
  $("editor-error").classList.add("hidden");
  updateVpnTypeUi();            // przed blokadą pól — decyduje, co w ogóle widać
  setEditorReadOnly(readOnly);  // po zbudowaniu wierszy — obejmuje też ich pola
  $("editor").showModal();
}

function editorError(msg) {
  const err = $("editor-error");
  err.textContent = msg;
  err.classList.remove("hidden");
}

// rozkłada wklejony adres bramy (np. https://vpn.klient.pl:443/myrealm) na części
function parseGateway(raw) {
  let s = raw.trim().replace(/^[a-zA-Z][\w+.-]*:\/\//, ""); // usuń schemat (https://)
  let realm = "";
  const slash = s.indexOf("/");
  if (slash >= 0) { realm = s.slice(slash + 1).replace(/\/+$/, ""); s = s.slice(0, slash); }
  let port = "";
  const colon = s.indexOf(":");
  if (colon >= 0) { port = s.slice(colon + 1).replace(/[^\d]/g, ""); s = s.slice(0, colon); }
  return { host: s, port, realm };
}

// gdy user wklei pełny adres w pole „Adres serwera", rozłóż go na host/port/realm
function splitGatewayField() {
  const raw = $("f-host").value;
  if (!/[:/]/.test(raw)) return; // zwykła nazwa hosta — nie ruszaj
  const g = parseGateway(raw);
  $("f-host").value = g.host;
  if (g.port) $("f-port").value = g.port;
  if (g.realm) $("f-realm").value = g.realm;
}

async function saveProfile(event) {
  event.preventDefault();
  if (editorReadOnly) return;  // podgląd aktywnego połączenia — nie zapisujemy
  splitGatewayField();  // gdyby user wkleił pełny adres i od razu zapisał
  const forwards = [];
  let rowNum = 0;
  for (const row of $("forwards").querySelectorAll(".fwd-edit")) {
    rowNum++;
    const label = row.querySelector(".f-label").value.trim();
    const ip = row.querySelector(".f-ip").value.trim();
    const rportRaw = row.querySelector(".f-rport").value.trim();
    if (!label && !ip && !rportRaw) continue; // pusty wiersz
    if (!ip || !rportRaw) {
      return editorError(t("editor.needIpPort", { row: rowNum }));
    }
    const rport = parseInt(rportRaw, 10);
    if (Number.isNaN(rport) || rport < 1 || rport > 65535) {
      return editorError(t("editor.badRowPort", { row: rowNum }));
    }
    forwards.push({ label, ip, remote_port: rport, local_port: null });
  }

  const isIpsec = $("f-vpn-type").value === "ipsec";
  if (isIpsec && !$("f-ipsec-psk").value) {
    return editorError(t("editor.needPsk"));
  }

  let tokenMode = "none";
  // gdy blok tokena jest ukryty (IPsec na sam klucz PSK), nie ma go gdzie wpisać
  if (!$("token-block").classList.contains("hidden") && $("f-token").checked) {
    const sel = [...document.getElementsByName("token-mode")].find((r) => r.checked);
    tokenMode = sel ? sel.value : "code";
  }

  const body = {
    name: $("f-name").value.trim(),
    vpn_type: isIpsec ? "ipsec" : "ssl",
    host: $("f-host").value.trim(),
    port: parseInt($("f-port").value, 10) || 443,
    realm: $("f-realm").value.trim(),
    username: $("f-username").value.trim(),
    password: $("f-password").value,
    token_mode: tokenMode,
    trusted_certs: JSON.parse($("editor").dataset.certs || "[]"),
    forwards,
    ipsec_auth: $("f-ipsec-auth").value,
    ipsec_psk: $("f-ipsec-psk").value,
    ipsec_local_id: $("f-ipsec-local-id").value.trim(),
    ipsec_remote_id: $("f-ipsec-remote-id").value.trim(),
    ipsec_remote_ts: $("f-ipsec-remote-ts").value.trim(),
    ipsec_aggressive: $("f-ipsec-aggressive").checked,
  };
  try {
    if (editingId) await api(`/profiles/${editingId}`, "PUT", body);
    else await api("/profiles", "POST", body);
    $("editor").close();
    refresh();
  } catch (e) {
    editorError(e.message);
  }
}

// --- autoryzacja ---

async function createVault() {
  const pass = $("create-pass").value;
  const err = $("auth-error");
  if (pass.length < 4) {
    err.textContent = t("auth.passTooShort");
    err.classList.remove("hidden");
    return;
  }
  if (pass !== $("create-pass2").value) {
    err.textContent = t("auth.passMismatch");
    err.classList.remove("hidden");
    return;
  }
  try {
    const res = await api("/vault/create", "POST", { password: pass });
    token = res.token;
    sessionStorage.setItem("vpn_token", token);
    $("create-pass").value = "";
    $("create-pass2").value = "";
    showMain();
  } catch (e) {
    err.textContent = e.message;
    err.classList.remove("hidden");
  }
}

async function unlockVault() {
  const err = $("auth-error");
  const pass = $("unlock-pass").value;
  if (pass.length < 4) {
    err.textContent = t("auth.passTooShort");
    err.classList.remove("hidden");
    return;
  }
  try {
    const res = await api("/vault/unlock", "POST", { password: pass });
    token = res.token;
    sessionStorage.setItem("vpn_token", token);
    $("unlock-pass").value = "";
    showMain();
  } catch (e) {
    err.textContent = e.message;
    err.classList.remove("hidden");
  }
}

// --- eksport / import pliku konfiguracji ---

function exportConfig() {
  // serwer ustawia nazwę pliku w Content-Disposition
  const a = document.createElement("a");
  a.href = "/api/vault/export";
  a.download = "";
  document.body.appendChild(a);
  a.click();
  a.remove();
}

function openImportDialog() {
  $("imp-file").value = "";
  $("imp-pass").value = "";
  $("imp-error").classList.add("hidden");
  $("import-dialog").showModal();
}

function readFileAsBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(",", 2)[1] || "");
    reader.onerror = () => reject(new Error(t("import.readFailed")));
    reader.readAsDataURL(file);
  });
}

async function submitImport(event) {
  event.preventDefault();
  const err = $("imp-error");
  const showErr = (m) => { err.textContent = m; err.classList.remove("hidden"); };
  const file = $("imp-file").files[0];
  const pass = $("imp-pass").value;
  if (!file) return showErr(t("import.needFile"));
  if (!pass) return showErr(t("import.needPass"));
  try {
    const data = await readFileAsBase64(file);
    const res = await api("/vault/import", "POST", { data, password: pass });
    token = res.token;
    sessionStorage.setItem("vpn_token", token);
    $("import-dialog").close();
    $("settings-dialog").close();
    $("imp-pass").value = "";
    showMain();
  } catch (e) {
    showErr(e.message);
  }
}

// --- blokada panelu ---

// Blokuje dostęp do konfiguracji. Aktywne tunele VPN działają dalej — blokujemy
// panel, nie połączenia. Czyścimy też stan i DOM, żeby powrót „wstecz"
// (bfcache) nie pokazał zapamiętanej listy połączeń.
async function lockPanel() {
  try { await api("/vault/lock", "POST", {}); } catch (e) { /* i tak blokujemy */ }
  token = null;
  sessionStorage.removeItem("vpn_token");
  state = null;
  $("profiles").innerHTML = "";
  showAuth();
}

// Po powrocie „wstecz/dalej" strona bywa przywracana z pamięci razem z DOM-em
// i zmiennymi — dlatego przy każdym takim pokazaniu weryfikujemy sesję na serwerze.
async function verifySession() {
  if (!token) { showAuth(); return; }
  try {
    state = await api("/state");
    render();
  } catch (e) {
    /* api() przy 401 samo pokaże ekran logowania */
  }
}

// --- podgląd hasła ---

function wireToggle(btn) {
  btn.addEventListener("click", () => {
    const input = $(btn.dataset.target);
    const showing = input.type === "text";
    input.type = showing ? "password" : "text";
    btn.textContent = showing ? "👁" : "🙈";
    btn.setAttribute("aria-label", t(showing ? "auth.showPass" : "auth.hidePass"));
  });
}

// --- start ---

document.addEventListener("DOMContentLoaded", () => {
  $("create-btn").onclick = createVault;
  $("unlock-btn").onclick = unlockVault;
  $("create-pass2").addEventListener("keydown", (e) => e.key === "Enter" && createVault());
  $("unlock-pass").addEventListener("keydown", (e) => e.key === "Enter" && unlockVault());
  document.querySelectorAll(".pass-toggle").forEach(wireToggle);

  $("f-vpn-type").addEventListener("change", updateVpnTypeUi);
  $("f-ipsec-auth").addEventListener("change", updateVpnTypeUi);
  $("f-token").addEventListener("change", () => {
    $("token-modes").classList.toggle("hidden", !$("f-token").checked);
  });
  $("f-host").addEventListener("blur", splitGatewayField);

  $("lock-btn").onclick = lockPanel;

  $("auth-export").onclick = exportConfig;
  $("auth-import").onclick = openImportDialog;
  $("update-install").onclick = installUpdate;
  $("update-later").onclick = () => {
    // „Później" chowa pasek do końca sesji przeglądarki — nowa wersja pokaże go znowu
    if (updateInfo && updateInfo.latest) {
      sessionStorage.setItem("vpn_update_skip", updateInfo.latest);
    }
    renderUpdateBar();
  };
  $("settings-check-now").onclick = checkUpdatesNow;

  $("settings-export").onclick = exportConfig;
  $("settings-import").onclick = () => { $("settings-dialog").close(); openImportDialog(); };
  $("import-form").addEventListener("submit", submitImport);
  $("imp-cancel").onclick = () => $("import-dialog").close();

  // „wstecz/dalej" może przywrócić stronę z pamięci (bfcache) razem z widokiem
  // sprzed blokady — wtedy sprawdzamy sesję na serwerze i wracamy do logowania.
  window.addEventListener("pageshow", (e) => { if (e.persisted) verifySession(); });
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible" && !document.getElementById("main-view").classList.contains("hidden")) {
      verifySession();
    }
  });

  $("settings-btn").onclick = () => {
    $("set-lang").value = settingValue("lang");
    $("set-fast-rdp").checked = settingEnabled("fast_rdp");
    $("set-check-updates").checked = settingEnabled("check_updates");
    $("settings-update-info").textContent = "";
    $("settings-error").classList.add("hidden");
    $("settings-dialog").showModal();
  };
  $("settings-cancel").onclick = () => $("settings-dialog").close();
  $("settings-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      await api("/settings", "PUT", {
        lang: $("set-lang").value,
        fast_rdp: $("set-fast-rdp").checked,
        check_updates: $("set-check-updates").checked,
      });
      $("settings-dialog").close();
      await refresh();
      await loadUpdate();
    } catch (e2) {
      const err = $("settings-error");
      err.textContent = e2.message;
      err.classList.remove("hidden");
    }
  });

  $("change-pass-btn").onclick = () => {
    ["cp-current", "cp-new", "cp-new2"].forEach((id) => { $(id).value = ""; });
    $("cp-error").classList.add("hidden");
    $("change-pass-dialog").showModal();
    $("cp-current").focus();
  };
  $("cp-cancel").onclick = () => $("change-pass-dialog").close();
  $("change-pass-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const cur = $("cp-current").value;
    const nw = $("cp-new").value;
    const nw2 = $("cp-new2").value;
    const err = $("cp-error");
    const showErr = (m) => { err.textContent = m; err.classList.remove("hidden"); };
    if (!cur) return showErr(t("changePass.needCurrent"));
    if (nw.length < 4) return showErr(t("auth.passTooShort"));
    if (nw !== nw2) return showErr(t("auth.passMismatch"));
    try {
      await api("/vault/change-password", "POST", { current: cur, new: nw });
      $("change-pass-dialog").close();
      ["cp-current", "cp-new", "cp-new2"].forEach((id) => { $(id).value = ""; });
      alert(t("changePass.done"));
    } catch (e2) {
      showErr(e2.message);
    }
  });

  $("add-fwd-form").addEventListener("submit", submitAddForward);
  $("af-cancel").onclick = () => $("add-fwd-dialog").close();
  // auto-uzupełnianie portu z nazwy, jak w edytorze profilu
  $("af-label").addEventListener("input", () => {
    const portInput = $("af-rport");
    if (portInput.value.trim() && portInput.dataset.auto !== "1") return;
    const words = ($("af-label").value.toLowerCase().match(/[a-ząćęłńóśźż]+/g) || []);
    for (const w of words) {
      if (SERVICE_PORTS[w]) {
        portInput.value = SERVICE_PORTS[w];
        portInput.dataset.auto = "1";
        return;
      }
    }
  });
  $("af-rport").addEventListener("input", () => { $("af-rport").dataset.auto = ""; });

  $("add-btn").onclick = () => openEditor(null);
  $("add-forward").onclick = () => $("forwards").appendChild(forwardRow());
  $("editor-form").addEventListener("submit", saveProfile);
  $("editor-cancel").onclick = () => $("editor").close();

  $("otp-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const otp = $("otp-input").value.trim();
    if (!otp) {
      $("otp-error").textContent = t("otp.missing");
      $("otp-error").classList.remove("hidden");
      return;
    }
    const dialog = $("otp-dialog");
    dialog.close();
    doConnect(dialog.dataset.pid, otp);
  });
  $("otp-cancel").onclick = () => $("otp-dialog").close();

  // zamknij menu akcji klikiem poza nim / klawiszem Esc
  document.addEventListener("click", (e) => {
    if (!e.target.closest(".fwd-menu-btn") && !e.target.closest("#action-menu")) closeMenu();
  });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeMenu(); });

  applyTranslations();
  loadVersion();

  if (token) {
    api("/state")
      .then((s) => { state = s; showMain(); })
      .catch(() => {});
  } else {
    showAuth();
  }
});
