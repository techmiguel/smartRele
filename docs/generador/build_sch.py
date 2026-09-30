import copy, sys, uuid
from kiutils.schematic import Schematic
from kiutils.symbol import SymbolLib
from kiutils.items.common import Position, Property, Effects, Font, Justify, PageSettings, TitleBlock
from kiutils.items.schitems import SchematicSymbol, LocalLabel, NoConnect, Connection, SymbolProjectInstance, SymbolProjectPath
from design import *
proj=sys.argv[2]; out=sys.argv[1]
SYMDIR='/usr/share/kicad/symbols'
_libs={}
def libsym(lib_id):
    lib,name=lib_id.split(':')
    if lib not in _libs: _libs[lib]=SymbolLib.from_file(f'{SYMDIR}/{lib}.kicad_sym')
    L=_libs[lib]; s=copy.deepcopy([x for x in L.symbols if x.entryName==name][0])
    if s.extends:  # aplanar símbolo derivado
        par=copy.deepcopy([x for x in L.symbols if x.entryName==s.extends][0])
        par.properties=s.properties
        for u in par.units: u.entryName=name
        par.entryName=name; s=par; s.extends=None
    s.libraryNickname=lib; s.entryName=name
    for u in s.units: u.libraryNickname=None
    return s
def pins_of(s):
    return {p.number:p for u in s.units for p in u.pins}
sch=Schematic.create_new()
sch.version=20230121; sch.generator='eeschema'
sch.uuid=ROOT
sch.paper=PageSettings(paperSize='A4')
sch.titleBlock=TitleBlock(title='Modulo rele Wi-Fi ESP-12F 230V',date='2026-09-25',revision='1.0',company='techmigue.dev',
    comments={1:'Inspirado en aman983/ESP-01S_Relay_Module (diseno nuevo)',2:'Hardware: CERN-OHL-W v2'})
eff=lambda sz=1.27,hide=False,j=None: Effects(font=Font(width=sz,height=sz),hide=hide,justify=Justify(horizontally=j) if j else Justify())
# posiciones en el esquemático (mm, rejilla de 1.27)
SP={'J1':(25.4,76.2),'F1':(50.8,63.5),'RV1':(71.12,76.2),'PS1':(106.68,76.2),'K1':(63.5,119.38),
    'C1':(142.24,76.2),'C2':(154.94,76.2),'C3':(165.1,76.2),'U1':(190.5,68.58),'C4':(213.36,76.2),'C5':(223.52,76.2),'C6':(233.68,76.2),
    'U2':(190.5,139.7),'R1':(147.32,127.0),'R2':(157.48,127.0),'R3':(236.22,127.0),'R4':(246.38,127.0),'R5':(256.54,160.02),
    'Q1':(114.3,160.02),'D1':(99.06,144.78),'R6':(99.06,172.72),'R7':(121.92,177.8),'SW1':(254.0,186.69),'J3':(144.78,180.34)}
POWER={'GND':'power:GND','+5V':'power:+5V','+3V3':'power:+3V3'}
used={}
def add_lib(lib_id):
    if lib_id not in used:
        used[lib_id]=libsym(lib_id); sch.libSymbols.append(used[lib_id])
    return used[lib_id]
def uid(*a): return str(uuid.uuid5(uuid.NAMESPACE_DNS,'sch-'+'-'.join(map(str,a))))
def place(lib_id,ref,val,x,y,props=(),uu=None,fp='',inbom=True,onboard=True,refhide=False,rot=0):
    s=add_lib(lib_id)
    ss=SchematicSymbol(); ss.libraryNickname,ss.entryName=lib_id.split(':')
    ss.position=Position(X=x,Y=y,angle=rot); ss.unit=1; ss.inBom=inbom; ss.onBoard=onboard; ss.uuid=uu or uid(ref,x,y)
    ss.properties=[Property(key='Reference',value=ref,id=0,position=Position(X=x+2.54,Y=y-3.81,angle=0),effects=eff(hide=refhide,j='left')),
                   Property(key='Value',value=val,id=1,position=Position(X=x+2.54,Y=y+3.81,angle=0),effects=eff(hide=refhide,j='left')),
                   Property(key='Footprint',value=fp,id=2,position=Position(X=x,Y=y,angle=0),effects=eff(hide=True)),
                   Property(key='Datasheet',value='~',id=3,position=Position(X=x,Y=y,angle=0),effects=eff(hide=True))]
    for i,(k,v) in enumerate(props): ss.properties.append(Property(key=k,value=v,id=4+i,position=Position(X=x,Y=y,angle=0),effects=eff(hide=True)))
    ss.pins={p:uid(ref,p) for p in pins_of(s)}
    ss.instances=[SymbolProjectInstance(name=proj,paths=[SymbolProjectPath(sheetInstancePath='/'+ROOT,reference=ref,unit=1)])]
    sch.schematicSymbols.append(ss); return s
def wire(a,b):
    c=Connection(type='wire',points=[Position(X=a[0],Y=a[1]),Position(X=b[0],Y=b[1])],uuid=uid('w',a,b)); sch.graphicalItems.append(c)
npwr=[0]
def attach(x,y,px,py,ang,net):
    # punto de conexión en hoja y dirección hacia fuera del pin
    X=round(x+px,2); Y=round(y-py,2); outd=(ang+180)%360
    d={0:(1,0),90:(0,-1),180:(-1,0),270:(0,1)}[outd]
    E=(round(X+d[0]*2.54,2),round(Y+d[1]*2.54,2)); wire((X,Y),E)
    if net in POWER:
        npwr[0]+=1; r=f'#PWR0{npwr[0]:02d}'
        rot=((outd-270)%360) if net=='GND' else ((outd-90)%360)
        place(POWER[net],r,net,E[0],E[1],refhide=True,inbom=False,onboard=False,rot=rot)
        # fijar posición de textos del símbolo de alimentación
        sch.schematicSymbols[-1].properties[1].effects=eff()
        sch.schematicSymbols[-1].properties[0].effects=eff(hide=True)
    else:
        la={0:0,90:90,180:180,270:270}[outd]
        sch.labels.append(LocalLabel(text=net,position=Position(X=E[0],Y=E[1],angle=la),effects=eff(j='left' if la in (0,90) else 'right'),uuid=uid('l',E,net)))
for r,(lib,val,fpid,x,y,rot,pads,lcsc,asm) in C.items():
    sx,sy=SP[r]
    props=[('LCSC',lcsc)] if lcsc else []
    props.append(('Montaje',asm))
    s=place(lib,r,val,sx,sy,props,uu=UU[r],fp=fpid)
    for num,p in pins_of(s).items():
        if num in pads: attach(sx,sy,p.position.X,p.position.Y,p.position.angle,pads[num])
        else:
            X=round(sx+p.position.X,2); Y=round(sy-p.position.Y,2)
            sch.noConnects.append(NoConnect(position=Position(X=X,Y=Y),uuid=uid('nc',r,num)))
# PWR_FLAG en redes alimentadas desde la red (entradas power_in del HLK)
for i,(n,x,y) in enumerate([('L_F',86.36,55.88),('N',86.36,99.06)]):
    place('power:PWR_FLAG',f'#FLG0{i+1}','PWR_FLAG',x,y,refhide=True,inbom=False,onboard=False)
    sch.schematicSymbols[-1].properties[1].effects=eff()
    wire((x,y),(x,y+2.54))
    sch.labels.append(LocalLabel(text=n,position=Position(X=x,Y=y+2.54,angle=270),effects=eff(j='right'),uuid=uid('fl',n)))
# notas
from kiutils.items.schitems import Text
for t,x,y in [('ZONA 230V AC - sin aislamiento',20,40),('ZONA SELV 5V/3V3 (aislada por PS1)',140,40),
              ('GPIO5 no es pin de arranque: el rele no conmuta en boot',100,195),('J3: solo primer grabado, SIN red conectada',140,198)]:
    sch.texts.append(Text(text=t,position=Position(X=x,Y=y,angle=0),effects=eff(1.8,j='left'),uuid=uid('t',t)))
sch.to_file(out)
print('sch ok', len(sch.schematicSymbols))
