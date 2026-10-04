#include "scheduler.h"

#include <Arduino.h>
#include <coredecls.h>  // settimeofday_cb
#include <sys/time.h>

#include "relay.h"

namespace {
// Any date before 2024 means "no time yet" (the ESP8266 boots in 1970).
constexpr time_t VALID_EPOCH = 1704067200;  // 2024-01-01 00:00 UTC

bool ntpSynced = false;
uint32_t lastMinuteKey = 0;
uint32_t lastCheck = 0;
}  // namespace

namespace scheduler {

bool matches(const Schedule& s, const tm& t) {
  return s.enabled && (s.days & (1 << t.tm_wday)) && s.hour == t.tm_hour && s.minute == t.tm_min;
}

int32_t minutesUntil(const Schedule& s, const tm& t) {
  if (!(s.days & 0x7F)) return -1;
  int32_t nowMin = t.tm_hour * 60 + t.tm_min;
  int32_t evMin = s.hour * 60 + s.minute;
  for (int d = 0; d <= 7; d++) {
    int wday = (t.tm_wday + d) % 7;
    if (!(s.days & (1 << wday))) continue;
    int32_t delta = d * 1440 + evMin - nowMin;
    if (delta > 0) return delta;  // the current minute has already run or is running
  }
  return -1;
}

void begin() {
  settimeofday_cb([](bool fromSntp) {
    if (fromSntp) ntpSynced = true;
    Serial.printf("[time] clock set (%s)\n", fromSntp ? "NTP" : "manual");
  });
  reconfigure();
}

void reconfigure() { configTime(settings.tz, settings.ntpServer); }

bool timeValid() { return time(nullptr) > VALID_EPOCH; }
bool timeFromNtp() { return ntpSynced; }

void setManualTime(time_t utc) {
  timeval tv = {utc, 0};
  settimeofday(&tv, nullptr);
}

int32_t nextEvent(uint8_t& index) {
  if (!timeValid()) return -1;
  time_t now = time(nullptr);
  tm t;
  localtime_r(&now, &t);
  int32_t best = -1;
  for (uint8_t i = 0; i < settings.scheduleCount; i++) {
    if (!settings.schedules[i].enabled) continue;
    int32_t m = minutesUntil(settings.schedules[i], t);
    if (m >= 0 && (best < 0 || m < best)) {
      best = m;
      index = i;
    }
  }
  return best;
}

void loop() {
  if (millis() - lastCheck < 500) return;
  lastCheck = millis();
  if (!timeValid()) return;

  time_t now = time(nullptr);
  uint32_t key = static_cast<uint32_t>(now / 60);
  if (key == lastMinuteKey) return;
  // A small backward correction (NTP resync) must not repeat schedules that already ran;
  // wait until the clock moves forward again. A forward jump only evaluates the current
  // minute (skipped minutes are not caught up).
  if (key < lastMinuteKey && lastMinuteKey - key <= 2) return;
  bool first = lastMinuteKey == 0;
  lastMinuteKey = key;

  tm t;
  localtime_r(&now, &t);
  // In the first valid minute after boot, schedules run only within its first seconds;
  // so a restart at 08:00:40 does not repeat the 08:00 schedule.
  if (first && t.tm_sec > 10) return;

  for (uint8_t i = 0; i < settings.scheduleCount; i++) {
    const Schedule& s = settings.schedules[i];
    if (!matches(s, t)) continue;
    Serial.printf("[sched] schedule %u: %s at %02u:%02u\n", i, store::actionName(s.action),
                  s.hour, s.minute);
    relay::apply(s.action, "schedule");
  }
}

}  // namespace scheduler
