import pcbnew, sys
from design import *
P=lambda x,y: pcbnew.VECTOR2I(pcbnew.FromMM(x+OX),pcbnew.FromMM(y+OY))
base=sys.argv[1]
b=pcbnew.LoadBoard(base+'.kicad_pcb')
from ses import import_ses; print('ses',import_ses(b, base+'.ses'))
for z in list(b.Zones()):
    if z.GetZoneName().startswith('TMP_'): b.Remove(z)
gnd=b.FindNet('GND')
def zone(layer,pts):
    z=pcbnew.ZONE(b); z.SetLayer(layer); z.SetNet(gnd)
    z.SetLocalClearance(pcbnew.FromMM(0.3)); z.SetMinThickness(pcbnew.FromMM(0.25))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL); z.SetThermalReliefGap(pcbnew.FromMM(0.4)); z.SetThermalReliefSpokeWidth(pcbnew.FromMM(0.5))
    z.SetZoneName('GND_LV')
    o=z.Outline(); o.NewOutline()
    for x,y in pts: o.Append(pcbnew.FromMM(x+OX),pcbnew.FromMM(y+OY))
    b.Add(z)
LV=[(31,0.4),(65.6,0.4),(65.6,47.6),(45.5,47.6),(45.5,28.0),(31,28.0)]
zone(pcbnew.B_Cu,LV); zone(pcbnew.F_Cu,LV)
def txt(s,x,y,size=1.2,rot=0):
    t=pcbnew.PCB_TEXT(b); t.SetText(s); t.SetPosition(P(x,y)); t.SetLayer(pcbnew.F_SilkS)
    t.SetTextSize(pcbnew.VECTOR2I(pcbnew.FromMM(size),pcbnew.FromMM(size))); t.SetTextThickness(pcbnew.FromMM(size*0.15)); t.SetTextAngleDegrees(rot); b.Add(t)
txt('N',4,36.3); txt('OUT',9.08,36.3); txt('L',14.16,36.3)
txt('!! 230V AC !!',8.5,31.0,1.0)
txt('rele-esp12f v1.0',24.5,46.6,1.0)
txt('techmigue.dev',55,47.0,0.8)
txt('3V3 GND TX RX IO0 RST',61.3,39.5,0.8,270)
# zona libre de cobre alrededor de la antena del ESP-12F
ka=pcbnew.ZONE(b); ka.SetIsRuleArea(True); ka.SetDoNotAllowCopperPour(True); ka.SetDoNotAllowTracks(True); ka.SetDoNotAllowVias(True)
ka.SetDoNotAllowPads(False); ka.SetDoNotAllowFootprints(False)
ls=pcbnew.LSET(); ls.AddLayer(pcbnew.F_Cu); ls.AddLayer(pcbnew.B_Cu); ka.SetLayerSet(ls); ka.SetZoneName('ANTENA')
o=ka.Outline(); o.NewOutline()
for x,y in [(40.5,0),(66,0),(66,8.0),(40.5,8.0)]: o.Append(pcbnew.FromMM(x+OX),pcbnew.FromMM(y+OY))
b.Add(ka)
# referencias de serigrafía legibles
POS={'R2':(39.6,9.4,90),'R1':(39.6,13.2,90),'C5':(39.6,18.9,90),'C4':(39.6,22.6,90),
     'R3':(65.2,15.8,90),'R4':(65.2,19.4,90),'R5':(65.2,23.0,90),'C6':(61.0,27.6,0),
     'C2':(48.3,33.6,0),'C3':(52.3,37.8,0),'D1':(48.0,37.0,0),'Q1':(50.6,42.6,0),
     'R7':(47.6,44.3,0),'R6':(51.8,44.3,0),'U1':(55.2,26.2,0),'C1':(46.0,26.3,0),
     'SW1':(56.6,38.2,0),'J3':(63.8,31.0,0),'U2':(52.5,27.0,0),'PS1':(20.0,2.0,0),
     'K1':(29.0,28.3,0),'F1':(9.0,26.3,0),'RV1':(22.6,22.6,0),'J1':(9.08,47.2,0)}
for fp in b.GetFootprints():
    r=fp.GetReference(); ref=fp.Reference()
    if r in POS:
        x,y,a=POS[r]; ref.SetPosition(P(x,y)); ref.SetTextAngleDegrees(a)
        ref.SetTextSize(pcbnew.VECTOR2I(pcbnew.FromMM(0.8),pcbnew.FromMM(0.8))); ref.SetTextThickness(pcbnew.FromMM(0.12))
filler=pcbnew.ZONE_FILLER(b); filler.Fill(b.Zones())
b.Save(base+'.kicad_pcb')
pcbnew.WriteDRCReport(b, base+'_drc.rpt', pcbnew.EDA_UNITS_MILLIMETRES, True)
print('done')
