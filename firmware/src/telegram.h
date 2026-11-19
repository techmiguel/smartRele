// Telegram bot: control the relay from anywhere on the Internet.
//
// The device opens an outgoing HTTPS connection to api.telegram.org and long-polls it for
// messages. Nothing has to be reachable from the Internet, so it works behind CGNAT, a phone
// hotspot or a router without port forwarding. Only the Telegram user IDs listed in the
// settings can control the relay; anyone else is only told their own ID.
//
// The connection (tls_link.h) is kept open between requests and driven without blocking, so the
// web server, the timer and the schedules keep running while the bot waits for messages. Its
// memory is reserved once at boot. A dead connection (network change, VPN, hotspot without
// data) is detected within POLL_SEC + 8 s and retried every 1 to 20 s until it comes back.
#pragma once

#include <Arduino.h>
#include <ArduinoJson.h>

namespace telegram {

#ifndef TELEGRAM_POLL_SEC
#define TELEGRAM_POLL_SEC 20
#endif
constexpr uint16_t POLL_SEC = TELEGRAM_POLL_SEC;  // long-poll length: worst-case notification delay
constexpr uint32_t MAX_AGE_SEC = 120;  // older commands (sent while offline) are not executed

void begin();
void loop();
void reconfigure();  // after the token changes

// State for the web interface: "off" (no token), "waiting" (no network or clock yet),
// "connecting", "online" or "error".
const char* state();
const String& botName();    // bot username, without "@", once known
const String& lastError();  // last error, in Spanish
void describe(JsonObject o);  // state and connection statistics for /api/status

bool validToken(const char* token);
// Parses "123, 456" into settings.tgUsers. Returns false if any entry is not a valid ID.
bool parseUsers(const char* text);
String usersText();  // "123, 456"

}  // namespace telegram
