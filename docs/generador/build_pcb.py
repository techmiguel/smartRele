import pcbnew, json, sys
from design import *
P=lambda x,y: pcbnew.VECTOR2I(pcbnew.FromMM(x+OX),pcbnew.FromMM(y+OY))
out=sys.argv[1]
b=pcbnew.NewBoard(out)
b.SetCopperLayerCount(2)
nets={}
def net(n):
    if n not in nets:
        ni=pcbnew.NETINFO_ITEM(b,n); b.Add(ni); nets[n]=ni
    return nets[n]
for r,(lib,val,fpid,x,y,rot,pads,lcsc,asm) in C.items():
    lib_n,name=fpid.split(':')
    fp=pcbnew.FootprintLoad(f'{FPLIB}/{lib_n}.pretty',name)
    fp.SetFPID(pcbnew.LIB_ID(lib_n,name))
    fp.SetReference(r); fp.SetValue(val)
    fp.SetPosition(P(x,y)); fp.SetOrientationDegrees(rot)
    fp.SetPath(pcbnew.KIID_PATH('/'+ROOT+'/'+UU[r]) if False else pcbnew.KIID_PATH('/'+UU[r]))
    if lcsc: fp.SetField('LCSC',lcsc) if hasattr(fp,'SetField') else None
    if asm!='JLCPCB':
        fp.SetAttributes(fp.GetAttributes() | pcbnew.FP_EXCLUDE_FROM_POS_FILES)
    if asm=='No montar':
        fp.SetAttributes(fp.GetAttributes() | pcbnew.FP_EXCLUDE_FROM_BOM)
    b.Add(fp)
    for p in fp.Pads():
        if p.GetNumber() in pads: p.SetNet(net(pads[p.GetNumber()]))
# contorno con esquinas redondeadas
W,H=BOARD; R=2.0
def seg(a,bb,layer=pcbnew.Edge_Cuts,w=0.1):
    s=pcbnew.PCB_SHAPE(b); s.SetShape(pcbnew.SHAPE_T_SEGMENT); s.SetStart(P(*a)); s.SetEnd(P(*bb)); s.SetLayer(layer); s.SetWidth(pcbnew.FromMM(w)); b.Add(s)
def arc(c,st,ang):
    s=pcbnew.PCB_SHAPE(b); s.SetShape(pcbnew.SHAPE_T_ARC); s.SetCenter(P(*c)); s.SetStart(P(*st)); s.SetArcAngleAndEnd(pcbnew.EDA_ANGLE(ang,pcbnew.DEGREES_T)); s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(pcbnew.FromMM(0.1)); b.Add(s)
seg((R,0),(W-R,0)); seg((W,R),(W,H-R)); seg((W-R,H),(R,H)); seg((0,H-R),(0,R))
arc((R,R),(0,R),90); arc((W-R,R),(W-R,0),90); arc((W-R,H-R),(W,H-R),90); arc((R,H-R),(R,H),90)
# pistas de red (ruteo manual)
def tr(n,pts,w,layer=pcbnew.F_Cu):
    for a,c in zip(pts,pts[1:]):
        t=pcbnew.PCB_TRACK(b); t.SetStart(P(*a)); t.SetEnd(P(*c)); t.SetWidth(pcbnew.FromMM(w)); t.SetLayer(layer); t.SetNet(net(n)); t.SetLocked(True); b.Add(t)
tr('L_IN',[(14.16,42.5),(18.16,38.5),(37.5,38.5),(38.5,37.5)],2.5)          # borna -> COM (carga)
tr('L_OUT',[(9.08,42.5),(9.08,37.0),(12.58,33.5),(22.3,33.5),(24.35,31.45)],2.5) # NO -> borna (carga)
tr('L_IN',[(12,26.3),(14.16,28.46),(14.16,42.5)],1.0,pcbnew.B_Cu)              # borna -> fusible (cara inferior)
tr('L_F',[(17.08,26.31),(17.08,12.0),(14.58,9.5),(5.5,9.5)],1.0)               # fusible -> HLK L
tr('L_F',[(17.08,26.31),(20.6,25.0)],1.0)                                       # fusible -> MOV
tr('N',[(4,42.5),(4,16.0),(5.5,14.5)],1.0)                                     # borna N -> HLK N
tr('N',[(25.6,26.3),(25.6,18.0),(8.0,18.0),(5.5,15.5),(5.5,14.5)],1.0,pcbnew.B_Cu)  # MOV -> N (inferior)
b.Save(out)
print('ok',len(list(b.GetFootprints())))
