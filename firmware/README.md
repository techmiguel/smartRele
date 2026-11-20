# SmartRele firmware · rele-esp12f

Firmware v1.4.2 for the rele-esp12f board (ESP-12F / ESP8266). The relay is controlled over Wi-Fi from a built-in web interface (in Spanish) or through a JSON REST API, and from anywhere on the Internet through an optional **Telegram bot**:

- **Manual on / off**, with the time the output has been on in the current ON period.
- **State-change timer**: after a delay (1 s to 7 days) it turns the relay on, off or toggles it.
- **Cyclic ON/OFF routine**: on for one period and off for another, repeated indefinitely.
- **Weekly schedules**: up to 16 rules of the form "at HH:MM, on these days, turn on/off/toggle".
- **Telegram bot**: on/off, status, timer and routine from the Telegram app, plus notifications when the relay changes on its own or the power comes back. See [Control over the Internet (Telegram)](#control-over-the-internet-telegram).

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

## Control over the Internet (Telegram)

The device opens an **outgoing** HTTPS connection to `api.telegram.org` and asks it for new messages (long polling). Nothing has to be reachable from the Internet: it works on a phone hotspot, behind the carrier's CGNAT and on any router without port forwarding, and needs no server of your own.

> [!IMPORTANT]
> The relay reaches the Internet through its Wi-Fi network. If that network is a phone hotspot, **that phone has to stay at home** (an old Android phone on its charger with a data SIM works well); you control the relay from another phone. Hotspot settings: 2.4 GHz band, "turn off hotspot when no devices are connected" disabled, and battery optimisation disabled for the settings app.

### Setup

1. In Telegram, open **@BotFather**, send `/newbot` and choose a name and a user name ending in `bot`. BotFather replies with a **token** such as `123456789:AAH...`. Anyone with the token controls the bot: keep it private.
2. On the relay page: *Ajustes → Telegram*, paste the token and press *Guardar Telegram*. The status line changes to *En línea · @your_bot*.
3. In Telegram, open your bot and send `/start`. With no authorised users yet, it replies with your **Telegram ID** (a number).
4. Write that number under *IDs autorizados* and press *Guardar Telegram*. Up to 4 IDs, separated by commas (for example, other people at home).
5. Send `/start` again: the bot shows the command list and an *Encender / Apagar / Estado* keyboard.

The clock must be set (NTP) before the first connection, because it is needed to check the server certificate.

### Commands

| Command | Function |
|---|---|
| `/encender`, `/apagar` (or the keyboard buttons) | Turns the relay on / off; stops the cyclic routine |
| `/estado` | State and time in it, timer, routine, next schedule, Wi-Fi signal |
| `/temporizador 30m [encender\|apagar]` | Starts the timer; without the last word it does the opposite of the current state |
| `/cancelar` | Cancels the timer |
| `/rutina 10m 50m` | Starts the cyclic routine (ON time, OFF time) |
| `/detener` | Stops the routine |
| `/avisos si\|no` | Turns notifications on or off |
| `/diagnostico` | Connection and memory statistics |
| `/id` | Shows your Telegram ID |
| `/reiniciar` | Restarts the device |
| `/ayuda` | Command list |

Durations: `45s`, `30m`, `2h`, `1h30m`, `1d`; a bare number means minutes.

### Notifications

With *Avisar de cambios: sí* (the default), every authorised user gets a message when:

- the device comes online after a restart or a power cut ("volvió la luz"), with the relay state;
- the relay changes from the web page, the timer or a weekly schedule.

Changes made from Telegram are answered in the chat and are not notified again; the cyclic routine is not notified, so it does not flood the chat. A notification can take up to 45 s (one long-poll period) to arrive; replies to commands are immediate.

### Behaviour and limits

- Commands typically take 1–2 s. Commands sent while the relay was offline and that arrive more than **5 minutes late are not executed**: the bot says so, to avoid surprises such as a lamp turning on hours later.
- Only the listed IDs can control the relay. Anyone else who writes to the bot is only told their own ID.
- The connection stays open and asks for news every 45 s: about 0.9 kB per poll plus a 25 s TCP keep-alive probe, roughly **1.5–2 MB of mobile data per day (about 50 MB a month)**. Each reconnection costs 1–6 kB more (less when the TLS session is resumed). To spend less, build with a longer poll (`-D TELEGRAM_POLL_SEC=50`); notifications then wait longer.
- The certificate of `api.telegram.org` is verified against the Go Daddy Root G2 root, with Starfield Root G2 and ISRG Root X1 (Let's Encrypt) as spares (`src/telegram_ca.h`, generated by `scripts/gen_trust_anchors.py`). If Telegram ever moves to a different authority, the status line says the certificate is not recognised and a firmware update with the new root is needed.
- An invalid token is retried every 10 minutes or as soon as it is changed. If another program uses the same bot (a webhook or a second device), Telegram rejects the connection: each relay needs its own bot.

### Reliability: network changes, VPN, lost data

On a phone hotspot the path to the Internet changes often: mobile data drops, the phone switches cell, a VPN is turned on or off. Each change kills the open connection **without notice**: the relay is never told, it just stops receiving. The bot is built for this:

| Situation | What the bot does | Back in |
|---|---|---|
| Connection dies silently (VPN switched on/off, network change) | TCP keep-alive probes after 25 s of silence (they also keep the mobile NAT entry open), and each long poll must be answered within 55 s (45 s poll + 10 s margin) | ≤ 1 min |
| No Internet (connections refused or hanging) | Retries after 1, 2, 5, 10 and then every 20 s | ≤ 20 s after the Internet returns |
| Slow or lossy link (2G/3G, congested cell) | Timeouts (DNS 8 s, connect + TLS 20 s, request 20 s, long-poll margin 10 s) grow ×2, ×3, ×4 after each timeout and shrink again after 20 good answers | keeps working; `slow` in `/api/status` |
| Wi-Fi lost | Reconnects at once when the Wi-Fi comes back | ~2 s |
| Phone out of credit: the carrier's DNS answers with its top-up portal, and the wrong answer stays in the DNS cache after the top-up | Does not depend on DNS (see below) | ≤ 20 s after the top-up |
| Telegram errors (502, 429), responses cut halfway | Drops the connection and retries | seconds |

Messages that were being sent when the connection dropped are sent again after reconnecting, and every command is answered once.

**Addresses.** While a prepaid line has no credit, many carriers answer every DNS query with the address of their top-up portal, and the ESP8266 keeps that answer cached for as long as its TTL says (lwIP allows up to a week), well after the top-up. Because the TLS certificate proves who is at the other end, the bot does not need DNS to be right: it tries, in turn, the **last address that passed the certificate check** (saved in flash, tried every other attempt), the DNS answer, and the addresses Telegram has used for years (149.154.166.110 and 149.154.167.220). A wrong address only fails the certificate check; it can never be mistaken for Telegram.

The TLS memory (BearSSL contexts and a 16.7 kB buffer, about 23 kB, plus a 6.2 kB stack for the cryptography) is **reserved once at boot** and reused by every connection. Earlier builds allocated it on each reconnection, and after a few network changes the heap was too fragmented to find 16.7 kB in one piece again: the bot went silent until the relay was restarted. If the server accepts 2 kB TLS records (Max Fragment Length), the buffer is reduced to 2.4 kB after the first connection. **Nothing blocks**: DNS lookups and TCP connections are asynchronous (lwIP callbacks) and the TLS engine only moves the bytes that are ready, so the web page, the timer and the schedules keep running while the bot waits on a slow network, however long the timeouts get. The host tests check that no pass of the main loop takes more than 300 ms.

**Watchdog.** A last line of defence covers causes nobody foresaw. It only counts time with the Wi-Fi up and the clock set but no answer from Telegram, and escalates:

| Silent for | Action |
|---|---|
| 5 min | The bot starts over: new connection, new TLS session, address search from the beginning |
| 10 min, then every 30 min | The Wi-Fi network is rejoined: new DHCP lease, DNS server and gateway |
| 60 min, then 2, 4, 8, 16 h | The device restarts, **only if the relay is off and no timer, routine or schedule (within 2 min) is pending**. After this restart the relay stays off whatever *Al volver la luz* says, and the "en línea" message explains why it restarted |

The load is therefore never switched by the watchdog. While the relay is on, it keeps rejoining the Wi-Fi every 30 min instead. Any answer from Telegram resets the count. *Ajustes → Telegram → Reconectar Telegram* (`POST /api/telegram/reconnect`) does the first step by hand.

`/diagnostico` (or `GET /api/status` → `telegram`) shows the time since boot, how long the current connection has lasted, the server address in use and where it came from, the number of connections and drops, the last drop reason and the free memory; `/api/status` also has `telegram.silentSec` (watchdog count) and `telegram.safetyRestarts`. *Ajustes → Telegram* only shows an error when Telegram has been unreachable for more than a minute.

### Host tests

`hosttest/` runs the bot code (`telegram.cpp`, `tls_link.cpp`) on a PC, with BearSSL compiled from the sources shipped with the ESP8266 core, against a fake Bot API server over real TLS that injects the faults above: silent connection death, refused and hanging connections, a phone out of credit whose DNS points at a top-up portal, Telegram changing address, DNS down, Wi-Fi loss, 502 errors, responses cut halfway, `Connection: close`, chunked responses, oversized messages, plus hundreds of reconnections to check that memory stays flat. A second build (`harness_wd`) runs the watchdog 60 times faster to check each step, and that it never restarts with the relay on.

```bash
pio run -e esp12f          # once, to fetch the core and ArduinoJson
hosttest/build.sh
python3 hosttest/test_bot.py            # about 12 minutes; --no-watchdog / --watchdog-only
```

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
| `GET /api/config` | — | Settings (without passwords; `tgToken` only says whether a token is set) |
| `POST /api/config` | `{"name","tz","ntp","powerOn":0\|1\|2,"adminPass","apSsid","apPass","tgToken","tgUsers":"123, 456","tgNotify":true}` | Changes settings; every field is optional. `"tgToken":""` disables the bot |
| `POST /api/time` | `{"epoch":1767225600}` | Sets the clock when there is no NTP |
| `GET /api/wifi/scan` | — | Scans for networks (replies 202 while scanning) |
| `POST /api/wifi` | `{"ssid":"...","pass":"..."}` | Stores the network and restarts |
| `POST /api/telegram/reconnect` | — | Drops the Telegram connection and reconnects at once |
| `POST /api/reboot` | — | Restarts |
| `POST /api/factory-reset` | — | Erases all settings and restarts |

`days` is a bit mask with Sunday in bit 0: Monday to Friday = 62, weekends = 65, every day = 127.

Changing the admin password or the access point name or password restarts the device, because ArduinoOTA, `/update` and the access point read them at boot.

## Security

- **Always set an admin password.** Without it, anyone on the network (or on the access point, whose password is public) can switch the relay.
- The Telegram bot is the only way to control the relay from outside your network. Keep the bot token private (it is stored in the module flash like the passwords) and list only trusted IDs. If the token leaks, revoke it in @BotFather (`/revoke`) and enter the new one.
- The web interface uses plain HTTP. Digest authentication does not send the password in clear text, but the rest of the traffic is unencrypted: use it only on your local network and do not expose it to the Internet by forwarding ports on the router.
- Passwords are stored unencrypted in the module flash. Anyone with physical access to the board can read them.
- **Never connect the serial adapter to J3 while the board is connected to the mains.**

## Layout

```
firmware/
├── platformio.ini     esp12f (serial) and esp12f_ota (network) environments
├── hosttest/          Bot code built for a PC and tested against a fault-injecting server
└── src/
    ├── main.cpp       Start-up and main loop
    ├── board.h        Pin assignment
    ├── settings.*     Persistent settings (LittleFS, JSON)
    ├── relay.*        Relay, timer and cyclic routine
    ├── scheduler.*    Time (NTP / time zone) and weekly schedules
    ├── network.*      Wi-Fi, access point, captive portal, mDNS, OTA, LED and SW1
    ├── web.*          HTTP server and REST API
    ├── telegram.*     Telegram bot (remote control and notifications)
    ├── tls_link.*     Non-blocking TLS client on BearSSL, memory reserved once
    ├── tcp_transport.cpp  TCP for the TLS link (lwIP, keep-alive, DNS fallback)
    ├── telegram_ca.h  Root certificates for api.telegram.org (BearSSL trust anchors)
    └── web_ui.h       Embedded web interface
```

Dependencies: Arduino core for ESP8266 (PlatformIO `espressif8266` platform) and [ArduinoJson](https://arduinojson.org/) 7, which PlatformIO downloads automatically.
