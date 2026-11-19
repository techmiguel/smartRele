#pragma once
#include <Arduino.h>
struct IPAddress {
  String toString() const { return String("192.168.43.20"); }
};
struct WiFiClass {
  int RSSI() { return -55; }
  IPAddress localIP() { return IPAddress(); }
};
extern WiFiClass WiFi;
