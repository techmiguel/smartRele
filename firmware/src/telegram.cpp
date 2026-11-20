#include "telegram.h"

#include <ArduinoJson.h>
#include <ESP8266WiFi.h>

#include "network.h"
#include "relay.h"
#include "scheduler.h"
#include "settings.h"
#include "tls_link.h"

#ifdef ARDUINO_ARCH_ESP8266
#include <StackThunk.h>
#endif

#ifdef TELEGRAM_TEST_ANCHORS  // host tests: trust the test server's certificate authority
#include TELEGRAM_TEST_ANCHORS
#else
#include "telegram_ca.h"
#endif

TcpTransport& telegramTransport();  // tcp_transport.cpp (or the host test harness)
bool telegramResolve(const char* host, uint32_t& ip);  // DNS lookup, idem
// Memory that survives a software restart (RTC on the ESP8266); `words` 32-bit words.
bool telegramRtcRead(uint32_t* data, size_t words);
bool telegramRtcWrite(uint32_t* data, size_t words);
bool telegramSoftRestart();  // the last reset was a software restart

namespace {
constexpr const char* HOST = "api.telegram.org";
constexpr size_t MAX_RESPONSE = 4096;  // larger updates are skipped (see handleOversize)
constexpr size_t MAX_TEXT = 1500;      // longer outgoing texts are cut
constexpr uint8_t QUEUE_SIZE = 6;
constexpr uint32_t HANDSHAKE_TIMEOUT_MS = 12000;
constexpr uint32_t REQUEST_TIMEOUT_MS = 15000;
constexpr uint32_t LONG_POLL_SLACK_MS = 8000;  // on top of POLL_SEC before giving up
constexpr uint32_t ONLINE_GRACE_MS = 60000;     // reconnections shorter than this are not errors
// Waits between connection attempts; the last one repeats. Short on purpose: after a network
// change (VPN, mobile data off and on) the bot must come back within half a minute.
constexpr uint16_t BACKOFF_S[] = {1, 2, 5, 10, 20};
constexpr uint8_t BACKOFF_STEPS = sizeof(BACKOFF_S) / sizeof(BACKOFF_S[0]);
// Engine buffer for records of up to 2 kB, if the server accepts the Max Fragment Length
// extension (16.7 kB otherwise).
constexpr size_t SMALL_BUF = 2048 + 325;

// ---------------------------------------------------------------- memory
// Allocated once, the first time the bot is enabled, and never freed: every reconnection reuses
// it, so heap fragmentation cannot leave the bot without memory after hours of operation.
br_ssl_client_context* sc = nullptr;
br_x509_minimal_context* xc = nullptr;
unsigned char* iobuf = nullptr;
size_t iobufSize = 0;
int8_t smallRecords = -1;  // -1 unknown, 0 server sends full records, 1 accepts 2 kB records
size_t usedLen = 0;        // part of the buffer given to the current connection

TlsLink link;

enum class Phase : uint8_t { Idle, Handshake, Ready, Sending, Waiting };
Phase phase = Phase::Idle;
enum class Req : uint8_t { None, GetMe, SetCommands, Updates, Send };
Req inFlight = Req::None;

String out;          // request being written
size_t outPos = 0;
String resp;         // response being read
bool respOverflow = false;
uint32_t phaseDeadline = 0;

int64_t offset = 0;  // next update_id to fetch
bool haveMe = false;
bool commandsSet = false;
bool bootNotified = false;
bool restartAfterAck = false;
bool restarting = false;     // restart requested: the bot stays quiet until it happens
bool wasOnNetwork = false;
bool lastOn = false;

uint32_t retryAt = 0;
uint8_t backoffStep = 0;
uint32_t lastOkAt = 0;     // last complete response (millis)
bool everOk = false;
uint32_t linkUpAt = 0;
uint32_t connects = 0, failures = 0;
String bot, error, lastFailure;

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
  String o;
  auto add = [&o](uint32_t v, const char* unit) {
    if (o.length()) o += ' ';
    o += v;
    o += ' ';
    o += unit;
  };
  if (d) add(d, "d");
  if (h) add(h, "h");
  if (m && !d) add(m, "min");
  if ((x && !d && !h) || !o.length()) add(x, "s");
  return o;
}

// "45s", "30m", "2h", "1h30m", "1d"; a bare number means minutes.
bool parseDuration(const char* s, uint32_t& result) {
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
  result = total;
  return true;
}

bool authorized(int64_t user) {
  for (uint8_t i = 0; i < settings.tgUserCount; i++)
    if (settings.tgUsers[i] == user) return true;
  return false;
}

void enqueue(int64_t chat, const String& text, bool keyboard = false) {
  if (qLen == QUEUE_SIZE) {  // full: drop the oldest
    queue[qHead].text = String();
    qHead = (qHead + 1) % QUEUE_SIZE;
    qLen--;
  }
  Out& o = queue[(qHead + qLen) % QUEUE_SIZE];
  o.chat = chat;
  o.text = text.length() > MAX_TEXT ? text.substring(0, MAX_TEXT) : text;
  o.keyboard = keyboard;
  qLen++;
}

void dequeue() {
  queue[qHead].text = String();
  qHead = (qHead + 1) % QUEUE_SIZE;
  qLen--;
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

String stateLine() { return relay::isOn() ? F("🟢 Encendido") : F("⚫ Apagado"); }

String linkErrorText(int err) {
  switch (err) {
    case TlsLink::ERR_TCP_CONNECT: return F("Sin acceso a api.telegram.org (¿hay datos en el hotspot? ¿una VPN?)");
    case TlsLink::ERR_TCP_CLOSED: return F("La conexión con Telegram se cortó");
    case BR_ERR_X509_NOT_TRUSTED: return F("Certificado de Telegram no reconocido: hace falta actualizar el firmware");
    case BR_ERR_X509_EXPIRED: return F("Certificado fuera de fecha: ¿la hora del relé es correcta?");
    case BR_ERR_X509_BAD_SERVER_NAME: return F("El servidor no es api.telegram.org (¿una VPN o un proxy en medio?)");
    default: return String(F("Error TLS ")) + err;
  }
}

// ---------------------------------------------------------------- connection
bool allocateTls() {
  if (iobuf) return true;
#ifdef ARDUINO_ARCH_ESP8266
  // Separate 6.2 kB stack for BearSSL (see tls_link.cpp), also kept for good.
  static bool thunk = false;
  if (!thunk) {
    if (ESP.getMaxFreeBlockSize() < 6400) {  // stack_thunk_add_ref() aborts if malloc fails
      error = F("Memoria insuficiente para la pila TLS: reinicia el relé");
      return false;
    }
    stack_thunk_add_ref();
    thunk = true;
  }
#endif
  // Contexts first, then the large buffer: three blocks that stay put for good.
  if (!sc) sc = static_cast<br_ssl_client_context*>(malloc(sizeof(br_ssl_client_context)));
  if (!xc) xc = static_cast<br_x509_minimal_context*>(malloc(sizeof(br_x509_minimal_context)));
  if (sc && xc) iobuf = static_cast<unsigned char*>(malloc(BR_SSL_BUFSIZE_MONO));
  if (!sc || !xc || !iobuf) {
    error = String(F("Memoria insuficiente (libre ")) + ESP.getFreeHeap() + F(" B): reinicia el relé");
    return false;
  }
  iobufSize = BR_SSL_BUFSIZE_MONO;
  link.init(sc, xc, TELEGRAM_TA, TELEGRAM_TA_COUNT);
  Serial.printf("[tg] TLS memory reserved (%u B), heap %u\n",
                (unsigned)(sizeof(*sc) + sizeof(*xc) + BR_SSL_BUFSIZE_MONO), ESP.getFreeHeap());
  return true;
}

void goIdle(const String& why) {
  link.close();
  phase = Phase::Idle;
  inFlight = Req::None;
  out = String();
  resp = String();
  failures++;
  lastFailure = why;
  uint32_t wait = BACKOFF_S[backoffStep] * 1000UL;
  if (backoffStep + 1 < BACKOFF_STEPS) backoffStep++;
  retryAt = millis() + wait;
  // Short interruptions are normal (the long poll, network hiccups): they only count as an
  // error for the web interface if Telegram has been unreachable for a while.
  if (!everOk || millis() - lastOkAt > ONLINE_GRACE_MS) error = why;
  Serial.printf("[tg] %s; retry in %lu s\n", why.c_str(), (unsigned long)(wait / 1000));
}

// Addresses of api.telegram.org. The DNS answer is not trusted on its own: while the phone has
// no credit, many carriers answer every name with their top-up portal, and the ESP8266 keeps
// that answer in its cache for as long as its TTL says (up to a week), well after the top-up.
// Since the TLS certificate proves who is at the other end, any address can be tried safely:
// the last one that passed the certificate check (saved in flash), the DNS answer, and the
// addresses Telegram has used for years. The verified one is tried every other attempt.
constexpr uint32_t ip4(uint8_t a, uint8_t b, uint8_t c, uint8_t d) {
  return a | b << 8 | c << 16 | static_cast<uint32_t>(d) << 24;  // network byte order
}
#ifdef TELEGRAM_TEST_BUILTIN_IP
constexpr uint32_t KNOWN_IPS[] = {TELEGRAM_TEST_BUILTIN_IP};
#else
constexpr uint32_t KNOWN_IPS[] = {ip4(149, 154, 166, 110), ip4(149, 154, 167, 220)};
#endif
constexpr uint8_t KNOWN_COUNT = sizeof(KNOWN_IPS) / sizeof(KNOWN_IPS[0]);

uint8_t attempt = 0;         // since the last successful connection
uint32_t currentIp = 0;
const char* currentSrc = "";

String ipText(uint32_t ip) {
  char b[16];
  snprintf(b, sizeof(b), "%u.%u.%u.%u", ip & 0xFF, (ip >> 8) & 0xFF, (ip >> 16) & 0xFF, ip >> 24);
  return String(b);
}

bool pickAddress(uint32_t& ip, const char*& src) {
  const uint32_t verified = settings.tgIp;
  for (uint8_t tries = 0; tries < 2 * (KNOWN_COUNT + 1); tries++) {
    uint8_t a = attempt++;
    if (verified && a % 2 == 0) {
      ip = verified;
      src = "verificada";
      return true;
    }
    uint8_t alt = (verified ? a / 2 : a) % (KNOWN_COUNT + 1);
    if (alt == 0) {
      if (telegramResolve(HOST, ip) && ip != verified) {
        src = "DNS";
        return true;
      }
    } else if (KNOWN_IPS[alt - 1] != verified) {
      ip = KNOWN_IPS[alt - 1];
      src = "conocida";
      return true;
    }
  }
  return false;
}

void startConnect() {
  if (!pickAddress(currentIp, currentSrc)) return goIdle(F("Sin dirección para api.telegram.org"));
  // Small records first; the full-size buffer only if the server does not accept them.
  size_t len = smallRecords == 0 ? iobufSize : SMALL_BUF;
  if (len > iobufSize) len = iobufSize;
  usedLen = len;
  connects++;
  uint32_t t = millis();
  if (!link.open(telegramTransport(), HOST, currentIp, 443, iobuf, len, time(nullptr)))
    return goIdle(linkErrorText(link.lastError()) + F(" · ") + ipText(currentIp) + F(" (") + currentSrc + ')');
  Serial.printf("[tg] TCP connected to %s (%s) in %lu ms\n", ipText(currentIp).c_str(), currentSrc,
                (unsigned long)(millis() - t));
  phase = Phase::Handshake;
  phaseDeadline = millis() + HANDSHAKE_TIMEOUT_MS;
}

void reconnectNow() {
  link.close();
  phase = Phase::Idle;
  retryAt = millis();
}

void onHandshakeDone() {
  // The certificate is valid: this address is really api.telegram.org.
  attempt = 0;
  if (settings.tgIp != currentIp) {
    settings.tgIp = currentIp;
    store::save();
    Serial.printf("[tg] verified address %s saved\n", ipText(currentIp).c_str());
  }
  bool small = link.smallRecords();
  Serial.printf("[tg] TLS ready (%s records%s), heap %u\n", small ? "2 kB" : "16 kB",
                link.resumed() ? ", resumed" : "", ESP.getFreeHeap());
  if (smallRecords < 0) {
    // First connection since boot: learn whether the server accepts 2 kB records.
    smallRecords = small ? 1 : 0;
    if (small && iobufSize > SMALL_BUF) {
      // It does: give the rest of the buffer back to the heap. The link is closed while the
      // block is resized, because realloc() may move it.
      link.close();
      unsigned char* p = static_cast<unsigned char*>(realloc(iobuf, SMALL_BUF));
      if (p) {
        iobuf = p;
        iobufSize = SMALL_BUF;
      }
      Serial.printf("[tg] buffer reduced to %u B, heap %u\n", (unsigned)iobufSize, ESP.getFreeHeap());
      return reconnectNow();
    }
    // It does not, but the handshake fitted the small buffer: later records might not.
    if (!small && usedLen < iobufSize) return reconnectNow();
  } else if (!small && usedLen < BR_SSL_BUFSIZE_MONO) {
    // The server used to accept small records and no longer does: the buffer has to grow.
    smallRecords = 0;
    link.close();
    unsigned char* p = static_cast<unsigned char*>(realloc(iobuf, BR_SSL_BUFSIZE_MONO));
    if (!p) return goIdle(F("Memoria insuficiente para la conexión segura: reinicia el relé"));
    iobuf = p;
    iobufSize = BR_SSL_BUFSIZE_MONO;
    return reconnectNow();
  }
  linkUpAt = millis();
  phase = Phase::Ready;
}

// Handshake that failed because a record did not fit the small buffer: the server ignores the
// Max Fragment Length extension. Retry at once with the full buffer.
bool retryWithFullBuffer(int err) {
  if (err != BR_ERR_TOO_LARGE || smallRecords == 0 || iobufSize < BR_SSL_BUFSIZE_MONO) return false;
  smallRecords = 0;
  link.close();
  Serial.println(F("[tg] server sends full-size records; using the 16 kB buffer"));
  phase = Phase::Idle;
  retryAt = millis();
  return true;
}

void beginRequest(Req type, const char* method, const String& body) {
  out.reserve(200 + body.length());
  out = F("POST /bot");
  out += settings.tgToken;
  out += '/';
  out += method;
  out += F(" HTTP/1.1\r\nHost: api.telegram.org\r\nContent-Type: application/json\r\nContent-Length: ");
  out += body.length();
  out += F("\r\nConnection: keep-alive\r\n\r\n");
  out += body;
  outPos = 0;
  inFlight = type;
  resp = String();
  respOverflow = false;
  phase = Phase::Sending;
  uint32_t timeout = REQUEST_TIMEOUT_MS;
  if (type == Req::Updates && !restartAfterAck) timeout = telegram::POLL_SEC * 1000UL + LONG_POLL_SLACK_MS;
  phaseDeadline = millis() + timeout;
}

// Returns 1 when a full response is in `body`, 0 while waiting and -1 if it cannot be read.
int parseResponse(int& status, String& body, bool& closeAfter) {
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
    if (!resp.endsWith(F("\r\n0\r\n\r\n"))) return 0;
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
  doc["limit"] = 1;
  doc["allowed_updates"].add("message");
  String body;
  serializeJson(doc, body);
  beginRequest(Req::Updates, "getUpdates", body);
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
      "{\"command\":\"diagnostico\",\"description\":\"Estado de la conexión\"},"
      "{\"command\":\"ayuda\",\"description\":\"Lista de órdenes\"}]}";
  beginRequest(Req::SetCommands, "setMyCommands", FPSTR(BODY));
}

void requestSend() {
  // The message leaves the queue only when Telegram answers: a connection that drops in the
  // meantime makes it go out again after reconnecting instead of losing it.
  const Out& o = queue[qHead];
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
  beginRequest(Req::Send, "sendMessage", body);
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
         "/diagnostico – estado de la conexión y de la memoria\n"
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
  t += F(" dBm · ");
  t += WiFi.localIP().toString();
  return t;
}

String diagText() {
  String t = F("🩺 Diagnóstico\n");
  t += F("Encendido hace ");
  t += fmtDur(millis() / 1000);
  t += F(" (");
  t += ESP.getResetReason();
  t += F(")\nConexión con Telegram activa hace ");
  t += fmtDur((millis() - linkUpAt) / 1000);
  t += F("\nServidor: ");
  t += ipText(currentIp);
  t += F(" (");
  t += currentSrc;
  t += ')';
  t += F("\nConexiones: ");
  t += connects;
  t += F(" · cortes: ");
  t += failures;
  if (lastFailure.length()) {
    t += F("\nÚltimo corte: ");
    t += lastFailure;
  }
  t += F("\nRegistros TLS: ");
  t += smallRecords == 1 ? F("2 kB") : F("16 kB");
  t += F("\nMemoria libre: ");
  t += ESP.getFreeHeap();
  t += F(" B (bloque mayor ");
  t += ESP.getMaxFreeBlockSize();
  t += F(" B)\nFirmware ");
  t += FW_VERSION;
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
  if (cmd == F("diagnostico") || cmd == F("diagnóstico") || cmd == F("diag")) return enqueue(chat, diagText());

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
    restartAfterAck = true;  // restarts once Telegram has confirmed this message (see handleResponse)
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
      t += String(text).substring(0, 60);
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

// Integer value of "key" in raw JSON text, searching from `from` (-1 if not found).
int64_t jsonIntAfter(const String& text, const char* key, int from = 0) {
  int p = text.indexOf(key, from);
  if (p < 0) return -1;
  const char* c = text.c_str() + p + strlen(key);
  while (*c == ' ' || *c == ':') c++;
  if (*c != '-' && !isdigit(static_cast<unsigned char>(*c))) return -1;
  return atoll(c);
}

// An update too large for the buffer (a very long message, or a reply quoting one): skip it,
// and tell the sender if the beginning of the response says who it was.
void handleOversize() {
  int64_t id = jsonIntAfter(resp, "\"update_id\"");
  if (id < 0) return;
  offset = id + 1;
  int c = resp.indexOf("\"chat\"");
  int64_t chat = c >= 0 ? jsonIntAfter(resp, "\"id\"", c) : -1;
  if (chat > 0 || chat < -1) enqueue(chat, F("Mensaje demasiado largo: envía solo la orden."));
  Serial.println(F("[tg] oversized update skipped"));
}


// ---------------------------------------------------------------- watchdog
// Last line of defence for causes nobody foresaw. It only counts time with Wi-Fi and a valid
// clock but no answer from Telegram, and escalates step by step.
#ifndef TELEGRAM_WD_SCALE  // host tests run it faster
#define TELEGRAM_WD_SCALE 1
#endif
constexpr uint32_t WD_RESET_MS = 5UL * 60000 / TELEGRAM_WD_SCALE;         // bot starts over
constexpr uint32_t WD_WIFI_MS = 10UL * 60000 / TELEGRAM_WD_SCALE;         // Wi-Fi rejoined
constexpr uint32_t WD_WIFI_REPEAT_MS = 30UL * 60000 / TELEGRAM_WD_SCALE;  // ... and again
constexpr uint32_t WD_RESTART_MS = 60UL * 60000 / TELEGRAM_WD_SCALE;      // device restart
constexpr uint32_t RTC_MAGIC = 0x54475744;  // "TGWD"

struct RtcRecord {
  uint32_t magic, restarts, downMin, check;
};

uint32_t downMs = 0;      // Wi-Fi up, Telegram silent, since the last answer
uint32_t wdTick = 0;
uint8_t wdStage = 0;
uint32_t wdWifiAt = 0;    // downMs at the last Wi-Fi rejoin
uint32_t safetyRestarts = 0;
uint32_t safetyDownMin = 0;
bool safetyBoot = false;
bool rtcChecked = false;

void checkRtc() {
  if (rtcChecked) return;
  rtcChecked = true;
  RtcRecord r{};
  if (telegramRtcRead(reinterpret_cast<uint32_t*>(&r), 4) && r.magic == RTC_MAGIC &&
      r.check == (r.magic ^ r.restarts ^ r.downMin) && telegramSoftRestart()) {
    safetyBoot = true;
    safetyRestarts = r.restarts;
    safetyDownMin = r.downMin;
  }
  RtcRecord clear{};
  telegramRtcWrite(reinterpret_cast<uint32_t*>(&clear), 4);
}

// Restarting must never switch the load: relay off, nothing about to switch it.
bool safeToRestart() {
  if (relay::isOn() || relay::timerActive() || relay::cycleActive()) return false;
  uint8_t idx;
  int32_t next = scheduler::nextEvent(idx);
  return next < 0 || next > 2;
}

void watchdog() {
  uint32_t now = millis();
  uint32_t dt = now - wdTick;
  wdTick = now;
  if (downMs < 0xF0000000UL) downMs += dt;

  if (wdStage < 1 && downMs >= WD_RESET_MS) {
    wdStage = 1;
    lastFailure = F("Vigilante: conexión del bot reiniciada");
    Serial.println(F("[tg] watchdog: restarting the bot connection"));
    link.forgetSession();
    telegram::reconnect();
  }
  if (downMs >= WD_WIFI_MS && (wdStage < 2 || downMs - wdWifiAt >= WD_WIFI_REPEAT_MS)) {
    wdStage = 2;
    wdWifiAt = downMs;
    lastFailure = F("Vigilante: Wi-Fi reconectado");
    Serial.println(F("[tg] watchdog: rejoining the Wi-Fi network"));
    network::reconnectWifi();
  }
  uint8_t shift = safetyRestarts < 4 ? safetyRestarts : 4;  // 1, 2, 4, 8, 16 h
  if (downMs >= (WD_RESTART_MS << shift) && safeToRestart()) {
    RtcRecord r{RTC_MAGIC, safetyRestarts + 1, downMs / 60000, 0};
    r.check = r.magic ^ r.restarts ^ r.downMin;
    telegramRtcWrite(reinterpret_cast<uint32_t*>(&r), 4);
    Serial.printf("[tg] watchdog: no answer for %lu min, restarting (relay off)\n",
                  (unsigned long)(downMs / 60000));
    link.close();
    phase = Phase::Idle;
    restarting = true;
    network::requestRestart(500);
  }
}

void markOk() {
  downMs = 0;
  wdStage = 0;
  safetyRestarts = 0;
  lastOkAt = millis();
  everOk = true;
  backoffStep = 0;
  error = String();
}

// Returns false if the connection must be dropped.
bool handleResponse(Req type, int status, const String& body) {
  if (status == 401 || status == 404) {
    haveMe = false;
    bot = String();
    error = F("Token no válido: revísalo en Ajustes");
    lastFailure = error;
    link.close();
    phase = Phase::Idle;
    retryAt = millis() + 600000;  // check again in 10 min, or as soon as the token changes
    return false;
  }
  if (status == 409) {
    goIdle(F("Otro programa está usando este bot (webhook u otro dispositivo)"));
    retryAt = millis() + 60000;
    return false;
  }
  if (status == 429 || status >= 500 || status == 0) {
    goIdle(String(F("Telegram respondió ")) + status);
    return false;
  }
  markOk();
  if (status != 200) {
    // Telegram refuses this request (user blocked the bot, chat not found...): drop it.
    Serial.printf("[tg] HTTP %d: %s\n", status, body.c_str());
    if (type == Req::Send) dequeue();
    return true;
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
    case Req::Send: dequeue(); break;
    case Req::Updates:
      if (restartAfterAck) {
        // This request carried the offset that confirms "/reiniciar", so it will not run again.
        network::requestRestart(300);
        restarting = true;
        link.close();
        phase = Phase::Idle;
        return false;
      }
      handleUpdates(body);
      break;
    default: break;
  }
  return true;
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

void nextRequest() {
  if (!haveMe) return beginRequest(Req::GetMe, "getMe", "{}");
  if (!commandsSet) return requestSetCommands();
  if (!bootNotified) {
    bootNotified = true;
    if (settings.tgNotify) {
      String t = F("🔌 ");
      t += settings.deviceName;
      t += F(" está en línea (");
      String reason = ESP.getResetReason();
      if (safetyBoot) {
        t += F("reinicio de seguridad: Telegram no respondió durante ");
        t += fmtDur(safetyDownMin * 60);
      } else {
        t += reason == F("Power On") || reason == F("External System") ? String(F("volvió la luz")) : reason;
      }
      t += F("). ");
      t += stateLine();
      t += '.';
      notifyAll(t);
    }
  }
  if (qLen) return requestSend();
  requestUpdates();
}

void pump() {
  switch (phase) {
    case Phase::Idle:
      if (reached(retryAt)) startConnect();
      return;

    case Phase::Handshake: {
      TlsLink::State st = link.poll();
      if (st == TlsLink::State::Ready) return onHandshakeDone();
      if (st == TlsLink::State::Failed) {
        if (retryWithFullBuffer(link.lastError())) return;
        return goIdle(linkErrorText(link.lastError()) + F(" · ") + ipText(currentIp) + F(" (") +
                      currentSrc + ')');
      }
      if (reached(phaseDeadline)) goIdle(F("Telegram no completó la conexión segura"));
      return;
    }

    case Phase::Ready:
      nextRequest();
      return;

    case Phase::Sending: {
      if (link.poll() != TlsLink::State::Ready) return goIdle(linkErrorText(link.lastError()));
      outPos += link.write(reinterpret_cast<const uint8_t*>(out.c_str()) + outPos, out.length() - outPos);
      if (outPos >= out.length()) {
        out = String();
        phase = Phase::Waiting;
      } else if (reached(phaseDeadline)) {
        goIdle(F("No se pudo enviar a Telegram"));
      }
      return;
    }

    case Phase::Waiting: {
      TlsLink::State st = link.poll();
      uint8_t buf[256];
      size_t n;
      while ((n = link.read(buf, sizeof(buf))) > 0) {
        if (resp.length() + n > MAX_RESPONSE) {
          respOverflow = true;
          break;
        }
        resp.concat(reinterpret_cast<const char*>(buf), n);
      }
      if (respOverflow) {
        if (inFlight == Req::Updates) handleOversize();
        return goIdle(F("Respuesta de Telegram demasiado grande"));
      }
      int status = 0;
      bool closeAfter = false;
      String body;
      int r = parseResponse(status, body, closeAfter);
      if (r < 0) return goIdle(F("Respuesta de Telegram no válida"));
      if (r == 0) {
        if (st != TlsLink::State::Ready) return goIdle(linkErrorText(link.lastError()));
        if (reached(phaseDeadline)) goIdle(F("Sin respuesta de Telegram"));
        return;
      }
      Req type = inFlight;
      inFlight = Req::None;
      resp = String();
      phase = Phase::Ready;
      if (!handleResponse(type, status, body)) return;
      if (phase == Phase::Ready && (closeAfter || st != TlsLink::State::Ready)) {
        // Server closed after this response (keep-alive limit): reconnect without counting it.
        link.close();
        phase = Phase::Idle;
        retryAt = millis();
      }
      return;
    }
  }
}
}  // namespace

namespace telegram {

bool wasSafetyRestart() {
  checkRtc();
  return safetyBoot;
}

void begin() {
  checkRtc();
  wdTick = millis();
  lastOn = relay::isOn();
  // Reserve the TLS memory right after boot, while the heap is still in one piece.
  if (settings.tgToken[0]) allocateTls();
}

void reconfigure() {
  link.close();
  phase = Phase::Idle;
  inFlight = Req::None;
  haveMe = commandsSet = false;
  bot = error = lastFailure = String();
  offset = 0;
  backoffStep = 0;
  retryAt = millis();
  while (qLen) dequeue();
  if (settings.tgToken[0]) allocateTls();
}

void reconnect() {
  link.close();
  phase = Phase::Idle;
  inFlight = Req::None;
  backoffStep = 0;
  attempt = 0;
  retryAt = millis();
  Serial.println(F("[tg] reconnect requested"));
}

void loop() {
  if (!settings.tgToken[0]) {
    if (phase != Phase::Idle) reconfigure();
    return;
  }
  if (restarting) return;
  trackRelay();
  bool online = network::staConnected() && scheduler::timeValid();
  if (!online) {
    if (phase != Phase::Idle) {
      link.close();
      phase = Phase::Idle;
      inFlight = Req::None;
    }
    wasOnNetwork = false;
    wdTick = millis();  // time without Wi-Fi is not the bot's failure
    return;
  }
  if (!wasOnNetwork) {
    // Wi-Fi just came (back): try at once instead of waiting for the backoff.
    wasOnNetwork = true;
    backoffStep = 0;
    retryAt = millis();
  }
  watchdog();
  if (restarting) return;
  if (!iobuf && !allocateTls()) return;
  // Several steps per call when there is progress (e.g. response read, next request sent).
  for (int i = 0; i < 4; i++) {
    Phase before = phase;
    pump();
    if (phase == before && phase != Phase::Ready) break;
  }
}

const char* state() {
  if (!settings.tgToken[0]) return "off";
  if (!network::staConnected() || !scheduler::timeValid()) return "waiting";
  if (error.length()) return "error";
  if (haveMe && (phase == Phase::Ready || phase == Phase::Sending || phase == Phase::Waiting)) return "online";
  return "connecting";
}

const String& botName() { return bot; }
const String& lastError() { return error; }

void describe(JsonObject o) {
  o["state"] = state();
  o["bot"] = bot;
  o["error"] = error;
  o["lastFailure"] = lastFailure;
  o["connects"] = connects;
  o["failures"] = failures;
  o["lastOk"] = everOk ? static_cast<int32_t>((millis() - lastOkAt) / 1000) : -1;
  o["records"] = smallRecords == 1 ? 2048 : smallRecords == 0 ? 16384 : 0;
  o["ip"] = ipText(currentIp);
  o["silentSec"] = downMs / 1000;
  o["safetyRestarts"] = safetyRestarts;
  o["ipSource"] = currentSrc;
}

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
