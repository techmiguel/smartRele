#include "tls_link.h"

#include <string.h>

#ifdef ARDUINO_ARCH_ESP8266
// BearSSL needs about 5.6 kB of stack, more than the 4 kB of the Arduino loop. These calls run
// the engine (and its cryptography) on the separate stack provided by the core (StackThunk).
#include <BearSSLHelpers.h>
#define br_ssl_engine_recvapp_ack BearSSL::thunk_br_ssl_engine_recvapp_ack
#define br_ssl_engine_recvapp_buf BearSSL::thunk_br_ssl_engine_recvapp_buf
#define br_ssl_engine_recvrec_ack BearSSL::thunk_br_ssl_engine_recvrec_ack
#define br_ssl_engine_recvrec_buf BearSSL::thunk_br_ssl_engine_recvrec_buf
#define br_ssl_engine_sendapp_ack BearSSL::thunk_br_ssl_engine_sendapp_ack
#define br_ssl_engine_sendapp_buf BearSSL::thunk_br_ssl_engine_sendapp_buf
#define br_ssl_engine_sendrec_ack BearSSL::thunk_br_ssl_engine_sendrec_ack
#define br_ssl_engine_sendrec_buf BearSSL::thunk_br_ssl_engine_sendrec_buf
#endif

void TlsLink::init(br_ssl_client_context* sc, br_x509_minimal_context* xc,
                   const br_x509_trust_anchor* anchors, size_t anchorCount) {
  sc_ = sc;
  xc_ = xc;
  br_ssl_client_init_full(sc_, xc_, anchors, anchorCount);
  br_ssl_engine_set_versions(&sc_->eng, BR_TLS12, BR_TLS12);
}

bool TlsLink::open(TcpTransport& tcp, const char* host, uint32_t ip, uint16_t port,
                   unsigned char* buf, size_t len, time_t now) {
  close();
  tcp_ = &tcp;
  error_ = 0;
  resumed_ = mfln_ = false;
  if (!tcp.connect(ip, port)) {
    fail(ERR_TCP_CONNECT);
    return false;
  }
  // Certificate dates are checked against this clock (days since year 0, seconds of the day).
  br_x509_minimal_set_time(xc_, static_cast<uint32_t>(now / 86400) + 719528,
                           static_cast<uint32_t>(now % 86400));
  br_ssl_engine_set_buffer(&sc_->eng, buf, len, 0);
  if (haveSession_) br_ssl_engine_set_session_parameters(&sc_->eng, &session_);
  if (!br_ssl_client_reset(sc_, host, haveSession_ ? 1 : 0)) {
    fail(br_ssl_engine_last_error(&sc_->eng));
    return false;
  }
  state_ = State::Handshake;
  poll();  // sends the ClientHello right away
  return state_ != State::Failed;
}

TlsLink::State TlsLink::poll() {
  if (state_ != State::Handshake && state_ != State::Ready) return state_;
  br_ssl_engine_context* eng = &sc_->eng;

  // Bounded loop: one pass per record moved, so a busy connection cannot hog the main loop.
  for (int pass = 0; pass < 8; pass++) {
    unsigned st = br_ssl_engine_current_state(eng);
    if (st & BR_SSL_CLOSED) {
      int err = br_ssl_engine_last_error(eng);
      fail(err ? err : ERR_TCP_CLOSED);
      return state_;
    }
    if (state_ == State::Handshake && (st & (BR_SSL_SENDAPP | BR_SSL_RECVAPP))) {
      state_ = State::Ready;
      mfln_ = br_ssl_engine_get_mfln_negotiated(eng);
      // Same session ID as offered = the server resumed it: no key exchange was needed.
      br_ssl_session_parameters now;
      br_ssl_engine_get_session_parameters(eng, &now);
      resumed_ = haveSession_ && now.session_id_len &&
                 now.session_id_len == session_.session_id_len &&
                 !memcmp(now.session_id, session_.session_id, now.session_id_len);
      session_ = now;
      haveSession_ = now.session_id_len > 0;
    }

    bool progress = false;
    if (st & BR_SSL_SENDREC) {
      size_t len;
      unsigned char* buf = br_ssl_engine_sendrec_buf(eng, &len);
      size_t room = tcp_->writable();
      if (room > len) room = len;
      if (room) {
        size_t n = tcp_->write(buf, room);
        if (n) {
          br_ssl_engine_sendrec_ack(eng, n);
          progress = true;
        }
      }
    }
    if (st & BR_SSL_RECVREC) {
      size_t avail = tcp_->available();
      if (avail) {
        size_t len;
        unsigned char* buf = br_ssl_engine_recvrec_buf(eng, &len);
        if (avail > len) avail = len;
        size_t n = tcp_->read(buf, avail);
        if (n) {
          br_ssl_engine_recvrec_ack(eng, n);  // decrypts; runs the handshake crypto
          progress = true;
        }
      }
    }
    if (!progress) break;
  }

  // Socket closed by the peer or the network: fatal once nothing is left to read.
  unsigned st = br_ssl_engine_current_state(eng);
  if (!tcp_->connected() && !tcp_->available() && !(st & BR_SSL_RECVAPP)) fail(ERR_TCP_CLOSED);
  return state_;
}

size_t TlsLink::write(const uint8_t* data, size_t len) {
  if (state_ != State::Ready) return 0;
  br_ssl_engine_context* eng = &sc_->eng;
  size_t done = 0;
  while (done < len) {
    if (!(br_ssl_engine_current_state(eng) & BR_SSL_SENDAPP)) break;  // record still going out
    size_t room;
    unsigned char* buf = br_ssl_engine_sendapp_buf(eng, &room);
    size_t n = len - done < room ? len - done : room;
    memcpy(buf, data + done, n);
    br_ssl_engine_sendapp_ack(eng, n);
    br_ssl_engine_flush(eng, 0);
    done += n;
    poll();
    if (state_ != State::Ready) break;
  }
  return done;
}

size_t TlsLink::read(uint8_t* out, size_t len) {
  if (state_ != State::Ready) {
    // Data that arrived just before the peer closed is still readable.
    if (state_ != State::Failed || error_ != ERR_TCP_CLOSED) return 0;
  }
  br_ssl_engine_context* eng = &sc_->eng;
  size_t done = 0;
  while (done < len && (br_ssl_engine_current_state(eng) & BR_SSL_RECVAPP)) {
    size_t avail;
    unsigned char* buf = br_ssl_engine_recvapp_buf(eng, &avail);
    size_t n = len - done < avail ? len - done : avail;
    memcpy(out + done, buf, n);
    br_ssl_engine_recvapp_ack(eng, n);
    done += n;
  }
  return done;
}

void TlsLink::close() {
  if (tcp_) tcp_->stop();
  if (state_ == State::Handshake || state_ == State::Ready) state_ = State::Closed;
  if (state_ == State::Failed) state_ = State::Closed;
}

void TlsLink::fail(int err) {
  error_ = err;
  state_ = State::Failed;
  // A failed handshake or a broken connection must not be resumed.
  if (err != ERR_TCP_CLOSED) haveSession_ = false;
}
