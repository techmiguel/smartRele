# Historial de cambios

Todas las revisiones relevantes del hardware se documentan aquí, junto con el criterio de ingeniería de cada cambio.

## [v3] — 2026-10-03

### Cambiado
- **Relé Omron G5RL-1A-E-HR DC5** (SPST-NO, 16 A / 250 VAC, LCSC C113250) en lugar del SRD-05VDC-SL-C. Usa la huella `Relay_SPST_Omron_G2RL-1A-E`, con el mismo patrón de 6 taladros de Ø1,3 mm que indica la hoja de datos del G5RL-1A-E. Al ser un modelo "-E" de alta capacidad, cada contacto sale por dos patillas y el fabricante exige usar ambas; en la placa, cada pareja queda unida por la pista de potencia.
- **Bobina y contactos a 20 mm** (8 mm de distancia interna, aislamiento reforzado). Desaparece la excepción de separación que exigía el SRD.
- **Placa de 66,5 × 49 mm** para alojar el relé de 29 × 12,7 mm.
- **J3 alimentado a 5 V** (pin 1 = GND, pin 2 = 5 V). Inyectar 3,3 V en la salida del AMS1117 polarizaba su diodo interno salida→entrada y cargaba el rail de 5 V. Además, el pin de 3,3 V de un adaptador USB-serie típico no soporta los picos del ESP8266. Se elimina la rama de +3V3 hacia J3, que partía el plano de GND bajo el módulo.
- **Carga de hasta 10 A**: L_IN y L_OUT duplicadas en ambas caras (2 × 2,5 mm). Según IPC-2221 (35 µm, capa externa), admiten unos 12 A con 20 °C de calentamiento.
- **Cobre de red alejado del borde**: F1 y RV1 se desplazan 2 mm y N y L_F se re-rutean. La distancia mínima al borde pasa de 1,3 a 2,0 mm.

### Añadido
- **C7 y C8 (100 nF)** en EN y RST: con R1/R2 forman un retardo RC de ~1 ms en el arranque, según la recomendación de Espressif.
- **C9 (10 µF X5R 0603, C19702)** junto al VCC del ESP-12F, en paralelo con C5 (100 nF), para cubrir los picos de transmisión.
- Hoja de datos y guía de usuario en PDF, y chasis imprimible en 3D.

### Corregido
- **Regla de diseño de K1 eliminada.** Reducía a 2 mm la separación de cualquier objeto dentro del courtyard de K1 y, al ser la última regla aplicable, anulaba la de 4 mm entre red y baja tensión en esa zona.
- **Pista de Net-(D3-A) fuera del área de la arandela de MH1.** Pasaba a 0,35 mm del taladro, bajo la tornillería. Ahora ninguna pista ni pad de señal entra en un círculo de Ø5 mm alrededor de MH1/MH2.
- **L_IN a 2,5 mm** (antes 2,0 mm), igualada con L_OUT.
- **Atributos de montaje**: K1 y J3 marcados como THT y C7/C8 como SMD, para que se exporten correctamente al CPL.

## [v2] — 2026-09-30

### Cambiado
- **Tamaño de 66 × 66 mm a 66,5 × 44 mm** (−33 % de área), con todos los componentes en la cara superior.
- **Nueva distribución**: fuente y ESP-12F en la franja superior (antena en el borde), zona de red abajo a la izquierda y baja tensión abajo a la derecha.
- **Tensión nominal de 110 VAC** (varistor 07D221K).
- **J3 como header 2×3** de 2,54 mm (antes 1×6): ocupa la mitad y queda a ~10 mm de la antena.
- Redes de la placa sincronizadas con el esquemático. Las clases MAINS y PWR se amplían a los nombres nuevos.
- Planos de GND en ambas caras, solo en la zona de baja tensión y a ≥ 4,5 mm del cobre de red por geometría.

### Fabricación
- **Montaje completo en JLCPCB**, incluidas las piezas THT: J1 (KANGNEX WJ500V-5.08-3P, C72334) y J3 (C65114).
- **F1 sustituido por Reomax MTS0500A** (T500mA 250 V, C2762401), por falta de stock del Littelfuse 39505000440; misma huella.
- **CPL con el centro de pads** (convención de JLCPCB). U2 y K1 usaban antes el centro del cuerpo y salían desplazados 3,8 y 1,4 mm.
- **Taladros ajustados**: J1 de Ø1,3 a Ø1,5 mm y RV1 de Ø0,6 a Ø1,0 mm, según las dimensiones de patilla de los fabricantes. Los pads de cobre no cambian.
- Modelos STEP de SW1/SW2, F1 y K1 en `3dmodels/`, referenciados con `${KIPRJMOD}`.

### Corregido
- Serigrafía: se recolocan 19 referencias y el texto de versión, que estaban solapados, junto a otro componente o fuera del borde.

## [v1] — 2026-09-25

- Diseño inicial: módulo de relé Wi-Fi con ESP-12F, fuente HLK-PM01, relé SRD-05VDC-SL-C y reglas de aislamiento propias entre red y baja tensión.

[v3]: https://github.com/techmiguel/smartRele/releases/tag/v3
[v2]: https://github.com/techmiguel/smartRele/releases/tag/v2
[v1]: https://github.com/techmiguel/smartRele/releases/tag/v1
