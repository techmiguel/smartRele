#include "network.h"

#include <ArduinoOTA.h>
#include <DNSServer.h>
#include <ESP8266WiFi.h>
#include <ESP8266mDNS.h>

#include "board.h"
#include "settings.h"

namespace {
String host;
String ap;
DNSServer dns;
bool apOn = false;
bool otaStarted = false;
uint32_t disconnectedSince = 0;
uint32_t restartAt = 0;
uint32_t buttonDownAt = 0;
WiFiEventHandler onGotIp, onDisconnected;

void startAp() {
  if (apOn) return;
  WiFi.mode(settings.wifiSsid[0] ? WIFI_AP_STA : WIFI_AP);
  WiFi.softAPConfig(IPAddress(192, 168, 4, 1), IPAddress(192, 168, 4, 1),
                    IPAddress(255, 255, 255, 0));
  WiFi.softAP(ap.c_str(), network::AP_PASSWORD);
  dns.setErrorReplyCode(DNSReplyCode::NoError);
  dns.start(53, "*", WiFi.softAPIP());
  apOn = true;
  Serial.printf("[wifi] AP \"%s\" up at %s\n", ap.c_str(), WiFi.softAPIP().toString().c_str());
}

void stopAp() {
  if (!apOn) return;
  dns.stop();
  WiFi.softAPdisconnect(true);
  WiFi.mode(WIFI_STA);
  apOn = false;
  Serial.println(F("[wifi] AP stopped"));
}

void startOta() {
  if (otaStarted) return;
  ArduinoOTA.setHostname(host.c_str());
  if (settings.adminPass[0]) ArduinoOTA.setPassword(settings.adminPass);
  ArduinoOTA.onStart([] { Serial.println(F("[ota] start")); });
  ArduinoOTA.onEnd([] { Serial.println(F("[ota] end")); });
  ArduinoOTA.onError([](ota_error_t e) { Serial.printf("[ota] error %u\n", e); });
  ArduinoOTA.begin(false);  // mDNS is handled by this module
  otaStarted = true;
}

// Blue LED: steady = connected; fast blink = setup AP;
// short flash every second = looking for the network; very fast blink = SW1 about to erase.
void updateLed() {
  uint32_t t = millis();
  bool on;
  if (buttonDownAt && t - buttonDownAt > 3000) on = (t / 60) & 1;
  else if (WiFi.isConnected()) on = true;
  else if (apOn) on = (t / 250) & 1;
  else on = (t % 1000) < 80;
  digitalWrite(PIN_WIFI_LED, on ? HIGH : LOW);
}

void handleButton() {
  bool pressed = digitalRead(PIN_BUTTON) == LOW;
  if (pressed && !buttonDownAt) buttonDownAt = millis() | 1;
  if (!pressed) buttonDownAt = 0;
  if (buttonDownAt && millis() - buttonDownAt > network::BUTTON_RESET_MS) {
    Serial.println(F("[btn] erasing Wi-Fi settings"));
    settings.wifiSsid[0] = 0;
    settings.wifiPass[0] = 0;
    store::save();
    buttonDownAt = 0;
    network::requestRestart(100);
  }
}
}  // namespace

namespace network {

const String& hostname() { return host; }
const String& apSsid() { return ap; }
bool staConnected() { return WiFi.isConnected(); }
bool apActive() { return apOn; }
bool captivePortal() { return apOn && !WiFi.isConnected(); }

void requestRestart(uint32_t delayMs) { restartAt = (millis() + delayMs) | 1; }

void begin() {
  pinMode(PIN_WIFI_LED, OUTPUT);
  digitalWrite(PIN_WIFI_LED, LOW);
  pinMode(PIN_BUTTON, INPUT);  // external R3 to 3.3 V

  char buf[24];
  snprintf(buf, sizeof(buf), "smartrele-%06x", ESP.getChipId());
  host = buf;
  snprintf(buf, sizeof(buf), "SmartRele-%06X", ESP.getChipId());
  ap = buf;
  if (!settings.deviceName[0]) strlcpy(settings.deviceName, host.c_str(), sizeof(settings.deviceName));

  WiFi.persistent(false);  // credentials live in config.json, not in the SDK flash area
  WiFi.setAutoReconnect(true);
  WiFi.hostname(host);
  WiFi.setSleepMode(WIFI_NONE_SLEEP);  // low web latency; power draw is not critical

  onGotIp = WiFi.onStationModeGotIP([](const WiFiEventStationModeGotIP& e) {
    Serial.printf("[wifi] connected to \"%s\", IP %s\n", settings.wifiSsid, e.ip.toString().c_str());
    disconnectedSince = 0;
  });
  onDisconnected = WiFi.onStationModeDisconnected([](const WiFiEventStationModeDisconnected&) {
    if (!disconnectedSince) disconnectedSince = millis() | 1;
  });

  if (settings.wifiSsid[0]) {
    WiFi.mode(WIFI_STA);
    WiFi.begin(settings.wifiSsid, settings.wifiPass);
    disconnectedSince = millis() | 1;
    Serial.printf("[wifi] connecting to \"%s\"\n", settings.wifiSsid);
  } else {
    startAp();
  }

  MDNS.begin(host.c_str());
  MDNS.addService("http", "tcp", 80);
  startOta();
}

void loop() {
  if (apOn) dns.processNextRequest();
  MDNS.update();
  ArduinoOTA.handle();
  handleButton();
  updateLed();

  if (settings.wifiSsid[0]) {
    bool connected = WiFi.isConnected();
    // No network for a minute: rescue AP (the station keeps retrying).
    if (!connected && !apOn && disconnectedSince && millis() - disconnectedSince > STA_FALLBACK_MS)
      startAp();
    // Network back: close the AP unless someone is connected to it.
    if (connected && apOn && WiFi.softAPgetStationNum() == 0) stopAp();
  }

  if (restartAt && static_cast<int32_t>(millis() - restartAt) >= 0) {
    Serial.println(F("[sys] restarting"));
    Serial.flush();
    ESP.restart();
  }
}

}  // namespace network
