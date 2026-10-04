# Changelog

All notable hardware revisions are documented here, together with the engineering rationale behind each change.

## [firmware 1.0.0] — 2026-10-04

### Added
- **First firmware for the board** in [`firmware/`](firmware/) (PlatformIO, Arduino core for ESP8266). The relay is controlled over Wi-Fi only: manual on/off, state-change timer, cyclic ON/OFF routine and up to 16 weekly schedules (NTP + POSIX time zone). Web interface, JSON REST API with Digest authentication, setup access point with captive portal, mDNS and OTA updates (ArduinoOTA and browser upload).
- **Hardware-aware defaults**: GPIO5 is driven low before anything else runs, the relay state is only written to flash when it changes (never during the cyclic routine), and each routine phase is at least 5 s.

## [v3] — 2026-10-03

### Changed
- **Omron G5RL-1A-E-HR DC5 relay** (SPST-NO, 16 A / 250 VAC, LCSC C113250) instead of the SRD-05VDC-SL-C. It uses the `Relay_SPST_Omron_G2RL-1A-E` footprint, which has the same 6-hole Ø1.3 mm pattern given in the G5RL-1A-E datasheet. As an "-E" high-capacity model, each contact comes out on two pins and the manufacturer requires both to be used; on the board each pair is joined by the power trace.
- **Coil and contacts 20 mm apart** (8 mm internal distance, reinforced insulation). The clearance exception required by the SRD relay is gone.
- **66.5 × 49 mm board** to fit the 29 × 12.7 mm relay.
- **J3 powered at 5 V** (pin 1 = GND, pin 2 = 5 V). Injecting 3.3 V into the AMS1117 output forward-biased its internal output→input diode and loaded the 5 V rail. Besides, the 3.3 V pin of a typical USB-serial adapter cannot supply the ESP8266 current peaks. The +3V3 branch to J3, which split the GND plane under the module, was removed.
- **Load current up to 10 A**: L_IN and L_OUT duplicated on both sides (2 × 2.5 mm). Per IPC-2221 (35 µm, external layer) they carry about 12 A with a 20 °C rise.
- **Mains copper moved away from the edge**: F1 and RV1 shifted by 2 mm and N and L_F re-routed. The minimum distance to the edge went from 1.3 to 2.0 mm.
- **Silkscreen and schematic labels in English** ("DANGER: 110 VAC", section titles, LED values). Schematic title block updated to revision v3.

### Added
- **C7 and C8 (100 nF)** on EN and RST: together with R1/R2 they form a ~1 ms RC delay at start-up, as recommended by Espressif.
- **C9 (10 µF X5R 0603, C19702)** next to the ESP-12F VCC pin, in parallel with C5 (100 nF), to cover the transmit current peaks.
- PDF datasheet and user guide, and a 3D-printable enclosure.

### Fixed
- **K1 design rule removed.** It reduced the clearance to 2 mm for any object inside the K1 courtyard and, being the last matching rule, overrode the 4 mm mains/low-voltage rule in that area.
- **Net-(D3-A) trace moved out of the MH1 washer area.** It ran 0.35 mm from the hole, under the hardware. No signal trace or pad now enters a Ø5 mm circle around MH1/MH2.
- **L_IN widened to 2.5 mm** (previously 2.0 mm), matching L_OUT.
- **Assembly attributes**: K1 and J3 marked as THT and C7/C8 as SMD, so they are exported correctly to the CPL.

## [v2] — 2026-09-30

### Changed
- **Board size reduced from 66 × 66 mm to 66.5 × 44 mm** (−33 % area), with all components on the top side.
- **New layout**: supply and ESP-12F in the top strip (antenna at the edge), mains zone at the bottom left and low voltage at the bottom right.
- **110 VAC nominal voltage** (07D221K varistor).
- **J3 as a 2×3 header**, 2.54 mm pitch (previously 1×6): half the size and ~10 mm away from the antenna.
- Board nets synchronized with the schematic. The MAINS and PWR net classes were extended to the new names.
- GND planes on both sides, only in the low-voltage zone and geometrically ≥ 4.5 mm away from mains copper.

### Manufacturing
- **Full assembly at JLCPCB**, including the THT parts: J1 (KANGNEX WJ500V-5.08-3P, C72334) and J3 (C65114).
- **F1 replaced with a Reomax MTS0500A** (T500mA 250 V, C2762401), because the Littelfuse 39505000440 was out of stock; same footprint.
- **CPL using the pad center** (JLCPCB convention). U2 and K1 previously used the body center and were offset by 3.8 and 1.4 mm.
- **Adjusted drill sizes**: J1 from Ø1.3 to Ø1.5 mm and RV1 from Ø0.6 to Ø1.0 mm, according to the manufacturers' lead dimensions. Copper pads are unchanged.
- STEP models for SW1/SW2, F1 and K1 in `3dmodels/`, referenced through `${KIPRJMOD}`.

### Fixed
- Silkscreen: 19 reference designators and the version text were repositioned; they overlapped, sat next to the wrong component or fell outside the board edge.

## [v1] — 2026-09-25

- Initial design: ESP-12F Wi-Fi relay module with HLK-PM01 supply, SRD-05VDC-SL-C relay and custom mains/low-voltage isolation rules.

[v3]: https://github.com/techmiguel/smartRele/releases/tag/v3
[v2]: https://github.com/techmiguel/smartRele/tree/v2
[v1]: https://github.com/techmiguel/smartRele/tree/v1
