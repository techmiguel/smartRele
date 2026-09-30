# rele-esp12f — Módulo de relé Wi-Fi monocanal (ESP-12F, 230 V con neutro)

Proyecto KiCad (creado con 7.0, se abre en 8 y 9). Abrir `rele-esp12f.kicad_pro`.

Inspirado en aman983/ESP-01S_Relay_Module. Diseño nuevo, sin archivos del original.

## Contenido
- `rele-esp12f.kicad_sch` — esquemático. Todos los símbolos tienen ocultos los números y nombres de pin (Symbol Properties → Show Pin Numbers / Show Pin Names, ambos desmarcados).
- `rele-esp12f.kicad_pcb` — PCB **66 × 66 mm**, 2 capas, ruteado completo.
- `rele-esp12f.kicad_dru` — reglas propias: 4 mm entre red 230 V y baja tensión, 2 mm entre redes de 230 V.
- `fabricacion/gerbers_JLCPCB.zip` — Gerbers y taladros listos para subir.
- `fabricacion/BOM_JLCPCB.csv` y `CPL_JLCPCB.csv` — ensamblado SMT (solo componentes SMD).
- `fabricacion/BOM_soldadura_manual.csv` — lo que se suelda a mano, incluye los dos taladros de montaje.
- `docs/` — PDF del esquemático, renders de ambas caras y scripts que generaron el diseño.

## Cambios de esta revisión
El tamaño creció de 66 × 48 mm a **66 × 66 mm**. No fue un ajuste cosmético: los dos taladros de montaje, por sí solos, obligaron a descartar las esquinas obvias (una cae sobre el PS1, la otra sobre la zona de exclusión de la antena), así que la única forma de meterlos sin violar esas dos restricciones fue ganar altura.

Añadido en esta revisión:
1. **SW2** — pulsador de RST (idéntico a SW1, mismo LCSC). Ya no hace falta puentear el pad de RST a mano para entrar en modo de grabado.
2. **D2 + R8** — LED de estado del relé, en paralelo con R6 sobre la propia señal GPIO5. No consume un GPIO adicional.
3. **D3 + R9** — LED de estado de WiFi, en GPIO4 (libre). El firmware decide el patrón (parpadeo al conectar, fijo si ya está asociado).
4. **MH1, MH2** — taladros de montaje M2, sin plateado y sin red eléctrica, ambos dentro de la zona SELV.
5. Símbolos del esquemático con números y nombres de pin ocultos, aplicado a nivel de cada símbolo (no instancia por instancia), tal como lo controla el diálogo "Symbol Properties" de KiCad.

## Estado de verificación
DRC sobre el diseño final: **0 errores de separación, 0 pads sin conectar, 0 footprints sin colocar.** Quedan únicamente avisos cosméticos de serigrafía (referencias que se solapan visualmente con pads o entre sí) que no afectan la fabricación ni la función.
Netlist del esquemático comparada por script contra la definición del diseño: **20 redes, 0 diferencias.**
ERC no se pudo correr desde línea de comandos (kicad-cli 7.0 no expone ese subcomando); córrelo tú desde la interfaz de KiCad como paso siguiente.

## Asignación del ESP-12F
GPIO5 → relé (vía SS8050, R6 1k, R7 10k a GND) y LED de relé (D2+R8). GPIO4 → LED de WiFi (D3+R9). GPIO0 → pulsador SW1 (grabado y conmutación local). EN, RST, GPIO0, GPIO2 con 10k a 3V3; GPIO15 con 10k a GND. RST también sale a SW2. J3 (3V3, GND, TX, RX, IO0, RST) solo para el primer grabado.

## Bornas J1
Pin 1 N · Pin 2 OUT (a la carga) · Pin 3 L (fase de entrada).

## Seguridad
- Nunca conectar el adaptador USB-serie a J3 con la placa conectada a la red. El primer grabado se hace alimentando por J3 (3V3); después, OTA.
- Excepción conocida: la pista de L hacia el COM del relé pasa a ~2,2 mm de los pads de bobina. Es inherente al patillaje del SRD (el COM está entre los pines de bobina) y está declarado en las reglas.
- Carga recomendada ≤ 5 A.
- MH1 y MH2 están deliberadamente dentro de la zona SELV (x > 31 mm). No atravieses la placa con tornillos metálicos fuera de esos dos puntos.

## Licencias
Hardware CERN-OHL-W v2 · Firmware MIT.
