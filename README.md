# rele-esp12f — Módulo de relé Wi-Fi monocanal (ESP-12F, 110 VAC con neutro)

Proyecto KiCad 10. Abrir `rele-esp12f.kicad_pro`.

Inspirado en aman983/ESP-01S_Relay_Module. Diseño nuevo, sin archivos del original.

## Contenido
- `rele-esp12f.kicad_sch` — esquemático. Todos los símbolos tienen ocultos los números y nombres de pin (Symbol Properties → Show Pin Numbers / Show Pin Names, ambos desmarcados).
- `rele-esp12f.kicad_pcb` — PCB **66,5 × 44 mm**, 2 capas, ruteado completo, planos de GND en ambas caras (solo zona de baja tensión).
- `rele-esp12f.kicad_dru` — reglas propias: 4 mm entre red y baja tensión, 2 mm entre redes de red, 2 mm dentro del courtyard de K1.
- `fabricacion/gerbers_JLCPCB.zip` — Gerbers, taladros y CPL listos para subir.
- `fabricacion/BOM_JLCPCB.csv` y `CPL_JLCPCB.csv` — montaje completo en JLCPCB: las 29 piezas, SMD y THT.
- `fabricacion/BOM_soldadura_manual.csv` — solo MH1 y MH2 (taladros de montaje, sin pieza). No queda nada por soldar a mano.
- `3dmodels/` — modelos STEP que no trae la librería de KiCad 10 (pulsador TS-1187A y fusible Reomax MTS), descargados de EasyEDA/LCSC con `easyeda2kicad`. La placa los referencia con `${KIPRJMOD}`.
- `docs/` — PDF del esquemático, renders de ambas caras y scripts que generaron el diseño original (v1; ya no reflejan el layout v2).

## Cambios de esta revisión (v2)
El tamaño bajó de 66 × 66 mm a **66,5 × 44 mm (−33 % de área)**. Todos los componentes siguen en la cara superior (ensamblado de una sola cara).

1. **Distribución nueva.** Franja superior: PS1 a la izquierda y el ESP-12F girado 270° con la antena en el borde derecho (sin cobre debajo, keepout de la huella). Abajo a la izquierda, zona de red: J1 en el borde inferior con la entrada de cable hacia fuera, F1 y RV1 encima y K1 a su derecha. Abajo a la derecha, baja tensión: U1 y sus condensadores, C1, driver del relé, pulsadores, LEDs, J3 y taladros.
2. **J3 pasa a header 2×3 de 2,54 mm** (antes 1×6). Mismo símbolo y mismas redes; ocupa la mitad y queda a ~10 mm de la antena.
3. **Sincronización con el esquemático.** Las redes de la placa se llaman ya como en el esquemático (`/L_IN`, `/N`, …) y R9 vale 220 Ω en ambos. Las clases de red MAINS y PWR incluyen los nombres nuevos para que las reglas de separación sigan aplicándose.
4. **Ruteo.** L_IN y L_OUT con pistas de 2,5 mm (hasta ~5 A); N y L_F de 1,0 mm (solo alimentan PS1, tras el fusible de 500 mA). Señales de 0,25–0,3 mm y alimentación de 0,5–0,6 mm.
5. **Planos de GND** en ambas caras, con un polígono que por geometría queda a ≥ 4,5 mm de todo el cobre de red (no depende solo de la clase de red).
6. **Serigrafía.** Aviso "PELIGRO: 110 VAC" en la zona de red, bornas N / OUT / L y pinout de J3 rotulado. Las referencias están recolocadas junto a su componente, sin solaparse con otros textos ni con pads y sin salirse del borde (antes R3/R4/R9 aparecían intercambiadas y D2, D3, R8, SW2, J1 y J3 quedaban cortadas o fuera de la placa).

## Fabricación y montaje (JLCPCB)
Todo va montado de fábrica. Las piezas THT se sueldan por ola.

| Ref | Pieza | LCSC | Nota |
|---|---|---|---|
| PS1 | HLK-PM01 | C209903 | |
| K1 | SRD-05VDC-SL-C | C35449 | |
| F1 | Reomax MTS0500A, T500mA 250V | C2762401 | Acción retardada (necesaria por el pico de arranque del HLK-PM01). Sustituye al Littelfuse 39505000440 (C3163369), que no tenía stock. Misma huella. |
| RV1 | 07D221K | C49072913 | |
| C1 | 470 µF 10 V | C112505 | |
| J1 | KANGNEX WJ500V-5.08-3P | C72334 | Borna 250 V / 18 A. |
| J3 | Header 2×3, 2,54 mm | C65114 | Solo se usa para el primer grabado. |

Detalles que afectan al pedido:
- **CPL con el centro de pads.** JLCPCB coloca cada pieza tomando como centro el de sus pads, no el del cuerpo. En U2 (la antena desplaza el cuerpo) y K1 (COM separado del resto de pines) no coinciden. Por eso U2 va en X = 149,65 y K1 en X = 130,95; con el centro del cuerpo salían desplazados 3,8 y 1,4 mm en la vista previa.
- **Taladros ajustados a las piezas reales.** J1 tiene taladros de Ø1,5 mm (pin de 0,9 × 0,8 mm, recomendación de KANGNEX) y RV1 de Ø1,0 mm (pata de 0,6 ± 0,1 mm). Las huellas de la librería traían Ø1,3 y Ø0,6 mm, que dejaban demasiada poca holgura para la inserción y la soldadura por ola. Los pads de cobre no cambian, así que las distancias de aislamiento son las mismas.
- **Revisar en el visor de JLCPCB** antes de pagar: que U2 y K1 encajen con sus pads, que la entrada de cable de J1 mire hacia el borde de la placa, que el pin 1 de J3 quede en el pad cuadrado (3V3) y que todas las piezas de la BOM estén seleccionadas.

Regenerar gerbers, taladros y render. Los ajustes de trazado guardados en la placa no coinciden con los del envío (dan extensiones `.gbr` y una capa B_Paste de más), así que hay que usar estas opciones:
```
kicad-cli pcb export gerbers --layers F.Cu,B.Cu,F.SilkS,B.SilkS,F.Mask,B.Mask,F.Paste,Edge.Cuts -o fabricacion/gerbers/ rele-esp12f.kicad_pcb
kicad-cli pcb export drill --format excellon --excellon-units mm --excellon-separate-th --excellon-zeros-format decimal -o fabricacion/gerbers/ rele-esp12f.kicad_pcb
kicad-cli pcb render --side top -w 1592 -h 904 --background opaque --quality basic --zoom 0.9954 -o docs/pcb_superior.png rele-esp12f.kicad_pcb
```
El ZIP lleva los 11 archivos de `fabricacion/gerbers/` más `CPL_JLCPCB.csv`.

## Estado de verificación
- DRC (kicad-cli 10.0.5, sobre el archivo guardado): **0 errores, 0 sin conectar, 30 avisos**:
  - 24 de huellas que difieren de la copia de la librería (entre ellas, los taladros ajustados de J1 y RV1 y los modelos 3D propios).
  - 6 de serigrafía de PS1 y J1 que roza las esquinas redondeadas del contorno. Los cuerpos reales quedan dentro de la placa.
- Paridad con el esquemático: 31 avisos: 29 por campos LCSC/Montaje que no están copiados a las huellas, y los 2 taladros de montaje, que no tienen símbolo. Ninguno afecta a la fabricación.
- ERC: **0 errores**, 9 avisos (extremos fuera de rejilla y símbolos que difieren de la librería).

## Asignación del ESP-12F
GPIO5 → relé (vía SS8050, R6 1k, R7 10k a GND) y LED de relé (D2+R8). GPIO4 → LED de WiFi (D3+R9). GPIO0 → pulsador SW1 (grabado y conmutación local). EN, RST, GPIO0, GPIO2 con 10k a 3V3; GPIO15 con 10k a GND. RST también sale a SW2. J3 solo para el primer grabado.

## J3 (programación, 2×3, paso 2,54 mm)
Fila superior: IO0 · TX · 3V3 — fila inferior: RST · RX · GND (rotulado en la placa).

## Bornas J1
Pin 1 N · Pin 2 OUT (a la carga) · Pin 3 L (fase de entrada).

## Seguridad
- Tensión de red: **110–120 VAC**. El varistor 07D221K está dimensionado para esta tensión; para 230 V habría que cambiarlo (p. ej. 07D471K). El fusible F1 (T500mA, 250 V) sirve para ambas.
- Nunca conectar el adaptador USB-serie a J3 con la placa conectada a la red. El primer grabado se hace alimentando por J3 (3V3); después, OTA.
- Excepción conocida: el COM del relé (L) queda a ~3,5 mm de los pads de bobina. Es inherente al patillaje del SRD (el COM está entre los pines de bobina) y está declarado en las reglas (2 mm dentro de K1).
- Carga recomendada ≤ 5 A.
- MH1 y MH2 están deliberadamente dentro de la zona de baja tensión (abajo a la derecha). No atravieses la placa con tornillos metálicos fuera de esos dos puntos.

## Licencias
Hardware CERN-OHL-W v2 · Firmware MIT.
