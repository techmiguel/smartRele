// SmartRele · rele-esp12f — firmware v1
//
// The relay is controlled over Wi-Fi only: on/off, state-change timer, cyclic ON/OFF
// routine and weekly schedules. Web interface and REST API on port 80.

#include <Arduino.h>

#include "board.h"
#include "network.h"
#include "relay.h"
#include "scheduler.h"
#include "settings.h"
#include "web.h"

void setup() {
  // First of all: relay at rest. R7 already keeps it open while the pin is high-impedance;
  // here the pin is driven low before anything else runs.
  digitalWrite(PIN_RELAY, LOW);
  pinMode(PIN_RELAY, OUTPUT);

  Serial.begin(115200);
  Serial.println();
  Serial.printf("\n[sys] SmartRele %s · reset reason: %s\n", FW_VERSION, ESP.getResetReason().c_str());

  if (!store::begin()) Serial.println(F("[fs] ERROR: no file system"));
  store::load();

  relay::begin();
  network::begin();
  scheduler::begin();
  web::begin();
  Serial.printf("[sys] ready: http://%s.local/\n", network::hostname().c_str());
}

void loop() {
  network::loop();
  web::loop();
  relay::loop();
  scheduler::loop();
}
