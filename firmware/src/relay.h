// K1 relay control: state, state-change timer and cyclic ON/OFF routine.
//
// Priority rules (every command arrives over Wi-Fi):
//  - A manual command or a weekly schedule stops the cyclic routine; the timer keeps running.
//  - Starting the timer stops the cyclic routine and vice versa: only one short-term
//    automation is active at a time.
//  - When the timer expires it runs its action once and becomes inactive.
#pragma once

#include "settings.h"

namespace relay {

constexpr uint32_t TIMER_MAX_SEC = 7UL * 24 * 3600;  // 7 days (fits in signed millis())
constexpr uint32_t CYCLE_MIN_SEC = 5;                // protects the contact's electrical life
constexpr uint32_t CYCLE_MAX_SEC = 24UL * 3600;

void begin();  // drives the pin low as early as possible and applies the power-on mode
void loop();

bool isOn();
void apply(RelayAction a, const char* source);  // direct command (stops the cyclic routine)
const char* lastSource();
uint32_t secondsSinceChange();

// Timer
bool startTimer(uint32_t seconds, RelayAction a);
void cancelTimer();
bool timerActive();
uint32_t timerRemaining();  // seconds
RelayAction timerAction();

// Cyclic routine
bool startCycle(uint32_t onSec, uint32_t offSec);
void stopCycle();
bool cycleActive();
uint32_t cyclePhaseRemaining();  // seconds to the next change

}  // namespace relay
