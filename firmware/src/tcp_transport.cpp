// Platform glue of the Telegram bot on the ESP8266: TCP through lwIP (WiFiClient), DNS and
// RTC memory.
#ifdef ARDUINO_ARCH_ESP8266

#include <ESP8266WiFi.h>
#include <lwip/dns.h>
#include <lwip/tcp.h>
// After lwIP, as in the core's own sources:
#include <include/ClientContext.h>

#include "tls_link.h"

namespace {
// WiFiClient around a connection opened here (its constructor from a ClientContext is protected).
class OwnedClient : public WiFiClient {
 public:
  OwnedClient() = default;
  explicit OwnedClient(ClientContext* c) : WiFiClient(c) {}
};

// TCP with a non-blocking connect: WiFiClient::connect() waits for the whole TCP handshake,
// which on a slow mobile link can take seconds (a lost SYN is only resent after 3 s). Here
// lwIP is asked to connect and calls back; meanwhile the relay, the web page and the timers
// keep running. Once connected, the lwIP socket is handed to a WiFiClient.
class EspTcp : public TcpTransport {
 public:
  bool begin(uint32_t ip, uint16_t port) override {
    stop();
    tcp_pcb* pcb = tcp_new();
    if (!pcb) return false;
    tcp_arg(pcb, this);
    tcp_err(pcb, &onError);
    status_ = 0;
    pending_ = pcb;
    IPAddress addr(ip);
    if (tcp_connect(pcb, addr, port, &onConnected) != ERR_OK) {
      abortPending();
      return false;
    }
    return true;
  }

  int8_t connectStatus() override {
    if (status_ == 1 && pending_) {
      tcp_pcb* pcb = pending_;
      pending_ = nullptr;
      tcp_arg(pcb, nullptr);
      tcp_err(pcb, nullptr);
      client_ = OwnedClient(new ClientContext(pcb, nullptr, nullptr));
      client_.setNoDelay(true);
      client_.setSync(false);  // write() returns once lwIP has the data; never waits for ACKs
      // Probe after 25 s of silence: keeps the mobile NAT entry alive during the 45 s long
      // poll and detects a dead path (network change, VPN switched on) in about 45 s.
      client_.keepAlive(25, 5, 4);
    }
    return status_;
  }
  bool connected() override { return status_ == 1 && client_.connected(); }
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
  void stop() override {
    abortPending();
    client_.abort();  // RST: frees the lwIP socket at once
    client_ = OwnedClient();
    status_ = 0;
  }

 private:
  void abortPending() {
    if (!pending_) return;
    tcp_arg(pending_, nullptr);
    tcp_err(pending_, nullptr);
    tcp_abort(pending_);
    pending_ = nullptr;
  }
  static err_t onConnected(void* arg, tcp_pcb*, err_t err) {
    auto self = static_cast<EspTcp*>(arg);
    if (self) self->status_ = err == ERR_OK ? 1 : -1;
    return ERR_OK;
  }
  static void onError(void* arg, err_t) {  // lwIP has already freed the socket
    auto self = static_cast<EspTcp*>(arg);
    if (!self) return;
    self->pending_ = nullptr;
    self->status_ = -1;
  }

  OwnedClient client_;
  tcp_pcb* pending_ = nullptr;
  volatile int8_t status_ = 0;
};

EspTcp tcp;

// Asynchronous DNS through lwIP. A late answer to an abandoned lookup is ignored (generation).
volatile uint32_t dnsGen = 0;
volatile int8_t dnsState = -1;
volatile uint32_t dnsIp = 0;

void onDns(const char*, const ip_addr_t* addr, void* arg) {
  if (reinterpret_cast<uintptr_t>(arg) != dnsGen) return;
  if (addr && IP_IS_V4(addr)) {
    dnsIp = ip4_addr_get_u32(ip_2_ip4(addr));
    dnsState = 1;
  } else {
    dnsState = -1;
  }
}
}  // namespace

TcpTransport& telegramTransport() { return tcp; }

// lwIP keeps answers in its cache for as long as their TTL says, up to a week. A carrier that
// answers with its top-up portal while the line has no credit can therefore leave a wrong
// address in the cache well after the top-up: the caller never relies on this answer alone.
bool telegramResolveStart(const char* host) {
  dnsGen = dnsGen + 1;
  dnsState = 0;
  ip_addr_t addr;
  err_t e = dns_gethostbyname(host, &addr, &onDns, reinterpret_cast<void*>(static_cast<uintptr_t>(dnsGen)));
  if (e == ERR_OK && IP_IS_V4(&addr)) {
    dnsIp = ip4_addr_get_u32(ip_2_ip4(&addr));
    dnsState = 1;
  } else if (e != ERR_INPROGRESS) {
    dnsState = -1;
  }
  return dnsState >= 0;
}

int8_t telegramResolvePoll(uint32_t& ip) {
  if (dnsState == 1) ip = dnsIp;
  return dnsState;
}

void telegramResolveCancel() { dnsGen = dnsGen + 1; }

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
