// Platform glue of the Telegram bot on the ESP8266: TCP through lwIP (WiFiClient), DNS and
// RTC memory.
#ifdef ARDUINO_ARCH_ESP8266

#include <ESP8266WiFi.h>

#include "tls_link.h"

namespace {
constexpr uint32_t DNS_TIMEOUT_MS = 3000;
constexpr uint32_t CONNECT_TIMEOUT_MS = 3000;

class EspTcp : public TcpTransport {
 public:
  bool connect(uint32_t ip, uint16_t port) override {
    stop();
    client_.setTimeout(CONNECT_TIMEOUT_MS);
    if (!client_.connect(IPAddress(ip), port)) return false;
    client_.setNoDelay(true);
    client_.setSync(false);  // write() returns once lwIP has the data; it never waits for ACKs
    // Probes after 15 s of silence: keeps the mobile NAT entry alive during the long poll and
    // detects a dead path (network change, VPN switched on) in about 30 s.
    client_.keepAlive(15, 5, 3);
    return true;
  }
  bool connected() override { return client_.connected(); }
  size_t available() override {
    int n = client_.available();
    return n > 0 ? n : 0;
  }
  size_t read(uint8_t* buf, size_t len) override {
    int n = client_.read(buf, len);
    return n > 0 ? n : 0;
  }
  size_t writable() override {
    int n = client_.availableForWrite();
    return n > 0 ? n : 0;
  }
  size_t write(const uint8_t* buf, size_t len) override { return client_.write(buf, len); }
  void stop() override { client_.abort(); }  // RST: frees the lwIP socket at once

 private:
  WiFiClient client_;
};

EspTcp tcp;
}  // namespace

TcpTransport& telegramTransport() { return tcp; }

// lwIP keeps answers in its cache for as long as their TTL says, up to a week. A carrier that
// answers with its top-up portal while the line has no credit can therefore leave a wrong
// address in the cache well after the top-up: the caller never relies on this answer alone.
bool telegramResolve(const char* host, uint32_t& ip) {
  IPAddress a;
  if (WiFi.hostByName(host, a, DNS_TIMEOUT_MS) != 1 || !a.isSet() || !a.isV4()) return false;
  ip = a.v4();
  return true;
}

// RTC user memory survives a software restart. Blocks 0-31 are left to the OTA boot loader.
constexpr uint32_t RTC_BLOCK = 96;
bool telegramRtcRead(uint32_t* data, size_t words) {
  return ESP.rtcUserMemoryRead(RTC_BLOCK, data, words * 4);
}
bool telegramRtcWrite(uint32_t* data, size_t words) {
  return ESP.rtcUserMemoryWrite(RTC_BLOCK, data, words * 4);
}
bool telegramSoftRestart() {
  const rst_info* r = ESP.getResetInfoPtr();
  return r && r->reason == REASON_SOFT_RESTART;
}

#endif
