// Local time (NTP + POSIX time zone) and weekly ON/OFF schedules.
#pragma once

#include <time.h>

#include "settings.h"

namespace scheduler {

void begin();        // applies the configured time zone and NTP server
void reconfigure();  // after changing the time zone or NTP server
void loop();

bool timeValid();               // false until the first sync (NTP or browser)
bool timeFromNtp();             // true once the time has come from NTP
void setManualTime(time_t utc); // time sent by the browser when there is no NTP

// Next enabled schedule: minutes until it (-1 if none) and its index.
int32_t nextEvent(uint8_t& index);

// Pure logic (no hardware), reusable in tests.
bool matches(const Schedule& s, const tm& t);
int32_t minutesUntil(const Schedule& s, const tm& t);  // -1 if it has no days

}  // namespace scheduler
