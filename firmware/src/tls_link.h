// Non-blocking TLS 1.2 client over a TCP stream, built directly on BearSSL.
//
// Why not BearSSL::WiFiClientSecure: that class allocates its ~24 kB of buffers and contexts on
// every connect() and frees them on stop(). After a few reconnections the ESP8266 heap is too
// fragmented to find 16.7 kB in one piece again, and the bot goes silent until a restart. It
// also runs the handshake and every write in blocking loops of up to 15 s. Here the contexts and
// the buffer are allocated once by the caller and reused for every connection, and poll() only
// moves the bytes that are ready, so the main loop never waits on the network, not even for the
// TCP connection.
//
// The engine runs in half-duplex ("mono") mode: one buffer for both directions, which fits
// HTTP request/response traffic and saves the second buffer.
//
// The code is plain C++ on top of a TcpTransport interface, so the same file is built and
// tested on a PC (see firmware/hosttest/) against a TLS server that injects network faults.
#pragma once

#include <stddef.h>
#include <stdint.h>
#include <time.h>

#include <bearssl/bearssl.h>

// Plain TCP stream under the TLS link. Every call returns immediately.
class TcpTransport {
 public:
  virtual ~TcpTransport() = default;
  // Starts connecting to an IPv4 address in network byte order (as in lwIP and sockaddr_in).
  // False if it cannot even start.
  virtual bool begin(uint32_t ip, uint16_t port) = 0;
  virtual int8_t connectStatus() = 0;  // 0 still connecting, 1 connected, -1 failed
  virtual bool connected() = 0;
  virtual size_t available() = 0;
  virtual size_t read(uint8_t* buf, size_t len) = 0;
  virtual size_t writable() = 0;  // bytes write() accepts now without blocking
  virtual size_t write(const uint8_t* buf, size_t len) = 0;
  virtual void stop() = 0;  // immediate; frees the socket
};

class TlsLink {
 public:
  enum class State : uint8_t { Closed, Connecting, Handshake, Ready, Failed };

  // Error codes besides BearSSL's (BR_ERR_*, all positive).
  static constexpr int ERR_TCP_CONNECT = -1;  // TCP connection failed
  static constexpr int ERR_TCP_CLOSED = -2;   // the peer or the network closed the socket

  // The contexts outlive the link; they are configured once here.
  void init(br_ssl_client_context* sc, br_x509_minimal_context* xc,
            const br_x509_trust_anchor* anchors, size_t anchorCount);

  // Starts a connection to `ip`: TCP connect, then the handshake, both driven by poll(). The
  // caller decides how long to wait (state() stays Connecting or Handshake meanwhile).
  // The certificate is checked against `host`, whatever address it came from. `buf` is the
  // engine buffer: BR_SSL_BUFSIZE_MONO bytes for full-size records; a smaller buffer makes
  // BearSSL ask for smaller records (Max Fragment Length extension).
  bool open(TcpTransport& tcp, const char* host, uint32_t ip, uint16_t port, unsigned char* buf,
            size_t len, time_t now);

  State poll();  // moves pending bytes between TCP and the engine; never blocks
  // Queues application data (only when Ready) and pushes it out. Returns the bytes accepted,
  // which can be fewer than `len`: call again after poll() with the rest.
  size_t write(const uint8_t* data, size_t len);
  size_t read(uint8_t* out, size_t len);  // application data received so far
  void close();                           // drops the connection immediately
  void forgetSession() { haveSession_ = false; }  // next handshake starts from scratch

  State state() const { return state_; }
  int lastError() const { return error_; }
  bool smallRecords() const { return mfln_; }  // the server accepted the smaller record size
  bool resumed() const { return resumed_; }    // last handshake reused the previous session
  size_t received() const { return received_; }  // bytes received on this connection

 private:
  void fail(int err);
  void startHandshake();
  const char* host_ = nullptr;
  unsigned char* buf_ = nullptr;
  size_t bufLen_ = 0;
  time_t now_ = 0;
  br_ssl_client_context* sc_ = nullptr;
  br_x509_minimal_context* xc_ = nullptr;
  TcpTransport* tcp_ = nullptr;
  br_ssl_session_parameters session_{};
  bool haveSession_ = false;
  bool resumed_ = false;
  bool mfln_ = false;
  size_t received_ = 0;
  State state_ = State::Closed;
  int error_ = 0;
};
