# -*- coding: utf-8 -*-
"""Generates docs/rele-esp12f_datasheet_user_guide.pdf

Datasheet + user guide for the rele-esp12f module (hardware v3).
Requires: reportlab, PyMuPDF (fitz), Pillow and kicad-cli 10 (for the layer views
and the schematic). Usage:  python scripts/generate_datasheet.py
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
from reportlab.graphics import renderPDF  # noqa: F401  (Drawing as a flowable)

PRJ = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
OUT = os.path.join(PRJ, 'docs', 'rele-esp12f_datasheet_user_guide.pdf')
KICAD_CLI = r'C:\Program Files\KiCad\10.0\bin\kicad-cli.exe'
PCB = os.path.join(PRJ, 'rele-esp12f.kicad_pcb')
SCH = os.path.join(PRJ, 'rele-esp12f.kicad_sch')
DOC_REV = 'B'
DOC_DATE = '2026-10-04'
HW_REV = 'v3'

# ---------------------------------------------------------------- fonts
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

# ---------------------------------------------------------------- colors
INK = colors.HexColor('#1d2733')
ACC = colors.HexColor('#0f5c8c')      # brand blue
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

# ---------------------------------------------------------------- styles
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

W_FULL = A4[0] - 2 * 18 * mm   # usable portrait width


def P(t, st=sBody):
    return Paragraph(t, st)


def bullets(items, st=sBul):
    return [Paragraph(t, st, bulletText='•') for t in items]


def steps(items):
    return [Paragraph(t, sNum, bulletText=f'{i}.') for i, t in enumerate(items, 1)]


def table(rows, widths, head=True, zebra=True, align_top=True, font=None, span=None, extra=None):
    """rows: list of lists of str/flowables. Strings are converted to Paragraph."""
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
    pal = {'danger': (RED, RED_BG), 'caution': (AMB, AMB_BG), 'note': (ACC, BLU_BG)}[kind]
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


# ---------------------------------------------------------------- graphic assets
def build_assets(tmp):
    a = {}
    # copper views (top and bottom, the latter seen from below)
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
    # schematic
    spdf = os.path.join(tmp, 'sch.pdf')
    subprocess.run([KICAD_CLI, 'sch', 'export', 'pdf', '-o', spdf, SCH], check=True, capture_output=True)
    pg = fitz.open(spdf)[0]
    a['sch'] = os.path.join(tmp, 'sch.png')
    pg.get_pixmap(dpi=260).save(a['sch'])
    # existing 3D renders, cropped to the board
    for name, src in [('r3d_top', 'pcb_top.png'), ('r3d_bot', 'pcb_bottom.png')]:
        im = Image.open(os.path.join(PRJ, 'docs', src)).convert('RGB')
        px = im.load()
        W, H = im.size
        # background: lavender gradient (blue > red and light). "Not background" mask.
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


# ---------------------------------------------------------------- drawings
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
    lbl(g, 8, 250, 'MAINS ZONE  110–120 VAC', 7.4, RED, font='Sans-B')
    lbl(g, bar + 12, 250, 'SELV ZONE  5 V / 3.3 V (isolated by PS1)', 7.4, ACC, font='Sans-B')
    lbl(g, bar + 3, 238, 'isolation barrier', 6.0, RED)
    lbl(g, bar + 3, 231, '≥ 4 mm in copper', 6.0, RED)

    box(g, 10, 150, 58, 62, 'J1', ('3P terminal', '5.08 mm', 'N · OUT · L'))
    box(g, 92, 188, 58, 30, 'F1', ('T500 mA 250 V',))
    box(g, 92, 140, 58, 30, 'RV1', ('07D221K',))
    box(g, 166, 168, 96, 52, 'PS1  HLK-PM01', ('isolated AC/DC', '5 V · 0.6 A'))
    box(g, 160, 30, 106, 58, 'K1  G5RL-1A-E-HR', ('NO contact 16 A', 'Coil 5 V · 80 mA'))
    box(g, 292, 176, 70, 40, 'U1', ('AMS1117-3.3', '1 A LDO'))
    box(g, 392, 112, Wd - 400, 104, 'U2  ESP-12F', ('ESP8266EX', 'Wi-Fi 2.4 GHz', 'b/g/n', 'PCB antenna'))
    box(g, 292, 50, 70, 38, 'Q1  SS8050', ('driver + D1', 'flyback'))
    box(g, 292, 112, 70, 36, 'D2 · D3', ('relay / Wi-Fi LED',))
    box(g, 392, 44, 64, 38, 'SW1 · SW2', ('IO0 · RST',))
    box(g, 392, 6, Wd - 400, 28, 'J3  PROG 2×3', ('UART · IO0 · RST · 5 V',))

    # mains
    arrow(g, [68, 203, 92, 203], RED)            ; lbl(g, 70, 206, 'L', 6.4, RED)
    arrow(g, [150, 203, 166, 203], RED)          ; lbl(g, 151, 206, 'L_F', 6.0, RED)
    arrow(g, [68, 160, 92, 155], RED, head=False); lbl(g, 72, 163, 'N', 6.4, RED)
    arrow(g, [150, 155, 158, 155, 158, 180, 166, 180], RED, head=False)
    lbl(g, 120, 182, 'L_F / N', 5.8, RED)
    arrow(g, [24, 150, 24, 70, 160, 70], RED)   ; lbl(g, 28, 73, 'L_IN', 6.2, RED)
    arrow(g, [160, 46, 40, 46, 40, 150], RED)   ; lbl(g, 44, 49, 'L_OUT → load', 6.2, RED)
    # SELV
    arrow(g, [262, 196, 292, 196], ACC)        ; lbl(g, 266, 199, '+5 V', 6.4, ACC)
    arrow(g, [362, 196, 392, 196], ACC)        ; lbl(g, 365, 199, '+3V3', 6.4, ACC)
    arrow(g, [276, 196, 276, 80, 266, 80], ACC); lbl(g, 270, 92, 'coil', 5.8, ACC)
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
    # board
    bx, by, bw, bh = 120, 120, 170, 88
    g.add(Rect(bx - 12, by - 12, bw + 24, bh + 24, rx=6, ry=6, fillColor=colors.HexColor('#f4f4f4'),
               strokeColor=MUTED, strokeDashArray=[3, 2], strokeWidth=0.8))
    lbl(g, bx - 6, by + bh + 4, 'Insulating enclosure (IP rating suited to the location)', 6.4, MUTED)
    g.add(Rect(bx, by, bw, bh, rx=3, ry=3, fillColor=colors.HexColor('#21412a'), strokeColor=INK))
    lbl(g, bx + bw / 2, by + bh - 18, 'rele-esp12f', 9, colors.white, 'middle', 'Sans-B')
    lbl(g, bx + bw / 2, by + bh - 30, 'J1 on the bottom edge', 6.6, colors.HexColor('#cfe3d3'), 'middle')
    xN, xO, xL = bx + 40, bx + 85, bx + 130
    for x, t in [(xN, 'N'), (xO, 'OUT'), (xL, 'L')]:
        g.add(Rect(x - 13, by - 2, 26, 22, fillColor=colors.HexColor('#5fbf7a'), strokeColor=INK, strokeWidth=0.6))
        g.add(Circle(x, by + 9, 5.5, fillColor=colors.white, strokeColor=INK, strokeWidth=0.6))
        lbl(g, x, by + 26, t, 7.4, colors.white, 'middle', 'Sans-B')
    # mains (supply on the right)
    sx = W_FULL - 70
    g.add(Rect(sx, 20, 66, 112, rx=3, ry=3, fillColor=colors.white, strokeColor=INK))
    lbl(g, sx + 33, 118, 'Distribution', 7.6, INK, 'middle', 'Sans-B')
    lbl(g, sx + 33, 108, 'panel', 7.6, INK, 'middle', 'Sans-B')
    lbl(g, sx + 33, 96, '110–120 VAC', 6.6, MUTED, 'middle')
    # circuit breaker on L
    yL, yN, yPE = 70, 40, 20
    g.add(Rect(sx - 100, yL - 11, 46, 22, fillColor=AMB_BG, strokeColor=AMB))
    lbl(g, sx - 77, yL + 1.5, 'Breaker', 6.2, AMB, 'middle', 'Sans-B')
    lbl(g, sx - 77, yL - 7, '≤ 10 A', 6.2, AMB, 'middle', 'Sans-B')
    g.add(Line(sx, yL, sx - 54, yL, strokeColor=RED, strokeWidth=1.6))
    g.add(PolyLine([sx - 100, yL, xL, yL, xL, by - 2], strokeColor=RED, strokeWidth=1.6))
    lbl(g, sx - 4, yL + 3, 'L (line)', 6.6, RED, 'end')
    # neutral
    g.add(PolyLine([sx, yN, xN, yN, xN, by - 2], strokeColor=ACC, strokeWidth=1.6))
    lbl(g, sx - 4, yN + 3, 'N (neutral)', 6.6, ACC, 'end')
    # load
    lx, ly = xO, 6
    g.add(PolyLine([xO, by - 2, xO, 104], strokeColor=colors.HexColor('#7a3a9a'), strokeWidth=1.6))
    g.add(Circle(xO, 92, 12, fillColor=colors.HexColor('#fff8d6'), strokeColor=INK, strokeWidth=0.9))
    g.add(Line(xO - 8.5, 83.5, xO + 8.5, 100.5, strokeColor=INK, strokeWidth=0.8))
    g.add(Line(xO - 8.5, 100.5, xO + 8.5, 83.5, strokeColor=INK, strokeWidth=0.8))
    lbl(g, xO - 16, 95, 'LOAD', 7.2, INK, 'end', 'Sans-B')
    lbl(g, xO - 16, 86, '≤ 10 A resistive', 6.2, MUTED, 'end')
    g.add(PolyLine([xO, 80, xO, yN], strokeColor=ACC, strokeWidth=1.6))
    g.add(Circle(xO, yN, 2.2, fillColor=ACC, strokeColor=ACC))
    # protective earth to the load
    g.add(PolyLine([sx, yPE, xO + 22, yPE, xO + 22, 84, xO + 11, 88], strokeColor=GRN, strokeWidth=1.2,
                   strokeDashArray=[4, 2]))
    lbl(g, sx - 4, yPE + 3, 'PE (earth) → to the load only, not to the board', 6.4, GRN, 'end')
    d.add(g)
    return d


def mech_drawing():
    s = 5.2  # pt per mm
    BW, BH = 66.5, 49.0
    ox, oy = 52, 40
    oy = 52
    d = Drawing(W_FULL, BH * s + 92)
    g = Group()

    def X(x): return ox + x * s
    def Y(y): return oy + (BH - y) * s

    g.add(Rect(X(0), Y(BH), BW * s, BH * s, rx=2 * s, ry=2 * s, fillColor=colors.HexColor('#f2f6f2'),
               strokeColor=INK, strokeWidth=1.1))
    # antenna (approx.)
    g.add(Rect(X(159.5 - 100), Y(117.5 - 100), 7.0 * s, 17.5 * s, fillColor=colors.HexColor('#fff3c4'),
               strokeColor=AMB, strokeDashArray=[2, 2], strokeWidth=0.7))
    lbl(g, X(63.0), Y(9.5), 'antenna', 6.2, AMB, 'middle', 'Sans-B')
    lbl(g, X(63.0), Y(12.2), '(approx.)', 5.6, AMB, 'middle')
    # approximate mains zone (label)
    lbl(g, X(14), Y(31), 'mains zone', 6.6, RED, 'middle', 'Sans-B')
    # components
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
    # J1 pins
    for i, (px, t) in enumerate([(3.34, 'N'), (8.42, 'OUT'), (13.50, 'L')]):
        g.add(Circle(X(px), Y(43.8), 1.4 * s / 2 + 0.5, fillColor=colors.white, strokeColor=RED))
    # mounting holes
    for (x, y, t) in [(51.2, 40.6, 'MH1'), (63.9, 46.4, 'MH2')]:
        g.add(Circle(X(x), Y(y), 1.1 * s, fillColor=colors.white, strokeColor=INK, strokeWidth=0.9))
        g.add(Circle(X(x), Y(y), 2.5 * s, fillColor=None, strokeColor=MUTED, strokeDashArray=[1.5, 1.5],
                     strokeWidth=0.5))
    lbl(g, X(51.2) - 15, Y(40.6) + 13, 'MH1', 6.4, INK, 'middle', 'Sans-B')
    lbl(g, X(63.9) + 3, Y(46.4) + 14, 'MH2', 6.4, INK, 'middle', 'Sans-B')

    # dimensions
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

    hdim(0, BW, Y(0) + 14, '66.5 mm')
    vdim(0, BH, X(0) - 10, '49.0 mm')
    hdim(0, 51.2, Y(BH) - 12, '51.2')
    hdim(0, 63.9, Y(BH) - 24, '63.9')
    vdim(0, 40.6, X(BW) + 30, '40.6')
    vdim(0, 46.4, X(BW) + 58, '46.4')
    for yy in (40.6, 46.4):
        g.add(Line(X(BW) + 2, Y(yy), X(BW) + 60, Y(yy), strokeColor=GRID, strokeWidth=0.4,
                   strokeDashArray=[1, 2]))
    lbl(g, X(0) + 2, Y(0) + 3, '0,0', 5.6, MUTED)
    lbl(g, X(0), oy - 46, 'Origin at the top-left corner (top view). R2 mm corners. '
        'MH1/MH2 holes Ø2.2 mm (M2); dashed circle = Ø5 mm keep-out for traces.', 6.4, MUTED)
    d.add(g)
    return d


# ---------------------------------------------------------------- page templates
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
    c.drawString(18 * mm + 44, h - 11.3 * mm, '·  Wi-Fi relay module 110–120 VAC  ·  Datasheet and user guide')
    c.drawRightString(w - 18 * mm, h - 11.3 * mm, f'Hardware {HW_REV}  ·  Doc. rev. {DOC_REV}  ·  {DOC_DATE}')
    c.setStrokeColor(GRID); c.setLineWidth(0.5)
    c.line(18 * mm, 12 * mm, w - 18 * mm, 12 * mm)
    c.setFont('Sans', 7.2)
    c.drawString(18 * mm, 8.3 * mm, 'Hardware CERN-OHL-W v2  ·  Uncertified prototype: see §1.4 and §8')
    c.drawRightString(w - 18 * mm, 8.3 * mm, f'Page {doc.page}')
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
    c.drawString(20 * mm, h - 24 * mm, 'DATASHEET  ·  USER GUIDE')
    c.setFont('Sans-B', 34)
    c.drawString(20 * mm, h - 42 * mm, 'rele-esp12f')
    c.setFont('Sans', 14)
    c.drawString(20 * mm, h - 52 * mm, 'Single-channel Wi-Fi relay module for 110–120 VAC')
    c.setFont('Sans', 10)
    c.setFillColor(colors.HexColor('#cfe2f0'))
    c.drawString(20 * mm, h - 60 * mm, 'ESP-12F (ESP8266EX)  ·  Omron G5RL-1A-E-HR 16 A  ·  HLK-PM01 isolated supply')
    c.setFont('Sans', 8.6)
    c.drawString(20 * mm, h - 82 * mm, f'Hardware {HW_REV}   ·   Document rev. {DOC_REV}   ·   {DOC_DATE}')
    # footer
    c.setFillColor(MUTED); c.setFont('Sans', 7.4)
    c.drawString(20 * mm, 14 * mm, 'KiCad 10 project · Hardware CERN-OHL-W v2 · Author: @techmigue')
    c.drawRightString(w - 20 * mm, 14 * mm, 'Development prototype — not certified (UL/CE)')
    c.restoreState()


def land_deco(c, doc):
    page_deco(c, doc)


# ---------------------------------------------------------------- content
def content(a):
    st = []
    E = st.extend
    A = st.append

    # ======================= COVER
    A(Spacer(1, 92 * mm))
    A(img(a['r3d_top'], 150 * mm))
    feat_l = [
        '<b>Mains switching</b>: 1 normally-open contact (SPST-NO) on the line conductor, 10 A resistive (board limit); 16 A relay, high-inrush model (100 A).',
        '<b>Integrated supply</b>: direct 110–120 VAC input, HLK-PM01 isolated 5 V / 3 W supply, 3.3 V LDO.',
        '<b>2.4 GHz Wi-Fi</b> 802.11 b/g/n with ESP8266EX; compatible with open firmware (Tasmota, ESPHome, Arduino).',
    ]
    feat_r = [
        '<b>Protection</b>: T500 mA time-lag fuse for the supply, 07D221K varistor, flyback diode on the coil.',
        '<b>Isolation</b>: ≥ 4 mm in copper between mains and low voltage; 8 mm coil-to-contact in the relay (reinforced insulation).',
        '<b>Full assembly at JLCPCB</b>: 32 parts, single side; 66.5 × 49 mm, 2 layers.',
    ]
    ft = Table([[bullets(feat_l), bullets(feat_r)]], colWidths=[W_FULL / 2, W_FULL / 2])
    ft.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0, 0), (-1, -1), 0)]))
    A(Spacer(1, 4))
    A(ft)
    A(NextPageTemplate('normal'))
    A(PageBreak())

    # ======================= TABLE OF CONTENTS
    A(Paragraph('Contents', S('tt', fontName='Sans-B', fontSize=16, leading=20, textColor=ACC, spaceAfter=10)))
    toc = TableOfContents()
    toc.levelStyles = [sTOC1, sTOC2]
    toc.dotsMinLevel = 0
    A(toc)
    A(PageBreak())

    # ======================= PART I
    A(Spacer(1, 40 * mm))
    A(Paragraph('Part I', sPart))
    A(P('<font size="15" color="#5b6b7a">Technical datasheet</font>', S('x', leading=22)))
    A(Spacer(1, 6))
    A(P('Electrical, functional and design specifications of the rele-esp12f module, hardware revision v3.', sBodyL))
    A(Spacer(1, 30 * mm))
    A(P('<b>How to read this document.</b> <b>Part I</b> is the datasheet: limits, characteristics, '
        'functional description and design rationale of the board. <b>Part II</b> is the user guide: '
        'safety, firmware flashing, installation, configuration, operation, maintenance and troubleshooting. '
        'Every numeric value in the specification tables carries a source tag, because not all of them have '
        'the same degree of certainty:', sBody))
    A(table([['Tag', 'Meaning'],
             ['<b>[D]</b>', 'Manufacturer datasheet included in <font face="Mono">docs/datasheets/</font> (Omron G5RL, AMS1117, ESP8266EX).'],
             ['<b>[F]</b>', 'Manufacturer data whose datasheet is <b>not</b> in the project (e.g. HLK-PM01, KANGNEX terminal block, varistor). Verify before relying on it.'],
             ['<b>[C]</b>', 'Calculated from the design (schematic, layout, IPC-2221). The calculation is in Appendix A.'],
             ['<b>[M]</b>', 'Measured on the KiCad layout (distances, dimensions). Not a measurement on a physical board.'],
             ['<b>[E]</b>', 'Design estimate or recommendation. Not measured on a real board.']],
            [1, 9]))
    A(PageBreak())

    # ---- 1. General description
    A(Paragraph('1. General description', sH1))
    A(P('The <b>rele-esp12f</b> is a single-channel, Wi-Fi-controlled mains switching module. It connects '
        'directly to a 110–120 VAC line with neutral, is powered from it through an isolated switch-mode '
        'supply and drives a load of up to 10 A through an Omron power relay whose normally-open contact is '
        'in series with the line conductor. Control is handled by an ESP-12F module (ESP8266EX SoC), which '
        'can run open firmware such as Tasmota or ESPHome, or custom code.'))
    A(P('The board is physically split into two zones: the <b>mains zone</b> (terminal block, fuse, varistor, '
        'supply input and relay contacts) and the extra-low-voltage <b>SELV zone</b> (5 V and 3.3 V, '
        'microcontroller, driver, LEDs, push buttons and programming header). The two zones only interact '
        'through two parts that provide their own isolation: the HLK-PM01 supply and relay K1.'))
    A(Paragraph('1.1 Key features', sH2))
    E(bullets([
        'Mains input 110–120 VAC, 50/60 Hz, with neutral. Estimated self-consumption ≈ 0.6 W idle and ≈ 1.2 W with the relay closed [E].',
        'Switched-line SPST-NO output; 10 A rms resistive as the board limit; Omron G5RL-1A-E-HR relay rated 16 A / 250 VAC, inrush up to 100 A [D].',
        'Hi-Link HLK-PM01 isolated supply (5 V, 600 mA) protected by a T500 mA fuse and a 140 VAC varistor [F].',
        'AMS1117-3.3 regulator and 10 µF + 100 nF decoupling next to the ESP-12F, following the Espressif guidelines.',
        'ESP8266EX: Xtensa L106 CPU at 80/160 MHz, Wi-Fi 802.11 b/g/n, +20 dBm in 802.11b [D].',
        'Safe boot state: the relay stays open during reset and boot (pull-down resistor on the transistor base).',
        'Indicators: red relay-status LED (hardwired) and blue Wi-Fi LED (firmware-controlled).',
        'Local push button SW1 (GPIO0, also used to enter flashing mode) and reset push button SW2.',
        'Programming header J3 (2×3, 2.54 mm) powered at 5 V from the USB-serial adapter; later updates over the air (OTA).',
        '2-layer FR-4 PCB, 1.6 mm, 35 µm copper, 66.5 × 49 mm. All components on the top side.',
    ]))
    A(Paragraph('1.2 Applications', sH2))
    E(bullets(['Remote switching of lighting, fans, resistive heaters and small appliances.',
               'Home-automation integration (Home Assistant, MQTT) with Tasmota or ESPHome.',
               'Timed and scheduled control of mains loads.']))
    A(Paragraph('1.3 Block diagram', sH2))
    A(fig(block_diagram(), 'Figure 1. Block diagram. The red dashed line is the isolation barrier: '
          'only PS1 (supply transformer) and K1 (8 mm coil-to-contact separation) cross it.'))
    A(img(a['r3d_bot'], 105 * mm, 'Figure 2. 3D render of the bottom side: copper, solder mask and THT leads only; there are no components (single-sided assembly).'))
    A(Paragraph('1.4 Product status', sH2))
    A(callout('caution', 'Development prototype, not certified', [
        'This board has not undergone electrical safety (IEC 62368-1, UL, CE) or electromagnetic compatibility testing. Isolation distances follow a design criterion (4 mm), not a formal assessment.',
        'Espressif lists the ESP8266EX as <b>NRND</b> (not recommended for new designs) in its 2025.11 datasheet. The module is still available, but its replacement should be planned for future revisions.',
        'Values tagged [E] have not been measured on a physical board. See Appendix C for known open points.']))
    A(PageBreak())

    # ---- 2. Specifications
    A(Paragraph('2. Specifications', sH1))
    A(Paragraph('2.1 Absolute maximum ratings', sH2))
    A(P('Exceeding any of these values may permanently damage the board or create a fire or shock hazard. '
        'They are not operating conditions.'))
    A(table([
        ['Parameter', 'Condition', 'Limit', 'Source / reason'],
        ['Mains voltage L–N', 'continuous', '140 VAC rms', '[F] Maximum continuous voltage of the 07D221K varistor. Above it, the varistor conducts and is destroyed.'],
        ['Load current (J1 OUT)', 'continuous rms', '10 A', '[C] 2 × 2.5 mm traces, 35 µm: +12 °C at 10 A (IPC-2221).'],
        ['Inrush peak current', 'K1 contact', '100 A peak', '[D] VDE test of the G5RL-1A-E-HR: 240 VAC, 100 A (0-P), 10 A steady state.'],
        ['Contact voltage', 'K1', '250 VAC', '[D] Omron G5RL.'],
        ['Voltage on J3 pin 2 (+5 V)', 'mains disconnected', '5.5 V', '[E] K1 coil ≤ 6.5 V (130 %) [D]; C1–C3 rated 10 V; margin over USB (5.25 V).'],
        ['Voltage on TX, RX, IO0, RST (J3)', '—', '−0.3 … 3.6 V', '[D] ESP8266EX, V<sub>IH</sub> max. 3.6 V. Not 5 V tolerant.'],
        ['Current per GPIO', 'per pin', '12 mA', '[D] ESP8266EX, I<sub>MAX</sub>.'],
        ['U1 junction temperature', '—', '125 °C', '[D] AMS1117.'],
        ['Electrostatic discharge', 'HBM, ESP pins', '2 kV', '[D] ESP8266EX. Handle J3 with ESD precautions.'],
    ], [3.2, 2, 1.8, 6]))
    A(Paragraph('2.2 Recommended operating conditions', sH2))
    A(table([
        ['Parameter', 'Min.', 'Typ.', 'Max.', 'Unit', 'Notes'],
        ['Mains voltage', '100', '115', '127', 'VAC', '110/120 V mains ±10 %. For 230 V, RV1 must be replaced (e.g. 07D471K).'],
        ['Mains frequency', '47', '50/60', '63', 'Hz', '[F] HLK-PM01.'],
        ['Resistive load', '—', '—', '10', 'A', 'See §2.4 for other load types.'],
        ['Ambient temperature (inside the enclosure)', '0', '25', '40', '°C', '[E] Conservative recommendation. The relay is rated −40…85 °C [D]; the real limit is set by PS1 and C1 [F].'],
        ['Relative humidity', '5', '—', '85', '%', '[D] Omron G5RL; non-condensing.'],
        ['Voltage on J3 (flashing only)', '4.75', '5.0', '5.25', 'V', 'VBUS from the USB-serial adapter.'],
    ], [3.6, 0.8, 0.9, 0.8, 0.9, 5.6]))
    A(Paragraph('2.3 Electrical characteristics', sH2))
    A(P('Unless otherwise noted, at 25 °C and 115 VAC.', sSmall))
    A(table([
        ['Parameter', 'Symbol / condition', 'Min.', 'Typ.', 'Max.', 'Unit', 'Source'],
        ['<b>Power supply</b>', '', '', '', '', '', ''],
        ['5 V rail voltage', 'V<sub>5V</sub>, PS1 output', '—', '5.0', '—', 'V', '[F]'],
        ['Available current on 5 V', 'I<sub>PS1</sub>', '—', '—', '600', 'mA', '[F]'],
        ['3.3 V rail voltage', 'V<sub>3V3</sub>, 0–0.8 A, full T<sub>j</sub>', '3.201', '3.300', '3.399', 'V', '[D]'],
        ['U1 dropout', 'I<sub>OUT</sub> = 0.8 A', '—', '1.1', '1.3', 'V', '[D]'],
        ['Available regulation headroom', 'V<sub>5V</sub> − V<sub>3V3</sub>', '—', '1.7', '—', 'V', '[C]'],
        ['ESP8266EX current, average', 'connected to Wi-Fi', '—', '80', '—', 'mA', '[D]'],
        ['ESP8266EX current, transmitting', '802.11b, 11 Mbps, +17 dBm', '—', '170', '—', 'mA', '[D]'],
        ['K1 coil current', '5 V', '—', '80', '—', 'mA', '[D] ±10 %'],
        ['Total load on the 5 V rail', 'relay closed + continuous TX', '—', '≈ 266', '—', 'mA', '[C] 44 % of PS1'],
        ['U1 dissipation', 'average / TX peak', '—', '0.14 / 0.29', '—', 'W', '[C]'],
        ['Power drawn from mains', 'relay open / closed', '—', '≈ 0.6 / 1.2', '—', 'W', '[E] PS1 η ≈ 70 %'],
        ['<b>Output (relay K1)</b>', '', '', '', '', '', ''],
        ['Contact configuration', '—', 'SPST-NO (1 NO), switches the line conductor', '', '', '', ''],
        ['Load current, board limit', 'resistive, rms', '—', '—', '10', 'A', '[C]'],
        ['Contact rated current', '250 VAC resistive', '—', '—', '16', 'A', '[D]'],
        ['Contact resistance', '1 A, 5 VDC, initial', '—', '—', '100', 'mΩ', '[D]'],
        ['Operate time', '—', '—', '—', '15', 'ms', '[D]'],
        ['Release time', 'without diode; D1 extends it', '—', '—', '5', 'ms', '[D]'],
        ['Coil must-operate / must-release voltage', '% of 5 V', '≥ 0.5 V', '—', '≤ 3.5 V', 'V', '[D] 70 % / 10 %'],
        ['Voltage across the coil', '5 V − V<sub>CE(sat)</sub>', '—', '≈ 4.8', '—', 'V', '[C]'],
        ['Electrical endurance', '16 A, 250 VAC resistive, 1,800 ops/h', '50,000', '—', '—', 'ops', '[D]'],
        ['Mechanical endurance', '18,000 ops/h', '10<super>7</super>', '—', '—', 'ops', '[D]'],
        ['<b>Isolation</b>', '', '', '', '', '', ''],
        ['Mains ↔ SELV copper clearance', 'minimum, both sides', '4.35', '—', '—', 'mm', '[M] L_IN ↔ GND plane'],
        ['Mains copper ↔ board edge', 'minimum', '2.0', '—', '—', 'mm', '[M] J1 N pad'],
        ['K1 coil ↔ contact', 'clearance / creepage', '8 / 8', '—', '—', 'mm', '[D] reinforced'],
        ['Coil ↔ contact dielectric strength', '1 min, 50/60 Hz', '6,000', '—', '—', 'VAC', '[D]'],
        ['Coil ↔ contact impulse', '1.2 × 50 µs', '10', '—', '—', 'kV', '[D]'],
        ['PS1 input–output isolation', '—', 'see Hi-Link datasheet', '', '', '', '[F]'],
    ], [3.6, 3.1, 0.95, 1.05, 0.95, 0.6, 1.9],
        extra=[('SPAN', (0, 1), (-1, 1)), ('BACKGROUND', (0, 1), (-1, 1), ACC2),
               ('SPAN', (0, 13), (-1, 13)), ('BACKGROUND', (0, 13), (-1, 13), ACC2),
               ('SPAN', (2, 14), (-1, 14)),
               ('SPAN', (0, 24), (-1, 24)), ('BACKGROUND', (0, 24), (-1, 24), ACC2),
               ('SPAN', (2, 30), (5, 30))]))
    A(Spacer(1, 6))
    A(table([
        ['Parameter (microcontroller and radio)', 'Condition', 'Value', 'Source'],
        ['SoC', '—', 'ESP8266EX, Xtensa L106 32-bit, 80/160 MHz', '[D]'],
        ['Operating voltage', '—', '2.5 … 3.6 V (3.3 V typ.)', '[D]'],
        ['Flash memory', 'ESP-12F module', '4 MB typ. (depends on module batch/vendor)', '[F]'],
        ['Band', '—', '2,412 … 2,484 MHz, 802.11 b/g/n (HT20)', '[D]'],
        ['Transmit power', '802.11b / g / n', '+20 / +17 / +14 dBm', '[D]'],
        ['Sensitivity', '11 Mbps CCK / 54 Mbps / MCS7', '−91 / −75 / −72 dBm', '[D]'],
        ['Logic levels', 'V<sub>IL</sub> / V<sub>IH</sub> / V<sub>OH</sub>', '≤ 0.25 V<sub>IO</sub> / ≥ 0.75 V<sub>IO</sub> / ≥ 0.8 V<sub>IO</sub>', '[D]'],
        ['Enable delay', 'R1·C7 = R2·C8', 'τ = 1 ms (EN reaches 0.75·V<sub>IO</sub> in ≈ 1.4 ms)', '[C]'],
    ], [3.6, 3, 5, 1]))
    A(Paragraph('2.4 Switching capacity by load type', sH2))
    A(P('The G5RL-1A-E-HR relay is designed for high-inrush loads, but the board limits the steady-state '
        'current to 10 A. For non-resistive loads, contact wear depends on the make inrush and on the break '
        'arc, so derating is recommended:'))
    A(table([
        ['Load type', 'Recommended steady current', 'At 120 VAC', 'Rationale'],
        ['Resistive (heater, heating element, oven)', '≤ 10 A', '≤ 1,200 W', '[C] Trace limit; 16 A contact [D].'],
        ['Incandescent / halogen lamp', '≤ 5 A', '≤ 600 W', '[D] UL TV-5 rating at 120 VAC (5 A steady, cold-filament inrush).'],
        ['LED drivers, switch-mode supplies (capacitive load)', '≤ 5 A', '≤ 600 W', '[E] The HR model is tested at 100 A peak [D]; margin is left for the sum of inrush peaks of several drivers.'],
        ['Motors, fans, transformers (inductive)', '≤ 3 A', '≤ 360 VA', '[E] The datasheet gives no motor rating for the -HR model. Consider an RC snubber at the load.'],
    ], [3.8, 2.4, 1.6, 6]))
    A(callout('note', 'The load is not protected by F1',
              'F1 (T500 mA) only protects the PS1 supply. The OUT terminal must be protected upstream by a '
              'circuit breaker or fuse of <b>10 A maximum</b>. An on-board fuse would not do: its breaking '
              'capacity (tens of amperes) is far below the short-circuit current of a mains outlet.'))
    A(Paragraph('2.5 Mechanical and environmental characteristics', sH2))
    A(table([
        ['Parameter', 'Value', 'Source'],
        ['Board dimensions', '66.5 × 49.0 mm, R2 mm corners', '[M]'],
        ['Thickness / material', '1.6 mm, FR-4, 2 layers, 35 µm (1 oz) copper on both sides', '[M]'],
        ['Height above the top side', '≈ 16 mm (relay 15.7 mm max. [D]; HLK-PM01 ≈ 15 mm [F])', '[E]'],
        ['Height below the board', '≈ 2 mm (THT leads trimmed after wave soldering)', '[E]'],
        ['Mounting holes', '2 × Ø2.2 mm (M2) at (51.2; 40.6) and (63.9; 46.4) mm; head or washer ≤ Ø5 mm', '[M]'],
        ['Terminal block J1', '3 poles, 5.08 mm pitch, 250 V / 18 A, wire entry towards the board edge', '[F]'],
        ['Relay weight', '≈ 10 g', '[D]'],
        ['Vibration (relay)', '10–55 Hz, 1.5 mm double amplitude', '[D]'],
        ['Shock (relay)', '100 m/s² malfunction; 1,000 m/s² destruction', '[D]'],
    ], [3, 8, 1]))
    A(fig(mech_drawing(), 'Figure 3. Mechanical drawing and interface elements (top view, dimensions in mm). '
          'The antenna area is approximate; it is drawn from the ESP-12F footprint outline.'))
    A(PageBreak())

    # ---- 3. Functional description
    A(Paragraph('3. Functional description', sH1))
    A(Paragraph('3.1 Mains input and protection', sH2))
    A(P('The line conductor enters through J1-3 (<b>L</b>) and the neutral through J1-1 (<b>N</b>). Two paths '
        'leave L: the load path, which goes straight to the K1 contact (net <font face="Mono">L_IN</font>), and the '
        'supply path, which goes through fuse F1 (net <font face="Mono">L_F</font>). Varistor RV1 sits between '
        '<font face="Mono">L_F</font> and N, i.e. <i>after</i> the fuse.'))
    E(bullets([
        '<b>Why RV1 is after F1.</b> Under a sustained overvoltage (e.g. 230 V connected by mistake) the varistor conducts continuously. This way the fuse opens, instead of the varistor overheating with no current limit.',
        '<b>Why F1 is time-lag (T).</b> The HLK-PM01 draws an inrush current when charging its input capacitor. A 500 mA fast-acting fuse could blow at every power-up.',
        '<b>Why the load does not go through F1.</b> The load current (up to 10 A) has nothing to do with the supply current (tens of mA). Its protection belongs to the installation (§2.4).',
    ]))
    A(Paragraph('3.2 Isolated supply and regulation', sH2))
    A(P('PS1 (Hi-Link HLK-PM01) converts mains into isolated 5 V. Together with K1, it is the only part that '
        'crosses the isolation barrier. The 5 V rail feeds the relay coil and the linear regulator U1 '
        '(AMS1117-3.3), which generates the 3.3 V for the ESP-12F.'))
    A(table([
        ['Component', 'Value', 'Function'],
        ['C1', '470 µF 10 V electrolytic', '5 V energy reservoir: absorbs the current step when the relay closes (80 mA) and the transmit peaks.'],
        ['C2 · C3', '22 µF X5R 0805 · 100 nF', 'U1 input: stability and fast response.'],
        ['C4 · C6', '22 µF X5R 0805 · 100 nF', 'U1 output. The AMS1117 needs ≥ 22 µF at its output to be stable.'],
        ['C9 · C5', '10 µF X5R 0603 · 100 nF', 'Next to the ESP-12F VCC pin (combination recommended by Espressif). C4 is ~25 mm of trace away and cannot cover the transmit edges.'],
    ], [1.6, 3.4, 8]))
    A(P('<b>LDO selection rationale.</b> With 5 V in and 3.3 V out there is 1.7 V of headroom, above the '
        'AMS1117 dropout (1.1 V typ. at 0.8 A [D]). Average dissipation is (5 − 3.3) V × 80 mA ≈ '
        '0.14 W; with θ<sub>JA</sub> ≈ 90 °C/W the junction temperature rise is about 13 °C (26 °C at transmit '
        'peak). A switching converter would save ~0.1 W, but would add noise next to the radio and more parts.'))
    A(Paragraph('3.3 Microcontroller and boot configuration', sH2))
    A(P('The ESP8266EX samples three strapping pins on the rising edge of reset to decide where to boot from. '
        'The on-board resistors select normal boot from flash; SW1 forces UART flashing mode.'))
    A(table([
        ['Pin', 'Net', 'Components', 'Level at boot', 'Effect'],
        ['GPIO15', '/GPIO15', 'R5 10 k to GND', '0', 'Must be 0 to boot from flash or UART.'],
        ['GPIO2', '/GPIO2', 'R4 10 k to 3V3', '1', 'Must be 1.'],
        ['GPIO0', '/GPIO0', 'R3 10 k to 3V3; SW1 to GND; J3-5', '1 (0 with SW1)', '1 = boot from flash; 0 = UART flashing mode.'],
        ['EN (CH_PD)', '/EN', 'R1 10 k to 3V3; C7 100 nF to GND', '↑ with τ = 1 ms', 'Enables the chip once VCC has settled.'],
        ['RST', '/RST', 'R2 10 k to 3V3; C8 100 nF; SW2 to GND; J3-6', '↑ with τ = 1 ms', 'External reset; SW2 restarts the module.'],
    ], [1.4, 1.4, 3.6, 1.8, 4.6]))
    A(P('The RC delay on EN and RST follows the Espressif power-up sequence: EN and RST must rise '
        'after VDD33 (t<sub>3</sub>, t<sub>5</sub> ≥ 0.1 ms [D]). Without capacitors, a slow ramp of the '
        '3.3 V rail can leave the chip in an undefined state.'))
    A(Paragraph('3.4 Relay driver', sH2))
    A(P('GPIO5 (net <font face="Mono">/RELAY</font>) drives the base of Q1 (SS8050, NPN) through R6 (1 kΩ). '
        'Q1 switches the low side of the coil (<font face="Mono">/COIL_N</font>); the other end is at +5 V. '
        'D1 (1N4148W) recirculates the coil current when Q1 turns off and clamps its collector to '
        '≈ 5.7 V. R7 (10 kΩ) holds the base at GND while GPIO5 is high-impedance (reset, boot, '
        'flashing): the relay <b>cannot close</b> until the firmware commands it.'))
    A(table([
        ['Quantity', 'Calculation', 'Result'],
        ['Coil current', '5 V / 62.5 Ω', '80 mA'],
        ['Base current (V<sub>OH</sub> = 3.3 V)', '(3.3 − 0.75) / 1 k − 0.75 / 10 k', '2.48 mA'],
        ['Base current (V<sub>OH</sub> min. = 2.64 V)', '(2.64 − 0.75) / 1 k − 0.75 / 10 k', '1.82 mA'],
        ['Forced β (worst case)', '80 mA / 1.82 mA', '≈ 44 → saturation with ample margin (SS8050 h<sub>FE</sub> ≫ 44)'],
        ['Total GPIO5 current', 'I<sub>B</sub> + I<sub>D2</sub> ≈ 2.5 + 1.4', '≈ 3.9 mA (< 12 mA [D])'],
    ], [3.3, 4.7, 5]))
    A(P('With a plain parallel diode the coil current decays slowly and the contact opens somewhat later than '
        'the 5 ms in the datasheet (not measured). For a 10 A AC load this is acceptable; a zener in series '
        'with D1 would speed up release at the cost of more voltage on Q1.', sBody))
    A(Paragraph('3.5 Indicators and push buttons', sH2))
    A(table([
        ['Ref.', 'Element', 'Connection', 'Logic', 'Notes'],
        ['D2', 'Red "relay" LED', 'GPIO5 → D2 → R8 1 k → GND', 'Active high', 'In parallel with the driver: on = close command issued. ≈ 1.4 mA [E].'],
        ['D3', 'Blue "Wi-Fi" LED', 'GPIO4 → R9 220 Ω → D3 → GND', 'Active high', 'Meaning defined by the firmware. Current ≈ 1–2 mA, depends on the blue LED V<sub>F</sub> [E].'],
        ['SW1', 'TS-1187A push button', 'GPIO0 ↔ GND', 'Active low', 'Local switching in service; held during reset = flashing mode.'],
        ['SW2', 'TS-1187A push button', 'RST ↔ GND', 'Active low', 'Module reset.'],
    ], [0.8, 2.3, 3.6, 1.6, 5]))
    A(PageBreak())

    # ---- 4. Connectors and pin assignment
    A(Paragraph('4. Connectors and pin assignment', sH1))
    A(Paragraph('4.1 J1 — Mains terminal block', sH2))
    A(table([
        ['Pin', 'Label', 'Net', 'Function', 'Recommended wire size'],
        ['1', 'N', '/N', 'Input neutral; shared by the load and PS1', '1.5 mm² (≈ 14 AWG) for 10 A [E]'],
        ['2', 'OUT', '/L_OUT', 'Switched line to the load', '1.5 mm²'],
        ['3', 'L', '/L_IN', 'Input line (from the circuit breaker)', '1.5 mm²'],
    ], [0.7, 1, 1.3, 5, 4]))
    A(P('KANGNEX WJ500V-5.08-3P terminal block (250 V / 18 A) [F]. The wire entry faces the bottom edge of the '
        'board. Use copper conductors; for stranded wire, use ferrules of the right size.', sBody))
    A(Paragraph('4.2 J3 — Programming (2×3, 2.54 mm pitch)', sH2))
    jt = Table([
        [P('<b>IO0</b><br/>pin 5', sCell), P('<b>TX</b><br/>pin 3', sCell), P('<b>GND</b><br/>pin 1 ■', sCell)],
        [P('<b>RST</b><br/>pin 6', sCell), P('<b>RX</b><br/>pin 4', sCell), P('<b>5V</b><br/>pin 2', sCell)],
    ], colWidths=[22 * mm] * 3, rowHeights=[12 * mm] * 2)
    jt.setStyle(TableStyle([('GRID', (0, 0), (-1, -1), 0.8, INK), ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#fafafa')),
                            ('BACKGROUND', (2, 0), (2, 0), colors.HexColor('#ffe9a8'))]))
    jdesc = table([
        ['Pin', 'Signal', 'Connect to adapter'],
        ['1 (square)', 'GND', 'GND'],
        ['2', '+5 V (input)', '5 V / VBUS'],
        ['3', 'ESP TXD', 'adapter RX'],
        ['4', 'ESP RXD', 'adapter TX'],
        ['5', 'GPIO0', 'GND to flash (or use SW1)'],
        ['6', 'RST', 'optional (or use SW2)'],
    ], [1.3, 1.6, 2.6])
    wrap = Table([[jt, jdesc]], colWidths=[75 * mm, W_FULL - 75 * mm])
    wrap.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('LEFTPADDING', (0, 0), (-1, -1), 0)]))
    jdesc._argW = [w * (W_FULL - 75 * mm) / W_FULL for w in jdesc._argW]
    A(wrap)
    A(P('Top view, with the board oriented as in Figure 3 (matches the silkscreen label). '
        'TX/RX are <b>3.3 V</b> lines: the adapter must use 3.3 V logic even though the board is powered '
        'from its 5 V.', sSmall))
    A(callout('danger', 'Use J3 only with the board disconnected from mains',
              'J3 is in the SELV zone, but an insulation failure in PS1 or K1 would bring it to mains potential, '
              'and through the adapter the computer as well. Never connect anything to J3 while mains is connected to J1.'))
    A(Paragraph('4.3 ESP-12F pin assignment', sH2))
    A(table([
        ['Module pin', 'GPIO', 'Net', 'Direction', 'Use'],
        ['20', 'GPIO5', '/RELAY', 'Output', 'Relay K1 (via Q1) and LED D2. Active high.'],
        ['19', 'GPIO4', '/WIFI_LED', 'Output', 'LED D3. Active high.'],
        ['18', 'GPIO0', '/GPIO0', 'Input', 'Push button SW1 (active low, pull-up R3). Strapping pin.'],
        ['22', 'GPIO1 / TXD', '/TXD', 'Output', 'UART0 TX → J3-3. Firmware log at 115,200 bit/s (typical).'],
        ['21', 'GPIO3 / RXD', '/RXD', 'Input', 'UART0 RX ← J3-4.'],
        ['17', 'GPIO2', '/GPIO2', '—', 'Pull-up R4. Strapping pin. Usable by the firmware with care (on many ESP-12F modules it drives the on-module blue LED, active low [F]).'],
        ['16', 'GPIO15', '/GPIO15', '—', 'Pull-down R5. Strapping pin. Do not use.'],
        ['1 · 3', 'RST · EN', '/RST · /EN', 'Input', 'Reset (SW2, J3-6) and enable, with a 1 ms RC.'],
        ['4, 5, 6, 7', 'GPIO16, 14, 12, 13', '—', '—', 'Not connected. Only reachable by soldering to the module castellations.'],
        ['2', 'ADC (TOUT)', '—', '—', 'Not connected.'],
        ['9–14', 'GPIO6–11', '—', '—', 'Internal flash bus. <b>Do not use.</b>'],
    ], [1.5, 2.1, 1.8, 1.4, 6.4]))
    A(PageBreak())

    # ---- 5. Hardware design
    A(Paragraph('5. Hardware design', sH1))
    A(P('This section summarizes the engineering criteria that define the topology, layout and margins of the '
        'board. The full schematic is on the following page.'))
    A(Paragraph('5.1 Board partitioning', sH2))
    E(bullets([
        '<b>Top strip:</b> PS1 on the left and the ESP-12F rotated 270° with its antenna on the right edge, over a copper-free area (footprint keep-out).',
        '<b>Bottom left, mains zone:</b> J1 on the bottom edge, F1 and RV1 above it and K1 to its right. No GND plane or low-voltage trace enters this zone.',
        '<b>Bottom right, low voltage:</b> U1 and its capacitors, C1, relay driver, push buttons, LEDs, J3 and the two mounting holes.',
        '<b>GND planes</b> on both sides, clipped by a polygon that geometrically stays ≥ 4.5 mm from all mains copper. The clearance therefore does not rely solely on correctly assigned net classes.',
        '<b>Mounting holes</b> inside the low-voltage zone, with a Ø5 mm circle free of traces and signal vias (GND plane only), so a metal washer cannot damage a trace.',
    ]))
    A(Paragraph('5.2 Design and isolation rules', sH2))
    A(table([
        ['Rule', 'Value', 'Rationale'],
        ['Mains ↔ low voltage', '4.0 mm (measured: 4.35 mm)', 'Custom rule in rele-esp12f.kicad_dru, with no exceptions across the board. Design distance between mains and SELV circuits.'],
        ['Between mains nets (L_IN, L_OUT, L_F, N)', '2.0 mm', 'Functional insulation between 120 V mains conductors.'],
        ['Mains copper ↔ board edge', '≥ 2.0 mm', 'Margin against contact with an enclosure or bracket; the enclosure must still be insulating.'],
        ['K1 coil ↔ contact', '8 mm (internal) / 20 mm between pads', 'G5RL reinforced insulation [D]. The 2 mm exception required by the previous revision\'s relay was removed.'],
        ['SELV signal / power', '0.25–0.3 mm / 0.5–0.6 mm', 'Standard JLCPCB manufacturing capability.'],
    ], [3.4, 3.2, 7]))
    A(Paragraph('5.3 Power traces', sH2))
    A(P('The load current flows through L_IN (J1-3 → K1) and L_OUT (K1 → J1-2). Both are 2.5 mm traces '
        '<b>duplicated on both sides</b> and joined at the THT pads of J1 and K1. Per IPC-2221 (external layer, '
        '35 µm), 2 × 2.5 mm carry ≈ 12 A with a 20 °C rise; at 10 A the expected rise is '
        '≈ 12 °C [C]. The G5RL-1A-E is a high-capacity model: each contact comes out on <b>two</b> pins and '
        'Omron requires both to be used [D]; on the board each pair is joined by the power trace. N, L_F and the '
        'branch to the fuse are 1.0 mm, enough for the 500 mA maximum of PS1.'))
    A(Paragraph('5.4 Radio frequency', sH2))
    A(P('The ESP-12F printed antenna overhangs towards the right edge with no copper underneath on any layer. '
        'A +3V3 branch that ran next to the keep-out and split the GND plane under the module was removed. '
        'J3 is ≈ 10 mm from the antenna. In the installation, the enclosure and wiring must not cover that area '
        '(§11.2).'))
    A(Paragraph('5.5 Copper views', sH2))
    two = Table([[RLImage(a['top'], width=W_FULL / 2 - 6, height=(W_FULL / 2 - 6) * Image.open(a['top']).size[1] / Image.open(a['top']).size[0]),
                  RLImage(a['bot'], width=W_FULL / 2 - 6, height=(W_FULL / 2 - 6) * Image.open(a['bot']).size[1] / Image.open(a['bot']).size[0])]],
                colWidths=[W_FULL / 2, W_FULL / 2])
    two.setStyle(TableStyle([('ALIGN', (0, 0), (-1, -1), 'CENTER')]))
    A(KeepTogether([two, Paragraph('Figure 4. Left: top copper (F.Cu) with silkscreen. Right: bottom copper '
                                   '(B.Cu) seen from below (mirrored). The wide traces in the mains zone are '
                                   'L_IN and L_OUT, duplicated on both sides.', sCap)]))
    A(Paragraph('5.6 Manufacturing and assembly', sH2))
    E(bullets([
        'Goal: fully assembled board from JLCPCB; all 32 parts, SMD and THT, are soldered at the factory (THT by wave). No part is left for hand soldering (MH1 and MH2 are just holes).',
        'Files in <font face="Mono">fabrication/</font>: gerbers and drill files (11 files), <font face="Mono">BOM_JLCPCB.csv</font> and <font face="Mono">CPL_JLCPCB.csv</font>, packaged in <font face="Mono">gerbers_JLCPCB.zip</font>.',
        'The CPL uses the <b>pad center</b>, not the body center: this is the reference JLCPCB uses. On U2 the antenna offsets the body (X = 149.65 mm); K1 is placed at the center of its 6 pads.',
        'Drill sizes matched to the real parts: J1 Ø1.5 mm and RV1 Ø1.0 mm, to give insertion and wave-soldering clearance. Copper pads are unchanged, so isolation distances are too.',
        'Before paying, check in the JLCPCB viewer that U2 and K1 sit on their pads, that the J1 wire entry faces the edge, that J3 pin 1 lands on the square pad (GND) and that every BOM line has a part selected.',
    ]))
    A(NextPageTemplate('landscape'))
    A(PageBreak())
    # landscape schematic
    lw = landscape(A4)[0] - 2 * 14 * mm
    A(Paragraph('5.7 Schematic', sH2))
    im = Image.open(a['sch'])
    iw, ih = im.size
    hmax = landscape(A4)[1] - 2 * 18 * mm - 30
    w = min(lw, hmax * iw / ih)
    A(RLImage(a['sch'], width=w, height=w * ih / iw))
    A(Paragraph('Figure 5. Full schematic (rele-esp12f.kicad_sch, exported with kicad-cli 10.0.5).', sCap))
    A(NextPageTemplate('normal'))
    A(PageBreak())

    # ---- 6. BOM
    A(Paragraph('6. Bill of materials', sH1))
    A(P('Matches <font face="Mono">fabrication/BOM_JLCPCB.csv</font>. All parts are mounted on the top side.'))
    A(table([
        ['Ref.', 'Qty', 'Value / part', 'Package', 'LCSC'],
        ['U2', '1', 'ESP-12F (ESP8266EX)', 'SMD module', 'C82891'],
        ['PS1', '1', 'Hi-Link HLK-PM01, isolated AC/DC 5 V 3 W', 'THT', 'C209903'],
        ['K1', '1', 'Omron G5RL-1A-E-HR DC5, SPST-NO 16 A 250 VAC', 'THT', 'C113250'],
        ['U1', '1', 'AMS1117-3.3, 1 A LDO', 'SOT-223', 'C6186'],
        ['Q1', '1', 'SS8050, NPN', 'SOT-23', 'C2150'],
        ['D1', '1', '1N4148W', 'SOD-123', 'C81598'],
        ['F1', '1', 'Reomax MTS0500A, T500 mA 250 V, time-lag', 'THT radial', 'C2762401'],
        ['RV1', '1', 'Varistor 07D221K', 'THT 7 mm disc', 'C49072913'],
        ['J1', '1', 'KANGNEX WJ500V-5.08-3P terminal block, 250 V 18 A', 'THT 5.08 mm', 'C72334'],
        ['J3', '1', 'Header 2×3, 2.54 mm', 'THT', 'C65114'],
        ['C1', '1', '470 µF 10 V electrolytic', 'THT radial Ø6.3 mm', 'C112505'],
        ['C2, C4', '2', '22 µF 10 V', '0805', 'C45783'],
        ['C9', '1', '10 µF 10 V X5R (Samsung CL10A106KP8NNNC)', '0603', 'C19702'],
        ['C3, C5, C6, C7, C8', '5', '100 nF', '0603', 'C14663'],
        ['R1–R5, R7', '6', '10 kΩ', '0603', 'C25804'],
        ['R6, R8', '2', '1 kΩ', '0603', 'C21190'],
        ['R9', '1', '220 Ω', '0603', 'C22962'],
        ['D2', '1', 'Red LED (relay)', '0603', 'C2286'],
        ['D3', '1', 'Blue LED (Wi-Fi)', '0603', 'C51933294'],
        ['SW1, SW2', '2', 'XKB TS-1187A push button', 'SMD', 'C318884'],
        ['MH1, MH2', '2', 'M2 mounting hole (no part)', 'Ø2.2 mm', '—'],
    ], [2.2, 0.8, 6, 2.4, 1.6]))
    A(P('Total: 32 assembled parts (20 BOM lines) plus 2 mounting holes.', sSmall))

    # ---- 7. Verification
    A(Paragraph('7. Design verification', sH1))
    A(table([
        ['Check', 'Tool', 'Result', 'Comment'],
        ['DRC (design rules)', 'kicad-cli 10.0.5, zones refilled', '0 errors · 0 unconnected · 29 warnings', '23 warnings for footprints that differ from the library (adjusted J1/RV1 drills, custom 3D models). 6 for PS1/J1 silkscreen touching the rounded corners; the bodies stay inside.'],
        ['ERC (schematic)', 'kicad-cli 10.0.5', '0 errors · 9 warnings', '3 off-grid endpoints and 6 warnings for symbols that differ from the library.'],
        ['Schematic ↔ PCB parity', 'kicad-cli 10.0.5', 'No connection differences', '34 warnings: LCSC/Assembly fields not copied to footprints and mounting holes without a symbol. None affects manufacturing.'],
        ['Mains ↔ SELV clearance', 'Measured on the layout', '4.35 mm min.', 'L_IN ↔ GND plane, on both sides.'],
        ['Netlist ↔ this document', 'Exported XML netlist', 'Matches', 'Pin assignment, values and nets in sections 3 and 4 extracted from the netlist.'],
    ], [2.6, 2.6, 2.8, 5.6]))
    A(callout('note', 'Pending validation on a physical board', [
        'Boot and switching with mains connected; temperature of U1, K1 and power traces at 10 A.',
        'Ripple on the 3.3 V rail during transmission and when the relay switches.',
        'Wi-Fi range inside the final enclosure.',
        'Dielectric strength test between J1 and J3 (to confirm the isolation of the assembly).']))
    A(PageBreak())

    # ======================= PART II
    A(Spacer(1, 60 * mm))
    A(Paragraph('Part II', sPart))
    A(P('<font size="15" color="#5b6b7a">User guide</font>', S('x2', leading=22)))
    A(Spacer(1, 6))
    A(P('Installation, configuration, operation and maintenance of the rele-esp12f module.', sBodyL))
    A(PageBreak())

    # ---- 8. Safety
    A(Paragraph('8. Safety', sH1))
    A(callout('danger', 'DANGER — Mains voltage: risk of death by electric shock', [
        'Installation must be carried out by a qualified person, in accordance with local electrical regulations.',
        'Switch off the supply at the panel and verify the absence of voltage before touching the board or the wiring.',
        'With mains connected, the whole left half of the board (J1, F1, RV1, PS1, K1 contacts) is at mains potential. Do not touch the board while it is operating.',
        'The board must always be installed inside an <b>insulating</b> enclosure that prevents contact with any part of it.',
        'Never connect the USB-serial adapter to J3 while the board is connected to mains.']))
    A(callout('caution', 'CAUTION — Intended use', [
        'For 110–120 VAC mains only. At 230 VAC varistor RV1 conducts and is destroyed (and F1 opens). For 230 V, RV1 must be replaced with a 07D471K and the design reviewed.',
        'Maximum load 10 A resistive; less for other load types (§2.4). Protect the line upstream with a circuit breaker or fuse of 10 A maximum.',
        'The relay only interrupts the line conductor. With the relay open, the load remains connected to neutral: to work on the load, switch off at the panel.',
        'Do not use in safety applications, medical equipment, systems whose failure could harm people, or outdoors without a suitable enclosure.',
        'The assembly is not certified. Its use is the responsibility of the installer.']))
    A(Paragraph('8.1 Board symbols and labels', sH2))
    A(table([
        ['Silkscreen label', 'Meaning'],
        ['DANGER: 110 VAC', 'Marks the mains zone.'],
        ['N · OUT · L (next to J1)', 'Neutral, switched output, input line.'],
        ['IO0 TX GND / RST RX 5V (next to J3)', 'Programming header pinout.'],
        ['rele-esp12f v3', 'Hardware revision identifier.'],
    ], [4, 8]))

    # ---- 9. Required material
    A(Paragraph('9. Required material', sH1))
    A(table([
        ['For', 'Material'],
        ['First flashing', 'USB-serial adapter with <b>3.3 V</b> logic and a 5 V output (CH340, CP2102, FT232…); 5 female dupont wires; PC with esptool (Python) or the Tasmota/ESPHome web flasher.'],
        ['Installation', 'Insulating enclosure; 2 nylon M2 screws, or metal ones with a washer ≤ Ø5 mm, and standoffs; 1.5 mm² copper wire (or the size required by the installation); ferrules for stranded wire; 3 mm flat screwdriver; voltage tester.'],
        ['Line protection', 'Circuit breaker (or fuse) of 10 A maximum, dedicated or shared with the load.'],
    ], [2.6, 10]))
    A(PageBreak())

    # ---- 10. First flashing
    A(Paragraph('10. First firmware flashing', sH1))
    A(P('The board ships <b>without application firmware</b>: the project repository does not include any. '
        'The first flashing is done through J3; later ones over Wi-Fi (OTA). This section describes the wiring '
        'and two common firmwares. The example configurations are derived from the pin assignment (§4.3) and '
        '<b>have not been tested on a physical board</b>.'))
    A(Paragraph('10.1 Adapter connection', sH2))
    A(table([
        ['USB-serial adapter', '→', 'Board J3'],
        ['GND', '→', 'pin 1 · GND (square pad)'],
        ['5 V (VBUS)', '→', 'pin 2 · 5V'],
        ['TX', '→', 'pin 4 · RX'],
        ['RX', '→', 'pin 3 · TX'],
        ['(optional) GND on a separate wire', '→', 'pin 5 · IO0, instead of pressing SW1'],
    ], [5, 0.6, 6]))
    A(P('<b>Why 5 V and not 3.3 V.</b> The 3.3 V pin of a typical adapter supplies on the order of 50–100 mA, '
        'while the ESP8266 draws peaks of several hundred mA when calibrating the radio: flashing that way causes '
        'resets. With the USB 5 V (up to 500 mA) the board runs as in service, through its own regulator. Besides, '
        'feeding 3.3 V into the AMS1117 output would forward-bias its internal diode and load the whole 5 V rail.'))
    A(Paragraph('10.2 Entering flashing mode', sH2))
    E(steps([
        'With the board <b>disconnected from mains</b>, wire the adapter as in the table above and plug it into the PC.',
        'Press and hold <b>SW1</b> (IO0).',
        'Press and release <b>SW2</b> (RST).',
        'Release SW1. The ESP8266 now waits for data on the UART. The red LED stays off and the relay does not move.',
    ]))
    A(Paragraph('10.3 Flashing with esptool', sH2))
    A(code('''
pip install esptool
esptool.py --chip esp8266 --port COM5 --baud 115200 flash_id          # check connection and flash size
esptool.py --chip esp8266 --port COM5 --baud 115200 erase_flash       # repeat steps 2-4 first
esptool.py --chip esp8266 --port COM5 --baud 460800 write_flash -fm dout 0x0 firmware.bin
'''))
    A(P('Replace <font face="Mono">COM5</font> with the adapter port (on Linux, <font face="Mono">/dev/ttyUSB0</font>). '
        'Flashing mode must be entered again (steps 2–4) before each command, because this header has no '
        'DTR/RTS auto-reset circuit. When done, press SW2 to start the firmware.'))
    A(Paragraph('10.4 Option A: Tasmota', sH2))
    A(P('Flash <font face="Mono">tasmota.bin</font> (generic ESP8266 build) and apply this template under '
        '<i>Configuration → Configure Other → Template</i>, ticking <i>Activate</i>:'))
    A(code('{"NAME":"rele-esp12f","GPIO":[32,0,0,0,544,224,0,0,0,0,0,0,0,0],"FLAG":0,"BASE":18}'))
    A(table([
        ['Position', 'GPIO', 'Code', 'Tasmota function'],
        ['1', 'GPIO0', '32', 'Button1 (SW1)'],
        ['5', 'GPIO4', '544', 'LedLink (D3, shows Wi-Fi/MQTT connection)'],
        ['6', 'GPIO5', '224', 'Relay1 (K1 and D2)'],
        ['others', '—', '0', 'Unused (GPIO1/3 remain the UART for logging)'],
    ], [1.3, 1.3, 1.3, 8]))
    A(P('Recommended console settings: <font face="Mono">PowerOnState 0</font> (relay open after a power '
        'outage) or <font face="Mono">PowerOnState 3</font> (restore the last state), and <font face="Mono">SetOption1 1</font> '
        'so that a long press on SW1 does not trigger an accidental factory reset. Check the codes against the '
        'documentation of the Tasmota version used.', sBody))
    A(Paragraph('10.5 Option B: ESPHome', sH2))
    A(code('''
esphome:
  name: rele-esp12f
esp8266:
  board: esp12e                 # ESP-12F: same pinout and 4 MB flash
  restore_from_flash: true
wifi:
  ssid: !secret wifi_ssid
  password: !secret wifi_password
  ap: {}                        # fallback access point if it cannot connect
captive_portal:
logger:
api:
ota:
  - platform: esphome
status_led:
  pin: GPIO4                    # D3, active high
switch:
  - platform: gpio
    id: relay
    name: "Relay"
    pin: GPIO5                  # Q1 -> K1, and LED D2
    restore_mode: RESTORE_DEFAULT_OFF
binary_sensor:
  - platform: gpio
    name: "Button SW1"
    pin:
      number: GPIO0
      inverted: true            # active low, external pull-up R3
    filters:
      - delayed_on: 30ms        # debounce
    on_press:
      - switch.toggle: relay
'''))
    A(callout('note', 'Custom firmware (Arduino / PlatformIO)', [
        'Board: "Generic ESP8266 Module" or "NodeMCU 1.0 (ESP-12E)"; 4 MB flash, DOUT or DIO mode.',
        'Configure GPIO5 as an output and write LOW first thing in <font face="Mono">setup()</font>.',
        'Read GPIO0 as a debounced input. Do not use GPIO6–11, and do not turn GPIO15/GPIO2 into outputs that could be left at the wrong level on reset.',
        'Include OTA updates from the first version: once the board is installed, J3 can no longer be used.']))
    A(PageBreak())

    # ---- 11. Installation
    A(Paragraph('11. Installation', sH1))
    A(Paragraph('11.1 Wiring diagram', sH2))
    A(fig(wiring_diagram(), 'Figure 6. Typical wiring. The relay interrupts the line conductor to the load; the neutral is shared. '
          'The protective earth (PE) goes directly to the load.'))
    A(Paragraph('11.2 Mechanical mounting', sH2))
    E(bullets([
        'Choose a <b>plastic</b> (non-metallic) enclosure with an IP rating suited to the location and enough inner space for the board (66.5 × 49 × ≈ 20 mm) plus the wiring and its bend radius.',
        'Fix the board through holes MH1 and MH2 (M2) with standoffs of ≥ 3 mm so the THT leads do not touch the bottom. Do not pass screws through the board anywhere else.',
        'Use screws with a head or washer of Ø ≤ 5 mm: this is the trace-free diameter around each hole.',
        'Keep the antenna area (top-right corner, Figure 3) free of metal and wiring. If the enclosure goes inside a metal box, the Wi-Fi range will drop significantly.',
        'Keep the mains wiring physically away from J3 and the ESP-12F; if needed, secure it to the enclosure with cable ties.',
        'Provide passive ventilation if the load approaches 10 A: the power traces, the relay and the terminal block heat up.',
    ]))
    A(Paragraph('11.3 Electrical connection', sH2))
    E(steps([
        'Switch off the circuit at the panel and <b>verify the absence of voltage</b> with a suitable tester.',
        'Strip 6–7 mm of each conductor (or crimp ferrules on stranded wire) [E: verify with the terminal block datasheet].',
        'Connect the <b>line</b> coming from the circuit breaker to <b>L</b> (J1-3).',
        'Connect the <b>neutral</b> to <b>N</b> (J1-1). If the load shares the neutral, join it off-board with a splice connector; J1 accepts a single conductor per pole [E].',
        'Connect the line wire going to the load to <b>OUT</b> (J1-2). The other load pole goes to neutral; earth goes directly to the load.',
        'Tighten the J1 screws firmly (≈ 0.4–0.5 N·m, typical for 5.08 mm terminal blocks; check the KANGNEX datasheet [F]). Gently pull each wire to verify it.',
        'Check there are no loose strands or exposed copper outside the terminal block, and close the enclosure before applying power.',
    ]))
    A(Paragraph('11.4 Pre-commissioning checks', sH2))
    A(table([
        ['#', 'Check', 'Correct if…'],
        ['1', 'Firmware flashed and tested while powered from J3 (no mains)', 'The blue LED shows the connection and the relay switches with SW1 / over Wi-Fi.'],
        ['2', 'J3 disconnected and free of wires', 'Nothing remains connected to the programming header.'],
        ['3', 'J1 polarity', 'L on the pole labeled "L", N on "N", load on "OUT".'],
        ['4', 'Upstream protection', 'Circuit breaker or fuse ≤ 10 A on the line.'],
        ['5', 'Enclosure closed', 'No part of the board is accessible.'],
        ['6', 'Power-up', 'After 1–3 s the firmware boots; the relay stays open unless the firmware restores a "closed" state.'],
    ], [0.5, 5, 7]))
    A(PageBreak())

    # ---- 12. Configuration
    A(Paragraph('12. Configuration', sH1))
    A(P('The steps depend on the firmware. This is the general sequence with Tasmota and ESPHome:'))
    A(Paragraph('12.1 Connecting to the Wi-Fi network', sH2))
    A(table([
        ['Step', 'Tasmota', 'ESPHome'],
        ['First boot', 'Creates the access point <font face="Mono">tasmota-XXXXXX</font>.', 'If the credentials in <font face="Mono">secrets.yaml</font> fail, it creates the fallback AP.'],
        ['Configure Wi-Fi', 'Join the AP, open 192.168.4.1 and enter SSID and password (2.4 GHz only).', 'Credentials are compiled in; with the fallback AP, captive portal at 192.168.4.1.'],
        ['Find the IP address', 'From the router, or from the serial console during flashing.', 'Home Assistant discovers it automatically (ESPHome integration).'],
        ['Integration', 'MQTT (Configuration → MQTT) or the Home Assistant Tasmota integration.', 'Native Home Assistant API.'],
    ], [2.2, 5.2, 5.2]))
    A(Paragraph('12.2 Recommended settings', sH2))
    E(bullets([
        '<b>State after a power outage</b>: explicitly choose "off" or "last state" depending on the load. For heaters or loads that must not start on their own, use "off".',
        '<b>Web UI and OTA password</b>: always set one. Otherwise anyone on the local network could switch the load or upload other firmware.',
        '<b>Wi-Fi network</b>: the ESP8266 only works on 2.4 GHz and with WPA2 (not WPA3-only). If the router merges bands under the same name, the 2.4 GHz band may need to be split out.',
        '<b>Limit switching</b>: avoid automations that switch the relay many times per minute; the electrical life of the contact is finite (§14.2).',
        '<b>Time (NTP) and time zone</b>, if timers are used.',
    ]))
    A(Paragraph('12.3 OTA updates', sH2))
    A(P('Tasmota: <i>Firmware Upgrade</i> from the web UI, with a <font face="Mono">.bin</font> or '
        '<font face="Mono">.bin.gz</font> file. ESPHome: <font face="Mono">esphome run rele-esp12f.yaml</font>, which '
        'compiles and uploads over the network. With 4 MB of flash there is room for two-stage updates. If an '
        'update fails and the module does not boot, the only option left is flashing through J3, removing the board '
        'from the installation (§10).'))

    # ---- 13. Operation
    A(Paragraph('13. Operation', sH1))
    A(Paragraph('13.1 Indicators', sH2))
    A(table([
        ['Indicator', 'State', 'Meaning'],
        ['Red LED (D2)', 'On', 'The firmware commands the relay to close (GPIO5 high). It is wired in parallel with the driver, so it reflects the command, not the mechanical position of the contact.'],
        ['Red LED (D2)', 'Off', 'Relay open; also during boot and flashing.'],
        ['Blue LED (D3)', 'Firmware-defined', 'Tasmota (LedLink): blinks while looking for Wi-Fi/MQTT, off once connected (configurable with LedState). ESPHome (status_led): blinks on error or warning, off when all is well.'],
        ['Audible click', 'When switching', 'K1 contact closing or opening. If the red LED changes without a click, see §15.'],
    ], [2.2, 2, 8.4]))
    A(Paragraph('13.2 Push buttons', sH2))
    A(table([
        ['Button', 'Action', 'Result'],
        ['SW1', 'Short press in service', 'Toggles the relay (if the firmware implements it; it does in the configurations of §10).'],
        ['SW1', 'Held at boot or while pressing SW2', 'Flashing mode: the firmware does not start. Release and press SW2 to return to normal mode.'],
        ['SW1', '40 s press (Tasmota)', 'Restores the Tasmota factory settings (unless SetOption1 1).'],
        ['SW2', 'Press', 'Restarts the module. The relay opens during the restart and returns to the state defined by the firmware.'],
    ], [1.6, 4, 7]))
    A(callout('caution', 'The push buttons are on the board', 'SW1 and SW2 are only reachable with the enclosure open, '
              'that is, next to parts at mains potential. Use them only with the board disconnected from mains (powered '
              'from J3), or add an external button on the enclosure wired with adequate insulation.'))
    A(Paragraph('13.3 Behavior on events', sH2))
    A(table([
        ['Event', 'Board behavior'],
        ['Power-up / mains restored', 'Relay open for ≈ 0.1–1 s until the firmware starts (R7 keeps Q1 off); then the configured state.'],
        ['Wi-Fi loss', 'The relay keeps its state. Local control (SW1) and internal timers keep working if the firmware allows it.'],
        ['Power outage', 'The relay opens (no coil supply). The load is de-energized.'],
        ['Transient overvoltage', 'RV1 clips the peaks at the PS1 input. It does not protect the load: use a surge protector at the panel for that.'],
        ['Sustained overvoltage (e.g. 230 V)', 'RV1 conducts, F1 opens and the board stops working. Requires repair (§14.4).'],
        ['Short circuit in the load', 'Must be cleared by the upstream circuit breaker. The K1 contact may be damaged or welded: inspect it (§15).'],
    ], [3.4, 9.2]))
    A(PageBreak())

    # ---- 14. Maintenance
    A(Paragraph('14. Maintenance', sH1))
    A(callout('danger', 'Before any intervention', 'Switch off the supply at the panel and verify the absence of voltage. '
              'No maintenance task is performed with the board energized.'))
    A(Paragraph('14.1 Inspection schedule', sH2))
    A(table([
        ['When', 'Task', 'What to look for'],
        ['One month after installation', 'Re-tighten the J1 screws', 'Copper settles after the first thermal cycles and the connection loosens.'],
        ['Every 12 months', 'Visual inspection with the enclosure open and de-energized', 'Discoloration or charring at J1, around K1 or on the power traces; RV1 bulged, cracked or blackened; C1 bulged; burning smell.'],
        ['Every 12 months', 'Functional test', 'Switching from the app and with SW1; audible click; the load turns on and off.'],
        ['Every 12 months', 'Firmware', 'Apply firmware security updates over OTA.'],
        ['After a storm or surge', 'RV1 inspection and functional test', 'A varistor that has absorbed strong surges degrades; if damaged, repair it (§14.4).'],
        ['If the load runs close to 10 A', 'Check every 6 months', 'Terminal block and relay temperature; if possible, thermography with the load connected (from outside the enclosure).'],
    ], [2.6, 3.6, 6.4]))
    A(Paragraph('14.2 Relay service life', sH2))
    A(P('Omron guarantees a minimum of <b>50,000 operations</b> at 16 A resistive and 250 VAC [D]. At lower '
        'currents the life is longer (endurance curve in the datasheet). As a conservative reference:'))
    A(table([
        ['Operations per day', 'Estimated minimum life at full load [C]'],
        ['10', '≈ 13.7 years'],
        ['20', '≈ 6.8 years'],
        ['50', '≈ 2.7 years'],
        ['200 (aggressive automation)', '≈ 8 months'],
    ], [5, 7]))
    A(P('End-of-life symptoms: the load does not turn off (welded contact), does not turn on or flickers (burnt '
        'contact), or there is abnormal heating around K1. In those cases, replace the relay or the board.', sBody))
    A(Paragraph('14.3 Cleaning', sH2))
    A(P('De-energized, with dry air or an antistatic brush. Do not use water or solvents, and do not apply '
        'conformal coating on the relay or the terminal block. If moisture has entered or there is condensation in '
        'the enclosure, keep the board out of service until it is completely dry and check the enclosure sealing.'))
    A(Paragraph('14.4 Repairs', sH2))
    E(bullets([
        '<b>F1 is not a user-replaceable fuse</b>: it is soldered. If it opens, the cause is usually an overvoltage (RV1) or a PS1 fault. Diagnose it before replacing the fuse, always with the same type: T500 mA 250 V, time-lag (Reomax MTS0500A or an equivalent with the same footprint).',
        'RV1, K1 and PS1 are THT and can be replaced with a soldering iron and a desoldering tool. Use exactly the BOM part numbers (§6): a relay without the "-E" variant or a different supply changes the current rating or the isolation.',
        'After any repair in the mains zone, make sure no solder residue or wire strands reduce the isolation distances, and repeat the checks of §11.4.',
    ]))
    A(PageBreak())

    # ---- 15. Troubleshooting
    A(Paragraph('15. Troubleshooting', sH1))
    A(P('For any measurement with the board open, power it from J3 with the USB adapter (5 V) and <b>with no '
        'mains on J1</b>. This allows checking the whole SELV section safely. Faults in the mains zone must be '
        'diagnosed de-energized (continuity, resistance) or by a qualified technician.'))
    A(table([
        ['Symptom', 'Probable cause', 'Check / solution'],
        ['With mains: no LED, not visible on the Wi-Fi network', 'F1 open, PS1 faulty, terminal block badly wired or no firmware.', 'Without mains, power from J3: if it works, the fault is in the mains zone (F1, RV1, PS1). Check F1 continuity de-energized.'],
        ['Firmware does not start; the serial console shows "boot mode:(1,x)"', 'GPIO0 low at boot.', 'SW1 stuck or IO0 wire to GND on J3. Release it and press SW2.'],
        ['esptool does not connect ("Failed to connect")', 'Not in flashing mode; TX/RX not crossed; port or drivers.', 'Repeat §10.2; cross TX↔RX; try 115,200 bit/s; check the COM port.'],
        ['Resets when Wi-Fi connects or the relay switches', 'Insufficient supply.', 'Via J3: use the adapter 5 V, not 3.3 V, and a short USB cable. With mains: check C1/C9 and the PS1 output.'],
        ['Red LED changes but there is no click and no switching', 'Q1, D1 or K1 coil faulty; low 5 V.', 'Measure 5 V between J3-2 and J3-1 (powered from J3). With GPIO5 high, the Q1 collector must be < 0.3 V.'],
        ['Click heard but the load gets no voltage', 'OUT/N wiring, breaker open, burnt contact.', 'De-energized, check L↔OUT continuity with the relay closed (powered from J3).'],
        ['The load never turns off', 'K1 contact welded (inrush or short circuit).', 'De-energized: L↔OUT continuity with the relay at rest. If there is continuity, replace K1 and check the load.'],
        ['Switches but the red LED does not light', 'D2 or R8 faulty or badly soldered.', 'No functional impact. Check D2/R8.'],
        ['Weak Wi-Fi or disconnections', 'Metal enclosure, covered antenna, distance, router on 5 GHz.', 'Relocate the enclosure; clear the antenna area; 2.4 GHz network; repeater.'],
        ['Hot terminal block or enclosure', 'Loose screw, undersized wire, load > 10 A.', 'Re-tighten, 1.5 mm² wire, reduce the load. If there is discoloration, replace the board.'],
        ['Does not work after a storm', 'RV1 and F1 damaged by overvoltage.', 'Visual inspection of RV1; repair per §14.4.'],
    ], [3.4, 3.6, 5.6]))
    A(PageBreak())

    # ======================= APPENDICES
    A(Paragraph('Appendix A. Design calculations', sH1))
    A(Paragraph('A.1 Power budget', sH2))
    A(table([
        ['Consumer', 'Rail', 'Typical', 'Worst case', 'Source'],
        ['ESP8266EX (average / 802.11b TX)', '3.3 V → 5 V via U1', '80 mA', '170 mA', '[D]'],
        ['LED D3', '3.3 V', '≈ 2 mA', '≈ 3 mA', '[E]'],
        ['LED D2 + Q1 base', '3.3 V', '3.9 mA', '3.9 mA', '[C]'],
        ['Dividers and pull-ups (R1–R5, R7)', '3.3 V', '< 0.5 mA', '< 1 mA', '[C]'],
        ['K1 coil', '5 V', '80 mA', '88 mA (−10 % R)', '[D]'],
        ['<b>Total on 5 V</b>', '', '<b>≈ 166 mA</b>', '<b>≈ 266 mA</b>', '[C]'],
        ['Margin on PS1 (600 mA)', '', '72 %', '56 %', '[C]'],
    ], [4.6, 2.8, 1.6, 2.2, 1.2]))
    A(P('The radio calibration peaks at boot (hundreds of mA for milliseconds) are covered by C1, C4 and C9. '
        'Power drawn from mains, assuming a PS1 efficiency of 70 % [E], is ≈ 0.6 W with the relay open '
        '(≈ 86 mA × 5 V / 0.7) and ≈ 1.2 W with the relay closed (≈ 166 mA × 5 V / 0.7).'))
    A(Paragraph('A.2 Regulator U1', sH2))
    A(code('''
P_U1 (average) = (5.0 - 3.3) V x 0.080 A  = 0.136 W   ->  dTj = 0.136 x 90 C/W ~ 12 C
P_U1 (peak)    = (5.0 - 3.3) V x 0.170 A  = 0.289 W   ->  dTj = 0.289 x 90 C/W ~ 26 C
Dropout margin: 5.0 - 3.3 = 1.7 V  >  1.1 V typ. (0.8 A) / 1.3 V max.
'''))
    A(Paragraph('A.3 Relay driver', sH2))
    A(code('''
I_coil   = 5 V / 62.5 ohm                        = 80 mA
I_B      = (V_OH - V_BE)/R6 - V_BE/R7
         = (2.64 - 0.75)/1000 - 0.75/10000       = 1.82 mA   (minimum V_OH = 0.8 x 3.3 V)
beta_forced = 80 / 1.82                           ~ 44       (saturation guaranteed)
V_coil   = 5.0 - V_CE(sat) (~0.2 V)               ~ 4.8 V   >  3.5 V (70 %, must operate)
V_collector at turn-off = 5.0 + V_F(D1) (~0.7 V)  ~ 5.7 V
'''))
    A(Paragraph('A.4 EN and RST delay', sH2))
    A(code('''
tau = R1 x C7 = 10 kohm x 100 nF = 1 ms
t(V = 0.75 x 3.3 V) = -tau x ln(1 - 0.75) = 1.39 ms
'''))
    A(Paragraph('A.5 Power trace capacity (IPC-2221, external layer)', sH2))
    A(code('''
I = k x dT^0.44 x A^0.725      k = 0.048 (external), A in mil^2, dT in C
2.5 mm x 35 um trace  ->  A = 98.4 mil x 1.38 mil = 136 mil^2
dT = 20 C:  I(1 trace) ~ 6.3 A    I(2 traces, F.Cu + B.Cu) ~ 12 A
I = 10 A over 2 traces (5 A each):  dT ~ 12 C
'''))
    A(Paragraph('A.6 Relay life', sH2))
    A(code('''
Life (years) = 50,000 operations / (operations_per_day x 365)
20 operations/day -> 50,000 / 7,300 = 6.8 years   (guaranteed minimum at 16 A resistive)
'''))

    A(Paragraph('Appendix B. References', sH1))
    A(table([
        ['Document', 'Location'],
        ['Omron G5RL PCB Power Relay, Cat. No. K132-E1-10', 'docs/datasheets/omron_g5rl.pdf'],
        ['AMS1117 1A Low Dropout Voltage Regulator', 'docs/datasheets/ams1117.pdf'],
        ['ESP8266EX Datasheet (2025.11, NRND)', 'docs/datasheets/0a-esp8266ex_datasheet_en.pdf'],
        ['ESP8266 Hardware Design Guidelines', 'docs/datasheets/esp8266_hardware_design_guidelines_en.pdf'],
        ['ESP-WROOM-02 Datasheet (module design reference)', 'docs/datasheets/esp-wroom-02_datasheet_en.pdf'],
        ['Hi-Link HLK-PM01 (not included)', 'Manufacturer datasheet; LCSC C209903'],
        ['Schematic and layout', 'rele-esp12f.kicad_sch / rele-esp12f.kicad_pcb (KiCad 10)'],
        ['Manufacturing files', 'fabrication/ (BOM, CPL, gerbers, ZIP for JLCPCB)'],
        ['IPC-2221B, Generic Standard on Printed Board Design', 'Trace current capacity'],
    ], [6, 6.6]))

    A(Paragraph('Appendix C. Known open points', sH1))
    A(P('Items identified while preparing this document. None prevents manufacturing the board.'))
    A(table([
        ['#', 'Where', 'Open point', 'Approach taken here'],
        ['1', 'docs/datasheets', 'The datasheets for HLK-PM01, KANGNEX WJ500V, 07D221K, SS8050 and Reomax MTS are missing.', 'Their values are tagged [F].'],
        ['2', 'Espressif', 'The ESP8266EX is listed as NRND.', 'Warning in §1.4.'],
        ['3', 'Firmware', 'The repository does not contain firmware.', 'Third-party firmwares are described (§10) with untested configurations.'],
    ], [0.5, 2.4, 6, 3.7]))

    A(Paragraph('Appendix D. Revision history', sH1))
    A(table([
        ['Revision', 'Date', 'Changes'],
        ['Hardware v1', '2026-09-25', '66 × 66 mm board with SRD-05VDC-SL-C relay.'],
        ['Hardware v2', '2026-09-30', '66.5 × 44 mm board, 110 VAC; new layout, 2×3 J3, GND planes with an isolation polygon, single-sided assembly.'],
        ['Hardware v3', '2026-10-03', 'Omron G5RL-1A-E-HR relay (16 A, reinforced insulation); 66.5 × 49 mm board; C7/C8 delay on EN/RST; C9 10 µF next to the ESP-12F; J3 powered at 5 V; L_IN/L_OUT duplicated on both sides (10 A); mains copper ≥ 2 mm from the edge; adjusted J1/RV1 drills; full assembly at JLCPCB.'],
        ['Document rev. A', '2026-10-03', 'First edition of the datasheet and user guide (Spanish).'],
        ['Document rev. B', DOC_DATE, 'English edition; silkscreen and schematic labels updated to English.'],
    ], [2.2, 1.8, 8.6]))
    return st


def main():
    with tempfile.TemporaryDirectory() as tmp:
        a = build_assets(tmp)
        doc = Doc(OUT, pagesize=A4, title='rele-esp12f — Datasheet and user guide',
                  author='@techmigue', subject='ESP-12F Wi-Fi relay module 110–120 VAC, hardware v3',
                  creator='scripts/generate_datasheet.py (ReportLab)',
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
        # A heading followed by an unbreakable block (figure, code) must not be orphaned
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
