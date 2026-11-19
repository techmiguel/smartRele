// Host test harness: runs the firmware's Telegram bot (telegram.cpp + tls_link.cpp) on a PC,
// with the relay, clock, Wi-Fi and storage replaced by stubs and a POSIX socket as TCP.
// test_bot.py starts it against a fake Bot API server that injects network faults.
//
// stdout: "EVENT ..." lines for the test; stderr: the firmware log.
// stdin: "wifi 0" / "wifi 1" (Wi-Fi lost / back), "stats", "quit".
#include <arpa/inet.h>
#include <errno.h>
#include <fcntl.h>
#include <malloc.h>
#include <netdb.h>
#include <netinet/in.h>
#include <netinet/tcp.h>
#include <poll.h>
#include <sys/socket.h>
#include <unistd.h>

#include <ESP8266WiFi.h>

#include <chrono>

#include "../src/network.h"
#include "../src/relay.h"
#include "../src/scheduler.h"
#include "../src/settings.h"
#include "../src/telegram.h"
#include "../src/tls_link.h"

// ---------------------------------------------------------------- Arduino mocks
HardwareSerial Serial;
EspClass ESP;
WiFiClass WiFi;
Settings settings;

static auto t0 = std::chrono::steady_clock::now();
uint32_t millis() {
  return (uint32_t)std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now() - t0).count();
}
void HardwareSerial::printf(const char* fmt, ...) {
  fprintf(stderr, "%7.3f ", millis() / 1000.0);
  va_list ap;
  va_start(ap, fmt);
  vfprintf(stderr, fmt, ap);
  va_end(ap);
}
void HardwareSerial::println(const char* s) { fprintf(stderr, "%7.3f %s\n", millis() / 1000.0, s); }
uint32_t EspClass::getFreeHeap() {
  // Not the ESP8266 heap: bytes in use by the process, reported so the test can check that
  // reconnections do not leak (it must stay flat).
  struct mallinfo2 mi = mallinfo2();
  return (uint32_t)mi.uordblks;
}

// ---------------------------------------------------------------- firmware stubs
static bool relayOn = false;
static const char* relaySrc = "boot";
static uint32_t relayChanged = 0;
static bool wifiUp = true;

namespace relay {
bool isOn() { return relayOn; }
void apply(RelayAction a, const char* src) {
  bool on = a == RelayAction::Toggle ? !relayOn : a == RelayAction::On;
  if (on != relayOn) relayChanged = millis();
  relayOn = on;
  relaySrc = src;
  printf("EVENT relay %s %s\n", on ? "on" : "off", src);
  fflush(stdout);
}
const char* lastSource() { return relaySrc; }
uint32_t secondsSinceChange() { return (millis() - relayChanged) / 1000; }
bool startTimer(uint32_t, RelayAction) { return true; }
void cancelTimer() {}
bool timerActive() { return false; }
uint32_t timerRemaining() { return 0; }
RelayAction timerAction() { return RelayAction::Off; }
bool startCycle(uint32_t, uint32_t) { return true; }
void stopCycle() {}
bool cycleActive() { return false; }
uint32_t cyclePhaseRemaining() { return 0; }
}  // namespace relay

namespace scheduler {
bool timeValid() { return true; }
int32_t nextEvent(uint8_t&) { return -1; }
}  // namespace scheduler

namespace network {
bool staConnected() { return wifiUp; }
void requestRestart(uint32_t) {
  printf("EVENT restart\n");
  fflush(stdout);
}
}  // namespace network

namespace store {
bool save() { return true; }
}  // namespace store

// ---------------------------------------------------------------- TCP over POSIX sockets
class HostTcp : public TcpTransport {
 public:
  bool connect(const char* host, uint16_t port) override {
    stop();
    if (!wifiUp) return false;
    fd_ = socket(AF_INET, SOCK_STREAM, 0);
    sockaddr_in a{};
    a.sin_family = AF_INET;
    a.sin_port = htons(atoi(getenv("TEST_PORT")));
    a.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
    if (getenv("TEST_REAL")) {  // the real host on the Internet
      addrinfo hints{}, *res = nullptr;
      hints.ai_family = AF_INET;
      hints.ai_socktype = SOCK_STREAM;
      if (getaddrinfo(host, nullptr, &hints, &res) || !res) return fail();
      a.sin_addr = ((sockaddr_in*)res->ai_addr)->sin_addr;
      a.sin_port = htons(port);
      freeaddrinfo(res);
    }
    fcntl(fd_, F_SETFL, O_NONBLOCK);
    int r = ::connect(fd_, (sockaddr*)&a, sizeof(a));
    if (r < 0 && errno != EINPROGRESS) return fail();
    pollfd p{fd_, POLLOUT, 0};
    if (poll(&p, 1, 3000) != 1) return fail();  // same 3 s limit as the ESP8266 transport
    int err = 0;
    socklen_t len = sizeof(err);
    getsockopt(fd_, SOL_SOCKET, SO_ERROR, &err, &len);
    if (err) return fail();
    int one = 1;
    setsockopt(fd_, IPPROTO_TCP, TCP_NODELAY, &one, sizeof(one));
    return true;
  }
  bool connected() override {
    if (fd_ < 0) return false;
    if (eof_) return false;
    pending();
    return !eof_;
  }
  size_t available() override { return pending(); }
  size_t read(uint8_t* buf, size_t len) override {
    if (fd_ < 0) return 0;
    ssize_t n = recv(fd_, buf, len, 0);
    if (n == 0) eof_ = true;
    return n > 0 ? n : 0;
  }
  size_t writable() override { return fd_ >= 0 && !eof_ ? 4096 : 0; }
  size_t write(const uint8_t* buf, size_t len) override {
    if (fd_ < 0) return 0;
    ssize_t n = send(fd_, buf, len, MSG_NOSIGNAL);
    if (n < 0 && errno != EAGAIN) eof_ = true;
    return n > 0 ? n : 0;
  }
  void stop() override {
    if (fd_ >= 0) close(fd_);
    fd_ = -1;
    eof_ = false;
  }

 private:
  bool fail() {
    stop();
    return false;
  }
  size_t pending() {
    if (fd_ < 0) return 0;
    char c;
    ssize_t n = recv(fd_, &c, 1, MSG_PEEK);
    if (n == 0) eof_ = true;
    if (n < 0 && errno != EAGAIN && errno != EWOULDBLOCK) eof_ = true;
    int avail = 0;
    if (n > 0) {
      // FIONREAD equivalent through a large peek
      static char tmp[65536];
      ssize_t m = recv(fd_, tmp, sizeof(tmp), MSG_PEEK);
      avail = m > 0 ? m : 0;
    }
    return avail;
  }
  int fd_ = -1;
  bool eof_ = false;
};

static HostTcp hostTcp;
TcpTransport& telegramTransport() { return hostTcp; }

// ---------------------------------------------------------------- main
int main() {
  strcpy(settings.deviceName, "Prueba");
  strcpy(settings.wifiSsid, "Hotspot");
  strcpy(settings.tgToken, getenv("TEST_TOKEN"));
  telegram::parseUsers("111");
  settings.tgNotify = true;
  fcntl(0, F_SETFL, O_NONBLOCK);

  telegram::begin();
  char line[128];
  size_t used = 0;
  for (;;) {
    telegram::loop();
    ssize_t n = read(0, line + used, sizeof(line) - 1 - used);
    if (n > 0) used += n;
    char* nl;
    while ((nl = (char*)memchr(line, '\n', used))) {
      *nl = 0;
      if (!strcmp(line, "quit")) return 0;
      if (!strncmp(line, "wifi ", 5)) wifiUp = line[5] == '1';
      if (!strcmp(line, "stats")) {
        JsonDocument d;
        telegram::describe(d.to<JsonObject>());
        std::string s;
        serializeJson(d, s);
        printf("EVENT stats %s heap=%u\n", s.c_str(), ESP.getFreeHeap());
        fflush(stdout);
      }
      size_t rest = used - (nl + 1 - line);
      memmove(line, nl + 1, rest);
      used = rest;
    }
    usleep(2000);
  }
}
