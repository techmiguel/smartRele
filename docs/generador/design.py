# Definición única del diseño: componentes, footprints, posiciones y nets
import uuid
FPLIB='/usr/share/kicad/footprints'
# ref: (lib_id símbolo, valor, footprint, x, y, rot, {pad: net}, LCSC, ensamblado)
C = {
 'J1': ('Connector:Screw_Terminal_01x03','N / L_OUT / L_IN','TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-3-5.08_1x03_P5.08mm_Horizontal',4,42.5,0,{'1':'N','2':'L_OUT','3':'L_IN'},'','Mano'),
 'F1': ('Device:Fuse','T500mA 250V','Fuse:Fuse_Littelfuse_395Series',12,26.3,0,{'1':'L_IN','2':'L_F'},'','Mano'),
 'RV1':('Device:Varistor','07D471K','Varistor:RV_Disc_D7mm_W3.4mm_P5mm',20.6,25.0,0,{'1':'L_F','2':'N'},'','Mano'),
 'PS1':('Converter_ACDC:HLK-PM01','HLK-PM01','Converter_ACDC:Converter_ACDC_Hi-Link_HLK-PMxx',5.5,9.5,0,{'1':'L_F','2':'N','3':'GND','4':'+5V'},'','Mano'),
 'K1': ('Relay:SANYOU_SRD_Form_C','SRD-05VDC-SL-C','Relay_THT:Relay_SPDT_SANYOU_SRD_Series_Form_C',38.5,37.5,180,{'1':'L_IN','2':'+5V','3':'L_OUT','5':'COIL_N'},'','Mano'),
 'C1': ('Device:C_Polarized','470uF 10V','Capacitor_THT:CP_Radial_D6.3mm_P2.50mm',46.0,30.0,0,{'1':'+5V','2':'GND'},'','Mano'),
 'C2': ('Device:C','22uF 10V','Capacitor_SMD:C_0805_2012Metric',48.3,35.3,0,{'1':'+5V','2':'GND'},'C45783','JLCPCB'),
 'C3': ('Device:C','100nF','Capacitor_SMD:C_0603_1608Metric',52.3,36.3,0,{'1':'+5V','2':'GND'},'C14663','JLCPCB'),
 'U1': ('Regulator_Linear:AMS1117-3.3','AMS1117-3.3','Package_TO_SOT_SMD:SOT-223-3_TabPin2',55.2,30.4,0,{'1':'GND','2':'+3V3','3':'+5V'},'C6186','JLCPCB'),
 'C6': ('Device:C','100nF','Capacitor_SMD:C_0603_1608Metric',61.0,30.4,90,{'1':'+3V3','2':'GND'},'C14663','JLCPCB'),
 'C4': ('Device:C','22uF 10V','Capacitor_SMD:C_0805_2012Metric',41.2,22.6,90,{'1':'+3V3','2':'GND'},'C45783','JLCPCB'),
 'C5': ('Device:C','100nF','Capacitor_SMD:C_0603_1608Metric',41.2,18.9,90,{'1':'+3V3','2':'GND'},'C14663','JLCPCB'),
 'R2': ('Device:R','10k','Resistor_SMD:R_0603_1608Metric',41.2,9.4,90,{'1':'+3V3','2':'RST'},'C25804','JLCPCB'),
 'R1': ('Device:R','10k','Resistor_SMD:R_0603_1608Metric',41.2,13.2,90,{'1':'+3V3','2':'EN'},'C25804','JLCPCB'),
 'U2': ('RF_Module:ESP-12F','ESP-12F','RF_Module:ESP-12E',52.5,12.6,0,{'1':'RST','3':'EN','8':'+3V3','15':'GND','16':'GPIO15','17':'GPIO2','18':'GPIO0','20':'RELAY','21':'RXD','22':'TXD'},'','Mano'),
 'R3': ('Device:R','10k','Resistor_SMD:R_0603_1608Metric',63.8,15.8,90,{'1':'+3V3','2':'GPIO0'},'C25804','JLCPCB'),
 'R4': ('Device:R','10k','Resistor_SMD:R_0603_1608Metric',63.8,19.4,90,{'1':'+3V3','2':'GPIO2'},'C25804','JLCPCB'),
 'R5': ('Device:R','10k','Resistor_SMD:R_0603_1608Metric',63.8,23.0,90,{'1':'GPIO15','2':'GND'},'C25804','JLCPCB'),
 'Q1': ('Device:Q_NPN_BEC','SS8050','Package_TO_SOT_SMD:SOT-23',48.0,42.6,0,{'1':'Q1_B','2':'GND','3':'COIL_N'},'C2150','JLCPCB'),
 'D1': ('Diode:1N4148W','1N4148W','Diode_SMD:D_SOD-123',48.0,38.8,0,{'1':'+5V','2':'COIL_N'},'C81598','JLCPCB'),
 'R6': ('Device:R','1k','Resistor_SMD:R_0603_1608Metric',51.8,45.8,0,{'1':'RELAY','2':'Q1_B'},'C21190','JLCPCB'),
 'R7': ('Device:R','10k','Resistor_SMD:R_0603_1608Metric',47.6,45.8,0,{'1':'Q1_B','2':'GND'},'C25804','JLCPCB'),
 'SW1':('Switch:SW_Push','TS-1187A','Button_Switch_SMD:SW_Push_1P1T_XKB_TS-1187A',56.6,41.6,0,{'1':'GPIO0','2':'GND'},'C318884','JLCPCB'),
 'J3': ('Connector:Conn_01x06_Pin','PROG','Connector_PinHeader_2.54mm:PinHeader_1x06_P2.54mm_Vertical',63.8,33.2,0,{'1':'+3V3','2':'GND','3':'TXD','4':'RXD','5':'GPIO0','6':'RST'},'','No montar'),
}
MAINS=['L_IN','L_OUT','N','L_F']
BOARD=(66,48)
OX,OY=100,100   # desplazamiento en la hoja
# UUID estables para enlazar esquemático y PCB
UU={r:str(uuid.uuid5(uuid.NAMESPACE_DNS,'rele-esp12f-'+r)) for r in C}
ROOT=str(uuid.uuid5(uuid.NAMESPACE_DNS,'rele-esp12f-root'))
