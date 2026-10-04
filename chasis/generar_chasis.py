# -*- coding: utf-8 -*-
"""Chasis imprimible en 3D para la placa rele-esp12f (66,5 x 49 mm, 1,6 mm).

Se ejecuta dentro de FreeCAD (consola Python):
    exec(open(r"<ruta>/chasis/generar_chasis.py", encoding="utf-8").read())

Sistema de coordenadas = el del STEP exportado con
    kicad-cli pcb export step --subst-models --user-origin 100x149mm
es decir, esquina inferior izquierda del PCB en (0, 0), X a lo largo de 66,5 mm,
Y a lo largo de 49 mm (Y_kicad = 149 - Y). Cara inferior del PCB en Z = Z_PCB.

Piezas generadas:
  Base     caja con suelo, soportes del PCB, columnas para los tornillos de la tapa,
           entrada de cables de J1, alivio de tracción y orejetas de fijación.
  Tapa     con faldón de centrado, pisadores del PCB y guías de luz de los LED.
SW1/SW2 son solo de depuración: quedan dentro, accesibles con la tapa quitada.
"""
import os
import FreeCAD as App
import Part
from FreeCAD import Vector as V

OUT = r"B:/embedded_ai_systems/smartRele/rele-esp12f_v2/rele-esp12f/chasis"
FONT_DIR, FONT = "C:/Windows/Fonts/", "arialbd.ttf"

# ---------------------------------------------------------------- parámetros
PCB_W, PCB_H, PCB_T = 66.5, 49.0, 1.6
CL = 0.3            # holgura PCB-pared
W = 2.4             # espesor de pared
FLOOR = 2.0         # espesor de suelo
STAND = 5.0         # PCB sobre el suelo (patillas THT asoman 3,3 mm por debajo)
Z_PCB = FLOOR + STAND          # cara inferior del PCB
Z_TOP = Z_PCB + PCB_T          # cara superior del PCB
Z_LID = 26.0        # cara inferior de la tapa (K1 llega a 24,3: 1,7 mm de aire)
LT = 2.5            # espesor de la tapa
LEDGE = 1.5         # anchura de la repisa perimetral de apoyo
FIT = 0.25          # holgura faldón-pared

cx0, cy0 = -CL, -CL
cx1, cy1 = PCB_W + CL, PCB_H + CL
ox0, oy0 = cx0 - W, cy0 - W
ox1, oy1 = cx1 + W, cy1 + W

# Columnas de los tornillos de la tapa (M3 autorroscante): fuera del contorno del PCB,
# a 0,64 mm de sus esquinas redondeadas (r = 2 mm).
BOSS_R, BOSS_PILOT, BOSS_DEPTH = 3.3, 2.5, 12.0
BOSSES = [(-2.2, -2.2), (PCB_W + 2.2, -2.2), (-2.2, PCB_H + 2.2), (PCB_W + 2.2, PCB_H + 2.2)]

# Taladros M2 del PCB (MH1, MH2) y pilares de apoyo bajo los pulsadores
MH = [(51.2, 8.4), (63.9, 2.6)]
SUPPORTS = [(61.0, 23.8), (57.2, 3.0)]    # pilares bajo SW1/SW2 (apoyo central del PCB)
LED = [(55.3, 25.0), (48.0, 4.7)]         # D2 (relé), D3 (WiFi)
LED_TOP = Z_PCB + 2.7

# Borna J1: entradas de cable (centro medido en el modelo 3D: 5,1 mm sobre la cara
# inferior del PCB, hueco de 2,8 x 3,0 mm)
J1_X = [3.34, 8.42, 13.50]
J1_Z = Z_PCB + 5.1
WIRE_D = 3.8


# ---------------------------------------------------------------- utilidades
def box(x0, x1, y0, y1, z0, z1):
    return Part.makeBox(x1 - x0, y1 - y0, z1 - z0, V(x0, y0, z0))


def cyl(x, y, r, z0, z1, d=V(0, 0, 1)):
    return Part.makeCylinder(r, z1 - z0, V(x, y, z0), d)


def cone(x, y, r0, r1, z0, z1):
    return Part.makeCone(r0, r1, z1 - z0, V(x, y, z0))


def fuse(shapes):
    s = shapes[0]
    for t in shapes[1:]:
        s = s.fuse(t)
    return s


def outline(z0, z1, fillet=1.0):
    """Contorno exterior: rectángulo + columnas de esquina."""
    b = box(ox0, ox1, oy0, oy1, z0, z1)
    vert = [e for e in b.Edges if abs(e.Vertexes[0].Z - e.Vertexes[1].Z) > 1e-6]
    b = b.makeFillet(fillet, vert)
    return fuse([b] + [cyl(x, y, BOSS_R, z0, z1) for x, y in BOSSES])


def text_solid(txt, size, depth):
    wires = Part.makeWireString(txt, FONT_DIR, FONT, size, 0)
    faces = []
    for ch in wires:
        if ch:
            faces.append(Part.makeFace(ch, "Part::FaceMakerBullseye"))
    comp = Part.Compound(faces)
    return comp.extrude(V(0, 0, depth)), comp.BoundBox


def text_top(txt, size, cx, cy, ztop, depth=0.6, align="center"):
    """Texto grabado en una cara horizontal superior. (cx, cy) es el centro, o el
    extremo derecho centrado en altura si align == "right"."""
    s, bb = text_solid(txt, size, depth + 0.2)
    x0 = cx - bb.XMax if align == "right" else cx - (bb.XMin + bb.XMax) / 2
    s.translate(V(x0, cy - (bb.YMin + bb.YMax) / 2, ztop - depth))
    return s


def text_front(txt, size, cx, cz, yface, depth=0.5):
    """Texto grabado en la cara frontal (normal -Y), legible desde delante."""
    s, bb = text_solid(txt, size, depth + 0.2)
    s.translate(V(-(bb.XMin + bb.XMax) / 2, -(bb.YMin + bb.YMax) / 2, -(depth + 0.2)))
    s.rotate(V(0, 0, 0), V(1, 0, 0), 90)       # x->x, y->z, z->-y  => Y en [0, depth+0.2]
    s.translate(V(cx, yface - 0.2, cz))        # de 0,2 mm fuera a 'depth' dentro de la pared
    return s


# ---------------------------------------------------------------- BASE
def make_base():
    shell = outline(0, Z_LID)
    cavity = box(cx0, cx1, cy0, cy1, FLOOR, Z_LID + 1)
    base = shell.cut(cavity)

    adds = []
    # columnas completas (se pierden al vaciar la cavidad)
    adds += [cyl(x, y, BOSS_R, 0, Z_LID) for x, y in BOSSES]
    # repisa perimetral: el PCB apoya 1,2 mm de su borde
    ring = box(cx0, cx1, cy0, cy1, FLOOR, Z_PCB).cut(
        box(cx0 + LEDGE, cx1 - LEDGE, cy0 + LEDGE, cy1 - LEDGE, FLOOR - 1, Z_PCB + 1))
    adds.append(ring)
    # torretas M2 en MH1/MH2 y pilares de apoyo bajo SW1/SW2 (se pueden pulsar con la
    # tapa quitada sin flexionar la placa)
    adds += [cyl(x, y, 2.75, FLOOR - 0.1, Z_PCB) for x, y in MH]
    adds += [cyl(x, y, 2.0, FLOOR - 0.1, Z_PCB) for x, y in SUPPORTS]
    # orejetas de fijación en los extremos (tornillo Ø4)
    ym = PCB_H / 2
    for side in (-1, 1):
        xe = ox0 if side < 0 else ox1
        tab = box(min(xe, xe + side * 9), max(xe, xe + side * 9), ym - 6, ym + 6, 0, 3)
        tab = tab.fuse(cyl(xe + side * 9, ym, 6, 0, 3))
        tab = tab.cut(cyl(xe + side * 9, ym, 2.2, -1, 4))
        adds.append(tab)
        # nervios de refuerzo de la orejeta (cartabones triangulares contra la pared)
        for dy in (-5.6, 4.4):
            pts = [V(xe, ym + dy, 3), V(xe + side * 4, ym + dy, 3), V(xe, ym + dy, 7), V(xe, ym + dy, 3)]
            adds.append(Part.Face(Part.makePolygon(pts)).extrude(V(0, 1.2, 0)))
    # delantal de alivio de tracción frente a J1
    apron = box(ox0, 20.0, oy0 - 13, oy0 + 0.1, 0, 3)
    adds.append(apron)
    # topes laterales del delantal (guían los cables)
    adds.append(box(ox0, ox0 + 2.0, oy0 - 13, oy0, 3, 6))
    adds.append(box(18.0, 20.0, oy0 - 13, oy0, 3, 6))
    base = fuse([base] + adds)

    cuts = []
    # pilotos M3 en las columnas
    cuts += [cyl(x, y, BOSS_PILOT / 2, Z_LID - BOSS_DEPTH, Z_LID + 1) for x, y in BOSSES]
    cuts += [cone(x, y, BOSS_PILOT / 2, BOSS_PILOT / 2 + 0.6, Z_LID - 0.6, Z_LID + 0.01)
             for x, y in BOSSES]
    # pilotos M2 en las torretas
    cuts += [cyl(x, y, 0.85, Z_PCB - 6, Z_PCB + 1) for x, y in MH]
    # entradas de cable de J1 (con avellanado exterior)
    for x in J1_X:
        cuts.append(Part.makeCylinder(WIRE_D / 2, W + 2, V(x, oy0 - 1, J1_Z), V(0, 1, 0)))
        cuts.append(Part.makeCone(WIRE_D / 2 + 0.8, WIRE_D / 2, 0.8, V(x, oy0 - 0.01, J1_Z), V(0, 1, 0)))
    # ranuras para brida (alivio de tracción) en el delantal
    for x in (ox0 + 3.2, 16.8):
        cuts.append(box(x - 1.0, x + 1.0, oy0 - 10.5, oy0 - 6.0, -1, 4))
    # ventilación: entrada baja al frente (bajo el relé), salida alta detrás (sobre PS1).
    # Ranuras de 1,5 mm: no deja pasar un dedo ni una sonda de 2,5 mm.
    for i in range(6):
        x = 25.0 + i * 3.5
        cuts.append(box(x, x + 1.5, oy0 - 1, cy0 + 0.1, FLOOR + 1.0, Z_PCB - 0.6))
    for i in range(8):
        x = 6.0 + i * 3.5
        cuts.append(box(x, x + 1.5, cy1 - 0.1, oy1 + 1, 15.0, 23.0))
    for i in range(5):
        y = 31.0 + i * 3.5
        cuts.append(box(cx1 - 0.1, ox1 + 1, y, y + 1.5, 13.0, 22.0))
    # rótulos de la borna en la cara frontal
    for x, t in zip(J1_X, ("N", "OUT", "L")):
        cuts.append(text_front(t, 2.6 if t != "OUT" else 1.7, x, J1_Z + 4.4, oy0))
    cuts.append(text_front("110 VAC  max 10 A", 2.4, 42.0, 16.0, oy0))
    cuts.append(text_front("@techmigue", 2.4, 42.0, 12.2, oy0))
    # rótulo inferior
    s, bb = text_solid("Smart Rele", 6, 0.8)
    s.rotate(V(0, 0, 0), V(0, 1, 0), 180)        # legible mirando la cara inferior
    bb = s.BoundBox
    s.translate(V(PCB_W / 2 - (bb.XMin + bb.XMax) / 2, PCB_H / 2 - (bb.YMin + bb.YMax) / 2,
                  -bb.ZMin - 0.2))                     # Z en [-0,2, 0,6]: 0,6 mm de grabado
    cuts.append(s)
    base = base.cut(fuse(cuts))
    return base.removeSplitter()


# ---------------------------------------------------------------- TAPA
PIPE_R, PIPE_BORE = 2.2, 1.3           # guía de luz de los LED
# Marcado de los LED: el mismo módulo para cada uno (anillo concéntrico + rótulo a la
# misma distancia, mismo tamaño y alineado a la derecha, centrado en la altura del
# agujero). Los agujeros no se mueven: siguen sobre D2 y D3.
LED_LABELS = ("RELE", "WiFi")
RING_R0, RING_R1 = 2.1, 2.6            # anillo grabado alrededor del agujero
LABEL_GAP = 1.4                        # anillo -> final del texto
LABEL_SIZE = 2.6


def make_lid():
    z1 = Z_LID + LT
    lid = outline(Z_LID, z1)
    adds = []
    # faldón de centrado
    skirt = box(cx0 + FIT, cx1 - FIT, cy0 + FIT, cy1 - FIT, Z_LID - 2.5, Z_LID + 0.1).cut(
        box(cx0 + FIT + 1.2, cx1 - FIT - 1.2, cy0 + FIT + 1.2, cy1 - FIT - 1.2, Z_LID - 3, Z_LID + 1))
    skirt = skirt.cut(fuse([cyl(x, y, BOSS_R + 0.3, Z_LID - 3, Z_LID + 1) for x, y in BOSSES]))
    adds.append(skirt)
    # pisadores del PCB (0,2 mm de holgura sobre la cara superior), en zonas sin piezas
    inner = box(cx0 + FIT, cx1 - FIT, cy0 + FIT, cy1 - FIT, 0, Z_LID + 0.1)
    for x, y, d in [(1.2, 17.0, 3.0), (39.0, 48.0, 2.6), (26.0, 2.4, 3.0), (65.6, 28.8, 2.4)]:
        post = cyl(x, y, d / 2, Z_TOP + 0.2, Z_LID + 0.1).fuse(
            cone(x, y, d / 2, d / 2 + 1.5, Z_LID - 1.5, Z_LID + 0.1))           # raíz reforzada
        adds.append(post.common(inner))
    # topes sobre PS1 (techo 23,7) y K1 (techo 24,3): 0,5 mm de holgura
    adds.append(box(14.0, 24.0, 33.0, 41.0, 23.7 + 0.5, Z_LID + 0.1))
    adds.append(box(27.0, 35.0, 9.5, 14.0, 24.29 + 0.5, Z_LID + 0.1))
    # guías de luz
    for x, y in LED:
        adds.append(cyl(x, y, PIPE_R, LED_TOP + 1.5, Z_LID + 0.1))
    lid = fuse([lid] + adds)

    cuts = []
    for x, y in BOSSES:
        cuts.append(cyl(x, y, 1.7, Z_LID - 1, z1 + 1))                 # paso M3
        cuts.append(cyl(x, y, 3.1, z1 - 1.0, z1 + 1))                  # alojamiento cabeza
    for x, y in LED:
        cuts.append(cyl(x, y, PIPE_BORE, LED_TOP, z1 + 1))
    lid = lid.cut(fuse(cuts))

    # marcado de los LED
    marks = []
    for (x, y), t in zip(LED, LED_LABELS):
        marks.append(cyl(x, y, RING_R1, z1 - 0.4, z1 + 1).cut(cyl(x, y, RING_R0, z1 - 1, z1 + 2)))
        marks.append(text_top(t, LABEL_SIZE, x - RING_R1 - LABEL_GAP, y, z1, align="right"))
    lid = lid.cut(fuse(marks))
    return lid.removeSplitter()


# ---------------------------------------------------------------- exportación
def print_pose(shape, flip):
    """Orientación de impresión: apoyada en Z = 0, centrada en XY."""
    s = shape.copy()
    if flip:
        s.rotate(V(0, 0, 0), V(1, 0, 0), 180)
    bb = s.BoundBox
    s.translate(V(-(bb.XMin + bb.XMax) / 2, -(bb.YMin + bb.YMax) / 2, -bb.ZMin))
    return s


def export(objs, pcb_step=None):
    import Mesh, MeshPart
    poses = {"Base": False, "Tapa": True}
    stl_dir = os.path.join(OUT, "stl")
    os.makedirs(stl_dir, exist_ok=True)
    for k, flip in poses.items():
        s = print_pose(objs[k].Shape, flip)
        # La malla más fina que salga limpia. Con cuerdas muy finas, el teselado de las
        # curvas B-spline de los rótulos genera autointersecciones. Cualquier valor de
        # esta lista queda muy por debajo de la resolución FDM (~0,1 mm).
        for ld, ad in [(0.03, 0.2), (0.04, 0.25), (0.05, 0.3), (0.06, 0.35)]:
            m = MeshPart.meshFromShape(Shape=s, LinearDeflection=ld, AngularDeflection=ad, Relative=False)
            if m.isSolid() and not m.hasNonManifolds() and not m.getSelfIntersections():
                break
        else:
            raise RuntimeError("malla no válida: " + k)
        print(k, "STL con deflexión %.2f mm, %d facetas" % (ld, m.CountFacets))
        m.write(os.path.join(stl_dir, "chasis_%s.stl" % k.lower()))
    Part.Compound([objs[k].Shape for k in poses]).exportStep(
        os.path.join(OUT, "chasis_rele-esp12f_ensamblado.step"))


# ---------------------------------------------------------------- documento
def build():
    name = "Chasis"
    if name in App.listDocuments():
        App.closeDocument(name)
    doc = App.newDocument(name)
    base, lid = make_base(), make_lid()
    parts = {"Base": base, "Tapa": lid}
    objs = {}
    for k, s in parts.items():
        o = doc.addObject("Part::Feature", k)
        o.Shape = s
        objs[k] = o
    # PCB montado como referencia de encaje (no se exporta)
    pcb_step = os.path.join(OUT, "rele-esp12f_pcb.step")
    if os.path.exists(pcb_step):
        pcb = Part.read(pcb_step)
        pcb.translate(V(0, 0, Z_PCB))
        doc.addObject("Part::Feature", "PCB_referencia").Shape = pcb
    doc.recompute()
    doc.saveAs(os.path.join(OUT, "chasis_rele-esp12f.FCStd"))
    return doc, objs


if True:   # FreeCAD ejecuta el script con exec(): construir siempre
    doc, objs = build()
    export(objs)
    for k, o in objs.items():
        s = o.Shape
        print(k, "valid", s.isValid(), "solids", len(s.Solids), "shells", len(s.Shells), "vol %.1f cm3" % (s.Volume / 1000),
              "bb", [round(v, 2) for v in (s.BoundBox.XMin, s.BoundBox.XMax, s.BoundBox.YMin,
                                           s.BoundBox.YMax, s.BoundBox.ZMin, s.BoundBox.ZMax)])
