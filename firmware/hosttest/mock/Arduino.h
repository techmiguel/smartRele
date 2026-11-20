// Minimal Arduino API for building the Telegram bot on a PC (host tests only).
#pragma once

#include <cctype>
#include <cstdarg>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <ctime>
#include <string>

#define PROGMEM
#define PSTR(s) (s)
class __FlashStringHelper;
#define F(s) (reinterpret_cast<const __FlashStringHelper*>(s))
#define FPSTR(p) (reinterpret_cast<const __FlashStringHelper*>(p))

uint32_t millis();

class String {
 public:
  String() = default;
  String(const char* s) : s_(s ? s : "") {}
  String(const __FlashStringHelper* s) : s_(reinterpret_cast<const char*>(s)) {}
  String(const std::string& s) : s_(s) {}
  String(char c) : s_(1, c) {}
  String(int v) : s_(std::to_string(v)) {}
  String(unsigned v) : s_(std::to_string(v)) {}
  String(long v) : s_(std::to_string(v)) {}
  String(unsigned long v) : s_(std::to_string(v)) {}
  String(long long v) : s_(std::to_string(v)) {}
  String(unsigned long long v) : s_(std::to_string(v)) {}

  const char* c_str() const { return s_.c_str(); }
  unsigned length() const { return s_.size(); }
  bool isEmpty() const { return s_.empty(); }
  bool reserve(unsigned n) { s_.reserve(n); return true; }
  bool concat(const char* s) { if (s) s_ += s; return true; }
  bool concat(const char* s, unsigned n) { s_.append(s, n); return true; }
  bool concat(const String& s) { s_ += s.s_; return true; }
  bool concat(char c) { s_ += c; return true; }

  String& operator+=(const String& o) { s_ += o.s_; return *this; }
  String& operator+=(const char* o) { if (o) s_ += o; return *this; }
  String& operator+=(const __FlashStringHelper* o) { s_ += reinterpret_cast<const char*>(o); return *this; }
  String& operator+=(char c) { s_ += c; return *this; }
  String& operator+=(int v) { s_ += std::to_string(v); return *this; }
  String& operator+=(unsigned v) { s_ += std::to_string(v); return *this; }
  String& operator+=(long v) { s_ += std::to_string(v); return *this; }
  String& operator+=(unsigned long v) { s_ += std::to_string(v); return *this; }
  String& operator+=(long long v) { s_ += std::to_string(v); return *this; }
  String& operator+=(unsigned long long v) { s_ += std::to_string(v); return *this; }

  bool operator==(const String& o) const { return s_ == o.s_; }
  bool operator==(const char* o) const { return s_ == o; }
  bool operator==(const __FlashStringHelper* o) const { return s_ == reinterpret_cast<const char*>(o); }
  bool operator!=(const String& o) const { return s_ != o.s_; }
  char operator[](unsigned i) const { return s_[i]; }

  int indexOf(char c, unsigned from = 0) const { auto p = s_.find(c, from); return p == std::string::npos ? -1 : (int)p; }
  int indexOf(const char* t, unsigned from = 0) const { auto p = s_.find(t, from); return p == std::string::npos ? -1 : (int)p; }
  int indexOf(const __FlashStringHelper* t, unsigned from = 0) const { return indexOf(reinterpret_cast<const char*>(t), from); }
  int indexOf(const String& t, unsigned from = 0) const { return indexOf(t.c_str(), from); }
  String substring(unsigned a) const { return a >= s_.size() ? String() : String(s_.substr(a)); }
  String substring(unsigned a, unsigned b) const {
    if (b > s_.size()) b = s_.size();
    return a >= b ? String() : String(s_.substr(a, b - a));
  }
  long toInt() const { return atol(s_.c_str()); }
  void toLowerCase() { for (auto& c : s_) c = tolower((unsigned char)c); }
  void trim() {
    size_t a = s_.find_first_not_of(" \t\r\n");
    size_t b = s_.find_last_not_of(" \t\r\n");
    s_ = a == std::string::npos ? "" : s_.substr(a, b - a + 1);
  }
  bool startsWith(const char* p) const { return s_.rfind(p, 0) == 0; }
  bool endsWith(const char* p) const { size_t n = strlen(p); return s_.size() >= n && s_.compare(s_.size() - n, n, p) == 0; }
  bool endsWith(const __FlashStringHelper* p) const { return endsWith(reinterpret_cast<const char*>(p)); }
  void remove(unsigned i) { if (i < s_.size()) s_.erase(i); }
  void remove(unsigned i, unsigned n) { if (i < s_.size()) s_.erase(i, n); }

 private:
  std::string s_;
};

template <typename T>
String operator+(String a, const T& b) { a += b; return a; }
inline String operator+(String a, const char* b) { a += b; return a; }

struct HardwareSerial {
  void printf(const char* fmt, ...) __attribute__((format(printf, 2, 3)));
  void println(const char* s);
  void println(const __FlashStringHelper* s) { println(reinterpret_cast<const char*>(s)); }
};
extern HardwareSerial Serial;

struct EspClass {
  uint32_t getFreeHeap();
  uint32_t getMaxFreeBlockSize() { return getFreeHeap(); }
  String getResetReason() { return String("External System"); }
};
extern EspClass ESP;
