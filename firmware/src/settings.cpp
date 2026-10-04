#include "settings.h"

#include <ArduinoJson.h>
#include <LittleFS.h>

Settings settings;

namespace {
constexpr const char* CONFIG_PATH = "/config.json";
constexpr const char* STATE_PATH = "/state.json";
int8_t cachedState = -1;  // -1 = unknown; avoids rewriting the same value

void copyStr(char* dst, size_t size, const char* src) {
  if (!src) src = "";
  strlcpy(dst, src, size);
}
}  // namespace

namespace store {

const char* actionName(RelayAction a) {
  switch (a) {
    case RelayAction::Off: return "off";
    case RelayAction::On: return "on";
    default: return "toggle";
  }
}

bool parseAction(const char* s, RelayAction& out) {
  if (!s) return false;
  if (!strcmp(s, "on")) out = RelayAction::On;
  else if (!strcmp(s, "off")) out = RelayAction::Off;
  else if (!strcmp(s, "toggle")) out = RelayAction::Toggle;
  else return false;
  return true;
}

bool begin() {
  if (LittleFS.begin()) return true;
  Serial.println(F("[fs] LittleFS mount failed; formatting"));
  return LittleFS.format() && LittleFS.begin();
}

void load() {
  settings = Settings();
  File f = LittleFS.open(CONFIG_PATH, "r");
  if (!f) {
    Serial.println(F("[fs] no settings; using defaults"));
    return;
  }
  JsonDocument doc;
  DeserializationError err = deserializeJson(doc, f);
  f.close();
  if (err) {
    Serial.printf("[fs] invalid config.json (%s); using defaults\n", err.c_str());
    return;
  }

  copyStr(settings.deviceName, sizeof(settings.deviceName), doc["name"] | "");
  copyStr(settings.wifiSsid, sizeof(settings.wifiSsid), doc["ssid"] | "");
  copyStr(settings.wifiPass, sizeof(settings.wifiPass), doc["pass"] | "");
  copyStr(settings.adminPass, sizeof(settings.adminPass), doc["admin"] | "");
  copyStr(settings.tz, sizeof(settings.tz), doc["tz"] | "UTC0");
  copyStr(settings.ntpServer, sizeof(settings.ntpServer), doc["ntp"] | "pool.ntp.org");
  uint8_t pm = doc["powerOn"] | 0;
  settings.powerOn = pm <= 2 ? static_cast<PowerOnMode>(pm) : PowerOnMode::Off;

  JsonObject c = doc["cycle"];
  settings.cycle.enabled = c["enabled"] | false;
  settings.cycle.onSec = c["on"] | 60UL;
  settings.cycle.offSec = c["off"] | 60UL;

  settings.scheduleCount = 0;
  for (JsonObject s : doc["schedules"].as<JsonArray>()) {
    if (settings.scheduleCount >= MAX_SCHEDULES) break;
    Schedule& d = settings.schedules[settings.scheduleCount];
    d.enabled = s["en"] | true;
    d.days = (s["days"] | 0x7F) & 0x7F;
    d.hour = s["h"] | 0;
    d.minute = s["m"] | 0;
    uint8_t a = s["a"] | 1;
    d.action = a <= 2 ? static_cast<RelayAction>(a) : RelayAction::On;
    if (d.hour > 23 || d.minute > 59) continue;
    settings.scheduleCount++;
  }
}

bool save() {
  JsonDocument doc;
  doc["name"] = settings.deviceName;
  doc["ssid"] = settings.wifiSsid;
  doc["pass"] = settings.wifiPass;
  doc["admin"] = settings.adminPass;
  doc["tz"] = settings.tz;
  doc["ntp"] = settings.ntpServer;
  doc["powerOn"] = static_cast<uint8_t>(settings.powerOn);
  JsonObject c = doc["cycle"].to<JsonObject>();
  c["enabled"] = settings.cycle.enabled;
  c["on"] = settings.cycle.onSec;
  c["off"] = settings.cycle.offSec;
  JsonArray arr = doc["schedules"].to<JsonArray>();
  for (uint8_t i = 0; i < settings.scheduleCount; i++) {
    const Schedule& s = settings.schedules[i];
    JsonObject o = arr.add<JsonObject>();
    o["en"] = s.enabled;
    o["days"] = s.days;
    o["h"] = s.hour;
    o["m"] = s.minute;
    o["a"] = static_cast<uint8_t>(s.action);
  }

  // Write to a temporary file and rename it: a power loss in the middle of the write
  // cannot leave a truncated config.json.
  File f = LittleFS.open("/config.tmp", "w");
  if (!f) return false;
  size_t n = serializeJson(doc, f);
  f.close();
  if (n == 0) return false;
  LittleFS.remove(CONFIG_PATH);
  return LittleFS.rename("/config.tmp", CONFIG_PATH);
}

bool loadRelayState() {
  File f = LittleFS.open(STATE_PATH, "r");
  if (!f) return false;
  JsonDocument doc;
  bool on = !deserializeJson(doc, f) && (doc["relay"] | false);
  f.close();
  cachedState = on ? 1 : 0;
  return on;
}

void saveRelayState(bool on) {
  if (cachedState == (on ? 1 : 0)) return;
  File f = LittleFS.open(STATE_PATH, "w");
  if (!f) return;
  f.print(on ? F("{\"relay\":true}") : F("{\"relay\":false}"));
  f.close();
  cachedState = on ? 1 : 0;
}

void factoryReset() {
  LittleFS.remove(CONFIG_PATH);
  LittleFS.remove(STATE_PATH);
  settings = Settings();
  cachedState = -1;
}

}  // namespace store
