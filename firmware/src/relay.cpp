#include "relay.h"

#include "board.h"

namespace {
bool state = false;
const char* source = "boot";
uint32_t changedAt = 0;

bool timerOn = false;
uint32_t timerDeadline = 0;
RelayAction timerAct = RelayAction::Off;

bool cycleOn = false;
uint32_t cycleDeadline = 0;

// Comparison that survives the millis() rollover (every ~49.7 days).
bool reached(uint32_t deadline) { return static_cast<int32_t>(millis() - deadline) >= 0; }

uint32_t remainingSec(uint32_t deadline) {
  int32_t ms = static_cast<int32_t>(deadline - millis());
  return ms <= 0 ? 0 : (static_cast<uint32_t>(ms) + 999) / 1000;
}

void write(bool on, const char* src) {
  if (on != state) {
    state = on;
    digitalWrite(PIN_RELAY, on ? HIGH : LOW);
    changedAt = millis();
    Serial.printf("[relay] %s (%s)\n", on ? "ON" : "OFF", src);
  }
  source = src;
  // The state is not saved during the cyclic routine: it would switch every few seconds and
  // wear out the flash; after a power loss the routine resumes from the ON phase.
  if (settings.powerOn == PowerOnMode::Last && !cycleOn) store::saveRelayState(state);
}

void setCycleEnabled(bool en) {
  if (settings.cycle.enabled == en) return;
  settings.cycle.enabled = en;
  store::save();
}

void beginPhase(bool on) {
  write(on, "cycle");
  cycleDeadline = millis() + (on ? settings.cycle.onSec : settings.cycle.offSec) * 1000UL;
}
}  // namespace

namespace relay {

void begin() {
  digitalWrite(PIN_RELAY, LOW);
  pinMode(PIN_RELAY, OUTPUT);
  changedAt = millis();

  if (settings.cycle.enabled && settings.cycle.onSec >= CYCLE_MIN_SEC &&
      settings.cycle.offSec >= CYCLE_MIN_SEC) {
    cycleOn = true;
    beginPhase(true);
    return;
  }
  settings.cycle.enabled = false;

  bool on = false;
  switch (settings.powerOn) {
    case PowerOnMode::On: on = true; break;
    case PowerOnMode::Last: on = store::loadRelayState(); break;
    default: break;
  }
  write(on, "boot");
}

void loop() {
  if (timerOn && reached(timerDeadline)) {
    timerOn = false;
    bool target = timerAct == RelayAction::Toggle ? !state : timerAct == RelayAction::On;
    write(target, "timer");
  }
  if (cycleOn && reached(cycleDeadline)) beginPhase(!state);
}

bool isOn() { return state; }
const char* lastSource() { return source; }
uint32_t secondsSinceChange() { return (millis() - changedAt) / 1000; }

void apply(RelayAction a, const char* src) {
  stopCycle();
  bool target = a == RelayAction::Toggle ? !state : a == RelayAction::On;
  write(target, src);
}

bool startTimer(uint32_t seconds, RelayAction a) {
  if (seconds == 0 || seconds > TIMER_MAX_SEC) return false;
  stopCycle();
  timerAct = a;
  timerDeadline = millis() + seconds * 1000UL;
  timerOn = true;
  Serial.printf("[relay] timer: %s in %lu s\n", store::actionName(a), (unsigned long)seconds);
  return true;
}

void cancelTimer() { timerOn = false; }
bool timerActive() { return timerOn; }
uint32_t timerRemaining() { return timerOn ? remainingSec(timerDeadline) : 0; }
RelayAction timerAction() { return timerAct; }

bool startCycle(uint32_t onSec, uint32_t offSec) {
  if (onSec < CYCLE_MIN_SEC || offSec < CYCLE_MIN_SEC || onSec > CYCLE_MAX_SEC ||
      offSec > CYCLE_MAX_SEC)
    return false;
  cancelTimer();
  settings.cycle.onSec = onSec;
  settings.cycle.offSec = offSec;
  settings.cycle.enabled = false;  // forces setCycleEnabled to save
  setCycleEnabled(true);
  cycleOn = true;
  beginPhase(true);
  return true;
}

void stopCycle() {
  if (!cycleOn) return;
  cycleOn = false;
  setCycleEnabled(false);
  if (settings.powerOn == PowerOnMode::Last) store::saveRelayState(state);
}

bool cycleActive() { return cycleOn; }
uint32_t cyclePhaseRemaining() { return cycleOn ? remainingSec(cycleDeadline) : 0; }

}  // namespace relay
