#include "telegram.h"

#include <ArduinoJson.h>
#include <ESP8266WiFi.h>
#include <WiFiClientSecureBearSSL.h>

#include "network.h"
#include "relay.h"
#include "scheduler.h"
#include "settings.h"
#include "telegram_ca.h"

namespace {
constexpr const char* HOST = "api.telegram.org";
constexpr size_t MAX_RESPONSE = 6144;         // larger replies are skipped (see readResponse)
// Heap used by a TLS connection besides its buffers: BearSSL stack (6.2 kB), client and
// X.509 contexts (~7 kB) and some margin for the rest of the firmware.
constexpr uint32_t TLS_OVERHEAD = 15000;
constexpr uint32_t REQUEST_TIMEOUT_MS = 15000;
constexpr uint8_t QUEUE_SIZE = 6;

BearSSL::WiFiClientSecure client;
BearSSL::X509List* anchors = nullptr;
BearSSL::Session session;  // TLS session resumption: faster reconnects
int8_t smallFragments = -1;  // -1 unknown; 1 if the server accepts 1 kB TLS records (saves 15 kB)

enum class Req : uint8_t { None, GetMe, SetCommands, Updates, Send };
Req inFlight = Req::None;
uint32_t deadline = 0;
String resp;
bool respOverflow = false;

int64_t offset = 0;          // next update_id to fetch
bool haveMe = false;         // getMe answered: the token is valid
bool commandsSet = false;    // command menu sent once per boot
bool bootNotified = false;
bool restartAfterAck = false;
bool tokenRejected = false;
uint32_t retryAt = 0;
uint32_t backoff = 0;
bool lastOn = false;
String bot, error;

struct Out {
  int64_t chat = 0;
  String text;
  bool keyboard = false;
};
Out queue[QUEUE_SIZE];
uint8_t qHead = 0, qLen = 0;

// ---------------------------------------------------------------- helpers
String i64(int64_t v) {
  char buf[24];
  char* p = buf + sizeof(buf) - 1;
  *p = 0;
  bool neg = v < 0;
  uint64_t u = neg ? -static_cast<uint64_t>(v) : static_cast<uint64_t>(v);
  do {
    *--p = '0' + u % 10;
    u /= 10;
  } while (u);
  if (neg) *--p = '-';
  return String(p);
}

bool reached(uint32_t t) { return static_cast<int32_t>(millis() - t) >= 0; }

String fmtDur(uint32_t s) {
  uint32_t d = s / 86400, h = s % 86400 / 3600, m = s % 3600 / 60, x = s % 60;
  String out;
  auto add = [&out](uint32_t v, const char* unit) {
    if (out.length()) out += ' ';
    out += v;
    out += ' ';
    out += unit;
  };
  if (d) add(d, "d");
  if (h) add(h, "h");
  if (m && !d) add(m, "min");
  if ((x && !d && !h) || !out.length()) add(x, "s");
  return out;
}

// "45s", "30m", "2h", "1h30m", "1d"; a bare number means minutes.
bool parseDuration(const char* s, uint32_t& out) {
  uint64_t total = 0;
  bool any = false;
  while (*s) {
    if (!isdigit(static_cast<unsigned char>(*s))) return false;
    uint64_t v = 0;
    while (isdigit(static_cast<unsigned char>(*s))) {
      v = v * 10 + (*s++ - '0');
      if (v > 1000000) return false;
    }
    uint32_t mult = 60;
    if (*s == 'd') mult = 86400, s++;
    else if (*s == 'h') mult = 3600, s++;
    else if (*s == 'm') {
      s++;
      if (!strncmp(s, "in", 2)) s += 2;
    } else if (*s == 's') mult = 1, s++;
    else if (*s) return false;
    total += v * mult;
    any = true;
  }
  if (!any || total == 0 || total > relay::TIMER_MAX_SEC) return false;
  out = total;
  return true;
}

bool authorized(int64_t user) {
  for (uint8_t i = 0; i < settings.tgUserCount; i++)
    if (settings.tgUsers[i] == user) return true;
  return false;
}

void enqueue(int64_t chat, const String& text, bool keyboard = false) {
  if (qLen == QUEUE_SIZE) {  // full: drop the oldest
    qHead = (qHead + 1) % QUEUE_SIZE;
    qLen--;
  }
  Out& o = queue[(qHead + qLen) % QUEUE_SIZE];
  o.chat = chat;
  o.text = text;
  o.keyboard = keyboard;
  qLen++;
}

void notifyAll(const String& text) {
  for (uint8_t i = 0; i < settings.tgUserCount; i++) enqueue(settings.tgUsers[i], text);
}

const char* sourceText(const char* src) {
  if (!strcmp(src, "manual")) return "desde la web";
  if (!strcmp(src, "timer")) return "por el temporizador";
  if (!strcmp(src, "schedule")) return "por un horario";
  if (!strcmp(src, "telegram")) return "desde Telegram";
  if (!strcmp(src, "cycle")) return "por la rutina";
  return "al arrancar";
}

String stateLine() {
  return relay::isOn() ? F("🟢 Encendido") : F("⚫ Apagado");
}

// ---------------------------------------------------------------- connection
void fail(const String& why, uint32_t retryMs = 0) {
  error = why;
  if (!retryMs) {
    backoff = backoff ? min<uint32_t>(backoff * 2, 300000) : 5000;
    retryMs = backoff;
  }
  retryAt = millis() + retryMs;
  Serial.printf("[tg] %s (retry in %lu s)\n", why.c_str(), (unsigned long)(retryMs / 1000));
}

void shutdown() {
  client.stop();
  inFlight = Req::None;
  resp = String();
}

bool connect() {
  if (!anchors) {
    String pem = FPSTR(TELEGRAM_CA);  // BearSSL parses from RAM, not from flash
    anchors = new BearSSL::X509List(pem.c_str());
  }
  // Max Fragment Length negotiation: with it, the receive buffer drops from 16.7 kB to 1 kB.
  // The probe is a short handshake without big buffers; repeated until a connection succeeds.
  if (smallFragments < 0) {
    bool ok = BearSSL::WiFiClientSecure::probeMaxFragmentLength(HOST, 443, 1024);
    Serial.printf("[tg] 1 kB TLS fragments %s\n", ok ? "supported" : "not supported");
    if (ok) smallFragments = 1;
  }
  int rx = smallFragments == 1 ? 1024 : 16384;
  int tx = smallFragments == 1 ? 1024 : 512;
  uint32_t need = rx + tx + TLS_OVERHEAD;
  uint32_t heap = ESP.getFreeHeap(), block = ESP.getMaxFreeBlockSize();
  if (heap < need || block < static_cast<uint32_t>(rx) + 400) {
    fail(String(F("Memoria insuficiente: libre ")) + heap + F(" B (bloque ") + block + F(" B), necesita ") + need + F(" B"));
    return false;
  }
  client.setTrustAnchors(anchors);
  client.setX509Time(time(nullptr));
  client.setSession(&session);
  client.setBufferSizes(rx, tx);
  client.setTimeout(8000);
  uint32_t t = millis();
  if (!client.connect(HOST, 443)) {
    char buf[80];
    int code = client.getLastSSLError(buf, sizeof(buf));
    shutdown();
    if (code) fail(String(F("Error TLS ")) + code + F(": ") + buf);
    else fail(String(F("No se pudo conectar con Telegram (memoria libre ")) + ESP.getFreeHeap() + F(" B)"));
    return false;
  }
  if (smallFragments < 0) smallFragments = 0;
  Serial.printf("[tg] connected in %lu ms, rx buffer %d B, heap %u\n", (unsigned long)(millis() - t), rx,
                ESP.getFreeHeap());
  return true;
}

bool send(Req type, const char* method, const String& body, uint32_t timeoutMs = REQUEST_TIMEOUT_MS) {
  String req;
  req.reserve(220 + body.length());
  req = F("POST /bot");
  req += settings.tgToken;
  req += '/';
  req += method;
  req += F(" HTTP/1.1\r\nHost: api.telegram.org\r\nContent-Type: application/json\r\nContent-Length: ");
  req += body.length();
  req += F("\r\nConnection: keep-alive\r\n\r\n");
  req += body;
  if (client.write(reinterpret_cast<const uint8_t*>(req.c_str()), req.length()) != req.length()) {
    shutdown();
    fail(F("Conexión con Telegram perdida"), 1000);
    return false;
  }
  inFlight = type;
  deadline = millis() + timeoutMs;
  resp = String();
  respOverflow = false;
  return true;
}

// Returns 1 when a full response is in `body`, 0 while waiting and -1 if it cannot be read.
int readResponse(int& status, String& body, bool& closeAfter) {
  uint8_t buf[256];
  while (client.available() > 0) {
    int n = client.read(buf, sizeof(buf));
    if (n <= 0) break;
    if (resp.length() + n > MAX_RESPONSE) {
      respOverflow = true;
      return -1;
    }
    resp.concat(reinterpret_cast<const char*>(buf), n);
  }
  int he = resp.indexOf(F("\r\n\r\n"));
  if (he < 0) return 0;
  String headers = resp.substring(0, he);
  headers.toLowerCase();
  status = headers.substring(9, 12).toInt();
  closeAfter = headers.indexOf(F("connection: close")) >= 0;
  size_t start = he + 4;

  int cl = headers.indexOf(F("content-length:"));
  if (cl >= 0) {
    size_t len = headers.substring(cl + 15).toInt();
    if (resp.length() < start + len) return 0;
    body = resp.substring(start, start + len);
    return 1;
  }
  if (headers.indexOf(F("transfer-encoding: chunked")) >= 0) {
    if (!resp.endsWith(F("\r\n0\r\n\r\n")) && !resp.endsWith(F("\n0\r\n\r\n"))) return 0;
    body = String();
    size_t p = start;
    while (p < resp.length()) {
      int eol = resp.indexOf(F("\r\n"), p);
      if (eol < 0) return -1;
      size_t len = strtoul(resp.substring(p, eol).c_str(), nullptr, 16);
      if (len == 0) return 1;
      body += resp.substring(eol + 2, eol + 2 + len);
      p = eol + 2 + len + 2;
    }
    return -1;
  }
  return -1;  // no length: not something the Bot API sends
}

// ---------------------------------------------------------------- requests
void requestUpdates() {
  JsonDocument doc;
  doc["offset"] = offset;
  doc["timeout"] = restartAfterAck ? 0 : telegram::POLL_SEC;
  doc["limit"] = 3;
  doc["allowed_updates"].add("message");
  String body;
  serializeJson(doc, body);
  send(Req::Updates, "getUpdates", body, (doc["timeout"].as<uint32_t>() + 15) * 1000UL);
}

void requestSetCommands() {
  static const char BODY[] PROGMEM =
      "{\"commands\":["
      "{\"command\":\"encender\",\"description\":\"Encender el relé\"},"
      "{\"command\":\"apagar\",\"description\":\"Apagar el relé\"},"
      "{\"command\":\"estado\",\"description\":\"Estado actual\"},"
      "{\"command\":\"temporizador\",\"description\":\"Ej.: /temporizador 30m apagar\"},"
      "{\"command\":\"cancelar\",\"description\":\"Cancelar el temporizador\"},"
      "{\"command\":\"rutina\",\"description\":\"Ej.: /rutina 10m 50m\"},"
      "{\"command\":\"detener\",\"description\":\"Detener la rutina\"},"
      "{\"command\":\"avisos\",\"description\":\"Avisos de cambios: si / no\"},"
      "{\"command\":\"ayuda\",\"description\":\"Lista de órdenes\"}]}";
  send(Req::SetCommands, "setMyCommands", FPSTR(BODY));
}

void requestSend() {
  Out& o = queue[qHead];
  JsonDocument doc;
  doc["chat_id"] = o.chat;
  doc["text"] = o.text;
  if (o.keyboard) {
    JsonObject k = doc["reply_markup"].to<JsonObject>();
    JsonArray rows = k["keyboard"].to<JsonArray>();
    JsonArray r1 = rows.add<JsonArray>();
    r1.add<JsonObject>()["text"] = "Encender";
    r1.add<JsonObject>()["text"] = "Apagar";
    rows.add<JsonArray>().add<JsonObject>()["text"] = "Estado";
    k["resize_keyboard"] = true;
    k["is_persistent"] = true;
  }
  String body;
  serializeJson(doc, body);
  if (send(Req::Send, "sendMessage", body)) {
    o.text = String();
    qHead = (qHead + 1) % QUEUE_SIZE;
    qLen--;
  }
}

// ---------------------------------------------------------------- commands
String helpText() {
  String t = F("🔌 ");
  t += settings.deviceName;
  t += F("\n\n"
         "/encender – enciende el relé\n"
         "/apagar – apaga el relé\n"
         "/estado – estado actual\n"
         "/temporizador 30m – cambia el estado dentro de 30 min; añade «encender» o «apagar» para elegir\n"
         "/cancelar – cancela el temporizador\n"
         "/rutina 10m 50m – encendido 10 min y apagado 50 min, sin fin\n"
         "/detener – detiene la rutina\n"
         "/avisos si | no – avisos cuando el relé cambia por otra vía\n"
         "/id – tu ID de Telegram\n"
         "/reiniciar – reinicia el dispositivo\n\n"
         "Duraciones: 45s, 30m, 2h, 1h30m, 1d (sin unidad = minutos).");
  return t;
}

String statusText() {
  String t = settings.deviceName;
  t += '\n';
  t += stateLine();
  t += F(" desde hace ");
  t += fmtDur(relay::secondsSinceChange());
  if (relay::timerActive()) {
    RelayAction a = relay::timerAction();
    t += a == RelayAction::On ? F("\n⏱ Se enciende en ") : a == RelayAction::Off ? F("\n⏱ Se apaga en ") : F("\n⏱ Cambia en ");
    t += fmtDur(relay::timerRemaining());
  }
  if (relay::cycleActive()) {
    t += F("\n🔁 Rutina ");
    t += fmtDur(settings.cycle.onSec);
    t += F(" / ");
    t += fmtDur(settings.cycle.offSec);
    t += relay::isOn() ? F(" · apaga en ") : F(" · enciende en ");
    t += fmtDur(relay::cyclePhaseRemaining());
  }
  uint8_t idx;
  int32_t in = scheduler::nextEvent(idx);
  if (in >= 0) {
    const Schedule& s = settings.schedules[idx];
    char hm[8];
    snprintf(hm, sizeof(hm), "%02u:%02u", s.hour, s.minute);
    t += F("\n📅 Próximo horario: ");
    t += s.action == RelayAction::On ? F("encender") : s.action == RelayAction::Off ? F("apagar") : F("cambiar");
    t += F(" a las ");
    t += hm;
    t += F(" (en ");
    t += fmtDur(static_cast<uint32_t>(in) * 60);
    t += ')';
  }
  t += F("\n📶 ");
  t += settings.wifiSsid;
  t += F(" · ");
  t += WiFi.RSSI();
  t += F(" dBm");
  return t;
}

void handleCommand(int64_t chat, const String& text) {
  // First word, lower case, without "/" or "@botname"; the rest are arguments.
  String cmd = text;
  cmd.trim();
  String args;
  int sp = cmd.indexOf(' ');
  if (sp > 0) {
    args = cmd.substring(sp + 1);
    args.trim();
    args.toLowerCase();
    cmd = cmd.substring(0, sp);
  }
  cmd.toLowerCase();
  if (cmd.startsWith("/")) cmd.remove(0, 1);
  int at = cmd.indexOf('@');
  if (at >= 0) cmd.remove(at);

  if (cmd == F("start") || cmd == F("ayuda") || cmd == F("help")) return enqueue(chat, helpText(), true);

  if (cmd == F("encender") || cmd == F("on") || cmd == F("prender")) {
    relay::apply(RelayAction::On, "telegram");
    return enqueue(chat, stateLine());
  }
  if (cmd == F("apagar") || cmd == F("off")) {
    relay::apply(RelayAction::Off, "telegram");
    return enqueue(chat, stateLine());
  }
  if (cmd == F("cambiar") || cmd == F("toggle")) {
    relay::apply(RelayAction::Toggle, "telegram");
    return enqueue(chat, stateLine());
  }
  if (cmd == F("estado") || cmd == F("status")) return enqueue(chat, statusText());

  if (cmd == F("temporizador") || cmd == F("timer")) {
    // "/temporizador 30m [encender|apagar]"; by default it does the opposite of the current state.
    RelayAction a = relay::isOn() ? RelayAction::Off : RelayAction::On;
    String dur = args;
    int s2 = args.indexOf(' ');
    if (s2 > 0) {
      dur = args.substring(0, s2);
      String w = args.substring(s2 + 1);
      w.trim();
      if (w == F("encender") || w == F("on")) a = RelayAction::On;
      else if (w == F("apagar") || w == F("off")) a = RelayAction::Off;
      else return enqueue(chat, F("Uso: /temporizador 30m encender  (o apagar)"));
    }
    uint32_t sec;
    if (!parseDuration(dur.c_str(), sec))
      return enqueue(chat, F("Uso: /temporizador 30m [encender | apagar]\nDe 1 s a 7 días: 45s, 30m, 2h, 1h30m, 1d."));
    relay::startTimer(sec, a);
    String t = F("⏱ ");
    t += a == RelayAction::On ? F("Se enciende en ") : F("Se apaga en ");
    t += fmtDur(sec);
    return enqueue(chat, t);
  }
  if (cmd == F("cancelar")) {
    if (!relay::timerActive()) return enqueue(chat, F("No hay ningún temporizador activo."));
    relay::cancelTimer();
    return enqueue(chat, F("⏱ Temporizador cancelado."));
  }

  if (cmd == F("rutina")) {
    int s2 = args.indexOf(' ');
    uint32_t on, off;
    if (s2 < 0 || !parseDuration(args.substring(0, s2).c_str(), on) ||
        !parseDuration(args.substring(s2 + 1).c_str(), off) || !relay::startCycle(on, off))
      return enqueue(chat, F("Uso: /rutina 10m 50m  (tiempo encendido y apagado; cada fase de 5 s a 24 h)"));
    String t = F("🔁 Rutina iniciada: ");
    t += fmtDur(on);
    t += F(" encendido, ");
    t += fmtDur(off);
    t += F(" apagado.");
    return enqueue(chat, t);
  }
  if (cmd == F("detener")) {
    if (!relay::cycleActive()) return enqueue(chat, F("La rutina no está activa."));
    relay::stopCycle();
    return enqueue(chat, String(F("🔁 Rutina detenida. ")) + stateLine());
  }

  if (cmd == F("avisos")) {
    if (args == F("si") || args == F("sí") || args == F("on")) settings.tgNotify = true;
    else if (args == F("no") || args == F("off")) settings.tgNotify = false;
    else if (args.length()) return enqueue(chat, F("Uso: /avisos si  o  /avisos no"));
    else settings.tgNotify = !settings.tgNotify;
    store::save();
    return enqueue(chat, settings.tgNotify ? F("🔔 Avisos activados.") : F("🔕 Avisos desactivados."));
  }
  if (cmd == F("id")) return enqueue(chat, String(F("Tu ID de Telegram es ")) + i64(chat));
  if (cmd == F("reiniciar")) {
    restartAfterAck = true;  // restarts once Telegram has confirmed this message (see loop)
    return enqueue(chat, F("Reiniciando…"));
  }
  enqueue(chat, F("No entiendo esa orden. Escribe /ayuda para ver la lista."));
}

void handleUpdates(const String& body) {
  JsonDocument filter;
  JsonObject f = filter["result"][0].to<JsonObject>();
  f["update_id"] = true;
  f["message"]["date"] = true;
  f["message"]["text"] = true;
  f["message"]["chat"]["id"] = true;
  f["message"]["from"]["id"] = true;
  f["message"]["from"]["first_name"] = true;
  JsonDocument doc;
  if (deserializeJson(doc, body, DeserializationOption::Filter(filter))) return;

  for (JsonObject u : doc["result"].as<JsonArray>()) {
    offset = u["update_id"].as<int64_t>() + 1;
    JsonObject m = u["message"];
    const char* text = m["text"];
    if (!text) continue;
    int64_t chat = m["chat"]["id"].as<int64_t>();
    int64_t from = m["from"]["id"].as<int64_t>();

    if (!authorized(from)) {
      Serial.printf("[tg] message from unauthorized user %s\n", i64(from).c_str());
      String t;
      if (!settings.tgUserCount) {
        t = F("👋 Hola, ");
        t += m["from"]["first_name"] | "";
        t += F(". Tu ID de Telegram es ");
        t += i64(from);
        t += F(".\n\nPara controlar el relé, escríbelo en su página web: Ajustes → Telegram → Usuarios autorizados.");
      } else {
        t = F("⛔ No tienes permiso para usar este relé. Tu ID de Telegram es ");
        t += i64(from);
        t += '.';
      }
      enqueue(chat, t);
      continue;
    }

    uint32_t date = m["date"] | 0UL;
    uint32_t now = time(nullptr);
    if (date && now > date + telegram::MAX_AGE_SEC) {
      String t = F("⌛ Orden «");
      t += text;
      t += F("» ignorada: llegó ");
      t += fmtDur(now - date);
      t += F(" tarde, porque el relé estaba sin conexión. Envíala de nuevo si aún la necesitas.");
      enqueue(chat, t);
      continue;
    }
    Serial.printf("[tg] command \"%s\" from %s\n", text, i64(from).c_str());
    handleCommand(chat, text);
  }
}

void handleResponse(Req type, int status, const String& body) {
  if (status == 401 || status == 404) {
    tokenRejected = true;
    haveMe = false;
    bot = String();
    shutdown();
    fail(F("Token no válido: revísalo en Ajustes"), 600000);
    return;
  }
  if (status == 409) {
    shutdown();
    fail(F("Otro programa está usando este bot (webhook u otro dispositivo)"), 60000);
    return;
  }
  if (status == 429 || status >= 500) {
    shutdown();
    fail(String(F("Telegram respondió ")) + status, 30000);
    return;
  }
  backoff = 0;
  error = String();
  if (status != 200) {
    // A single message that Telegram refuses (user blocked the bot, chat not found...).
    Serial.printf("[tg] HTTP %d: %s\n", status, body.c_str());
    return;
  }
  switch (type) {
    case Req::GetMe: {
      JsonDocument doc;
      if (deserializeJson(doc, body)) break;
      bot = doc["result"]["username"] | "";
      haveMe = true;
      Serial.printf("[tg] bot @%s online\n", bot.c_str());
      break;
    }
    case Req::SetCommands: commandsSet = true; break;
    case Req::Updates:
      if (restartAfterAck) {
        // This request carried the offset that confirms "/reiniciar", so it will not run again.
        network::requestRestart(300);
        return;
      }
      handleUpdates(body);
      break;
    default: break;
  }
}

void trackRelay() {
  bool on = relay::isOn();
  if (on == lastOn) return;
  lastOn = on;
  const char* src = relay::lastSource();
  // Telegram commands already get a reply; the cyclic routine would flood the chat.
  if (!settings.tgNotify || !strcmp(src, "telegram") || !strcmp(src, "cycle")) return;
  String t = settings.deviceName;
  t += F(": ");
  t += on ? F("🟢 encendido ") : F("⚫ apagado ");
  t += sourceText(src);
  notifyAll(t);
}
}  // namespace

namespace telegram {

void begin() { lastOn = relay::isOn(); }

void reconfigure() {
  shutdown();
  haveMe = commandsSet = tokenRejected = false;
  bot = error = String();
  offset = 0;
  backoff = 0;
  retryAt = millis();
  qLen = 0;
}

void loop() {
  if (!settings.tgToken[0]) {
    if (client.connected() || inFlight != Req::None) shutdown();
    return;
  }
  trackRelay();
  if (!network::staConnected() || !scheduler::timeValid()) {
    if (inFlight != Req::None) shutdown();
    return;
  }

  if (inFlight != Req::None) {
    int status = 0;
    bool closeAfter = false;
    String body;
    int r = readResponse(status, body, closeAfter);
    if (r == 0) {
      if (reached(deadline) || !client.connected()) {
        shutdown();
        fail(F("Sin respuesta de Telegram"), 2000);
      }
      return;
    }
    Req type = inFlight;
    inFlight = Req::None;
    if (r < 0) {
      // Response too large or unreadable. For getUpdates, skip the update that caused it.
      if (type == Req::Updates && respOverflow) {
        int p = resp.indexOf(F("\"update_id\":"));
        if (p >= 0) offset = atoll(resp.c_str() + p + 12) + 1;
      }
      shutdown();
      fail(F("Respuesta de Telegram no válida"), 2000);
      return;
    }
    resp = String();
    handleResponse(type, status, body);
    if (closeAfter) client.stop();
    return;
  }

  if (!client.connected()) {
    if (!reached(retryAt) || tokenRejected) return;
    if (!connect()) return;
  }

  if (!haveMe) return (void)send(Req::GetMe, "getMe", "{}");
  if (!commandsSet) return requestSetCommands();
  if (!bootNotified) {
    bootNotified = true;
    if (settings.tgNotify) {
      String t = F("🔌 ");
      t += settings.deviceName;
      t += F(" está en línea (");
      String reason = ESP.getResetReason();
      t += reason == F("Power On") ? String(F("volvió la luz")) : reason;
      t += F("). ");
      t += stateLine();
      t += '.';
      notifyAll(t);
    }
  }
  if (qLen) return requestSend();
  requestUpdates();
}

const char* state() {
  if (!settings.tgToken[0]) return "off";
  if (!network::staConnected() || !scheduler::timeValid()) return "waiting";
  if (error.length()) return "error";
  return haveMe ? "online" : "connecting";
}

const String& botName() { return bot; }
const String& lastError() { return error; }

bool validToken(const char* t) {
  // "<digits>:<30+ characters of [A-Za-z0-9_-]>"
  const char* p = t;
  while (isdigit(static_cast<unsigned char>(*p))) p++;
  if (p == t || *p != ':') return false;
  size_t n = 0;
  for (p++; *p; p++, n++)
    if (!isalnum(static_cast<unsigned char>(*p)) && *p != '_' && *p != '-') return false;
  return n >= 30 && strlen(t) < sizeof(settings.tgToken);
}

bool parseUsers(const char* text) {
  int64_t ids[MAX_TG_USERS];
  uint8_t n = 0;
  const char* p = text;
  while (*p) {
    while (*p == ' ' || *p == ',' || *p == ';') p++;
    if (!*p) break;
    if (!isdigit(static_cast<unsigned char>(*p)) || n == MAX_TG_USERS) return false;
    int64_t v = 0;
    while (isdigit(static_cast<unsigned char>(*p))) {
      v = v * 10 + (*p++ - '0');
      if (v > 9007199254740991LL) return false;  // Telegram IDs fit in 52 bits
    }
    if (*p && *p != ' ' && *p != ',' && *p != ';') return false;
    if (v == 0) return false;
    ids[n++] = v;
  }
  for (uint8_t i = 0; i < n; i++) settings.tgUsers[i] = ids[i];
  settings.tgUserCount = n;
  return true;
}

String usersText() {
  String t;
  for (uint8_t i = 0; i < settings.tgUserCount; i++) {
    if (i) t += F(", ");
    t += i64(settings.tgUsers[i]);
  }
  return t;
}

}  // namespace telegram
