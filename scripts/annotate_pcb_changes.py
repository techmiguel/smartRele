# Draws the v3/v3.1 change call-outs on docs/pcb_top.png and docs/pcb_bottom.png (output: docs/linkedin/).
from PIL import Image, ImageDraw, ImageFont
import sys
import os
REPO=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
S=2  # supersampling
M=56
W,H=1080*S,1350*S
F="/usr/share/fonts/opentype/inter/"
def font(w,sz): return ImageFont.truetype(F+f"Inter-{w}.otf", sz*S)
BG=(247,248,250); INK=(15,23,42); MUTED=(71,85,105)
CAT={"Red eléctrica / seguridad":(239,68,68),"RF / antena":(147,51,234),
     "Alimentación y arranque ESP":(8,145,178),"Mecánica":(217,119,6)}
# mm -> source px (fitted on C5, C8 and verified on MH1/MH2/D3)
def mm(x,y): return (-963.5+x*13.1, -1197.2+y*13.1)

def build(src, crop, items, title, subtitle, out, footer, H=H):
    img=Image.open(src).convert("RGB")
    canvas=Image.new("RGB",(W,H),BG); d=ImageDraw.Draw(canvas)
    # header
    d.text((M*S,44*S),title,font=font("Bold",40),fill=INK)
    d.text((M*S,98*S),subtitle,font=font("Medium",21),fill=MUTED)
    # board card
    cx0,cy0,cx1,cy1=crop
    bw=W-2*M*S; sc=bw/(cx1-cx0); bh=int((cy1-cy0)*sc)
    board=img.crop(crop).resize((bw,bh),Image.LANCZOS)
    bx,by=M*S,150*S
    mask=Image.new("L",(bw,bh),0); ImageDraw.Draw(mask).rounded_rectangle((0,0,bw,bh),radius=22*S,fill=255)
    canvas.paste(board,(bx,by),mask)
    def P(p): return (bx+(p[0]-cx0)*sc, by+(p[1]-cy0)*sc)
    # boxes
    for it in items:
        col=CAT[it["cat"]]
        for k,(a,b) in enumerate(it["boxes"]):
            x0,y0=P(a); x1,y1=P(b)
            d.rounded_rectangle((x0,y0,x1,y1),radius=8*S,outline=(255,255,255),width=9*S)
            d.rounded_rectangle((x0,y0,x1,y1),radius=8*S,outline=col,width=5*S)
            # badge
            r=19*S
            ax,ay=it.get("badge",["tl"]*9)[k] if "badge" in it else "tl", None
            pos=it.get("badge",["tl"]*len(it["boxes"]))[k]
            bxp={"tl":(x0,y0),"tr":(x1,y0),"bl":(x0,y1),"br":(x1,y1)}[pos]
            d.ellipse((bxp[0]-r,bxp[1]-r,bxp[0]+r,bxp[1]+r),fill=col,outline=(255,255,255),width=3*S)
            d.text(bxp,str(it["n"]),font=font("Bold",21),fill=(255,255,255),anchor="mm")
    # legend
    ly=by+bh+24*S
    cats=[]; [cats.append(i["cat"]) for i in items if i["cat"] not in cats]
    x=M*S
    for c in cats:
        d.rounded_rectangle((x,ly+3*S,x+16*S,ly+19*S),radius=4*S,fill=CAT[c])
        t=font("SemiBold",17); d.text((x+24*S,ly),c,font=t,fill=MUTED)
        x+=24*S+d.textlength(c,font=t)+30*S
    ly+=42*S
    cols=2; colw=(W-2*M*S-30*S)//cols
    rows=(len(items)+1)//cols
    avail=H-76*S-ly; rowh=min(avail//rows,150*S)
    for i,it in enumerate(items):
        c=i//rows if len(items)>4 else i%cols
        r=i%rows if len(items)>4 else i//cols
        x=M*S+c*(colw+30*S); y=ly+r*rowh
        col=CAT[it["cat"]]; rr=17*S
        d.ellipse((x,y,x+2*rr,y+2*rr),fill=col)
        d.text((x+rr,y+rr),str(it["n"]),font=font("Bold",19),fill=(255,255,255),anchor="mm")
        tx=x+2*rr+14*S
        d.text((tx,y+1*S),it["t"],font=font("Bold",20),fill=INK)
        # wrap detail
        fd=font("Regular",17); words=it["d"].split(); line=""; yy=y+31*S
        maxw=colw-(tx-x)
        for w_ in words:
            test=(line+" "+w_).strip()
            if d.textlength(test,font=fd)>maxw:
                d.text((tx,yy),line,font=fd,fill=MUTED); yy+=23*S; line=w_
            else: line=test
        d.text((tx,yy),line,font=fd,fill=MUTED)
    # footer
    d.line((M*S,H-62*S,W-M*S,H-62*S),fill=(226,232,240),width=2*S)
    d.text((M*S,H-44*S),footer,font=font("Medium",16),fill=MUTED)
    d.text((W-M*S,H-44*S),"github.com/techmiguel/smartRele",font=font("SemiBold",16),fill=INK,anchor="ra")
    canvas.resize((W//S,H//S),Image.LANCZOS).save(out,optimize=True)

def box(c,hw,hh): return ((c[0]-hw,c[1]-hh),(c[0]+hw,c[1]+hh))
top=[
 dict(n=1,cat="RF / antena",t="Recorte bajo la antena",
      d="7,6 × 18,7 mm sin FR-4 ni cobre bajo la antena del ESP-12F, como recomienda Espressif.",
      boxes=[((1108,128),(1218,354))],badge=["bl"]),
 dict(n=2,cat="Red eléctrica / seguridad",t="Relé Omron G5RL (16 A)",
      d="Bobina y contactos a 20 mm con aislamiento reforzado; carga de hasta 10 A.",
      boxes=[((556,512),(954,694))],badge=["tr"]),
 dict(n=3,cat="Alimentación y arranque ESP",t="C9 de 10 µF junto a VCC",
      d="Absorbe los picos de ~400 mA del ESP-12F al transmitir.",
      boxes=[box(mm(139.22,104.8),20,30)],badge=["tl"]),
 dict(n=4,cat="Alimentación y arranque ESP",t="C7 / C8 de 100 nF en EN y RST",
      d="Retardo RC de ~1 ms en el arranque, según la guía de Espressif.",
      boxes=[box(mm(139.2,115),20,17),box(mm(161.5,140.3),22,14)],badge=["tl","bl"]),
 dict(n=5,cat="Alimentación y arranque ESP",t="J3 de programación a 5 V",
      d="Ya no polariza en inverso el AMS1117 ni divide el plano GND bajo el módulo.",
      boxes=[((1098,494),(1212,614))],badge=["tr"]),
 dict(n=6,cat="Red eléctrica / seguridad",t="F1 y RV1 desplazados 2 mm",
      d="El cobre de red queda a ≥ 2,0 mm del borde (antes 1,3 mm).",
      boxes=[((383,426),(608,499))],badge=["tl"]),
 dict(n=7,cat="Mecánica",t="Pista de D3 fuera de MH1",
      d="Ninguna señal dentro de Ø5 mm de los tornillos de fijación.",
      boxes=[((952,624),(1042,712))],badge=["br"]),
]
build(f"{REPO}/docs/pcb_top.png",(343,106,1227,766),top,
      "smartRele v3.1: qué cambió y por qué",
      "Wi-Fi relay con ESP-12F · 110 VAC · cambios aplicados tras la revisión de diseño",
      f"{REPO}/docs/linkedin/pcb_top_cambios.png","Cara superior · render KiCad")
bot=[
 dict(n=8,cat="Red eléctrica / seguridad",t="L_IN / L_OUT en ambas caras",
      d="2 × 2,5 mm por cara: ~12 A con +20 °C (IPC-2221). Soporta la carga de 10 A.",
      boxes=[((896,478),(1200,738))],badge=["tr"]),
 dict(n=9,cat="Red eléctrica / seguridad",t="Separación de 4 mm en toda la placa",
      d="Se eliminó la regla local de K1 que reducía la distancia red ↔ baja tensión a 2 mm.",
      boxes=[((834,430),(890,742))],badge=["tl"]),
]
build(f"{REPO}/docs/pcb_bottom.png",(343,106,1227,766),bot,
      "smartRele v3.1: cara inferior",
      "Pistas de potencia y aislamiento entre la zona de red y la de baja tensión",
      f"{REPO}/docs/linkedin/pcb_bottom_cambios.png","Cara inferior · render KiCad (vista espejada)", H=1130*S)
