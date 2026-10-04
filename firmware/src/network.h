// Wi-Fi: station, setup access point, mDNS, OTA, blue LED and SW1 push button.
#pragma once

#include <Arduino.h>

namespace network {

// WPA2 password of the "SmartRele-XXXXXX" setup access point.
constexpr const char* AP_PASSWORD = "smartrele";
// Without a network connection for this long, the AP is opened too so the device can be reconfigured.
constexpr uint32_t STA_FALLBACK_MS = 60000;
// SW1 press time that erases the Wi-Fi settings.
constexpr uint32_t BUTTON_RESET_MS = 8000;

void begin();
void loop();

const String& hostname();   // smartrele-xxxxxx (also the mDNS name)
const String& apSsid();     // SmartRele-XXXXXX
bool staConnected();
bool apActive();
bool captivePortal();       // true when requests must be redirected to the portal

void requestRestart(uint32_t delayMs = 800);  // deferred restart (lets the web server reply)

}  // namespace network
