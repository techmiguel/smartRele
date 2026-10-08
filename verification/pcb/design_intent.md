# Design intent

Read by the independent reviewer. Facts the schematic cannot show; keep it short.

- Purpose of the board: single-channel Wi-Fi relay (ESP-12F) that switches a mains load.
- Supply input (voltage range, source, max current): 110–120 VAC 50/60 Hz mains on J1 (N, L_IN). On-board HLK-PM01 gives 5 V / 0.6 A max; AMS1117 gives 3.3 V for the ESP-12F. F1 (T500 mA) protects only the supply branch.
- Loads and their currents (motors, relays, LEDs, radios): K1 contacts switch up to 10 A resistive at 120 VAC (L_IN → L_OUT); K1 coil 5 V / ~80 mA; ESP-12F peaks ~400 mA during RF calibration; two indicator LEDs at a few mA.
- External connectors and what plugs into them: J1 = mains terminal block (N, switched OUT, L in). J3 = 2×3 programming header for a USB-serial adapter (5 V, GND, TX, RX, GPIO0, RST), used only with mains disconnected.
- Environment (temperature, humidity, mains, battery, enclosure): indoor, inside a 3D-printed insulating enclosure (enclosure/). No battery.
- Target fab/assembly house and process: JLCPCB, 2 layers 1.6 mm, full assembly on the top side (SMD reflow + THT wave/selective solder). Supplier codes are LCSC numbers.
- Decisions that look wrong but are intentional:
  - The board has a 7.6 × 18.7 mm cut-out in the top-right corner: the ESP-12F antenna overhangs it on purpose (Espressif guideline: no base-board FR-4 or copper under the PCB antenna).
  - Footprints differ from the KiCad library on purpose: J1 drill Ø1.5 mm and RV1 drill Ø1.0 mm (actual lead sizes), custom 3D models for F1, SW1/SW2 and K1. K1 uses the G2RL-1A-E footprint, whose hole pattern equals the G5RL-1A-E datasheet.
  - Mains ↔ low-voltage clearance is a 4 mm custom DRC rule (rele-esp12f.kicad_dru); GND pours are clipped by a polygon away from mains copper.
  - J3 carries 5 V (not 3.3 V) so the adapter supplies the ESP-12F through the LDO.
  - U2 pins 9–14 (internal SPI flash) are left unconnected on purpose.
