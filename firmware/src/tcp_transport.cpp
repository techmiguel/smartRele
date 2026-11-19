// TCP transport of the Telegram bot on the ESP8266 (lwIP through WiFiClient).
#ifdef ARDUINO_ARCH_ESP8266

#include <ESP8266WiFi.h>

#include "tls_link.h"

namespace {
constexpr uint32_t DNS_TIMEOUT_MS = 3000;
constexpr uint32_t CONNECT_TIMEOUT_MS = 3000;

class EspTcp : public TcpTransport {
 public:
  bool connect(const char* host, uint16_t port) override {
    stop();
    IPAddress ip;
    if (WiFi.hostByName(host, ip, DNS_TIMEOUT_MS) == 1 && ip.isSet()) {
      lastIp_ = ip;  // reused when DNS fails (for example right after a network change)
    } else if (lastIp_.isSet()) {
      ip = lastIp_;
    } else {
      return false;
    }
    client_.setTimeout(CONNECT_TIMEOUT_MS);
    if (!client_.connect(ip, port)) {
      lastIp_ = IPAddress();  // maybe stale: look it up again next time
      return false;
    }
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
  IPAddress lastIp_;
};

EspTcp tcp;
}  // namespace

TcpTransport& telegramTransport() { return tcp; }

#endif
