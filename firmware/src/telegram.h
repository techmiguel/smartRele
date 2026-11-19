// Telegram bot: control the relay from anywhere on the Internet.
//
// The device opens an outgoing HTTPS connection to api.telegram.org and long-polls it for
// messages. Nothing has to be reachable from the Internet, so it works behind CGNAT, a phone
// hotspot or a router without port forwarding. Only the Telegram user IDs listed in the
// settings can control the relay; anyone else is only told their own ID.
//
// The connection is kept open between requests and read without blocking, so the web server,
// the timer and the schedules keep running while the bot waits for messages. Only the TLS
// handshake (about 1 s at 160 MHz) blocks the main loop, and it happens once per connection.
#pragma once

#include <Arduino.h>

namespace telegram {

constexpr uint16_t POLL_SEC = 25;      // long-poll length: also the worst-case notification delay
constexpr uint32_t MAX_AGE_SEC = 120;  // older commands (sent while offline) are not executed

void begin();
void loop();
void reconfigure();  // after the token changes

// State for the web interface: "off" (no token), "waiting" (no network or clock yet),
// "connecting", "online" or "error".
const char* state();
const String& botName();    // bot username, without "@", once known
const String& lastError();  // last error, in Spanish

bool validToken(const char* token);
// Parses "123, 456" into settings.tgUsers. Returns false if any entry is not a valid ID.
bool parseUsers(const char* text);
String usersText();  // "123, 456"

}  // namespace telegram
