#include "web.h"

#include <ArduinoJson.h>
#include <ESP8266HTTPUpdateServer.h>
#include <ESP8266WebServer.h>
#include <ESP8266WiFi.h>

#include "network.h"
#include "relay.h"
#include "scheduler.h"
#include "settings.h"
#include "web_ui.h"

#ifndef FW_VERSION
#define FW_VERSION "dev"
#endif

namespace {
ESP8266WebServer server(80);
ESP8266HTTPUpdateServer updater;
constexpr const char* ADMIN_USER = "admin";

// ---------------------------------------------------------------- helpers
bool authorized() {
  if (!settings.adminPass[0]) return true;
  if (server.authenticate(ADMIN_USER, settings.adminPass)) return true;
  server.requestAuthentication(DIGEST_AUTH, "SmartRele");
  return false;
}

void sendJson(int code, const JsonDocument& doc) {
  String out;
  serializeJson(doc, out);
  server.sendHeader(F("Cache-Control"), F("no-store"));
  server.send(code, F("application/json"), out);
}

void sendError(int code, const __FlashStringHelper* msg) {
  JsonDocument doc;
  doc["error"] = msg;
  sendJson(code, doc);
}

void sendOk(const __FlashStringHelper* msg = nullptr) {
  JsonDocument doc;
  doc["ok"] = true;
  if (msg) doc["message"] = msg;
  sendJson(200, doc);
}

bool parseBody(JsonDocument& doc) {
  if (!server.hasArg(F("plain")) || deserializeJson(doc, server.arg(F("plain")))) {
    sendError(400, F("Invalid JSON"));
    return false;
  }
  return true;
}

// Wraps a handler with the password check.
template <typename F>
std::function<void()> guarded(F fn) {
  return [fn]() {
    if (authorized()) fn();
  };
}

bool parseHHMM(const char* s, uint8_t& h, uint8_t& m) {
  if (!s) return false;
  unsigned hh, mm;
  if (sscanf(s, "%u:%u", &hh, &mm) != 2 || hh > 23 || mm > 59) return false;
  h = hh;
  m = mm;
  return true;
}

void scheduleToJson(JsonObject o, const Schedule& s) {
  char t[8];  // "HH:MM"; extra room keeps -Wformat-truncation quiet
  snprintf(t, sizeof(t), "%02u:%02u", s.hour, s.minute);
  o["enabled"] = s.enabled;
  o["days"] = s.days;
  o["time"] = t;
  o["action"] = store::actionName(s.action);
}

// Applies the fields present in the JSON to a schedule. Returns false if any is invalid.
bool scheduleFromJson(JsonVariantConst j, Schedule& s) {
  if (j["enabled"].is<bool>()) s.enabled = j["enabled"];
  if (!j["days"].isNull()) {
    int d = j["days"] | -1;
    if (d < 1 || d > 0x7F) return false;
    s.days = d;
  }
  if (!j["time"].isNull() && !parseHHMM(j["time"], s.hour, s.minute)) return false;
  if (!j["action"].isNull() && !store::parseAction(j["action"], s.action)) return false;
  return true;
}

int scheduleIndexArg() {
  if (!server.hasArg(F("id"))) return -1;
  int id = server.arg(F("id")).toInt();
  return (id >= 0 && id < settings.scheduleCount) ? id : -1;
}

// ---------------------------------------------------------------- handlers
void handleStatus() {
  JsonDocument doc;
  doc["name"] = settings.deviceName;
  doc["host"] = network::hostname();
  doc["auth"] = settings.adminPass[0] != 0;

  JsonObject r = doc["relay"].to<JsonObject>();
  r["on"] = relay::isOn();
  r["source"] = relay::lastSource();
  r["since"] = relay::secondsSinceChange();

  JsonObject t = doc["timer"].to<JsonObject>();
  t["active"] = relay::timerActive();
  t["remaining"] = relay::timerRemaining();
  t["action"] = store::actionName(relay::timerAction());

  JsonObject c = doc["cycle"].to<JsonObject>();
  c["active"] = relay::cycleActive();
  c["on"] = settings.cycle.onSec;
  c["off"] = settings.cycle.offSec;
  c["remaining"] = relay::cyclePhaseRemaining();

  JsonArray arr = doc["schedules"].to<JsonArray>();
  for (uint8_t i = 0; i < settings.scheduleCount; i++)
    scheduleToJson(arr.add<JsonObject>(), settings.schedules[i]);

  uint8_t idx = 0;
  int32_t inMin = scheduler::nextEvent(idx);
  if (inMin >= 0) {
    JsonObject n = doc["next"].to<JsonObject>();
    scheduleToJson(n, settings.schedules[idx]);
    n["in"] = inMin;
  }

  JsonObject tm_ = doc["time"].to<JsonObject>();
  bool valid = scheduler::timeValid();
  tm_["valid"] = valid;
  tm_["ntp"] = scheduler::timeFromNtp();
  tm_["tz"] = settings.tz;
  if (valid) {
    time_t now = time(nullptr);
    tm lt;
    localtime_r(&now, &lt);
    char buf[24];
    strftime(buf, sizeof(buf), "%Y-%m-%d %H:%M:%S", &lt);
    tm_["epoch"] = static_cast<uint32_t>(now);
    tm_["local"] = buf;
  }

  JsonObject w = doc["wifi"].to<JsonObject>();
  w["ssid"] = settings.wifiSsid;
  w["connected"] = network::staConnected();
  if (network::staConnected()) {
    w["ip"] = WiFi.localIP().toString();
    w["rssi"] = WiFi.RSSI();
  }
  w["ap"] = network::apActive();
  w["apSsid"] = network::apSsid();

  JsonObject s = doc["sys"].to<JsonObject>();
  s["fw"] = FW_VERSION;
  s["uptime"] = millis() / 1000;
  s["heap"] = ESP.getFreeHeap();
  s["reset"] = ESP.getResetReason();
  sendJson(200, doc);
}

void handleRelay() {
  JsonDocument doc;
  if (!parseBody(doc)) return;
  RelayAction a;
  if (!store::parseAction(doc["action"], a)) return sendError(400, F("action: on, off or toggle"));
  relay::apply(a, "manual");
  sendOk();
}

void handleTimerStart() {
  JsonDocument doc;
  if (!parseBody(doc)) return;
  RelayAction a = RelayAction::Off;
  if (!doc["action"].isNull() && !store::parseAction(doc["action"], a))
    return sendError(400, F("action: on, off or toggle"));
  uint32_t sec = doc["seconds"] | 0UL;
  if (!relay::startTimer(sec, a)) return sendError(400, F("Duration between 1 s and 7 days"));
  sendOk(F("Timer started"));
}

void handleTimerCancel() {
  relay::cancelTimer();
  sendOk(F("Timer cancelled"));
}

void handleCycleStart() {
  JsonDocument doc;
  if (!parseBody(doc)) return;
  if (!relay::startCycle(doc["on"] | 0UL, doc["off"] | 0UL))
    return sendError(400, F("Each phase between 5 s and 24 h"));
  sendOk(F("Routine started"));
}

void handleCycleStop() {
  relay::stopCycle();
  sendOk(F("Routine stopped"));
}

void handleScheduleList() {
  JsonDocument doc;
  JsonArray arr = doc.to<JsonArray>();
  for (uint8_t i = 0; i < settings.scheduleCount; i++)
    scheduleToJson(arr.add<JsonObject>(), settings.schedules[i]);
  sendJson(200, doc);
}

void handleScheduleAdd() {
  JsonDocument doc;
  if (!parseBody(doc)) return;
  if (settings.scheduleCount >= MAX_SCHEDULES) return sendError(409, F("Maximum 16 schedules"));
  if (doc["time"].isNull()) return sendError(400, F("Missing time (HH:MM)"));
  Schedule s;
  if (!scheduleFromJson(doc, s)) return sendError(400, F("Invalid schedule"));
  settings.schedules[settings.scheduleCount++] = s;
  store::save();
  sendOk(F("Schedule added"));
}

void handleScheduleUpdate() {
  int id = scheduleIndexArg();
  if (id < 0) return sendError(404, F("No such schedule"));
  JsonDocument doc;
  if (!parseBody(doc)) return;
  Schedule s = settings.schedules[id];
  if (!scheduleFromJson(doc, s)) return sendError(400, F("Invalid schedule"));
  settings.schedules[id] = s;
  store::save();
  sendOk();
}

void handleScheduleDelete() {
  int id = scheduleIndexArg();
  if (id < 0) return sendError(404, F("No such schedule"));
  for (uint8_t i = id; i + 1 < settings.scheduleCount; i++) settings.schedules[i] = settings.schedules[i + 1];
  settings.scheduleCount--;
  store::save();
  sendOk(F("Schedule deleted"));
}

void handleConfigGet() {
  JsonDocument doc;
  doc["name"] = settings.deviceName;
  doc["tz"] = settings.tz;
  doc["ntp"] = settings.ntpServer;
  doc["powerOn"] = static_cast<uint8_t>(settings.powerOn);
  doc["ssid"] = settings.wifiSsid;
  doc["auth"] = settings.adminPass[0] != 0;
  JsonObject c = doc["cycle"].to<JsonObject>();
  c["on"] = settings.cycle.onSec;
  c["off"] = settings.cycle.offSec;
  sendJson(200, doc);
}

void handleConfigSet() {
  JsonDocument doc;
  if (!parseBody(doc)) return;
  bool timeChanged = false;
  if (doc["name"].is<const char*>()) {
    const char* n = doc["name"];
    if (!*n || strlen(n) >= sizeof(settings.deviceName)) return sendError(400, F("Name must be 1 to 32 characters"));
    strlcpy(settings.deviceName, n, sizeof(settings.deviceName));
  }
  if (doc["tz"].is<const char*>()) {
    const char* tz = doc["tz"];
    if (!*tz || strlen(tz) >= sizeof(settings.tz)) return sendError(400, F("Invalid time zone"));
    timeChanged |= strcmp(tz, settings.tz) != 0;
    strlcpy(settings.tz, tz, sizeof(settings.tz));
  }
  if (doc["ntp"].is<const char*>()) {
    const char* ntp = doc["ntp"];
    if (!*ntp || strlen(ntp) >= sizeof(settings.ntpServer)) return sendError(400, F("Invalid NTP server"));
    timeChanged |= strcmp(ntp, settings.ntpServer) != 0;
    strlcpy(settings.ntpServer, ntp, sizeof(settings.ntpServer));
  }
  if (!doc["powerOn"].isNull()) {
    int pm = doc["powerOn"] | -1;
    if (pm < 0 || pm > 2) return sendError(400, F("powerOn: 0, 1 or 2"));
    settings.powerOn = static_cast<PowerOnMode>(pm);
    if (settings.powerOn == PowerOnMode::Last) store::saveRelayState(relay::isOn());
  }
  bool passChanged = false;
  if (doc["adminPass"].is<const char*>()) {
    const char* p = doc["adminPass"];
    size_t len = strlen(p);
    if (len < 8 || len >= sizeof(settings.adminPass)) return sendError(400, F("Password must be 8 to 32 characters"));
    passChanged = strcmp(p, settings.adminPass) != 0;
    strlcpy(settings.adminPass, p, sizeof(settings.adminPass));
  }
  if (!store::save()) return sendError(500, F("Could not save"));
  if (timeChanged) scheduler::reconfigure();
  if (passChanged) {
    // ArduinoOTA and the web updater read the password at boot.
    network::requestRestart(1500);
    return sendOk(F("Saved. Restarting to apply the password"));
  }
  sendOk(F("Settings saved"));
}

void handleTime() {
  JsonDocument doc;
  if (!parseBody(doc)) return;
  uint32_t epoch = doc["epoch"] | 0UL;
  if (epoch < 1704067200UL) return sendError(400, F("Invalid epoch"));
  // NTP time wins: the browser time is only accepted while there is no sync.
  if (scheduler::timeFromNtp()) return sendOk();
  scheduler::setManualTime(epoch);
  sendOk(F("Time taken from the browser"));
}

void handleWifiScan() {
  int n = WiFi.scanComplete();
  JsonDocument doc;
  if (n == WIFI_SCAN_FAILED) {
    WiFi.scanNetworks(true, false);
    doc["scanning"] = true;
    return sendJson(202, doc);
  }
  if (n == WIFI_SCAN_RUNNING) {
    doc["scanning"] = true;
    return sendJson(202, doc);
  }
  JsonArray arr = doc["networks"].to<JsonArray>();
  for (int i = 0; i < n; i++) {
    if (WiFi.SSID(i).isEmpty()) continue;
    bool dup = false;  // several access points of the same network: list it once
    for (JsonObject o : arr) dup |= WiFi.SSID(i) == o["ssid"].as<const char*>();
    if (dup) continue;
    JsonObject o = arr.add<JsonObject>();
    o["ssid"] = WiFi.SSID(i);
    o["rssi"] = WiFi.RSSI(i);
    o["secure"] = WiFi.encryptionType(i) != ENC_TYPE_NONE;
  }
  WiFi.scanDelete();
  sendJson(200, doc);
}

void handleWifiSet() {
  JsonDocument doc;
  if (!parseBody(doc)) return;
  const char* ssid = doc["ssid"] | "";
  const char* pass = doc["pass"] | "";
  if (!*ssid || strlen(ssid) >= sizeof(settings.wifiSsid)) return sendError(400, F("SSID must be 1 to 32 characters"));
  size_t pl = strlen(pass);
  if ((pl > 0 && pl < 8) || pl >= sizeof(settings.wifiPass)) return sendError(400, F("Wi-Fi password must be 8 to 64 characters"));
  strlcpy(settings.wifiSsid, ssid, sizeof(settings.wifiSsid));
  strlcpy(settings.wifiPass, pass, sizeof(settings.wifiPass));
  if (!store::save()) return sendError(500, F("Could not save"));
  network::requestRestart(1500);
  sendOk(F("Saved. Restarting"));
}

void handleReboot() {
  network::requestRestart();
  sendOk(F("Restarting"));
}

void handleFactoryReset() {
  store::factoryReset();
  network::requestRestart();
  sendOk(F("Settings erased. Restarting"));
}

void handleRoot() {
  server.sendHeader(F("Cache-Control"), F("no-cache"));
  server.send_P(200, PSTR("text/html; charset=utf-8"), WEB_UI);
}

void handleNotFound() {
  // Captive portal: any request to another host is redirected to the device page,
  // which makes the phone open the setup page when it joins the AP.
  if (network::captivePortal() && server.hostHeader() != WiFi.softAPIP().toString()) {
    server.sendHeader(F("Location"), String(F("http://")) + WiFi.softAPIP().toString() + '/');
    server.send(302, F("text/plain"), "");
    return;
  }
  sendError(404, F("Not found"));
}
}  // namespace

namespace web {

void begin() {
  server.on(F("/"), HTTP_GET, guarded(handleRoot));
  server.on(F("/api/status"), HTTP_GET, guarded(handleStatus));
  server.on(F("/api/relay"), HTTP_POST, guarded(handleRelay));
  server.on(F("/api/timer"), HTTP_POST, guarded(handleTimerStart));
  server.on(F("/api/timer"), HTTP_DELETE, guarded(handleTimerCancel));
  server.on(F("/api/cycle"), HTTP_POST, guarded(handleCycleStart));
  server.on(F("/api/cycle"), HTTP_DELETE, guarded(handleCycleStop));
  server.on(F("/api/schedules"), HTTP_GET, guarded(handleScheduleList));
  server.on(F("/api/schedules"), HTTP_POST, guarded(handleScheduleAdd));
  server.on(F("/api/schedules"), HTTP_PUT, guarded(handleScheduleUpdate));
  server.on(F("/api/schedules"), HTTP_DELETE, guarded(handleScheduleDelete));
  server.on(F("/api/config"), HTTP_GET, guarded(handleConfigGet));
  server.on(F("/api/config"), HTTP_POST, guarded(handleConfigSet));
  server.on(F("/api/time"), HTTP_POST, guarded(handleTime));
  server.on(F("/api/wifi/scan"), HTTP_GET, guarded(handleWifiScan));
  server.on(F("/api/wifi"), HTTP_POST, guarded(handleWifiSet));
  server.on(F("/api/reboot"), HTTP_POST, guarded(handleReboot));
  server.on(F("/api/factory-reset"), HTTP_POST, guarded(handleFactoryReset));
  server.onNotFound(handleNotFound);

  // /update: firmware.bin upload from the browser (same credentials as the web UI).
  updater.setup(&server, "/update", ADMIN_USER, settings.adminPass);
  server.begin();
}

void loop() { server.handleClient(); }

}  // namespace web
