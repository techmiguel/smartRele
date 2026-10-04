// Pin assignment of the rele-esp12f board (checked against the schematic netlist).
#pragma once

#include <Arduino.h>

// GPIO5 -> R6 1 kΩ -> Q1 base (SS8050) -> K1 coil. R7 10 kΩ to GND keeps the relay open
// while the pin is high-impedance (reset, boot, flashing).
// The red LED D2 hangs from the same net: it lights up with the relay.
constexpr uint8_t PIN_RELAY = 5;  // active high

// GPIO4 -> R9 -> D3 (blue) -> GND
constexpr uint8_t PIN_WIFI_LED = 4;  // active high

// SW1 between GPIO0 and GND, R3 10 kΩ to 3.3 V. Held at boot = flashing mode.
// At run time it is only used to erase the Wi-Fi settings (long press);
// it does not control the relay in this version.
constexpr uint8_t PIN_BUTTON = 0;  // active low
