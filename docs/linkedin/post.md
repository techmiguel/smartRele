# Publicación de LinkedIn — smartRele v3.1

Imágenes (en este orden): `pcb_top_cambios.png`, `pcb_bottom_cambios.png`

---

Un relé Wi-Fi a 110 VAC tiene que funcionar, pero sobre todo tiene que ser seguro. ⚡

Revisé mi placa smartRele (ESP-12F + relé) contra las guías de Espressif, los datasheets y las reglas de aislamiento. Estos son los cambios que hice en la v3.1:

📡 RF
1️⃣ Recorte en la placa bajo la antena del ESP-12F: sin FR-4 ni cobre debajo, como recomienda Espressif.

🔌 Red eléctrica y seguridad
2️⃣ Relé Omron G5RL de 16 A: bobina y contactos a 20 mm, con aislamiento reforzado.
6️⃣ Fusible y varistor desplazados: el cobre de red queda a 2 mm del borde (antes 1,3 mm).
8️⃣ Pistas de fase duplicadas en ambas caras (2 × 2,5 mm): cargas de hasta 10 A según IPC-2221.
9️⃣ Separación de 4 mm entre red y baja tensión en toda la placa, sin excepciones locales.

🔋 Alimentación y arranque
3️⃣ 10 µF junto al VCC del módulo para los picos de ~400 mA al transmitir.
4️⃣ 100 nF en EN y RST: retardo RC de ~1 ms en el arranque.
5️⃣ Conector de programación a 5 V: ya no polariza en inverso el regulador ni divide el plano de masa.

🔩 Mecánica
7️⃣ Ninguna pista dentro del área de los tornillos de fijación.

Lo que aprendí: casi ningún cambio se nota a simple vista, pero cada uno corrige un fallo que solo aparecería en campo.

El diseño completo (KiCad, firmware y caja imprimible) es open source 👇
github.com/techmiguel/smartRele

¿Qué revisas tú primero en una placa que maneja tensión de red?

#PCB #KiCad #ESP8266 #IoT #HardwareDesign #ElectronicsEngineering #OpenSourceHardware #DiseñoElectrónico
