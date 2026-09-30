# rele-esp12f — Módulo de relé Wi-Fi monocanal (ESP-12F, 110 VAC con neutro)

Proyecto KiCad 10. Abrir `rele-esp12f.kicad_pro`.

Inspirado en aman983/ESP-01S_Relay_Module. Diseño nuevo, sin archivos del original.

## Contenido
- `rele-esp12f.kicad_sch` — esquemático. Todos los símbolos tienen ocultos los números y nombres de pin (Symbol Properties → Show Pin Numbers / Show Pin Names, ambos desmarcados).
- `rele-esp12f.kicad_pcb` — PCB **66,5 × 44 mm**, 2 capas, ruteado completo, planos de GND en ambas caras (solo zona de baja tensión).
- `rele-esp12f.kicad_dru` — reglas propias: 4 mm entre red y baja tensión, 2 mm entre redes de red, 2 mm dentro del courtyard de K1.
- `fabricacion/gerbers_JLCPCB.zip` — Gerbers y taladros listos para subir.
- `fabricacion/BOM_JLCPCB.csv` y `CPL_JLCPCB.csv` — ensamblado en JLCPCB.
- `fabricacion/BOM_soldadura_manual.csv` — lo que se suelda a mano o no se monta, incluye los dos taladros de montaje.
- `docs/` — PDF del esquemático, renders de ambas caras y scripts que generaron el diseño original (v1; ya no reflejan el layout v2).

## Cambios de esta revisión (v2)
El tamaño bajó de 66 × 66 mm a **66,5 × 44 mm (−33 % de área)**. Todos los componentes siguen en la cara superior (ensamblado de una sola cara).

1. **Distribución nueva.** Franja superior: PS1 a la izquierda y el ESP-12F girado 270° con la antena en el borde derecho (sin cobre debajo, keepout de la huella). Abajo a la izquierda, zona de red: J1 en el borde inferior con la entrada de cable hacia fuera, F1 y RV1 encima y K1 a su derecha. Abajo a la derecha, baja tensión: U1 y sus condensadores, C1, driver del relé, pulsadores, LEDs, J3 y taladros.
2. **J3 pasa a header 2×3 de 2,54 mm** (antes 1×6). Mismo símbolo y mismas redes; ocupa la mitad y queda a ~10 mm de la antena.
3. **Sincronización con el esquemático.** Las redes de la placa se llaman ya como en el esquemático (`/L_IN`, `/N`, …) y R9 vale 220 Ω en ambos. Las clases de red MAINS y PWR incluyen los nombres nuevos para que las reglas de separación sigan aplicándose.
4. **Ruteo.** L_IN y L_OUT con pistas de 2,5 mm (hasta ~5 A); N y L_F de 1,0 mm (solo alimentan PS1, tras el fusible de 500 mA). Señales de 0,25–0,3 mm y alimentación de 0,5–0,6 mm.
5. **Planos de GND** en ambas caras, con un polígono que por geometría queda a ≥ 4,5 mm de todo el cobre de red (no depende solo de la clase de red).
6. **Serigrafía.** Aviso "PELIGRO: 110 VAC" en la zona de red, bornas N / OUT / L y pinout de J3 rotulado.

## Estado de verificación
- DRC (kicad-cli 10.0.5, sobre el archivo guardado): **0 errores, 0 sin conectar, 49 avisos** (23 huella/librería, 12+8+6 de serigrafía). Son avisos de serigrafía (referencias que se solapan o tocan el borde), huellas que difieren de la copia actual de la librería y campos LCSC/Montaje que no están copiados a las huellas. Ninguno afecta a la fabricación.
- ERC: **0 errores**, 9 avisos (extremos fuera de rejilla y símbolos que difieren de la librería).

## Asignación del ESP-12F
GPIO5 → relé (vía SS8050, R6 1k, R7 10k a GND) y LED de relé (D2+R8). GPIO4 → LED de WiFi (D3+R9). GPIO0 → pulsador SW1 (grabado y conmutación local). EN, RST, GPIO0, GPIO2 con 10k a 3V3; GPIO15 con 10k a GND. RST también sale a SW2. J3 solo para el primer grabado.

## J3 (programación, 2×3, paso 2,54 mm)
Fila superior: IO0 · TX · 3V3 — fila inferior: RST · RX · GND (rotulado en la placa).

## Bornas J1
Pin 1 N · Pin 2 OUT (a la carga) · Pin 3 L (fase de entrada).

## Seguridad
- Tensión de red: **110–120 VAC**. El varistor 07D221K está dimensionado para esta tensión; para 230 V habría que cambiarlo (p. ej. 07D471K).
- Nunca conectar el adaptador USB-serie a J3 con la placa conectada a la red. El primer grabado se hace alimentando por J3 (3V3); después, OTA.
- Excepción conocida: el COM del relé (L) queda a ~3,5 mm de los pads de bobina. Es inherente al patillaje del SRD (el COM está entre los pines de bobina) y está declarado en las reglas (2 mm dentro de K1).
- Carga recomendada ≤ 5 A.
- MH1 y MH2 están deliberadamente dentro de la zona de baja tensión (abajo a la derecha). No atravieses la placa con tornillos metálicos fuera de esos dos puntos.

## Licencias
Hardware CERN-OHL-W v2 · Firmware MIT.
