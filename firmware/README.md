# SmartRele firmware · rele-esp12f

Firmware v1.0.0 for the rele-esp12f board (ESP-12F / ESP8266). The relay is **controlled over Wi-Fi only**, from a built-in web interface or through a JSON REST API:

- **Manual on / off.**
- **State-change timer**: after a delay (1 s to 7 days) it turns the relay on, off or toggles it.
- **Cyclic ON/OFF routine**: on for one period and off for another, repeated indefinitely.
- **Weekly schedules**: up to 16 rules of the form "at HH:MM, on these days, turn on/off/toggle".

Push button SW1 does not control the relay in this version: it only erases the Wi-Fi settings.

## Hardware used

| GPIO | Function | Active level |
|---|---|---|
| GPIO5 | Relay K1 (through Q1) and red LED D2 | High |
| GPIO4 | Blue LED D3 (Wi-Fi status) | High |
| GPIO0 | Push button SW1 (R3 to 3.3 V) | Low |

Pins checked against the schematic netlist. R7 (10 kΩ to GND) keeps the relay open while GPIO5 is high-impedance (reset, boot and flashing); the firmware also drives the pin low as its very first instruction.

## Build and flash

Requires [PlatformIO](https://platformio.org/) (CLI or the VS Code extension). From this folder:

```bash
pio run -e esp12f
```

First flashing through header J3 (see the [main README](../README.md#first-firmware-flashing): board **disconnected from the mains**, 3.3 V USB-serial adapter, J3 powered at 5 V, hold SW1 while releasing SW2):

```bash
pio run -e esp12f -t upload
```

Serial monitor (115200 baud), useful to see the IP address and relay events:

```bash
pio device monitor
```

### Over-the-air updates (OTA)

Once the device is on the network there are two options, both protected by the admin password:

- **Browser**: *System → Update firmware* (`http://<device>/update`) and upload `.pio/build/esp12f/firmware.bin`.
- **PlatformIO** (ArduinoOTA): set the environment variable `SMARTRELE_PASS` to the admin password and run:

```bash
pio run -e esp12f_ota -t upload --upload-port smartrele-xxxxxx.local
```

The relay keeps its state while the update is written. The restart that follows briefly releases it, and then the *state at power-up* setting (or the cyclic routine, if it was active) is applied.

## Getting started

1. With no network configured, the device creates the access point **`SmartRele-XXXXXX`** (password `smartrele`). The blue LED blinks fast.
2. Join it from a phone. The setup page opens by itself; if it does not, browse to `http://192.168.4.1`.
3. Under *Settings*, set an **admin password** (user `admin`, 8–32 characters) and the time zone.
4. Under *Wi-Fi network*, pick the network, enter its password and press *Save and restart*.
5. The device joins the network (blue LED steady) and is reachable at `http://smartrele-xxxxxx.local/` (mDNS) or at the IP address the router assigns (shown on the serial monitor and in the router).

`XXXXXX` is the chip ID in hexadecimal, different on every board.

If the network is unavailable for 60 s, the access point opens again (the device keeps retrying the network) so the settings can be changed. It closes as soon as the network is back and nobody is connected to it.

**Erasing the Wi-Fi network**: hold SW1 for **8 s** (from 3 s on, the blue LED blinks very fast). The device restarts in access point mode. Schedules and the password are kept; to erase everything use *Factory reset* in the web interface.

### Blue LED (D3)

| Pattern | Meaning |
|---|---|
| Steady | Connected to the Wi-Fi network |
| Short flash every second | Looking for the network |
| Fast blink (2 Hz) | Setup access point active |
| Very fast blink | SW1 held: at 8 s the network is erased |

The red LED (D2) is wired in parallel with the relay driver: lit = relay closed.

## Behaviour

### Priorities between automations

| Command | Cyclic routine | Timer |
|---|---|---|
| Manual (web/API) | Stops it | Keeps running |
| Weekly schedule | Stops it | Keeps running |
| Start timer | Stops it | — |
| Start cyclic routine | — | Cancels it |

The timer and the cyclic routine cannot be active at the same time. When the timer expires it runs its action once.

### Time and schedules

- The time comes from **NTP** (`pool.ntp.org` by default) and is converted to local time with the configured **POSIX time zone** (the web interface lists those of Latin America, the US and Europe; any other can be typed in). The default is UTC.
- Without Internet access (for example, using only the access point) the web page sends the browser time when it opens. NTP time always takes precedence.
- Schedules do not run until the time is valid; the timer and the cyclic routine do, because they only use the internal clock.
- Each schedule runs once in its minute. After a restart it only runs if the device boots within the first 10 s of that minute. Schedules missed during a power cut are not caught up.
- When daylight saving time ends, a schedule inside the repeated hour may run twice.

### After a power cut

| Situation when power returns | Behaviour |
|---|---|
| Cyclic routine active | Resumes, starting with the ON phase |
| *State at power-up* = Off (default) | Relay open |
| = On | Relay closed |
| = Last state | State before the power cut |

The timer does **not** survive a restart. Schedules, the cyclic routine and the settings are stored in flash (LittleFS). The last relay state is only written when it changes, and never during the cyclic routine, to avoid wearing out the flash.

### Limits

| Parameter | Range |
|---|---|
| Timer | 1 s – 7 days |
| Cyclic routine phase | 5 s – 24 h |
| Schedules | 16 |

The 5 s minimum per phase prevents absurdly fast switching, but it is not enough for the relay to last: the Omron datasheet guarantees **50,000–100,000 electrical operations** at rated load (depending on the model). A 5 s ON / 5 s OFF routine makes 360 operations per hour and would use up 50,000 in less than a week; a 10 min ON / 50 min OFF routine would take more than five years. Choose phases as long as the application allows.

## REST API

All routes take and return JSON. When an admin password is set, **HTTP Digest** authentication is used with user `admin`. Examples with `curl`:

```bash
curl --digest -u admin:PASSWORD http://smartrele-xxxxxx.local/api/status
```

```bash
curl --digest -u admin:PASSWORD -X POST -H "Content-Type: application/json" -d '{"action":"on"}' http://smartrele-xxxxxx.local/api/relay
```

| Method and route | Body | Function |
|---|---|---|
| `GET /api/status` | — | Full status: relay, timer, routine, schedules, next event, time, Wi-Fi and system |
| `POST /api/relay` | `{"action":"on"\|"off"\|"toggle"}` | Direct command |
| `POST /api/timer` | `{"seconds":1800,"action":"off"}` | Starts the timer (`action` defaults to `off`) |
| `DELETE /api/timer` | — | Cancels the timer |
| `POST /api/cycle` | `{"on":600,"off":3000}` | Starts the cyclic routine (seconds) |
| `DELETE /api/cycle` | — | Stops the cyclic routine |
| `GET /api/schedules` | — | List of schedules |
| `POST /api/schedules` | `{"time":"07:30","days":62,"action":"on","enabled":true}` | Adds a schedule |
| `PUT /api/schedules?id=N` | Any field of the above | Modifies schedule N (0-based index) |
| `DELETE /api/schedules?id=N` | — | Deletes schedule N |
| `GET /api/config` | — | Settings (without passwords) |
| `POST /api/config` | `{"name","tz","ntp","powerOn":0\|1\|2,"adminPass"}` | Changes settings; every field is optional |
| `POST /api/time` | `{"epoch":1767225600}` | Sets the clock when there is no NTP |
| `GET /api/wifi/scan` | — | Scans for networks (replies 202 while scanning) |
| `POST /api/wifi` | `{"ssid":"...","pass":"..."}` | Stores the network and restarts |
| `POST /api/reboot` | — | Restarts |
| `POST /api/factory-reset` | — | Erases all settings and restarts |

`days` is a bit mask with Sunday in bit 0: Monday to Friday = 62, weekends = 65, every day = 127.

Changing the admin password restarts the device, because ArduinoOTA and `/update` read it at boot.

## Security

- **Always set an admin password.** Without it, anyone on the network (or on the access point, whose password is public) can switch the relay.
- The web interface uses plain HTTP. Digest authentication does not send the password in clear text, but the rest of the traffic is unencrypted: use it only on your local network and do not expose it to the Internet by forwarding ports on the router.
- Passwords are stored unencrypted in the module flash. Anyone with physical access to the board can read them.
- **Never connect the serial adapter to J3 while the board is connected to the mains.**

## Layout

```
firmware/
├── platformio.ini     esp12f (serial) and esp12f_ota (network) environments
└── src/
    ├── main.cpp       Start-up and main loop
    ├── board.h        Pin assignment
    ├── settings.*     Persistent settings (LittleFS, JSON)
    ├── relay.*        Relay, timer and cyclic routine
    ├── scheduler.*    Time (NTP / time zone) and weekly schedules
    ├── network.*      Wi-Fi, access point, captive portal, mDNS, OTA, LED and SW1
    ├── web.*          HTTP server and REST API
    └── web_ui.h       Embedded web interface
```

Dependencies: Arduino core for ESP8266 (PlatformIO `espressif8266` platform) and [ArduinoJson](https://arduinojson.org/) 7, which PlatformIO downloads automatically.
