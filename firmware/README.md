# SmartRele firmware · rele-esp12f

Firmware v1.3.0 for the rele-esp12f board (ESP-12F / ESP8266). The relay is **controlled over Wi-Fi only**, from a built-in web interface (in Spanish) or through a JSON REST API:

- **Manual on / off**, with the time the output has been on in the current ON period.
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

### Flashing with an ESP32-S3 DevKitC-1 as USB-serial bridge

Any ESP32-S3 DevKitC-1 (or clone) with two USB ports, "USB" and "UART", can replace the USB-serial adapter. The S3 is held **in reset** (EN tied to GND), which leaves its GPIO43/44 in high impedance so that its on-board USB-UART chip (CP2102N or CH343) talks directly to the ESP-12F. Nothing is flashed on the S3.

| ESP32-S3 DevKitC-1 | J3 (relay board) | Net | ESP-12F pad |
|---|---|---|---|
| EN → GND of the S3 itself | — | — | — |
| GND | J3-1 (square pad) | GND | 15 |
| 5V | J3-2 | +5V | — (through U1) |
| TX (GPIO43) | J3-3 | TXD | 22 (TXD0) |
| RX (GPIO44) | J3-4 | RXD | 21 (RXD0) |
| — | J3-5, J3-6 (GPIO0, RST) | — | use SW1 / SW2 |

- **TX goes to TX and RX to RX.** The DevKit labels name the S3 pins, not the bridge chip pins. The bridge transmits into the S3 RX (GPIO44) and receives from the S3 TX (GPIO43), so the crossover is already done on the DevKit.
- Plug the cable into the **"UART"** port. The DevKit 5V pin (USB VBUS) powers the board; do not use its 3V3 pin.
- Check the bridge first: with EN tied to GND, short TX to RX on the S3, open `pio device monitor -p COMx` and confirm that typed characters echo back.
- DTR/RTS are not wired to J3, so enter flashing mode by hand: hold SW1, press and release SW2, release SW1. Do this before each command:

```bash
pio run -e esp12f -t erase --upload-port COMx
```

```bash
pio run -e esp12f -t upload --upload-port COMx
```

- Then press SW2 to start the firmware. If the upload fails at 460800 baud, set `upload_speed = 115200` temporarily.
- The web interface is embedded in the firmware, so `uploadfs` is not needed.

Serial monitor (115200 baud), useful to see the IP address and relay events:

```bash
pio device monitor
```

### Over-the-air updates (OTA)

Once the device is on the network there are two options, both protected by the admin password:

- **Browser**: *Ajustes → Actualizar firmware* (`http://<device>/update`) and upload `.pio/build/esp12f/firmware.bin`.
- **PlatformIO** (ArduinoOTA): set the environment variable `SMARTRELE_PASS` to the admin password and run:

```bash
pio run -e esp12f_ota -t upload --upload-port smartrele-xxxxxx.local
```

The relay keeps its state while the update is written. The restart that follows briefly releases it, and then the *state at power-up* setting (or the cyclic routine, if it was active) is applied.

## Getting started

1. With no network configured, the device creates the access point **`SmartRele-XXXXXX`** (password `smartrele`). The blue LED blinks fast.
2. Join it from a phone. The setup page opens by itself; if it does not, browse to `http://192.168.4.1`.
3. The main page shows the device name, a large remote-control style button and the time spent in the current state.
   - The button shows the action it will perform: **ON** with a green ring while the output is off, **OFF** with a red ring while it is on.
   - Three buttons at the bottom open simple panels:
     - **Temporizador**: hour/minute/second wheels and an ENCENDER/APAGAR toggle.
     - **Rutina**: ON and OFF times of the cyclic routine.
     - **Ajustes**: name, state at power-up, admin password, name and password of the device's own access point, Wi-Fi, firmware update and restart.
   - Under *Ajustes*, set an **admin password** (user `admin`, 8–32 characters).
4. Under *Ajustes → Red Wi-Fi*, pick the network, enter its password and press *Conectar*.
5. The device joins the network (blue LED steady) and is reachable at `http://smartrele-xxxxxx.local/` (mDNS) or at the IP address the router assigns (shown on the serial monitor and in the router).

`XXXXXX` is the chip ID in hexadecimal, different on every board. The access point name (1–32 characters) and password (8–63 characters) can be changed under *Ajustes → Wi-Fi propia del relé*; the device restarts to apply them.

If the network is unavailable for 60 s, the access point opens again (the device keeps retrying the network) so the settings can be changed. It closes as soon as the network is back and nobody is connected to it.

**Erasing the Wi-Fi network**: hold SW1 for **8 s** (from 3 s on, the blue LED blinks very fast). The device restarts in access point mode, with the default name and password `smartrele`. Schedules and the admin password are kept; to erase everything use `POST /api/factory-reset`.

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

- The time comes from **NTP** (`pool.ntp.org` by default) and is converted to local time with the configured **POSIX time zone** (`tz` field of `POST /api/config`). The default is UTC. Since v1.2.0 the web interface does not show the weekly schedules or the time zone: they are managed through the REST API.
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
| `POST /api/config` | `{"name","tz","ntp","powerOn":0\|1\|2,"adminPass","apSsid","apPass"}` | Changes settings; every field is optional |
| `POST /api/time` | `{"epoch":1767225600}` | Sets the clock when there is no NTP |
| `GET /api/wifi/scan` | — | Scans for networks (replies 202 while scanning) |
| `POST /api/wifi` | `{"ssid":"...","pass":"..."}` | Stores the network and restarts |
| `POST /api/reboot` | — | Restarts |
| `POST /api/factory-reset` | — | Erases all settings and restarts |

`days` is a bit mask with Sunday in bit 0: Monday to Friday = 62, weekends = 65, every day = 127.

Changing the admin password or the access point name or password restarts the device, because ArduinoOTA, `/update` and the access point read them at boot.

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
