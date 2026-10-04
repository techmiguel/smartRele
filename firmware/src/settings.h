// Persistent settings in LittleFS (/config.json) and relay state (/state.json).
#pragma once

#include <Arduino.h>

constexpr uint8_t MAX_SCHEDULES = 16;

enum class RelayAction : uint8_t { Off = 0, On = 1, Toggle = 2 };
enum class PowerOnMode : uint8_t { Off = 0, On = 1, Last = 2 };

// Weekly schedule: at the given time, on the selected days, run the action.
struct Schedule {
  bool enabled = true;
  uint8_t days = 0x7F;  // bit0 = Sunday ... bit6 = Saturday (same as tm_wday)
  uint8_t hour = 0;
  uint8_t minute = 0;
  RelayAction action = RelayAction::On;
};

// Cyclic routine: ON for onSec, OFF for offSec, then start over.
struct CycleConfig {
  bool enabled = false;
  uint32_t onSec = 60;
  uint32_t offSec = 60;
};

struct Settings {
  char deviceName[33] = "";
  char wifiSsid[33] = "";
  char wifiPass[65] = "";
  char adminPass[33] = "";   // empty = web and OTA without password (not recommended)
  char tz[64] = "UTC0";      // POSIX time zone, e.g. "COT5" or "CET-1CEST,M3.5.0,M10.5.0/3"
  char ntpServer[48] = "pool.ntp.org";
  PowerOnMode powerOn = PowerOnMode::Off;
  CycleConfig cycle;
  Schedule schedules[MAX_SCHEDULES];
  uint8_t scheduleCount = 0;
};

extern Settings settings;

namespace store {
bool begin();                       // mounts LittleFS (formats it if corrupted)
void load();                        // loads /config.json or keeps the defaults
bool save();                        // writes /config.json
bool loadRelayState();              // last saved relay state
void saveRelayState(bool on);       // writes only on change (flash wear)
void factoryReset();                // erases all settings
const char* actionName(RelayAction a);
bool parseAction(const char* s, RelayAction& out);
}  // namespace store
