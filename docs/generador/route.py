import pcbnew, sys, shutil
from design import *
from proj import write_pro, DRU
P=lambda x,y: pcbnew.VECTOR2I(pcbnew.FromMM(x+OX),pcbnew.FromMM(y+OY))
base=sys.argv[1]  # sin extensión
write_pro(base+'.kicad_pro', base.split('/')[-1]); open(base+'.kicad_dru','w').write(DRU)
b=pcbnew.LoadBoard(base+'.kicad_pcb')
def keepout(pts,name):
    z=pcbnew.ZONE(b); z.SetIsRuleArea(True); z.SetDoNotAllowTracks(True); z.SetDoNotAllowVias(True)
    z.SetDoNotAllowPads(False); z.SetDoNotAllowCopperPour(True); z.SetDoNotAllowFootprints(False)
    ls=pcbnew.LSET(); ls.AddLayer(pcbnew.F_Cu); ls.AddLayer(pcbnew.B_Cu); z.SetLayerSet(ls)
    z.SetZoneName(name)
    o=z.Outline(); o.NewOutline()
    for x,y in pts: o.Append(pcbnew.FromMM(x+OX),pcbnew.FromMM(y+OY))
    b.Add(z)
keepout([(0,0),(30,0),(30,25.5),(33.5,25.5),(33.5,48),(0,48)],'TMP_MAINS')
keepout([(33.5,34.0),(42.5,34.0),(42.5,41.0),(33.5,41.0)],'TMP_COM')
pcbnew.ExportSpecctraDSN(b, base+'.dsn')
print('dsn ok')
