# -*- coding: utf-8 -*-
"""Genera docs/rele-esp12f_datasheet_guia_usuario.pdf

Hoja de datos + guía de usuario del módulo rele-esp12f (rev. v3).
Requiere: reportlab, PyMuPDF (fitz), Pillow y kicad-cli 10 (para las vistas de capas
y el esquemático). Uso:  python scripts/generar_datasheet.py
"""
import os, subprocess, tempfile, datetime
import fitz
from PIL import Image
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer,
                                Table, TableStyle, Image as RLImage, PageBreak,
                                NextPageTemplate, KeepTogether, CondPageBreak, Preformatted)
from reportlab.platypus.tableofcontents import TableOfContents
from reportlab.graphics.shapes import Drawing, Rect, Line, String, Circle, Polygon, PolyLine, Group
from reportlab.graphics import renderPDF  # noqa: F401  (Drawing como flowable)

PRJ = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
OUT = os.path.join(PRJ, 'docs', 'rele-esp12f_datasheet_guia_usuario.pdf')
KICAD_CLI = r'C:\Program Files\KiCad\10.0\bin\kicad-cli.exe'
PCB = os.path.join(PRJ, 'rele-esp12f.kicad_pcb')
SCH = os.path.join(PRJ, 'rele-esp12f.kicad_sch')
DOC_REV = 'A'
DOC_DATE = '2026-10-03'
HW_REV = 'v3'

# ---------------------------------------------------------------- fuentes
F = r'C:\Windows\Fonts'
pdfmetrics.registerFont(TTFont('Sans', os.path.join(F, 'segoeui.ttf')))
pdfmetrics.registerFont(TTFont('Sans-B', os.path.join(F, 'segoeuib.ttf')))
pdfmetrics.registerFont(TTFont('Sans-I', os.path.join(F, 'segoeuii.ttf')))
pdfmetrics.registerFont(TTFont('Sans-BI', os.path.join(F, 'segoeuiz.ttf')))
pdfmetrics.registerFont(TTFont('Mono', os.path.join(F, 'consola.ttf')))
pdfmetrics.registerFont(TTFont('Mono-B', os.path.join(F, 'consolab.ttf')))
from reportlab.pdfbase.pdfmetrics import registerFontFamily
registerFontFamily('Sans', normal='Sans', bold='Sans-B', italic='Sans-I', boldItalic='Sans-BI')
registerFontFamily('Mono', normal='Mono', bold='Mono-B', italic='Mono', boldItalic='Mono-B')

# ---------------------------------------------------------------- colores
INK = colors.HexColor('#1d2733')
ACC = colors.HexColor('#0f5c8c')      # azul de marca
ACC2 = colors.HexColor('#e8f1f8')
GRID = colors.HexColor('#c5d2de')
ZEBRA = colors.HexColor('#f5f8fb')
MUTED = colors.HexColor('#5b6b7a')
RED = colors.HexColor('#b3261e')
RED_BG = colors.HexColor('#fdecea')
AMB = colors.HexColor('#9a6700')
AMB_BG = colors.HexColor('#fff6dc')
BLU_BG = colors.HexColor('#eaf3fb')
GRN = colors.HexColor('#2e7d32')
MAINS_BG = colors.HexColor('#fdeeee')
SELV_BG = colors.HexColor('#eaf2fb')

# ---------------------------------------------------------------- estilos
def S(name, **kw):
    base = dict(fontName='Sans', fontSize=9, leading=12.6, textColor=INK)
    base.update(kw)
    return ParagraphStyle(name, **base)

sBody = S('body', alignment=TA_JUSTIFY, spaceAfter=5)
sBodyL = S('bodyl', spaceAfter=4)
sSmall = S('small', fontSize=7.6, leading=10, textColor=MUTED)
sCell = S('cell', fontSize=7.8, leading=10.2)
sCellB = S('cellb', fontName='Sans-B', fontSize=7.8, leading=10.2)
sHead = S('head', fontName='Sans-B', fontSize=7.8, leading=10.2, textColor=colors.white)
sH1 = S('h1', fontName='Sans-B', fontSize=16, leading=20, textColor=ACC, spaceBefore=4, spaceAfter=8, keepWithNext=1)
sH2 = S('h2', fontName='Sans-B', fontSize=11.5, leading=15, textColor=INK, spaceBefore=10, spaceAfter=5, keepWithNext=1)
sH3 = S('h3', fontName='Sans-B', fontSize=9.5, leading=13, textColor=ACC, spaceBefore=7, spaceAfter=3, keepWithNext=1)
sPart = S('part', fontName='Sans-B', fontSize=30, leading=36, textColor=ACC)
sCap = S('cap', fontName='Sans-I', fontSize=7.8, leading=10, textColor=MUTED, alignment=TA_CENTER,
         spaceBefore=3, spaceAfter=8)
sBul = S('bul', leftIndent=11, bulletIndent=2, spaceAfter=2.5)
sNum = S('num', leftIndent=14, bulletIndent=0, spaceAfter=3)
sCode = ParagraphStyle('code', fontName='Mono', fontSize=7.3, leading=9.2, textColor=INK)
sTOC1 = S('toc1', fontName='Sans-B', fontSize=9.2, leading=13.2, leftIndent=0, spaceBefore=1.5)
sTOC2 = S('toc2', fontSize=8.2, leading=10.6, leftIndent=14, textColor=MUTED)

W_FULL = A4[0] - 2 * 18 * mm   # ancho útil retrato


def P(t, st=sBody):
    return Paragraph(t, st)


def bullets(items, st=sBul):
    return [Paragraph(t, st, bulletText='•') for t in items]


def steps(items):
    return [Paragraph(t, sNum, bulletText=f'{i}.') for i, t in enumerate(items, 1)]


def table(rows, widths, head=True, zebra=True, align_top=True, font=None, span=None, extra=None):
    """rows: lista de listas de str/flowables. Los str se convierten en Paragraph."""
    data = []
    for r_i, r in enumerate(rows):
        row = []
        for c in r:
            if isinstance(c, str):
                st = sHead if (head and r_i == 0) else sCell
                row.append(Paragraph(c, st))
            else:
                row.append(c)
        data.append(row)
    tot = sum(widths)
    widths = [w * W_FULL / tot for w in widths]
    t = Table(data, colWidths=widths, repeatRows=1 if head else 0)
    st = [('GRID', (0, 0), (-1, -1), 0.4, GRID),
          ('VALIGN', (0, 0), (-1, -1), 'TOP' if align_top else 'MIDDLE'),
          ('LEFTPADDING', (0, 0), (-1, -1), 4), ('RIGHTPADDING', (0, 0), (-1, -1), 4),
          ('TOPPADDING', (0, 0), (-1, -1), 2.5), ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5)]
    if head:
        st.append(('BACKGROUND', (0, 0), (-1, 0), ACC))
    if zebra:
        for i in range(1 if head else 0, len(data)):
            if i % 2 == 0:
                st.append(('BACKGROUND', (0, i), (-1, i), ZEBRA))
    if extra:
        st += extra
    t.setStyle(TableStyle(st))
    return t


def callout(kind, title, body):
    pal = {'peligro': (RED, RED_BG), 'atencion': (AMB, AMB_BG), 'nota': (ACC, BLU_BG)}[kind]
    tst = S('ct', fontName='Sans-B', fontSize=8.6, leading=11.5, textColor=pal[0])
    bst = S('cb', fontSize=8.4, leading=11.4)
    content = [Paragraph(title, tst)]
    if isinstance(body, str):
        content.append(Paragraph(body, bst))
    else:
        for b in body:
            content.append(Paragraph(b, bst, bulletText='•') if not b.startswith('§') else Paragraph(b[1:], bst))
    t = Table([[content]], colWidths=[W_FULL])
    t.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), pal[1]),
                           ('LINEBEFORE', (0, 0), (0, -1), 3, pal[0]),
                           ('LEFTPADDING', (0, 0), (-1, -1), 9), ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                           ('TOPPADDING', (0, 0), (-1, -1), 5), ('BOTTOMPADDING', (0, 0), (-1, -1), 6)]))
    return KeepTogether([Spacer(1, 3), t, Spacer(1, 6)])


def code(text):
    pre = Preformatted(text.strip('\n'), sCode)
    t = Table([[pre]], colWidths=[W_FULL])
    t.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f3f5f7')),
                           ('BOX', (0, 0), (-1, -1), 0.4, GRID),
                           ('LEFTPADDING', (0, 0), (-1, -1), 7), ('TOPPADDING', (0, 0), (-1, -1), 5),
                           ('BOTTOMPADDING', (0, 0), (-1, -1), 5)]))
    return KeepTogether([t, Spacer(1, 6)])


def img(path, width, caption=None):
    im = Image.open(path)
    w, h = im.size
    flow = [RLImage(path, width=width, height=width * h / w)]
    if caption:
        flow.append(Paragraph(caption, sCap))
    return KeepTogether(flow)


def fig(drawing, caption):
    return KeepTogether([drawing, Paragraph(caption, sCap)])


# ---------------------------------------------------------------- recursos gráficos
def build_assets(tmp):
    a = {}
    # vistas de cobre (top y bottom, esta última vista desde abajo)
    for name, layers, extra in [('top', 'F.Cu,F.SilkS,Edge.Cuts', []),
                                ('bot', 'B.Cu,B.SilkS,Edge.Cuts', ['--mirror'])]:
        pdf = os.path.join(tmp, name + '.pdf')
        subprocess.run([KICAD_CLI, 'pcb', 'export', 'pdf', '--layers', layers, '--mode-single',
                        *extra, '-o', pdf, PCB], check=True, capture_output=True)
        pg = fitz.open(pdf)[0]
        bb = None
        for d in pg.get_drawings():
            bb = d['rect'] if bb is None else bb | d['rect']
        clip = fitz.Rect(bb.x0 - 3, bb.y0 - 3, bb.x1 + 3, bb.y1 + 3)
        a[name] = os.path.join(tmp, name + '.png')
        pg.get_pixmap(dpi=400, clip=clip).save(a[name])
    # esquemático
    spdf = os.path.join(tmp, 'sch.pdf')
    subprocess.run([KICAD_CLI, 'sch', 'export', 'pdf', '-o', spdf, SCH], check=True, capture_output=True)
    pg = fitz.open(spdf)[0]
    a['sch'] = os.path.join(tmp, 'sch.png')
    pg.get_pixmap(dpi=260).save(a['sch'])
    # renders 3D existentes, recortados a la placa
    for name, src in [('r3d_top', 'pcb_superior.png'), ('r3d_bot', 'pcb_inferior.png')]:
        im = Image.open(os.path.join(PRJ, 'docs', src)).convert('RGB')
        px = im.load()
        W, H = im.size
        # fondo: degradado lavanda (azul > rojo y claro). Máscara de "no fondo".
        xs, ys = [], []
        for y in range(0, H, 2):
            for x in range(0, W, 2):
                r, g, b = px[x, y]
                bg = (b > r + 8) and (b > g) and (r + g + b) > 330 and abs(r - g) < 14
                if not bg:
                    xs.append(x); ys.append(y)
        box = (max(min(xs) - 8, 0), max(min(ys) - 8, 0), min(max(xs) + 8, W), min(max(ys) + 8, H))
        a[name] = os.path.join(tmp, name + '.png')
        im.crop(box).save(a[name])
    return a


# ---------------------------------------------------------------- dibujos
def arrow(g, pts, col=INK, w=0.9, head=True, dash=None):
    g.add(PolyLine(pts, strokeColor=col, strokeWidth=w, strokeDashArray=dash))
    if head:
        (x1, y1), (x2, y2) = pts[-4:-2], pts[-2:]
        x1, y1 = pts[-4], pts[-3]
        x2, y2 = pts[-2], pts[-1]
        import math
        ang = math.atan2(y2 - y1, x2 - x1)
        L, Wd = 5, 2.4
        p1 = (x2 - L * math.cos(ang) + Wd * math.sin(ang), y2 - L * math.sin(ang) - Wd * math.cos(ang))
        p2 = (x2 - L * math.cos(ang) - Wd * math.sin(ang), y2 - L * math.sin(ang) + Wd * math.cos(ang))
        g.add(Polygon([x2, y2, p1[0], p1[1], p2[0], p2[1]], fillColor=col, strokeColor=col, strokeWidth=0.3))


def box(g, x, y, w, h, title, sub=(), fill=colors.white, stroke=INK, tcol=INK):
    g.add(Rect(x, y, w, h, rx=3, ry=3, fillColor=fill, strokeColor=stroke, strokeWidth=0.9))
    lines = [title] + list(sub)
    n = len(lines)
    lh = 9.2
    y0 = y + h / 2 + (n - 1) * lh / 2 - 3
    for i, s in enumerate(lines):
        g.add(String(x + w / 2, y0 - i * lh, s, fontName='Sans-B' if i == 0 else 'Sans',
                     fontSize=7.8 if i == 0 else 6.8, fillColor=tcol, textAnchor='middle'))


def lbl(g, x, y, s, size=6.4, col=MUTED, anchor='start', font='Sans'):
    g.add(String(x, y, s, fontName=font, fontSize=size, fillColor=col, textAnchor=anchor))


def block_diagram():
    d = Drawing(W_FULL, 262)
    g = Group()
    Wd = W_FULL
    bar = 212
    g.add(Rect(0, 0, bar - 4, 262, fillColor=MAINS_BG, strokeColor=None))
    g.add(Rect(bar + 4, 0, Wd - bar - 4, 262, fillColor=SELV_BG, strokeColor=None))
    g.add(Line(bar, 0, bar, 262, strokeColor=RED, strokeWidth=1.2, strokeDashArray=[4, 3]))
    lbl(g, 8, 250, 'ZONA DE RED  110–120 VAC', 7.4, RED, font='Sans-B')
    lbl(g, bar + 12, 250, 'ZONA SELV  5 V / 3,3 V (aislada por PS1)', 7.4, ACC, font='Sans-B')
    lbl(g, bar + 3, 238, 'barrera de aislamiento', 6.0, RED)
    lbl(g, bar + 3, 231, '≥ 4 mm en cobre', 6.0, RED)

    box(g, 10, 150, 58, 62, 'J1', ('Borna 3P', '5,08 mm', 'N · OUT · L'))
    box(g, 92, 188, 58, 30, 'F1', ('T500 mA 250 V',))
    box(g, 92, 140, 58, 30, 'RV1', ('07D221K',))
    box(g, 166, 168, 96, 52, 'PS1  HLK-PM01', ('AC/DC aislado', '5 V · 0,6 A'))
    box(g, 160, 30, 106, 58, 'K1  G5RL-1A-E-HR', ('Contacto NA 16 A', 'Bobina 5 V · 80 mA'))
    box(g, 292, 176, 70, 40, 'U1', ('AMS1117-3.3', 'LDO 1 A'))
    box(g, 392, 112, Wd - 400, 104, 'U2  ESP-12F', ('ESP8266EX', 'Wi-Fi 2,4 GHz', 'b/g/n', 'antena PCB'))
    box(g, 292, 50, 70, 38, 'Q1  SS8050', ('driver + D1', 'flyback'))
    box(g, 292, 112, 70, 36, 'D2 · D3', ('LED relé / Wi-Fi',))
    box(g, 392, 44, 64, 38, 'SW1 · SW2', ('IO0 · RST',))
    box(g, 392, 6, Wd - 400, 28, 'J3  PROG 2×3', ('UART · IO0 · RST · 5 V',))

    # red
    arrow(g, [68, 203, 92, 203], RED)            ; lbl(g, 70, 206, 'L', 6.4, RED)
    arrow(g, [150, 203, 166, 203], RED)          ; lbl(g, 151, 206, 'L_F', 6.0, RED)
    arrow(g, [68, 160, 92, 155], RED, head=False); lbl(g, 72, 163, 'N', 6.4, RED)
    arrow(g, [150, 155, 158, 155, 158, 180, 166, 180], RED, head=False)
    lbl(g, 120, 182, 'L_F / N', 5.8, RED)
    arrow(g, [24, 150, 24, 70, 160, 70], RED)   ; lbl(g, 28, 73, 'L_IN', 6.2, RED)
    arrow(g, [160, 46, 40, 46, 40, 150], RED)   ; lbl(g, 44, 49, 'L_OUT → carga', 6.2, RED)
    # SELV
    arrow(g, [262, 196, 292, 196], ACC)        ; lbl(g, 266, 199, '+5 V', 6.4, ACC)
    arrow(g, [362, 196, 392, 196], ACC)        ; lbl(g, 365, 199, '+3V3', 6.4, ACC)
    arrow(g, [276, 196, 276, 80, 266, 80], ACC); lbl(g, 270, 92, 'bobina', 5.8, ACC)
    arrow(g, [292, 62, 266, 62], ACC)          ; lbl(g, 268, 52, 'COIL_N', 5.8, ACC)
    arrow(g, [392, 124, 378, 124, 378, 70, 362, 70], ACC); lbl(g, 380, 96, 'GPIO5', 6.0, ACC)
    arrow(g, [378, 130, 362, 130], ACC)        ; lbl(g, 364, 150, 'GPIO5/4', 5.8, ACC)
    arrow(g, [424, 82, 424, 112], ACC)         ; lbl(g, 427, 92, 'GPIO0 / RST', 5.8, ACC)
    arrow(g, [Wd - 14, 34, Wd - 14, 112], ACC) ; lbl(g, Wd - 17, 70, 'UART', 5.8, ACC, anchor='end')
    d.add(g)
    return d


def wiring_diagram():
    d = Drawing(W_FULL, 220)
    g = Group()
    # placa
    bx, by, bw, bh = 120, 120, 170, 88
    g.add(Rect(bx - 12, by - 12, bw + 24, bh + 24, rx=6, ry=6, fillColor=colors.HexColor('#f4f4f4'),
               strokeColor=MUTED, strokeDashArray=[3, 2], strokeWidth=0.8))
    lbl(g, bx - 6, by + bh + 4, 'Caja aislante (IP adecuada al lugar)', 6.4, MUTED)
    g.add(Rect(bx, by, bw, bh, rx=3, ry=3, fillColor=colors.HexColor('#21412a'), strokeColor=INK))
    lbl(g, bx + bw / 2, by + bh - 18, 'rele-esp12f', 9, colors.white, 'middle', 'Sans-B')
    lbl(g, bx + bw / 2, by + bh - 30, 'J1 en el borde inferior', 6.6, colors.HexColor('#cfe3d3'), 'middle')
    xN, xO, xL = bx + 40, bx + 85, bx + 130
    for x, t in [(xN, 'N'), (xO, 'OUT'), (xL, 'L')]:
        g.add(Rect(x - 13, by - 2, 26, 22, fillColor=colors.HexColor('#5fbf7a'), strokeColor=INK, strokeWidth=0.6))
        g.add(Circle(x, by + 9, 5.5, fillColor=colors.white, strokeColor=INK, strokeWidth=0.6))
        lbl(g, x, by + 26, t, 7.4, colors.white, 'middle', 'Sans-B')
    # red (fuente a la derecha)
    sx = W_FULL - 70
    g.add(Rect(sx, 20, 66, 112, rx=3, ry=3, fillColor=colors.white, strokeColor=INK))
    lbl(g, sx + 33, 118, 'Cuadro', 7.6, INK, 'middle', 'Sans-B')
    lbl(g, sx + 33, 108, 'eléctrico', 7.6, INK, 'middle', 'Sans-B')
    lbl(g, sx + 33, 96, '110–120 VAC', 6.6, MUTED, 'middle')
    # magnetotérmico en L
    yL, yN, yPE = 70, 40, 20
    g.add(Rect(sx - 100, yL - 11, 46, 22, fillColor=AMB_BG, strokeColor=AMB))
    lbl(g, sx - 77, yL + 1.5, 'Magnetot.', 6.2, AMB, 'middle', 'Sans-B')
    lbl(g, sx - 77, yL - 7, '≤ 10 A', 6.2, AMB, 'middle', 'Sans-B')
    g.add(Line(sx, yL, sx - 54, yL, strokeColor=RED, strokeWidth=1.6))
    g.add(PolyLine([sx - 100, yL, xL, yL, xL, by - 2], strokeColor=RED, strokeWidth=1.6))
    lbl(g, sx - 4, yL + 3, 'L (fase)', 6.6, RED, 'end')
    # neutro
    g.add(PolyLine([sx, yN, xN, yN, xN, by - 2], strokeColor=ACC, strokeWidth=1.6))
    lbl(g, sx - 4, yN + 3, 'N (neutro)', 6.6, ACC, 'end')
    # carga
    lx, ly = xO, 6
    g.add(PolyLine([xO, by - 2, xO, 104], strokeColor=colors.HexColor('#7a3a9a'), strokeWidth=1.6))
    g.add(Circle(xO, 92, 12, fillColor=colors.HexColor('#fff8d6'), strokeColor=INK, strokeWidth=0.9))
    g.add(Line(xO - 8.5, 83.5, xO + 8.5, 100.5, strokeColor=INK, strokeWidth=0.8))
    g.add(Line(xO - 8.5, 100.5, xO + 8.5, 83.5, strokeColor=INK, strokeWidth=0.8))
    lbl(g, xO - 16, 95, 'CARGA', 7.2, INK, 'end', 'Sans-B')
    lbl(g, xO - 16, 86, '≤ 10 A resistiva', 6.2, MUTED, 'end')
    g.add(PolyLine([xO, 80, xO, yN], strokeColor=ACC, strokeWidth=1.6))
    g.add(Circle(xO, yN, 2.2, fillColor=ACC, strokeColor=ACC))
    # tierra a la carga
    g.add(PolyLine([sx, yPE, xO + 22, yPE, xO + 22, 84, xO + 11, 88], strokeColor=GRN, strokeWidth=1.2,
                   strokeDashArray=[4, 2]))
    lbl(g, sx - 4, yPE + 3, 'PE (tierra) → solo a la carga, no a la placa', 6.4, GRN, 'end')
    d.add(g)
    return d


def mech_drawing():
    s = 5.2  # pt por mm
    BW, BH = 66.5, 49.0
    ox, oy = 52, 40
    oy = 52
    d = Drawing(W_FULL, BH * s + 92)
    g = Group()

    def X(x): return ox + x * s
    def Y(y): return oy + (BH - y) * s

    g.add(Rect(X(0), Y(BH), BW * s, BH * s, rx=2 * s, ry=2 * s, fillColor=colors.HexColor('#f2f6f2'),
               strokeColor=INK, strokeWidth=1.1))
    # antena (aprox.)
    g.add(Rect(X(159.5 - 100), Y(117.5 - 100), 7.0 * s, 17.5 * s, fillColor=colors.HexColor('#fff3c4'),
               strokeColor=AMB, strokeDashArray=[2, 2], strokeWidth=0.7))
    lbl(g, X(63.0), Y(9.5), 'antena', 6.2, AMB, 'middle', 'Sans-B')
    lbl(g, X(63.0), Y(12.2), '(aprox.)', 5.6, AMB, 'middle')
    # zona de red aproximada (rótulo)
    lbl(g, X(14), Y(31), 'zona de red', 6.6, RED, 'middle', 'Sans-B')
    # elementos
    def comp(x, y, w, h, t, col=INK, fill=colors.white):
        g.add(Rect(X(x - w / 2), Y(y + h / 2), w * s, h * s, fillColor=fill, strokeColor=col, strokeWidth=0.6))
        lbl(g, X(x), Y(y) - 2.2, t, 6.2, col, 'middle', 'Sans-B')
    comp(18.94, 12.0, 34, 20, 'PS1')
    comp(50.5, 9.6, 18, 16, 'U2 (ESP-12F)')
    comp(30.9, 37.35, 29, 12.7, 'K1')
    g.add(Rect(X(0.8), Y(48.75), 15.24 * s, 7.5 * s, fillColor=colors.HexColor('#e3f4e7'), strokeColor=RED,
               strokeWidth=0.6))
    lbl(g, X(8.42), Y(39.6), 'J1', 6.4, RED, 'middle', 'Sans-B')
    for px, t in [(3.34, 'N'), (8.42, 'OUT'), (13.50, 'L')]:
        lbl(g, X(px), Y(47.6), t, 5.6, RED, 'middle', 'Sans-B')
    comp(61.71, 33.65, 7.6, 5.1, 'J3', ACC)
    for (x, y, t) in [(61.0, 25.2, 'SW1'), (57.2, 46.0, 'SW2')]:
        comp(x, y, 6.0, 6.0, t, ACC)
    for (x, y, t, c) in [(55.3, 24.0, 'D2', RED), (48.0, 44.3, 'D3', ACC)]:
        g.add(Circle(X(x), Y(y), 1.6 * s / 2 + 1, fillColor=c, strokeColor=c))
        lbl(g, X(x) - 7, Y(y) - 2, t, 6.4, c, 'end', 'Sans-B')
    # J1 pines
    for i, (px, t) in enumerate([(3.34, 'N'), (8.42, 'OUT'), (13.50, 'L')]):
        g.add(Circle(X(px), Y(43.8), 1.4 * s / 2 + 0.5, fillColor=colors.white, strokeColor=RED))
    # taladros
    for (x, y, t) in [(51.2, 40.6, 'MH1'), (63.9, 46.4, 'MH2')]:
        g.add(Circle(X(x), Y(y), 1.1 * s, fillColor=colors.white, strokeColor=INK, strokeWidth=0.9))
        g.add(Circle(X(x), Y(y), 2.5 * s, fillColor=None, strokeColor=MUTED, strokeDashArray=[1.5, 1.5],
                     strokeWidth=0.5))
    lbl(g, X(51.2) - 15, Y(40.6) + 13, 'MH1', 6.4, INK, 'middle', 'Sans-B')
    lbl(g, X(63.9) + 3, Y(46.4) + 14, 'MH2', 6.4, INK, 'middle', 'Sans-B')

    # cotas
    def hdim(x1, x2, y, t):
        g.add(Line(X(x1), y, X(x2), y, strokeColor=MUTED, strokeWidth=0.5))
        for xx in (x1, x2):
            g.add(Line(X(xx), y - 3, X(xx), y + 3, strokeColor=MUTED, strokeWidth=0.5))
        lbl(g, (X(x1) + X(x2)) / 2, y + 2.5, t, 6.6, INK, 'middle')

    def vdim(y1, y2, x, t):
        g.add(Line(x, Y(y1), x, Y(y2), strokeColor=MUTED, strokeWidth=0.5))
        for yy in (y1, y2):
            g.add(Line(x - 3, Y(yy), x + 3, Y(yy), strokeColor=MUTED, strokeWidth=0.5))
        lbl(g, x - 4, (Y(y1) + Y(y2)) / 2 - 2, t, 6.6, INK, 'end')

    hdim(0, BW, Y(0) + 14, '66,5 mm')
    vdim(0, BH, X(0) - 10, '49,0 mm')
    hdim(0, 51.2, Y(BH) - 12, '51,2')
    hdim(0, 63.9, Y(BH) - 24, '63,9')
    vdim(0, 40.6, X(BW) + 30, '40,6')
    vdim(0, 46.4, X(BW) + 58, '46,4')
    for yy in (40.6, 46.4):
        g.add(Line(X(BW) + 2, Y(yy), X(BW) + 60, Y(yy), strokeColor=GRID, strokeWidth=0.4,
                   strokeDashArray=[1, 2]))
    lbl(g, X(0) + 2, Y(0) + 3, '0,0', 5.6, MUTED)
    lbl(g, X(0), oy - 46, 'Origen en la esquina superior izquierda (vista superior). Esquinas R2 mm. '
        'Taladros MH1/MH2 Ø2,2 mm (M2); círculo discontinuo = Ø5 mm libre de pistas.', 6.4, MUTED)
    d.add(g)
    return d


# ---------------------------------------------------------------- plantillas de página
class Doc(BaseDocTemplate):
    def __init__(self, fn, **kw):
        super().__init__(fn, **kw)
        self.part = ''

    def afterFlowable(self, f):
        if isinstance(f, Paragraph):
            sn = f.style.name
            if sn in ('h1', 'h2'):
                lvl = 0 if sn == 'h1' else 1
                txt = f.getPlainText()
                key = 'k%d' % id(f)
                self.canv.bookmarkPage(key)
                self.canv.addOutlineEntry(txt, key, level=lvl, closed=lvl > 0)
                self.notify('TOCEntry', (lvl, txt, self.page, key))
            elif sn == 'part':
                key = 'p%d' % id(f)
                self.canv.bookmarkPage(key)
                self.canv.addOutlineEntry(f.getPlainText(), key, level=0)


def page_deco(c, doc):
    w, h = c._pagesize
    c.saveState()
    c.setStrokeColor(ACC); c.setLineWidth(1.2)
    c.line(18 * mm, h - 13 * mm, w - 18 * mm, h - 13 * mm)
    c.setFont('Sans-B', 7.6); c.setFillColor(ACC)
    c.drawString(18 * mm, h - 11.3 * mm, 'rele-esp12f')
    c.setFont('Sans', 7.6); c.setFillColor(MUTED)
    c.drawString(18 * mm + 44, h - 11.3 * mm, '·  Módulo de relé Wi-Fi 110–120 VAC  ·  Hoja de datos y guía de usuario')
    c.drawRightString(w - 18 * mm, h - 11.3 * mm, f'Hardware {HW_REV}  ·  Doc. rev. {DOC_REV}  ·  {DOC_DATE}')
    c.setStrokeColor(GRID); c.setLineWidth(0.5)
    c.line(18 * mm, 12 * mm, w - 18 * mm, 12 * mm)
    c.setFont('Sans', 7.2)
    c.drawString(18 * mm, 8.3 * mm, 'Hardware CERN-OHL-W v2  ·  Prototipo sin certificación: ver §1.4 y §8')
    c.drawRightString(w - 18 * mm, 8.3 * mm, f'Página {doc.page}')
    c.restoreState()


def cover_deco(c, doc):
    w, h = A4
    c.saveState()
    c.setFillColor(ACC)
    c.rect(0, h - 92 * mm, w, 92 * mm, stroke=0, fill=1)
    c.setFillColor(colors.HexColor('#0b4a72'))
    c.rect(0, h - 96 * mm, w, 4 * mm, stroke=0, fill=1)
    c.setFillColor(colors.white)
    c.setFont('Sans', 10.5)
    c.drawString(20 * mm, h - 24 * mm, 'HOJA DE DATOS  ·  GUÍA DE USUARIO')
    c.setFont('Sans-B', 34)
    c.drawString(20 * mm, h - 42 * mm, 'rele-esp12f')
    c.setFont('Sans', 14)
    c.drawString(20 * mm, h - 52 * mm, 'Módulo de relé Wi-Fi monocanal para 110–120 VAC')
    c.setFont('Sans', 10)
    c.setFillColor(colors.HexColor('#cfe2f0'))
    c.drawString(20 * mm, h - 60 * mm, 'ESP-12F (ESP8266EX)  ·  Omron G5RL-1A-E-HR 16 A  ·  Fuente aislada HLK-PM01')
    c.setFont('Sans', 8.6)
    c.drawString(20 * mm, h - 82 * mm, f'Hardware {HW_REV}   ·   Documento rev. {DOC_REV}   ·   {DOC_DATE}')
    # pie
    c.setFillColor(MUTED); c.setFont('Sans', 7.4)
    c.drawString(20 * mm, 14 * mm, 'Proyecto KiCad 10 · Hardware CERN-OHL-W v2 · Autor: @techmigue')
    c.drawRightString(w - 20 * mm, 14 * mm, 'Prototipo de desarrollo — no certificado (UL/CE)')
    c.restoreState()


def land_deco(c, doc):
    page_deco(c, doc)


# ---------------------------------------------------------------- contenido
def content(a):
    st = []
    E = st.extend
    A = st.append

    # ======================= PORTADA
    A(Spacer(1, 92 * mm))
    A(img(a['r3d_top'], 150 * mm))
    feat_l = [
        '<b>Conmutación de red</b>: 1 contacto NA (SPST-NO) sobre la fase, 10 A resistivos (límite de placa); relé de 16 A con modelo de alto pico de arranque (100 A).',
        '<b>Alimentación integrada</b>: entrada directa 110–120 VAC, fuente aislada HLK-PM01 de 5 V / 3 W, LDO de 3,3 V.',
        '<b>Wi-Fi 2,4 GHz</b> 802.11 b/g/n con ESP8266EX; compatible con firmware abierto (Tasmota, ESPHome, Arduino).',
    ]
    feat_r = [
        '<b>Protección</b>: fusible retardado T500 mA para la fuente, varistor 07D221K, diodo de libre circulación en la bobina.',
        '<b>Aislamiento</b>: ≥ 4 mm en cobre entre red y baja tensión; 8 mm bobina–contacto en el relé (aislamiento reforzado).',
        '<b>Montaje completo en JLCPCB</b>: 32 piezas, una sola cara; 66,5 × 49 mm, 2 capas.',
    ]
    ft = Table([[bullets(feat_l), bullets(feat_r)]], colWidths=[W_FULL / 2, W_FULL / 2])
    ft.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0, 0), (-1, -1), 0)]))
    A(Spacer(1, 4))
    A(ft)
    A(NextPageTemplate('normal'))
    A(PageBreak())

    # ======================= ÍNDICE
    A(Paragraph('Contenido', S('tt', fontName='Sans-B', fontSize=16, leading=20, textColor=ACC, spaceAfter=10)))
    toc = TableOfContents()
    toc.levelStyles = [sTOC1, sTOC2]
    toc.dotsMinLevel = 0
    A(toc)
    A(PageBreak())

    # ======================= PARTE I
    A(Spacer(1, 40 * mm))
    A(Paragraph('Parte I', sPart))
    A(P('<font size="15" color="#5b6b7a">Hoja de datos técnica</font>', S('x', leading=22)))
    A(Spacer(1, 6))
    A(P('Especificaciones eléctricas, funcionales y de diseño del módulo rele-esp12f, revisión de hardware v3.', sBodyL))
    A(Spacer(1, 30 * mm))
    A(P('<b>Cómo leer este documento.</b> La <b>Parte I</b> es la hoja de datos: límites, características, '
        'descripción funcional y criterios de diseño de la placa. La <b>Parte II</b> es la guía de usuario: '
        'seguridad, grabación del firmware, instalación, configuración, operación, mantenimiento y diagnóstico. '
        'Cada valor numérico de las tablas de especificación lleva una marca de origen, porque no todos tienen '
        'el mismo grado de certeza:', sBody))
    A(table([['Marca', 'Significado'],
             ['<b>[D]</b>', 'Hoja de datos del fabricante incluida en <font face="Mono">docs/datasheets/</font> (Omron G5RL, AMS1117, ESP8266EX).'],
             ['<b>[F]</b>', 'Dato del fabricante cuya hoja <b>no</b> está en el proyecto (p. ej. HLK-PM01, borna KANGNEX, varistor). Comprobar antes de depender de él.'],
             ['<b>[C]</b>', 'Calculado a partir del diseño (esquemático, layout, IPC-2221). El cálculo está en el Apéndice A.'],
             ['<b>[M]</b>', 'Medido sobre el layout en KiCad (distancias, cotas). No es una medida sobre una placa física.'],
             ['<b>[E]</b>', 'Estimación o recomendación de diseño. No medida en una placa real.']],
            [1, 9]))
    A(PageBreak())

    # ---- 1. Descripción general
    A(Paragraph('1. Descripción general', sH1))
    A(P('El <b>rele-esp12f</b> es un módulo de conmutación de red de un canal controlado por Wi-Fi. Se conecta '
        'directamente a una línea de 110–120 VAC con neutro, se alimenta de ella a través de una fuente '
        'conmutada aislada y gobierna una carga de hasta 10 A mediante un relé de potencia Omron con contacto '
        'normalmente abierto en serie con la fase. El control lo hace un módulo ESP-12F (SoC ESP8266EX), que '
        'puede ejecutar firmware abierto como Tasmota o ESPHome, o un programa propio.'))
    A(P('La placa está dividida físicamente en dos zonas: la <b>zona de red</b> (borna, fusible, varistor, entrada '
        'de la fuente y contactos del relé) y la <b>zona SELV</b> de muy baja tensión (5 V y 3,3 V, '
        'microcontrolador, driver, LEDs, pulsadores y conector de programación). Las dos zonas solo se comunican '
        'a través de dos elementos que aportan aislamiento propio: la fuente HLK-PM01 y el relé K1.'))
    A(Paragraph('1.1 Características principales', sH2))
    E(bullets([
        'Entrada de red 110–120 VAC, 50/60 Hz, con neutro. Consumo propio estimado ≈ 0,6 W en reposo y ≈ 1,2 W con el relé cerrado [E].',
        'Salida SPST-NO de fase conmutada; 10 A rms resistivos como límite de la placa; relé Omron G5RL-1A-E-HR de 16 A / 250 VAC, pico de arranque hasta 100 A [D].',
        'Fuente aislada Hi-Link HLK-PM01 (5 V, 600 mA) protegida con fusible T500 mA y varistor de 140 VAC [F].',
        'Regulador AMS1117-3.3 y desacoplo 10 µF + 100 nF junto al ESP-12F, siguiendo la guía de Espressif.',
        'ESP8266EX: CPU Xtensa L106 a 80/160 MHz, Wi-Fi 802.11 b/g/n, +20 dBm en 802.11b [D].',
        'Estado de arranque seguro: el relé permanece abierto durante el reset y el arranque (resistencia de bajada en la base del transistor).',
        'Indicadores: LED rojo de estado del relé (cableado por hardware) y LED azul de Wi-Fi (controlado por firmware).',
        'Pulsador local SW1 (GPIO0, también entrada al modo de grabación) y pulsador de reset SW2.',
        'Conector de programación J3 (2×3, 2,54 mm) con alimentación de 5 V desde el adaptador USB-serie; actualizaciones posteriores por OTA.',
        'PCB FR-4 de 2 capas, 1,6 mm, cobre de 35 µm, 66,5 × 49 mm. Todos los componentes en la cara superior.',
    ]))
    A(Paragraph('1.2 Aplicaciones', sH2))
    E(bullets(['Encendido remoto de iluminación, ventiladores, calefactores resistivos y pequeños electrodomésticos.',
               'Integración en domótica (Home Assistant, MQTT) con Tasmota o ESPHome.',
               'Temporización y programación horaria de cargas de red.']))
    A(Paragraph('1.3 Diagrama de bloques', sH2))
    A(fig(block_diagram(), 'Figura 1. Diagrama de bloques. La línea discontinua roja es la barrera de aislamiento: '
          'solo la cruzan PS1 (transformador de la fuente) y K1 (separación bobina–contacto de 8 mm).'))
    A(img(a['r3d_bot'], 105 * mm, 'Figura 2. Render 3D de la cara inferior: solo cobre, máscara y terminales THT; no hay componentes (montaje de una cara).'))
    A(Paragraph('1.4 Estado del producto', sH2))
    A(callout('atencion', 'Prototipo de desarrollo, sin certificación', [
        'Esta placa no ha pasado ensayos de seguridad eléctrica (IEC 62368-1, UL, CE) ni de compatibilidad electromagnética. Las distancias de aislamiento siguen un criterio de diseño (4 mm), no una evaluación formal.',
        'Espressif clasifica el ESP8266EX como <b>NRND</b> (no recomendado para diseños nuevos) en su hoja de datos de 2025.11. El módulo sigue disponible, pero conviene prever su sustitución en futuras revisiones.',
        'Los valores marcados [E] no se han medido en una placa física. Ver el Apéndice C para las discrepancias conocidas entre la documentación del proyecto y este documento.']))
    A(PageBreak())

    # ---- 2. Especificaciones
    A(Paragraph('2. Especificaciones', sH1))
    A(Paragraph('2.1 Límites absolutos', sH2))
    A(P('Superar cualquiera de estos valores puede dañar la placa de forma permanente o crear un riesgo de '
        'incendio o descarga. No son condiciones de funcionamiento.'))
    A(table([
        ['Parámetro', 'Condición', 'Límite', 'Origen / motivo'],
        ['Tensión de red L–N', 'continua', '140 VAC rms', '[F] Tensión máxima de servicio del varistor 07D221K. Por encima conduce y se destruye.'],
        ['Corriente de carga (J1 OUT)', 'rms continua', '10 A', '[C] Pistas 2 × 2,5 mm, 35 µm: +12 °C a 10 A (IPC-2221).'],
        ['Corriente de pico de arranque', 'contacto K1', '100 A pico', '[D] Ensayo VDE del G5RL-1A-E-HR: 240 VAC, 100 A (0-P), 10 A estables.'],
        ['Tensión de contacto', 'K1', '250 VAC', '[D] Omron G5RL.'],
        ['Tensión en J3 pin 2 (+5 V)', 'sin red conectada', '5,5 V', '[E] Bobina K1 ≤ 6,5 V (130 %) [D]; C1–C3 de 10 V; margen respecto a USB (5,25 V).'],
        ['Tensión en TX, RX, IO0, RST (J3)', '—', '−0,3 … 3,6 V', '[D] ESP8266EX, V<sub>IH</sub> máx. 3,6 V. No admite lógica de 5 V.'],
        ['Corriente por GPIO', 'por pin', '12 mA', '[D] ESP8266EX, I<sub>MAX</sub>.'],
        ['Temperatura de unión U1', '—', '125 °C', '[D] AMS1117.'],
        ['Descarga electrostática', 'HBM, pines del ESP', '2 kV', '[D] ESP8266EX. Manipular J3 con precauciones ESD.'],
    ], [3.2, 2, 1.8, 6]))
    A(Paragraph('2.2 Condiciones de funcionamiento recomendadas', sH2))
    A(table([
        ['Parámetro', 'Mín.', 'Típ.', 'Máx.', 'Unidad', 'Notas'],
        ['Tensión de red', '100', '115', '127', 'VAC', 'Red de 110/120 V ±10 %. Para 230 V hay que cambiar RV1 (p. ej. 07D471K).'],
        ['Frecuencia de red', '47', '50/60', '63', 'Hz', '[F] HLK-PM01.'],
        ['Carga resistiva', '—', '—', '10', 'A', 'Ver §2.4 para otros tipos de carga.'],
        ['Temperatura ambiente (dentro de la caja)', '0', '25', '40', '°C', '[E] Recomendación conservadora. El relé admite −40…85 °C [D]; el límite real lo marcan PS1 y C1 [F].'],
        ['Humedad relativa', '5', '—', '85', '%', '[D] Omron G5RL; sin condensación.'],
        ['Tensión en J3 (solo grabación)', '4,75', '5,0', '5,25', 'V', 'VBUS del adaptador USB-serie.'],
    ], [3.6, 0.8, 0.9, 0.8, 0.9, 5.6]))
    A(Paragraph('2.3 Características eléctricas', sH2))
    A(P('Salvo indicación, a 25 °C y 115 VAC.', sSmall))
    A(table([
        ['Parámetro', 'Símbolo / condición', 'Mín.', 'Típ.', 'Máx.', 'Ud.', 'Origen'],
        ['<b>Alimentación</b>', '', '', '', '', '', ''],
        ['Tensión del rail de 5 V', 'V<sub>5V</sub>, salida PS1', '—', '5,0', '—', 'V', '[F]'],
        ['Corriente disponible en 5 V', 'I<sub>PS1</sub>', '—', '—', '600', 'mA', '[F]'],
        ['Tensión del rail de 3,3 V', 'V<sub>3V3</sub>, 0–0,8 A, T<sub>j</sub> completa', '3,201', '3,300', '3,399', 'V', '[D]'],
        ['Caída mínima de U1', 'I<sub>OUT</sub> = 0,8 A', '—', '1,1', '1,3', 'V', '[D]'],
        ['Margen de regulación disponible', 'V<sub>5V</sub> − V<sub>3V3</sub>', '—', '1,7', '—', 'V', '[C]'],
        ['Consumo del ESP8266EX, media', 'conectado a Wi-Fi', '—', '80', '—', 'mA', '[D]'],
        ['Consumo del ESP8266EX, transmisión', '802.11b, 11 Mbps, +17 dBm', '—', '170', '—', 'mA', '[D]'],
        ['Corriente de bobina K1', '5 V', '—', '80', '—', 'mA', '[D] ±10 %'],
        ['Carga total en el rail de 5 V', 'relé cerrado + TX continuo', '—', '≈ 266', '—', 'mA', '[C] 44 % de PS1'],
        ['Disipación de U1', 'media / pico TX', '—', '0,14 / 0,29', '—', 'W', '[C]'],
        ['Potencia absorbida de la red', 'relé abierto / cerrado', '—', '≈ 0,6 / 1,2', '—', 'W', '[E] η PS1 ≈ 70 %'],
        ['<b>Salida (relé K1)</b>', '', '', '', '', '', ''],
        ['Configuración del contacto', '—', 'SPST-NO (1 NA), conmuta la fase', '', '', '', ''],
        ['Corriente de carga, límite de placa', 'resistiva, rms', '—', '—', '10', 'A', '[C]'],
        ['Corriente nominal del contacto', '250 VAC resistiva', '—', '—', '16', 'A', '[D]'],
        ['Resistencia de contacto', '1 A, 5 VDC, inicial', '—', '—', '100', 'mΩ', '[D]'],
        ['Tiempo de cierre', '—', '—', '—', '15', 'ms', '[D]'],
        ['Tiempo de apertura', 'sin diodo; D1 lo alarga', '—', '—', '5', 'ms', '[D]'],
        ['Tensión de cierre / apertura de bobina', '% de 5 V', '≥ 0,5 V', '—', '≤ 3,5 V', 'V', '[D] 70 % / 10 %'],
        ['Tensión aplicada a la bobina', '5 V − V<sub>CE(sat)</sub>', '—', '≈ 4,8', '—', 'V', '[C]'],
        ['Vida eléctrica', '16 A, 250 VAC resistiva, 1 800 man./h', '50 000', '—', '—', 'man.', '[D]'],
        ['Vida mecánica', '18 000 man./h', '10<super>7</super>', '—', '—', 'man.', '[D]'],
        ['<b>Aislamiento</b>', '', '', '', '', '', ''],
        ['Separación red ↔ SELV en cobre', 'mínima, ambas caras', '4,35', '—', '—', 'mm', '[M] L_IN ↔ plano GND'],
        ['Separación cobre de red ↔ borde', 'mínima', '2,0', '—', '—', 'mm', '[M] pad N de J1'],
        ['Bobina ↔ contacto K1', 'distancia en aire / superficial', '8 / 8', '—', '—', 'mm', '[D] reforzado'],
        ['Rigidez dieléctrica bobina ↔ contacto', '1 min, 50/60 Hz', '6 000', '—', '—', 'VAC', '[D]'],
        ['Impulso bobina ↔ contacto', '1,2 × 50 µs', '10', '—', '—', 'kV', '[D]'],
        ['Aislamiento entrada–salida de PS1', '—', 'ver hoja de Hi-Link', '', '', '', '[F]'],
    ], [3.6, 3.1, 0.95, 1.05, 0.95, 0.6, 1.9],
        extra=[('SPAN', (0, 1), (-1, 1)), ('BACKGROUND', (0, 1), (-1, 1), ACC2),
               ('SPAN', (0, 13), (-1, 13)), ('BACKGROUND', (0, 13), (-1, 13), ACC2),
               ('SPAN', (2, 14), (-1, 14)),
               ('SPAN', (0, 24), (-1, 24)), ('BACKGROUND', (0, 24), (-1, 24), ACC2),
               ('SPAN', (2, 30), (5, 30))]))
    A(Spacer(1, 6))
    A(table([
        ['Parámetro (microcontrolador y radio)', 'Condición', 'Valor', 'Origen'],
        ['SoC', '—', 'ESP8266EX, Xtensa L106 32 bit, 80/160 MHz', '[D]'],
        ['Tensión de trabajo', '—', '2,5 … 3,6 V (3,3 V típ.)', '[D]'],
        ['Memoria flash', 'módulo ESP-12F', '4 MB típ. (según lote/fabricante del módulo)', '[F]'],
        ['Banda', '—', '2 412 … 2 484 MHz, 802.11 b/g/n (HT20)', '[D]'],
        ['Potencia de transmisión', '802.11b / g / n', '+20 / +17 / +14 dBm', '[D]'],
        ['Sensibilidad', '11 Mbps CCK / 54 Mbps / MCS7', '−91 / −75 / −72 dBm', '[D]'],
        ['Niveles lógicos', 'V<sub>IL</sub> / V<sub>IH</sub> / V<sub>OH</sub>', '≤ 0,25 V<sub>IO</sub> / ≥ 0,75 V<sub>IO</sub> / ≥ 0,8 V<sub>IO</sub>', '[D]'],
        ['Retardo de habilitación', 'R1·C7 = R2·C8', 'τ = 1 ms (EN alcanza 0,75·V<sub>IO</sub> en ≈ 1,4 ms)', '[C]'],
    ], [3.6, 3, 5, 1]))
    A(Paragraph('2.4 Capacidad de conmutación según el tipo de carga', sH2))
    A(P('El relé G5RL-1A-E-HR está pensado para cargas con pico de arranque alto, pero la placa limita la '
        'corriente estable a 10 A. Para cargas no resistivas, el desgaste del contacto depende del pico de '
        'cierre y del arco de apertura, por lo que se recomienda reducir la corriente:'))
    A(table([
        ['Tipo de carga', 'Corriente estable recomendada', 'A 120 VAC', 'Fundamento'],
        ['Resistiva (calefactor, resistencia, horno)', '≤ 10 A', '≤ 1 200 W', '[C] Límite de pistas; contacto de 16 A [D].'],
        ['Lámpara incandescente / halógena', '≤ 5 A', '≤ 600 W', '[D] Homologación UL TV-5 a 120 VAC (5 A estables, pico de filamento frío).'],
        ['Drivers LED, fuentes conmutadas (carga capacitiva)', '≤ 5 A', '≤ 600 W', '[E] El modelo HR está ensayado a 100 A de pico [D]; se deja margen por la suma de picos de varios drivers.'],
        ['Motores, ventiladores, transformadores (inductiva)', '≤ 3 A', '≤ 360 VA', '[E] La hoja no da potencia de motor para el modelo -HR. Considerar un snubber RC en la carga.'],
    ], [3.8, 2.4, 1.6, 6]))
    A(callout('nota', 'La carga no está protegida por F1',
              'F1 (T500 mA) solo protege la fuente PS1. La salida OUT debe protegerse aguas arriba con un '
              'magnetotérmico o fusible de <b>10 A como máximo</b>. Un fusible de placa no serviría: su poder de '
              'corte (decenas de amperios) es muy inferior a la corriente de cortocircuito de una toma de red.'))
    A(Paragraph('2.5 Características mecánicas y ambientales', sH2))
    A(table([
        ['Parámetro', 'Valor', 'Origen'],
        ['Dimensiones de la placa', '66,5 × 49,0 mm, esquinas R2 mm', '[M]'],
        ['Espesor / material', '1,6 mm, FR-4, 2 capas, cobre 35 µm (1 oz) en ambas caras', '[M]'],
        ['Altura sobre la cara superior', '≈ 16 mm (relé 15,7 mm máx. [D]; HLK-PM01 ≈ 15 mm [F])', '[E]'],
        ['Altura bajo la placa', '≈ 2 mm (terminales THT recortados tras soldadura por ola)', '[E]'],
        ['Taladros de fijación', '2 × Ø2,2 mm (M2) en (51,2; 40,6) y (63,9; 46,4) mm; cabeza o arandela ≤ Ø5 mm', '[M]'],
        ['Borna J1', '3 polos, paso 5,08 mm, 250 V / 18 A, entrada de cable hacia el borde', '[F]'],
        ['Peso del relé', '≈ 10 g', '[D]'],
        ['Vibración (relé)', '10–55 Hz, 1,5 mm doble amplitud', '[D]'],
        ['Choque (relé)', '100 m/s² sin fallo; 1 000 m/s² sin destrucción', '[D]'],
    ], [3, 8, 1]))
    A(fig(mech_drawing(), 'Figura 3. Plano mecánico y elementos de interfaz (vista superior, cotas en mm). '
          'La zona de antena es aproximada; se ha dibujado a partir del contorno de la huella del ESP-12F.'))
    A(PageBreak())

    # ---- 3. Descripción funcional
    A(Paragraph('3. Descripción funcional', sH1))
    A(Paragraph('3.1 Entrada de red y protección', sH2))
    A(P('La fase entra por J1-3 (<b>L</b>) y el neutro por J1-1 (<b>N</b>). Desde L salen dos caminos: el de '
        'la carga, que va directo al contacto de K1 (red <font face="Mono">L_IN</font>) y el de la fuente, que '
        'pasa por el fusible F1 (red <font face="Mono">L_F</font>). El varistor RV1 está entre <font face="Mono">L_F</font> '
        'y N, es decir, <i>detrás</i> del fusible.'))
    E(bullets([
        '<b>Por qué RV1 va detrás de F1.</b> Ante una sobretensión prolongada (p. ej. 230 V conectados por error) el varistor conduce de forma continua. Así lo que se abre es el fusible, en vez de que el varistor se sobrecaliente sin límite de corriente.',
        '<b>Por qué F1 es retardado (T).</b> La HLK-PM01 tiene un pico de corriente de arranque al cargar su condensador de entrada. Un fusible rápido de 500 mA podría abrirse en cada encendido.',
        '<b>Por qué la carga no pasa por F1.</b> La corriente de la carga (hasta 10 A) no tiene nada que ver con la de la fuente (decenas de mA). Su protección corresponde a la instalación (§2.4).',
    ]))
    A(Paragraph('3.2 Fuente aislada y regulación', sH2))
    A(P('PS1 (Hi-Link HLK-PM01) convierte la red en 5 V aislados. Es el único elemento, junto con K1, que cruza '
        'la barrera de aislamiento. Del rail de 5 V cuelgan la bobina del relé y el regulador lineal U1 '
        '(AMS1117-3.3), que genera los 3,3 V del ESP-12F.'))
    A(table([
        ['Componente', 'Valor', 'Función'],
        ['C1', '470 µF 10 V electrolítico', 'Depósito de energía en 5 V: absorbe el escalón de corriente al cerrar el relé (80 mA) y los picos de transmisión.'],
        ['C2 · C3', '22 µF X5R 0805 · 100 nF', 'Entrada de U1: estabilidad y respuesta rápida.'],
        ['C4 · C6', '22 µF X5R 0805 · 100 nF', 'Salida de U1. El AMS1117 necesita ≥ 22 µF en salida para ser estable.'],
        ['C9 · C5', '10 µF X5R 0603 · 100 nF', 'Junto al pin VCC del ESP-12F (combinación recomendada por Espressif). C4 está a ~25 mm de pista y no cubre los flancos de la transmisión.'],
    ], [1.6, 3.4, 8]))
    A(P('<b>Criterio de elección del LDO.</b> Con 5 V de entrada y 3,3 V de salida quedan 1,7 V de margen, por '
        'encima de la caída del AMS1117 (1,1 V típ. a 0,8 A [D]). La disipación media es (5 − 3,3) V × 80 mA ≈ '
        '0,14 W; con θ<sub>JA</sub> ≈ 90 °C/W el aumento de temperatura de unión ronda 13 °C (26 °C en pico de '
        'transmisión). Un convertidor conmutado ahorraría ~0,1 W, pero añadiría ruido junto a la radio y más piezas.'))
    A(Paragraph('3.3 Microcontrolador y configuración de arranque', sH2))
    A(P('El ESP8266EX lee tres pines de configuración ("strapping") en el flanco de subida del reset para decidir '
        'de dónde arranca. Las resistencias de la placa fijan el arranque normal desde flash; SW1 permite forzar '
        'el modo de grabación por UART.'))
    A(table([
        ['Pin', 'Red', 'Componentes', 'Nivel en arranque', 'Efecto'],
        ['GPIO15', '/GPIO15', 'R5 10 k a GND', '0', 'Obligatorio a 0 para arrancar desde flash o UART.'],
        ['GPIO2', '/GPIO2', 'R4 10 k a 3V3', '1', 'Obligatorio a 1.'],
        ['GPIO0', '/GPIO0', 'R3 10 k a 3V3; SW1 a GND; J3-5', '1 (0 con SW1)', '1 = arranque desde flash; 0 = modo de grabación UART.'],
        ['EN (CH_PD)', '/EN', 'R1 10 k a 3V3; C7 100 nF a GND', '↑ con τ = 1 ms', 'Habilita el chip después de que se estabilice VCC.'],
        ['RST', '/RST', 'R2 10 k a 3V3; C8 100 nF; SW2 a GND; J3-6', '↑ con τ = 1 ms', 'Reset externo; SW2 reinicia el módulo.'],
    ], [1.4, 1.4, 3.6, 1.8, 4.6]))
    A(P('El retardo RC en EN y RST responde a la secuencia de encendido de Espressif: EN y RST deben subir '
        'después que VDD33 (t<sub>3</sub>, t<sub>5</sub> ≥ 0,1 ms [D]). Sin condensadores, un arranque lento del '
        'rail de 3,3 V puede dejar el chip en un estado indefinido.'))
    A(Paragraph('3.4 Driver del relé', sH2))
    A(P('GPIO5 (red <font face="Mono">/RELAY</font>) ataca la base de Q1 (SS8050, NPN) a través de R6 (1 kΩ). '
        'Q1 conmuta el lado bajo de la bobina (<font face="Mono">/COIL_N</font>); el otro extremo está en +5 V. '
        'D1 (1N4148W) recircula la corriente de la bobina al abrirse Q1 y limita la sobretensión en su colector a '
        '≈ 5,7 V. R7 (10 kΩ) mantiene la base a GND mientras GPIO5 está en alta impedancia (reset, arranque, '
        'grabación): el relé <b>no puede cerrarse</b> hasta que el firmware lo ordene.'))
    A(table([
        ['Magnitud', 'Cálculo', 'Resultado'],
        ['Corriente de bobina', '5 V / 62,5 Ω', '80 mA'],
        ['Corriente de base (V<sub>OH</sub> = 3,3 V)', '(3,3 − 0,75) / 1 k − 0,75 / 10 k', '2,48 mA'],
        ['Corriente de base (V<sub>OH</sub> mín. = 2,64 V)', '(2,64 − 0,75) / 1 k − 0,75 / 10 k', '1,82 mA'],
        ['β forzada (peor caso)', '80 mA / 1,82 mA', '≈ 44 → saturación con amplio margen (h<sub>FE</sub> del SS8050 ≫ 44)'],
        ['Corriente total de GPIO5', 'I<sub>B</sub> + I<sub>D2</sub> ≈ 2,5 + 1,4', '≈ 3,9 mA (< 12 mA [D])'],
    ], [3.3, 4.7, 5]))
    A(P('Con un diodo simple en paralelo la corriente de la bobina decae despacio y el contacto se abre algo '
        'más tarde que los 5 ms de la hoja (no medido). Para una carga de 10 A en alterna es aceptable; un zener '
        'en serie con D1 aceleraría la apertura a costa de más tensión en Q1.', sBody))
    A(Paragraph('3.5 Indicadores y pulsadores', sH2))
    A(table([
        ['Ref.', 'Elemento', 'Conexión', 'Lógica', 'Notas'],
        ['D2', 'LED rojo "relé"', 'GPIO5 → D2 → R8 1 k → GND', 'Activo alto', 'En paralelo con el driver: encendido = orden de cierre enviada. ≈ 1,4 mA [E].'],
        ['D3', 'LED azul "Wi-Fi"', 'GPIO4 → R9 220 Ω → D3 → GND', 'Activo alto', 'Significado definido por el firmware. Corriente ≈ 1–2 mA, depende de la V<sub>F</sub> del LED azul [E].'],
        ['SW1', 'Pulsador TS-1187A', 'GPIO0 ↔ GND', 'Activo bajo', 'Conmutación local en servicio; mantenido durante el reset = modo de grabación.'],
        ['SW2', 'Pulsador TS-1187A', 'RST ↔ GND', 'Activo bajo', 'Reinicio del módulo.'],
    ], [0.8, 2.3, 3.6, 1.6, 5]))
    A(PageBreak())

    # ---- 4. Conectores y asignación de pines
    A(Paragraph('4. Conectores y asignación de pines', sH1))
    A(Paragraph('4.1 J1 — Borna de red', sH2))
    A(table([
        ['Pin', 'Rótulo', 'Red', 'Función', 'Sección de cable recomendada'],
        ['1', 'N', '/N', 'Neutro de entrada; común a la carga y a PS1', '1,5 mm² (≈ 14 AWG) para 10 A [E]'],
        ['2', 'OUT', '/L_OUT', 'Fase conmutada hacia la carga', '1,5 mm²'],
        ['3', 'L', '/L_IN', 'Fase de entrada (desde el magnetotérmico)', '1,5 mm²'],
    ], [0.7, 1, 1.3, 5, 4]))
    A(P('Borna KANGNEX WJ500V-5.08-3P (250 V / 18 A) [F]. La entrada de cable mira hacia el borde inferior de la '
        'placa. Usar conductor de cobre; si es flexible, con puntera (terminal tubular) del tamaño adecuado.', sBody))
    A(Paragraph('4.2 J3 — Programación (2×3, paso 2,54 mm)', sH2))
    jt = Table([
        [P('<b>IO0</b><br/>pin 5', sCell), P('<b>TX</b><br/>pin 3', sCell), P('<b>GND</b><br/>pin 1 ■', sCell)],
        [P('<b>RST</b><br/>pin 6', sCell), P('<b>RX</b><br/>pin 4', sCell), P('<b>5V</b><br/>pin 2', sCell)],
    ], colWidths=[22 * mm] * 3, rowHeights=[12 * mm] * 2)
    jt.setStyle(TableStyle([('GRID', (0, 0), (-1, -1), 0.8, INK), ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#fafafa')),
                            ('BACKGROUND', (2, 0), (2, 0), colors.HexColor('#ffe9a8'))]))
    jdesc = table([
        ['Pin', 'Señal', 'Conectar al adaptador'],
        ['1 (cuadrado)', 'GND', 'GND'],
        ['2', '+5 V (entrada)', '5 V / VBUS'],
        ['3', 'TXD del ESP', 'RX del adaptador'],
        ['4', 'RXD del ESP', 'TX del adaptador'],
        ['5', 'GPIO0', 'GND para grabar (o usar SW1)'],
        ['6', 'RST', 'opcional (o usar SW2)'],
    ], [1.3, 1.6, 2.6])
    wrap = Table([[jt, jdesc]], colWidths=[75 * mm, W_FULL - 75 * mm])
    wrap.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('LEFTPADDING', (0, 0), (-1, -1), 0)]))
    jdesc._argW = [w * (W_FULL - 75 * mm) / W_FULL for w in jdesc._argW]
    A(wrap)
    A(P('Vista desde arriba, con la placa orientada como en la Figura 3 (el rótulo de la serigrafía coincide). '
        'Las líneas TX/RX son de <b>3,3 V</b>: el adaptador debe tener lógica de 3,3 V aunque se alimente la '
        'placa con sus 5 V.', sSmall))
    A(callout('peligro', 'J3 solo con la placa desconectada de la red',
              'J3 está en la zona SELV, pero un fallo de aislamiento en PS1 o K1 lo pondría a tensión de red, y a '
              'través del adaptador también el ordenador. Nunca conectar nada a J3 con la red conectada en J1.'))
    A(Paragraph('4.3 Asignación de pines del ESP-12F', sH2))
    A(table([
        ['Pin módulo', 'GPIO', 'Red', 'Dirección', 'Uso'],
        ['20', 'GPIO5', '/RELAY', 'Salida', 'Relé K1 (vía Q1) y LED D2. Activo alto.'],
        ['19', 'GPIO4', '/WIFI_LED', 'Salida', 'LED D3. Activo alto.'],
        ['18', 'GPIO0', '/GPIO0', 'Entrada', 'Pulsador SW1 (activo bajo, pull-up R3). Strapping.'],
        ['22', 'GPIO1 / TXD', '/TXD', 'Salida', 'UART0 TX → J3-3. Log del firmware a 115 200 bit/s (habitual).'],
        ['21', 'GPIO3 / RXD', '/RXD', 'Entrada', 'UART0 RX ← J3-4.'],
        ['17', 'GPIO2', '/GPIO2', '—', 'Pull-up R4. Strapping. Libre para el firmware con precaución (en muchos ESP-12F lleva el LED azul del módulo, activo bajo [F]).'],
        ['16', 'GPIO15', '/GPIO15', '—', 'Pull-down R5. Strapping. No usar.'],
        ['1 · 3', 'RST · EN', '/RST · /EN', 'Entrada', 'Reset (SW2, J3-6) y habilitación, con RC de 1 ms.'],
        ['4, 5, 6, 7', 'GPIO16, 14, 12, 13', '—', '—', 'Sin conectar. Accesibles solo soldando al castellado del módulo.'],
        ['2', 'ADC (TOUT)', '—', '—', 'Sin conectar.'],
        ['9–14', 'GPIO6–11', '—', '—', 'Bus de la flash interna. <b>No usar.</b>'],
    ], [1.5, 2.1, 1.8, 1.4, 6.4]))
    A(PageBreak())

    # ---- 5. Diseño de hardware
    A(Paragraph('5. Diseño de hardware', sH1))
    A(P('Esta sección resume los criterios de ingeniería que fijan la topología, el layout y los márgenes de la '
        'placa. El esquemático completo está en la página siguiente.'))
    A(Paragraph('5.1 Particionado de la placa', sH2))
    E(bullets([
        '<b>Franja superior:</b> PS1 a la izquierda y el ESP-12F girado 270° con la antena en el borde derecho, sobre una zona sin cobre (keepout de la huella).',
        '<b>Abajo a la izquierda, zona de red:</b> J1 en el borde inferior, F1 y RV1 encima y K1 a su derecha. Ningún plano de GND ni pista de baja tensión entra en esta zona.',
        '<b>Abajo a la derecha, baja tensión:</b> U1 y sus condensadores, C1, driver del relé, pulsadores, LEDs, J3 y los dos taladros de fijación.',
        '<b>Planos de GND</b> en ambas caras, recortados con un polígono que, por geometría, queda a ≥ 4,5 mm de todo el cobre de red. Así la separación no depende solo de que las clases de red estén bien asignadas.',
        '<b>Taladros de fijación</b> dentro de la zona de baja tensión, con un círculo de Ø5 mm libre de pistas y vías de señal (solo plano de GND), para que una arandela metálica no pueda dañar una pista.',
    ]))
    A(Paragraph('5.2 Reglas de diseño y aislamiento', sH2))
    A(table([
        ['Regla', 'Valor', 'Criterio'],
        ['Red ↔ baja tensión', '4,0 mm (medido: 4,35 mm)', 'Regla propia en rele-esp12f.kicad_dru, sin excepciones en toda la placa. Distancia de diseño entre circuito de red y SELV.'],
        ['Entre redes de red (L_IN, L_OUT, L_F, N)', '2,0 mm', 'Aislamiento funcional entre conductores de red a 120 V.'],
        ['Cobre de red ↔ borde', '≥ 2,0 mm', 'Margen frente a contacto con una caja o soporte; la caja debe seguir siendo aislante.'],
        ['Bobina ↔ contacto en K1', '8 mm (interna) / 20 mm entre pads', 'Aislamiento reforzado del G5RL [D]. Se eliminó la excepción de 2 mm que tenía el relé de la revisión anterior.'],
        ['Señal / alimentación SELV', '0,25–0,3 mm / 0,5–0,6 mm', 'Capacidad de fabricación estándar de JLCPCB.'],
    ], [3.4, 3.2, 7]))
    A(Paragraph('5.3 Pistas de potencia', sH2))
    A(P('La corriente de la carga recorre L_IN (J1-3 → K1) y L_OUT (K1 → J1-2). Ambas son pistas de 2,5 mm '
        '<b>duplicadas en las dos caras</b> y unidas en los pads THT de J1 y K1. Según IPC-2221 (capa externa, '
        '35 µm), 2 × 2,5 mm admiten ≈ 12 A con 20 °C de calentamiento; a 10 A el calentamiento previsto es '
        '≈ 12 °C [C]. El G5RL-1A-E es un modelo de alta capacidad: cada contacto sale por <b>dos</b> patillas y '
        'Omron exige usar ambas [D]; en la placa cada pareja está unida por la pista de potencia. N, L_F y el '
        'ramal hacia el fusible son de 1,0 mm, suficientes para los 500 mA máximos de PS1.'))
    A(Paragraph('5.4 Radiofrecuencia', sH2))
    A(P('La antena impresa del ESP-12F sobresale hacia el borde derecho sin cobre debajo en ninguna capa. '
        'Se eliminó una rama de +3V3 que pasaba junto al keepout y partía el plano de GND bajo el módulo. '
        'J3 queda a ≈ 10 mm de la antena. En la instalación, la caja y los cables no deben cubrir esa zona '
        '(§11.2).'))
    A(Paragraph('5.5 Vistas de cobre', sH2))
    two = Table([[RLImage(a['top'], width=W_FULL / 2 - 6, height=(W_FULL / 2 - 6) * Image.open(a['top']).size[1] / Image.open(a['top']).size[0]),
                  RLImage(a['bot'], width=W_FULL / 2 - 6, height=(W_FULL / 2 - 6) * Image.open(a['bot']).size[1] / Image.open(a['bot']).size[0])]],
                colWidths=[W_FULL / 2, W_FULL / 2])
    two.setStyle(TableStyle([('ALIGN', (0, 0), (-1, -1), 'CENTER')]))
    A(KeepTogether([two, Paragraph('Figura 4. Izquierda: cobre superior (F.Cu) con serigrafía. Derecha: cobre '
                                   'inferior (B.Cu) visto desde abajo (espejado). Las pistas anchas de la zona de '
                                   'red son L_IN y L_OUT, duplicadas en ambas caras.', sCap)]))
    A(Paragraph('5.6 Fabricación y montaje', sH2))
    E(bullets([
        'Objetivo: placa montada completa en JLCPCB; las 32 piezas, SMD y THT, se sueldan en fábrica (THT por ola). Ninguna pieza queda para soldadura manual (MH1 y MH2 son solo taladros).',
        'Archivos en <font face="Mono">fabricacion/</font>: gerbers y taladros (11 archivos), <font face="Mono">BOM_JLCPCB.csv</font> y <font face="Mono">CPL_JLCPCB.csv</font>, empaquetados en <font face="Mono">gerbers_JLCPCB.zip</font>.',
        'El CPL usa el <b>centro de pads</b>, no el del cuerpo: es la referencia que usa JLCPCB. En U2 la antena desplaza el cuerpo (X = 149,65 mm); K1 va en el centro de sus 6 pads.',
        'Taladros ajustados a las piezas reales: J1 Ø1,5 mm y RV1 Ø1,0 mm, para dar holgura de inserción y soldadura por ola. Los pads de cobre no cambian, así que las distancias de aislamiento tampoco.',
        'Antes de pagar, revisar en el visor de JLCPCB que U2 y K1 encajan en sus pads, que la entrada de cable de J1 mira al borde, que el pin 1 de J3 cae en el pad cuadrado (GND) y que todas las referencias de la BOM están seleccionadas.',
    ]))
    A(NextPageTemplate('landscape'))
    A(PageBreak())
    # esquemático apaisado
    lw = landscape(A4)[0] - 2 * 14 * mm
    A(Paragraph('5.7 Esquemático', sH2))
    im = Image.open(a['sch'])
    iw, ih = im.size
    hmax = landscape(A4)[1] - 2 * 18 * mm - 30
    w = min(lw, hmax * iw / ih)
    A(RLImage(a['sch'], width=w, height=w * ih / iw))
    A(Paragraph('Figura 5. Esquemático completo (rele-esp12f.kicad_sch, exportado con kicad-cli 10.0.5). El '
                'cajetín conserva "Rev 1.1" y el nombre del proyecto de origen; ver Apéndice C.', sCap))
    A(NextPageTemplate('normal'))
    A(PageBreak())

    # ---- 6. BOM
    A(Paragraph('6. Lista de materiales', sH1))
    A(P('Coincide con <font face="Mono">fabricacion/BOM_JLCPCB.csv</font>. Todas las piezas van montadas en la cara superior.'))
    A(table([
        ['Ref.', 'Cant.', 'Valor / pieza', 'Encapsulado', 'LCSC'],
        ['U2', '1', 'ESP-12F (ESP8266EX)', 'SMD módulo', 'C82891'],
        ['PS1', '1', 'Hi-Link HLK-PM01, AC/DC 5 V 3 W aislado', 'THT', 'C209903'],
        ['K1', '1', 'Omron G5RL-1A-E-HR DC5, SPST-NO 16 A 250 VAC', 'THT', 'C113250'],
        ['U1', '1', 'AMS1117-3.3, LDO 1 A', 'SOT-223', 'C6186'],
        ['Q1', '1', 'SS8050, NPN', 'SOT-23', 'C2150'],
        ['D1', '1', '1N4148W', 'SOD-123', 'C81598'],
        ['F1', '1', 'Reomax MTS0500A, T500 mA 250 V, acción retardada', 'THT radial', 'C2762401'],
        ['RV1', '1', 'Varistor 07D221K', 'THT disco 7 mm', 'C49072913'],
        ['J1', '1', 'Borna KANGNEX WJ500V-5.08-3P, 250 V 18 A', 'THT 5,08 mm', 'C72334'],
        ['J3', '1', 'Header 2×3, 2,54 mm', 'THT', 'C65114'],
        ['C1', '1', '470 µF 10 V electrolítico', 'THT radial Ø6,3 mm', 'C112505'],
        ['C2, C4', '2', '22 µF 10 V', '0805', 'C45783'],
        ['C9', '1', '10 µF 10 V X5R (Samsung CL10A106KP8NNNC)', '0603', 'C19702'],
        ['C3, C5, C6, C7, C8', '5', '100 nF', '0603', 'C14663'],
        ['R1–R5, R7', '6', '10 kΩ', '0603', 'C25804'],
        ['R6, R8', '2', '1 kΩ', '0603', 'C21190'],
        ['R9', '1', '220 Ω', '0603', 'C22962'],
        ['D2', '1', 'LED rojo (relé)', '0603', 'C2286'],
        ['D3', '1', 'LED azul (Wi-Fi)', '0603', 'C51933294'],
        ['SW1, SW2', '2', 'Pulsador XKB TS-1187A', 'SMD', 'C318884'],
        ['MH1, MH2', '2', 'Taladro de fijación M2 (sin pieza)', 'Ø2,2 mm', '—'],
    ], [2.2, 0.8, 6, 2.4, 1.6]))
    A(P('Total: 32 piezas montadas (20 líneas de BOM) más 2 taladros.', sSmall))

    # ---- 7. Verificación
    A(Paragraph('7. Verificación del diseño', sH1))
    A(table([
        ['Comprobación', 'Herramienta', 'Resultado', 'Comentario'],
        ['DRC (reglas de diseño)', 'kicad-cli 10.0.5, zonas rellenadas', '0 errores · 0 sin conectar · 29 avisos', '23 avisos de huellas que difieren de la librería (taladros ajustados de J1/RV1, modelos 3D propios). 6 de serigrafía de PS1/J1 que roza las esquinas redondeadas; los cuerpos quedan dentro.'],
        ['ERC (esquemático)', 'kicad-cli 10.0.5', '0 errores · 9 avisos', '3 extremos fuera de rejilla y 6 avisos de símbolos que difieren de la librería.'],
        ['Paridad esquemático ↔ PCB', 'KiCad (dato del README)', 'Sin diferencias de conexión', '34 avisos: campos LCSC/Montaje no copiados a las huellas y taladros sin símbolo. Ninguno afecta a la fabricación.'],
        ['Separación red ↔ SELV', 'Medida en el layout', '4,35 mm mín.', 'L_IN ↔ plano de GND, en ambas caras.'],
        ['Netlist ↔ este documento', 'Netlist XML exportada', 'Coincide', 'Asignación de pines, valores y redes de las secciones 3 y 4 extraídos de la netlist.'],
    ], [2.6, 2.6, 2.8, 5.6]))
    A(callout('nota', 'Pendiente de validar en una placa física', [
        'Arranque y conmutación con la red conectada; temperatura de U1, K1 y pistas de potencia a 10 A.',
        'Ondulación del rail de 3,3 V durante la transmisión y al conmutar el relé.',
        'Alcance de Wi-Fi dentro de la caja definitiva.',
        'Prueba de rigidez dieléctrica entre J1 y J3 (si se quiere confirmar el aislamiento del conjunto).']))
    A(PageBreak())

    # ======================= PARTE II
    A(Spacer(1, 60 * mm))
    A(Paragraph('Parte II', sPart))
    A(P('<font size="15" color="#5b6b7a">Guía de usuario</font>', S('x2', leading=22)))
    A(Spacer(1, 6))
    A(P('Instalación, configuración, operación y mantenimiento del módulo rele-esp12f.', sBodyL))
    A(PageBreak())

    # ---- 8. Seguridad
    A(Paragraph('8. Seguridad', sH1))
    A(callout('peligro', 'PELIGRO — Tensión de red: riesgo de muerte por descarga eléctrica', [
        'La instalación debe hacerla una persona cualificada, conforme al reglamento eléctrico local.',
        'Cortar la alimentación en el cuadro y comprobar la ausencia de tensión antes de tocar la placa o el cableado.',
        'Con la red conectada, toda la mitad izquierda de la placa (J1, F1, RV1, PS1, contactos de K1) está a tensión de red. No tocar la placa en funcionamiento.',
        'La placa debe ir siempre dentro de una caja <b>aislante</b> que impida el contacto con cualquier parte.',
        'Nunca conectar el adaptador USB-serie a J3 con la placa conectada a la red.']))
    A(callout('atencion', 'ATENCIÓN — Uso conforme', [
        'Solo para redes de 110–120 VAC. A 230 VAC el varistor RV1 conduce y se destruye (y F1 se abre). Para 230 V hay que cambiar RV1 por un 07D471K y revisar el diseño.',
        'Carga máxima 10 A resistivos; menos para otros tipos (§2.4). Proteger la línea aguas arriba con un magnetotérmico o fusible de 10 A como máximo.',
        'El relé interrumpe solo la fase. Con el relé abierto, la carga sigue unida al neutro: para intervenir en la carga, cortar en el cuadro.',
        'No usar en aplicaciones de seguridad, equipos médicos, sistemas cuyo fallo pueda causar daños a personas, ni en exteriores sin una caja adecuada.',
        'El conjunto no tiene certificación. Su uso es responsabilidad de quien lo instala.']))
    A(Paragraph('8.1 Símbolos y rótulos de la placa', sH2))
    A(table([
        ['Rótulo en serigrafía', 'Significado'],
        ['PELIGRO: 110 VAC', 'Delimita la zona de red.'],
        ['N · OUT · L (junto a J1)', 'Neutro, salida conmutada, fase de entrada.'],
        ['IO0 TX GND / RST RX 5V (junto a J3)', 'Asignación del conector de programación.'],
        ['rele-esp12f v3', 'Identificación de la revisión de hardware.'],
    ], [4, 8]))

    # ---- 9. Contenido y herramientas
    A(Paragraph('9. Material necesario', sH1))
    A(table([
        ['Para', 'Material'],
        ['Primera grabación', 'Adaptador USB-serie con lógica de <b>3,3 V</b> y salida de 5 V (CH340, CP2102, FT232…); 5 cables dupont hembra; PC con esptool (Python) o la herramienta web de Tasmota/ESPHome.'],
        ['Instalación', 'Caja aislante; 2 tornillos M2 de nylon o metálicos con arandela ≤ Ø5 mm y separadores; cable de cobre de 1,5 mm² (o la sección que exija la instalación); punteras si el cable es flexible; destornillador plano de 3 mm; comprobador de ausencia de tensión.'],
        ['Protección de la línea', 'Magnetotérmico (o fusible) de 10 A como máximo, dedicado o compartido con la carga.'],
    ], [2.6, 10]))
    A(PageBreak())

    # ---- 10. Primera grabación
    A(Paragraph('10. Primera grabación del firmware', sH1))
    A(P('La placa sale de fábrica <b>sin firmware de aplicación</b>: el repositorio del proyecto no incluye '
        'ninguno. La primera grabación se hace por J3; las siguientes, por Wi-Fi (OTA). En esta sección se '
        'describen el conexionado y dos firmwares habituales. Las configuraciones de ejemplo se derivan de la '
        'asignación de pines (§4.3) y <b>no se han probado en una placa física</b>.'))
    A(Paragraph('10.1 Conexión del adaptador', sH2))
    A(table([
        ['Adaptador USB-serie', '→', 'J3 de la placa'],
        ['GND', '→', 'pin 1 · GND (pad cuadrado)'],
        ['5 V (VBUS)', '→', 'pin 2 · 5V'],
        ['TX', '→', 'pin 4 · RX'],
        ['RX', '→', 'pin 3 · TX'],
        ['(opcional) GND con un cable aparte', '→', 'pin 5 · IO0, en lugar de pulsar SW1'],
    ], [5, 0.6, 6]))
    A(P('<b>Por qué 5 V y no 3,3 V.</b> El pin de 3,3 V de un adaptador típico da del orden de 50–100 mA, y el '
        'ESP8266 pide picos de varios cientos de mA al calibrar la radio: grabar así produce reinicios. Con los 5 V '
        'del USB (hasta 500 mA) la placa funciona como en servicio, a través de su propio regulador. Además, meter '
        '3,3 V por la salida del AMS1117 polarizaría su diodo interno y cargaría todo el rail de 5 V.'))
    A(Paragraph('10.2 Entrar en modo de grabación', sH2))
    E(steps([
        'Con la placa <b>desconectada de la red</b>, conectar el adaptador como en la tabla anterior y enchufarlo al PC.',
        'Mantener pulsado <b>SW1</b> (IO0).',
        'Pulsar y soltar <b>SW2</b> (RST).',
        'Soltar SW1. El ESP8266 queda esperando datos por la UART. El LED rojo no se enciende y el relé no se mueve.',
    ]))
    A(Paragraph('10.3 Grabación con esptool', sH2))
    A(code('''
pip install esptool
esptool.py --chip esp8266 --port COM5 --baud 115200 flash_id          # comprobar conexión y tamaño de flash
esptool.py --chip esp8266 --port COM5 --baud 115200 erase_flash       # repetir los pasos 2-4 antes
esptool.py --chip esp8266 --port COM5 --baud 460800 write_flash -fm dout 0x0 firmware.bin
'''))
    A(P('Sustituir <font face="Mono">COM5</font> por el puerto del adaptador (en Linux, <font face="Mono">/dev/ttyUSB0</font>). '
        'Hay que volver a entrar en modo de grabación (pasos 2–4) antes de cada orden, porque este conector no tiene '
        'el circuito de reset automático por DTR/RTS. Al terminar, pulsar SW2 para arrancar el firmware.'))
    A(Paragraph('10.4 Opción A: Tasmota', sH2))
    A(P('Grabar <font face="Mono">tasmota.bin</font> (versión genérica para ESP8266) y aplicar esta plantilla en '
        '<i>Configuration → Configure Other → Template</i>, marcando <i>Activate</i>:'))
    A(code('{"NAME":"rele-esp12f","GPIO":[32,0,0,0,544,224,0,0,0,0,0,0,0,0],"FLAG":0,"BASE":18}'))
    A(table([
        ['Posición', 'GPIO', 'Código', 'Función Tasmota'],
        ['1', 'GPIO0', '32', 'Button1 (SW1)'],
        ['5', 'GPIO4', '544', 'LedLink (D3, indica conexión Wi-Fi/MQTT)'],
        ['6', 'GPIO5', '224', 'Relay1 (K1 y D2)'],
        ['resto', '—', '0', 'Sin uso (GPIO1/3 quedan como UART para el log)'],
    ], [1.3, 1.3, 1.3, 8]))
    A(P('Ajustes recomendados en la consola: <font face="Mono">PowerOnState 0</font> (relé abierto tras un corte de '
        'red) o <font face="Mono">PowerOnState 3</font> (recupera el último estado), y <font face="Mono">SetOption1 1</font> '
        'para que una pulsación larga de SW1 no haga un reset de fábrica accidental. Comprobar los códigos con la '
        'documentación de la versión de Tasmota usada.', sBody))
    A(Paragraph('10.5 Opción B: ESPHome', sH2))
    A(code('''
esphome:
  name: rele-esp12f
esp8266:
  board: esp12e                 # ESP-12F: misma asignación y 4 MB de flash
  restore_from_flash: true
wifi:
  ssid: !secret wifi_ssid
  password: !secret wifi_password
  ap: {}                        # punto de acceso de respaldo si no conecta
captive_portal:
logger:
api:
ota:
  - platform: esphome
status_led:
  pin: GPIO4                    # D3, activo alto
switch:
  - platform: gpio
    id: rele
    name: "Relé"
    pin: GPIO5                  # Q1 -> K1, y LED D2
    restore_mode: RESTORE_DEFAULT_OFF
binary_sensor:
  - platform: gpio
    name: "Pulsador SW1"
    pin:
      number: GPIO0
      inverted: true            # activo bajo, pull-up externo R3
    filters:
      - delayed_on: 30ms        # antirrebote
    on_press:
      - switch.toggle: rele
'''))
    A(callout('nota', 'Firmware propio (Arduino / PlatformIO)', [
        'Placa: "Generic ESP8266 Module" o "NodeMCU 1.0 (ESP-12E)"; flash 4 MB, modo DOUT o DIO.',
        'Configurar GPIO5 como salida y escribir LOW antes que nada en <font face="Mono">setup()</font>.',
        'Leer GPIO0 como entrada con antirrebote. No usar GPIO6–11 ni cambiar GPIO15/GPIO2 a salidas que puedan quedar en un nivel incorrecto al reiniciar.',
        'Incluir actualización OTA desde la primera versión: después de instalar la placa ya no se podrá usar J3.']))
    A(PageBreak())

    # ---- 11. Instalación
    A(Paragraph('11. Instalación', sH1))
    A(Paragraph('11.1 Esquema de conexión', sH2))
    A(fig(wiring_diagram(), 'Figura 6. Conexión típica. El relé interrumpe la fase hacia la carga; el neutro es común. '
          'El conductor de protección (PE) va directamente a la carga.'))
    A(Paragraph('11.2 Montaje mecánico', sH2))
    E(bullets([
        'Elegir una caja <b>de plástico</b> (no metálica) con grado IP acorde al lugar y espacio interior para la placa (66,5 × 49 × ≈ 20 mm) más los cables y su radio de curvatura.',
        'Fijar la placa con los taladros MH1 y MH2 (M2) y separadores de ≥ 3 mm para que los terminales THT no toquen el fondo. No atravesar la placa con tornillos en ningún otro punto.',
        'Usar tornillería con cabeza o arandela de Ø ≤ 5 mm: es el diámetro libre de pistas alrededor de cada taladro.',
        'Dejar libre de metal y de cables la zona de la antena (esquina superior derecha, Figura 3). Si la caja va dentro de un registro metálico, el alcance Wi-Fi bajará notablemente.',
        'Separar físicamente los cables de red de la zona de J3 y del ESP-12F; si es necesario, sujetarlos con bridas a la caja.',
        'Prever ventilación pasiva si la carga se acerca a 10 A: las pistas de potencia, el relé y las bornas se calientan.',
    ]))
    A(Paragraph('11.3 Conexión eléctrica', sH2))
    E(steps([
        'Cortar el circuito en el cuadro y <b>comprobar la ausencia de tensión</b> con un comprobador adecuado.',
        'Pelar 6–7 mm de cada conductor (o colocar punteras si es cable flexible) [E: verificar con la hoja de la borna].',
        'Conectar la <b>fase</b> procedente del magnetotérmico en <b>L</b> (J1-3).',
        'Conectar el <b>neutro</b> en <b>N</b> (J1-1). Si la carga comparte neutro, unirlo fuera de la placa con un borne de empalme; J1 admite un solo conductor por polo [E].',
        'Conectar el cable de fase hacia la carga en <b>OUT</b> (J1-2). El otro polo de la carga, a neutro; la tierra, directamente a la carga.',
        'Apretar los tornillos de J1 con firmeza (≈ 0,4–0,5 N·m, valor habitual en bornas de 5,08 mm; comprobar en la hoja de KANGNEX [F]). Tirar suavemente de cada cable para verificarlo.',
        'Comprobar que no hay hilos sueltos ni cobre visible fuera de la borna y cerrar la caja antes de dar tensión.',
    ]))
    A(Paragraph('11.4 Comprobación antes de la puesta en servicio', sH2))
    A(table([
        ['#', 'Comprobación', 'Correcto si…'],
        ['1', 'Firmware grabado y probado alimentando por J3 (sin red)', 'El LED azul indica conexión y el relé conmuta con SW1 / desde la red Wi-Fi.'],
        ['2', 'J3 desconectado y sin cables', 'No queda nada conectado al conector de programación.'],
        ['3', 'Polaridad de J1', 'L en el polo rotulado "L", N en "N", carga en "OUT".'],
        ['4', 'Protección aguas arriba', 'Magnetotérmico o fusible ≤ 10 A en la línea.'],
        ['5', 'Caja cerrada', 'No hay acceso a ninguna parte de la placa.'],
        ['6', 'Puesta en tensión', 'Tras 1–3 s el firmware arranca; el relé permanece abierto salvo que el firmware restaure un estado "cerrado".'],
    ], [0.5, 5, 7]))
    A(PageBreak())

    # ---- 12. Configuración
    A(Paragraph('12. Configuración', sH1))
    A(P('Los pasos dependen del firmware. Esta es la secuencia general con Tasmota y ESPHome:'))
    A(Paragraph('12.1 Conexión a la red Wi-Fi', sH2))
    A(table([
        ['Paso', 'Tasmota', 'ESPHome'],
        ['Primer arranque', 'Crea el punto de acceso <font face="Mono">tasmota-XXXXXX</font>.', 'Si las credenciales de <font face="Mono">secrets.yaml</font> no conectan, crea el AP de respaldo.'],
        ['Configurar Wi-Fi', 'Conectarse al AP, abrir 192.168.4.1 y escribir SSID y contraseña (solo 2,4 GHz).', 'Las credenciales van compiladas; con el AP de respaldo, portal cautivo en 192.168.4.1.'],
        ['Encontrar la IP', 'Desde el router, o por la consola serie durante la grabación.', 'Home Assistant la descubre automáticamente (integración ESPHome).'],
        ['Integración', 'MQTT (Configuration → MQTT) o integración Tasmota de Home Assistant.', 'API nativa de Home Assistant.'],
    ], [2.2, 5.2, 5.2]))
    A(Paragraph('12.2 Ajustes recomendados', sH2))
    E(bullets([
        '<b>Estado tras un corte de red</b>: elegir explícitamente "apagado" o "último estado" según la carga. Para calefactores o cargas que no deben arrancar solas, usar "apagado".',
        '<b>Contraseña de la interfaz web y de OTA</b>: definirla siempre. Cualquiera en la red local podría conmutar la carga o cargar otro firmware.',
        '<b>Red Wi-Fi</b>: el ESP8266 solo funciona en 2,4 GHz y con WPA2 (no WPA3 exclusivo). Si el router mezcla bandas con el mismo nombre, puede ser necesario separar la de 2,4 GHz.',
        '<b>Limitar maniobras</b>: evitar automatizaciones que conmuten el relé muchas veces por minuto; la vida eléctrica del contacto es finita (§14.2).',
        '<b>Hora (NTP) y zona horaria</b>, si se usan temporizadores.',
    ]))
    A(Paragraph('12.3 Actualización por OTA', sH2))
    A(P('Tasmota: <i>Firmware Upgrade</i> desde la interfaz web, con un archivo <font face="Mono">.bin</font> o '
        '<font face="Mono">.bin.gz</font>. ESPHome: <font face="Mono">esphome run rele-esp12f.yaml</font>, que '
        'compila y sube por red. Con 4 MB de flash hay espacio para la actualización en dos etapas. Si una '
        'actualización falla y el módulo no arranca, solo queda la grabación por J3, desmontando la placa de la '
        'instalación (§10).'))

    # ---- 13. Operación
    A(Paragraph('13. Operación', sH1))
    A(Paragraph('13.1 Indicadores', sH2))
    A(table([
        ['Indicador', 'Estado', 'Significado'],
        ['LED rojo (D2)', 'Encendido', 'El firmware ordena el cierre del relé (GPIO5 a nivel alto). Está cableado en paralelo con el driver, así que refleja la orden, no la posición mecánica del contacto.'],
        ['LED rojo (D2)', 'Apagado', 'Relé abierto; también durante el arranque y la grabación.'],
        ['LED azul (D3)', 'Según firmware', 'Tasmota (LedLink): parpadea mientras busca Wi-Fi/MQTT, apagado al conectar (configurable con LedState). ESPHome (status_led): parpadea si hay error o aviso, apagado si todo está bien.'],
        ['Clic audible', 'Al conmutar', 'Cierre o apertura del contacto de K1. Si el LED rojo cambia sin clic, ver §15.'],
    ], [2.2, 2, 8.4]))
    A(Paragraph('13.2 Pulsadores', sH2))
    A(table([
        ['Pulsador', 'Acción', 'Resultado'],
        ['SW1', 'Pulsación corta en servicio', 'Conmuta el relé (si el firmware lo implementa; sí en las configuraciones de §10).'],
        ['SW1', 'Mantenido al arrancar o al pulsar SW2', 'Modo de grabación: el firmware no arranca. Soltar y pulsar SW2 para volver al modo normal.'],
        ['SW1', 'Pulsación de 40 s (Tasmota)', 'Restablece la configuración de fábrica de Tasmota (salvo SetOption1 1).'],
        ['SW2', 'Pulsación', 'Reinicia el módulo. El relé se abre durante el reinicio y vuelve al estado que defina el firmware.'],
    ], [1.6, 4, 7]))
    A(callout('atencion', 'Los pulsadores están en la placa', 'SW1 y SW2 solo son accesibles con la caja abierta, es decir, '
              'junto a partes con tensión de red. Úsalos con la placa sin tensión de red (alimentada por J3), o '
              'añade un pulsador externo en la caja cableado con aislamiento adecuado.'))
    A(Paragraph('13.3 Comportamiento ante eventos', sH2))
    A(table([
        ['Evento', 'Comportamiento de la placa'],
        ['Encendido / vuelta de la red', 'Relé abierto durante ≈ 0,1–1 s hasta que arranca el firmware (R7 mantiene Q1 cortado); después, el estado configurado.'],
        ['Pérdida de Wi-Fi', 'El relé mantiene su estado. El control local (SW1) y los temporizadores internos siguen funcionando si el firmware lo permite.'],
        ['Corte de red', 'El relé se abre (sin alimentación en la bobina). La carga queda sin tensión.'],
        ['Sobretensión transitoria', 'RV1 recorta los picos en la entrada de PS1. No protege la carga: para eso, un protector de sobretensiones en el cuadro.'],
        ['Sobretensión permanente (p. ej. 230 V)', 'RV1 conduce, F1 se abre y la placa deja de funcionar. Requiere reparación (§14.4).'],
        ['Cortocircuito en la carga', 'Lo debe cortar el magnetotérmico aguas arriba. El contacto de K1 puede quedar dañado o soldado: revisar (§15).'],
    ], [3.4, 9.2]))
    A(PageBreak())

    # ---- 14. Mantenimiento
    A(Paragraph('14. Mantenimiento', sH1))
    A(callout('peligro', 'Antes de cualquier intervención', 'Cortar la alimentación en el cuadro y comprobar la ausencia de tensión. '
              'Ninguna operación de mantenimiento se hace con la placa en tensión.'))
    A(Paragraph('14.1 Plan de inspección', sH2))
    A(table([
        ['Cuándo', 'Tarea', 'Qué buscar'],
        ['Al mes de instalar', 'Reapretar los tornillos de J1', 'El cobre se asienta tras los primeros ciclos térmicos y la conexión se afloja.'],
        ['Cada 12 meses', 'Inspección visual con la caja abierta y sin tensión', 'Decoloración o carbonización en J1, en la zona de K1 o en las pistas de potencia; RV1 abombado, agrietado o ennegrecido; C1 abombado; olor a quemado.'],
        ['Cada 12 meses', 'Prueba funcional', 'Conmutación desde la aplicación y con SW1; clic audible; la carga enciende y apaga.'],
        ['Cada 12 meses', 'Firmware', 'Aplicar actualizaciones de seguridad del firmware por OTA.'],
        ['Tras una tormenta o sobretensión', 'Inspección de RV1 y prueba funcional', 'Un varistor que ha absorbido picos fuertes se degrada; si está dañado, reparar (§14.4).'],
        ['Si la carga trabaja cerca de 10 A', 'Revisión cada 6 meses', 'Temperatura de bornas y relé; si es posible, termografía con la carga conectada (desde fuera de la caja).'],
    ], [2.6, 3.6, 6.4]))
    A(Paragraph('14.2 Vida útil del relé', sH2))
    A(P('Omron garantiza un mínimo de <b>50 000 maniobras</b> a 16 A resistivos y 250 VAC [D]. A corrientes '
        'menores la vida es mayor (curva de durabilidad de la hoja de datos). Como referencia conservadora:'))
    A(table([
        ['Maniobras al día', 'Vida mínima estimada a plena carga [C]'],
        ['10', '≈ 13,7 años'],
        ['20', '≈ 6,8 años'],
        ['50', '≈ 2,7 años'],
        ['200 (automatización agresiva)', '≈ 8 meses'],
    ], [5, 7]))
    A(P('Síntomas de fin de vida: la carga no se apaga (contacto soldado), no se enciende o parpadea (contacto '
        'quemado), o hay calentamiento anómalo junto a K1. En esos casos, sustituir el relé o la placa.', sBody))
    A(Paragraph('14.3 Limpieza', sH2))
    A(P('Sin tensión, con aire seco o un pincel antiestático. No usar agua ni disolventes, y no aplicar barnices '
        'sobre el relé ni la borna. Si ha entrado humedad o hay condensación en la caja, dejar la placa fuera de '
        'servicio hasta que esté completamente seca y revisar la estanqueidad de la caja.'))
    A(Paragraph('14.4 Reparaciones', sH2))
    E(bullets([
        '<b>F1 no es un fusible sustituible por el usuario</b>: va soldado. Si se abre, la causa suele ser una sobretensión (RV1) o una avería de PS1. Hay que diagnosticarla antes de cambiarlo, siempre por el mismo tipo: T500 mA 250 V, acción retardada (Reomax MTS0500A o equivalente con la misma huella).',
        'RV1, K1 y PS1 son THT y se pueden sustituir con soldador y desoldador. Usar exactamente las referencias de la BOM (§6): un relé sin la variante "-E" o una fuente distinta cambian la corriente admisible o el aislamiento.',
        'Tras cualquier reparación en la zona de red, comprobar que no quedan restos de estaño ni hilos que reduzcan las distancias de aislamiento, y repetir la comprobación de §11.4.',
    ]))
    A(PageBreak())

    # ---- 15. Diagnóstico
    A(Paragraph('15. Diagnóstico de averías', sH1))
    A(P('Para cualquier medida con la placa abierta, alimentarla por J3 con el adaptador USB (5 V) y <b>sin red '
        'en J1</b>. Así se comprueba toda la parte SELV sin riesgo. Las averías de la zona de red deben diagnosticarse '
        'sin tensión (continuidad, resistencia) o por un técnico cualificado.'))
    A(table([
        ['Síntoma', 'Causa probable', 'Comprobación / solución'],
        ['Con red: ningún LED, no aparece en la red Wi-Fi', 'F1 abierto, PS1 averiada, borna mal conectada o sin firmware.', 'Sin red, alimentar por J3: si funciona, la avería está en la zona de red (F1, RV1, PS1). Comprobar continuidad de F1 sin tensión.'],
        ['El firmware no arranca; la consola serie muestra "boot mode:(1,x)"', 'GPIO0 a nivel bajo al arrancar.', 'SW1 atascado o cable de IO0 a GND en J3. Liberar y pulsar SW2.'],
        ['esptool no conecta ("Failed to connect")', 'No está en modo de grabación; TX/RX sin cruzar; puerto o drivers.', 'Repetir §10.2; cruzar TX↔RX; probar a 115 200 bit/s; comprobar el puerto COM.'],
        ['Reinicios al conectar el Wi-Fi o al conmutar el relé', 'Alimentación insuficiente.', 'Por J3: usar los 5 V del adaptador, no los 3,3 V, y un cable USB corto. Con red: revisar C1/C9 y la salida de PS1.'],
        ['LED rojo cambia pero no hay clic ni conmuta', 'Q1, D1 o bobina de K1 averiados; 5 V bajos.', 'Medir 5 V entre J3-2 y J3-1 (alimentado por J3). Con GPIO5 alto, el colector de Q1 debe estar a < 0,3 V.'],
        ['Hay clic pero la carga no recibe tensión', 'Cableado de OUT/N, magnetotérmico abierto, contacto quemado.', 'Sin tensión, comprobar continuidad L↔OUT con el relé cerrado (alimentado por J3).'],
        ['La carga no se apaga nunca', 'Contacto de K1 soldado (pico de arranque o cortocircuito).', 'Sin tensión: continuidad L↔OUT con el relé en reposo. Si hay continuidad, sustituir K1 y revisar la carga.'],
        ['Conmuta pero el LED rojo no se enciende', 'D2 o R8 averiados o mal soldados.', 'Funcionalmente no afecta. Revisar D2/R8.'],
        ['Wi-Fi débil o desconexiones', 'Caja metálica, antena tapada, distancia, router en 5 GHz.', 'Reubicar la caja; liberar la zona de antena; red de 2,4 GHz; repetidor.'],
        ['Borna o caja calientes', 'Tornillo flojo, sección insuficiente, carga > 10 A.', 'Reapretar, cable de 1,5 mm², reducir la carga. Si hay decoloración, sustituir la placa.'],
        ['Tras una tormenta no funciona', 'RV1 y F1 dañados por sobretensión.', 'Inspección visual de RV1; reparación según §14.4.'],
    ], [3.4, 3.6, 5.6]))
    A(PageBreak())

    # ======================= APÉNDICES
    A(Paragraph('Apéndice A. Cálculos de diseño', sH1))
    A(Paragraph('A.1 Presupuesto de potencia', sH2))
    A(table([
        ['Consumidor', 'Rail', 'Típico', 'Peor caso', 'Fuente'],
        ['ESP8266EX (media / TX 802.11b)', '3,3 V → 5 V vía U1', '80 mA', '170 mA', '[D]'],
        ['LED D3', '3,3 V', '≈ 2 mA', '≈ 3 mA', '[E]'],
        ['LED D2 + base de Q1', '3,3 V', '3,9 mA', '3,9 mA', '[C]'],
        ['Divisores y pull-ups (R1–R5, R7)', '3,3 V', '< 0,5 mA', '< 1 mA', '[C]'],
        ['Bobina de K1', '5 V', '80 mA', '88 mA (−10 % R)', '[D]'],
        ['<b>Total en 5 V</b>', '', '<b>≈ 166 mA</b>', '<b>≈ 266 mA</b>', '[C]'],
        ['Margen sobre PS1 (600 mA)', '', '72 %', '56 %', '[C]'],
    ], [4.6, 2.8, 1.6, 2.2, 1.2]))
    A(P('Los picos de calibración de la radio en el arranque (centenas de mA durante milisegundos) los cubren C1, '
        'C4 y C9. La potencia absorbida de la red, con un rendimiento de PS1 supuesto del 70 % [E], es ≈ 0,6 W con '
        'el relé abierto (≈ 86 mA × 5 V / 0,7) y ≈ 1,2 W con el relé cerrado (≈ 166 mA × 5 V / 0,7).'))
    A(Paragraph('A.2 Regulador U1', sH2))
    A(code('''
P_U1 (media) = (5,0 - 3,3) V x 0,080 A  = 0,136 W   ->  dTj = 0,136 x 90 C/W ~ 12 C
P_U1 (pico)  = (5,0 - 3,3) V x 0,170 A  = 0,289 W   ->  dTj = 0,289 x 90 C/W ~ 26 C
Margen de caída: 5,0 - 3,3 = 1,7 V  >  1,1 V tip. (0,8 A) / 1,3 V máx.
'''))
    A(Paragraph('A.3 Driver del relé', sH2))
    A(code('''
I_bobina = 5 V / 62,5 ohm                        = 80 mA
I_B      = (V_OH - V_BE)/R6 - V_BE/R7
         = (2,64 - 0,75)/1000 - 0,75/10000       = 1,82 mA   (V_OH mínimo = 0,8 x 3,3 V)
beta_forzada = 80 / 1,82                          ~ 44       (saturación garantizada)
V_bobina = 5,0 - V_CE(sat) (~0,2 V)               ~ 4,8 V   >  3,5 V (70 %, cierre)
V_colector al abrir = 5,0 + V_F(D1) (~0,7 V)      ~ 5,7 V
'''))
    A(Paragraph('A.4 Retardo de EN y RST', sH2))
    A(code('''
tau = R1 x C7 = 10 kohm x 100 nF = 1 ms
t(V = 0,75 x 3,3 V) = -tau x ln(1 - 0,75) = 1,39 ms
'''))
    A(Paragraph('A.5 Capacidad de las pistas de potencia (IPC-2221, capa externa)', sH2))
    A(code('''
I = k x dT^0,44 x A^0,725      k = 0,048 (externa), A en mil^2, dT en C
Pista 2,5 mm x 35 um  ->  A = 98,4 mil x 1,38 mil = 136 mil^2
dT = 20 C:  I(1 pista) ~ 6,3 A    I(2 pistas, F.Cu + B.Cu) ~ 12 A
I = 10 A con 2 pistas (5 A cada una):  dT ~ 12 C
'''))
    A(Paragraph('A.6 Vida del relé', sH2))
    A(code('''
Vida (años) = 50 000 maniobras / (maniobras_día x 365)
20 maniobras/día -> 50 000 / 7 300 = 6,8 años   (mínimo garantizado a 16 A resistivos)
'''))

    A(Paragraph('Apéndice B. Referencias', sH1))
    A(table([
        ['Documento', 'Ubicación'],
        ['Omron G5RL PCB Power Relay, Cat. No. K132-E1-10', 'docs/datasheets/omron_g5rl.pdf'],
        ['AMS1117 1A Low Dropout Voltage Regulator', 'docs/datasheets/ams1117.pdf'],
        ['ESP8266EX Datasheet (2025.11, NRND)', 'docs/datasheets/0a-esp8266ex_datasheet_en.pdf'],
        ['ESP8266 Hardware Design Guidelines', 'docs/datasheets/esp8266_hardware_design_guidelines_en.pdf'],
        ['ESP-WROOM-02 Datasheet (referencia de diseño de módulo)', 'docs/datasheets/esp-wroom-02_datasheet_en.pdf'],
        ['Hi-Link HLK-PM01 (no incluido)', 'Hoja del fabricante; LCSC C209903'],
        ['Esquemático y layout', 'rele-esp12f.kicad_sch / rele-esp12f.kicad_pcb (KiCad 10)'],
        ['Archivos de fabricación', 'fabricacion/ (BOM, CPL, gerbers, ZIP para JLCPCB)'],
        ['IPC-2221B, Generic Standard on Printed Board Design', 'Capacidad de corriente de pistas'],
    ], [6, 6.6]))

    A(Paragraph('Apéndice C. Discrepancias conocidas', sH1))
    A(P('Diferencias detectadas al preparar este documento. Ninguna impide fabricar la placa, pero conviene '
        'corregirlas en la documentación del proyecto.'))
    A(table([
        ['#', 'Dónde', 'Discrepancia', 'Criterio adoptado aquí'],
        ['1', 'README (tabla de fabricación)', 'Indica "bobina 5 V, ~106 mA" para K1. En la hoja de Omron, 106 mA / 47,2 Ω es el modelo de bajo ruido (-LN). El G5RL-1A-E-HR de 5 V consume 80 mA / 62,5 Ω / 400 mW.', 'Se usa 80 mA [D]. El cálculo del driver tiene más margen que con 106 mA.'],
        ['2', 'Cajetín del esquemático', 'Muestra "Rev: 1.1", fecha 2026-09-25 y el nombre "ESP-01S_Relay_Module". La serigrafía de la PCB dice "rele-esp12f v3".', 'Se documenta el hardware como v3.'],
        ['3', 'README · Licencias', 'Menciona "Firmware MIT", pero el repositorio no contiene firmware.', 'Se describen firmwares de terceros (§10) con configuraciones no probadas.'],
        ['4', 'docs/datasheets', 'Faltan las hojas de HLK-PM01, KANGNEX WJ500V, 07D221K, SS8050 y Reomax MTS.', 'Sus valores se marcan [F].'],
        ['5', 'Espressif', 'El ESP8266EX figura como NRND.', 'Aviso en §1.4.'],
    ], [0.5, 2.4, 6, 3.7]))

    A(Paragraph('Apéndice D. Historial de revisiones', sH1))
    A(table([
        ['Revisión', 'Fecha', 'Cambios'],
        ['Hardware v1', '—', 'Placa de 66 × 66 mm con relé SRD-05VDC-SL-C.'],
        ['Hardware v2', '—', 'Placa de 66,5 × 44 mm, 110 VAC; nueva distribución, J3 2×3, planos de GND con polígono de aislamiento, montaje en una cara.'],
        ['Hardware v3', '2026-10-03', 'Relé Omron G5RL-1A-E-HR (16 A, aislamiento reforzado); placa de 66,5 × 49 mm; C7/C8 de retardo en EN/RST; C9 10 µF junto al ESP-12F; J3 alimentado a 5 V; L_IN/L_OUT duplicadas en ambas caras (10 A); cobre de red a ≥ 2 mm del borde; taladros de J1/RV1 ajustados; montaje completo en JLCPCB.'],
        ['Documento rev. A', DOC_DATE, 'Primera edición de la hoja de datos y la guía de usuario.'],
    ], [2.2, 1.8, 8.6]))
    return st


def main():
    with tempfile.TemporaryDirectory() as tmp:
        a = build_assets(tmp)
        doc = Doc(OUT, pagesize=A4, title='rele-esp12f — Hoja de datos y guía de usuario',
                  author='@techmigue', subject='Módulo de relé Wi-Fi ESP-12F 110–120 VAC, hardware v3',
                  creator='scripts/generar_datasheet.py (ReportLab)',
                  leftMargin=18 * mm, rightMargin=18 * mm, topMargin=18 * mm, bottomMargin=17 * mm)
        fr = Frame(18 * mm, 17 * mm, A4[0] - 36 * mm, A4[1] - 35 * mm, id='f', leftPadding=0, rightPadding=0,
                   topPadding=0, bottomPadding=0)
        frc = Frame(18 * mm, 17 * mm, A4[0] - 36 * mm, A4[1] - 35 * mm, id='fc', leftPadding=0, rightPadding=0,
                    topPadding=0, bottomPadding=0)
        L = landscape(A4)
        frl = Frame(14 * mm, 15 * mm, L[0] - 28 * mm, L[1] - 32 * mm, id='fl', leftPadding=0, rightPadding=0,
                    topPadding=0, bottomPadding=0)
        doc.addPageTemplates([PageTemplate('cover', [frc], onPage=cover_deco, pagesize=A4),
                              PageTemplate('normal', [fr], onPage=page_deco, pagesize=A4),
                              PageTemplate('landscape', [frl], onPage=land_deco, pagesize=L)])
        story = content(a)
        # Un título seguido de un bloque indivisible (figura, código) no debe quedar huérfano
        merged = []
        for f in story:
            if (isinstance(f, KeepTogether) and merged and isinstance(merged[-1], Paragraph)
                    and merged[-1].style.name in ('h1', 'h2', 'h3')):
                h = merged.pop()
                f = KeepTogether([h] + list(f._content))
            merged.append(f)
        doc.multiBuild(merged)
    print('OK ->', OUT)


if __name__ == '__main__':
    main()
