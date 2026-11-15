# -*- coding: utf-8 -*-
"""3D-printable enclosure for the rele-esp12f board (66.5 x 49 mm, 1.6 mm thick).

Run it inside FreeCAD (Python console), with the repository root as working directory:
    exec(open(r"<path>/enclosure/generate_enclosure.py", encoding="utf-8").read())
or headless:
    freecadcmd enclosure/generate_enclosure.py

Coordinate system = that of the STEP exported with
    kicad-cli pcb export step --subst-models --user-origin 100x149mm
i.e. bottom-left corner of the PCB at (0, 0), X along the 66.5 mm side,
Y along the 49 mm side (Y_kicad = 149 - Y). PCB bottom face at Z = Z_PCB.

Generated parts:
  Base     box with floor, PCB supports, lid screw bosses, J1 cable entry,
           strain relief and mounting tabs.
  Lid      with centering skirt, PCB hold-down posts and LED light pipes.
SW1/SW2 are for debugging only: they stay inside, reachable with the lid removed.
"""
import os
import FreeCAD as App
import Part
from FreeCAD import Vector as V

try:
    OUT = os.path.dirname(os.path.abspath(__file__))
except NameError:   # exec() from the FreeCAD console: repository root as working directory
    OUT = os.path.join(os.getcwd(), "enclosure")
FONT_DIR = "C:/Windows/Fonts/"
# Verdana Bold: designed for small sizes (wide sidebearings, open apertures).
FONT = "verdanab.ttf"
# Engraved-text printability for a 0.4 mm nozzle (checked on every label, see check_text):
LETTER_GAP = 0.85   # material between adjacent letters: two extrusion lines
MIN_GAP = 0.45      # material inside a glyph (counters, apertures, i dot): one line
MIN_STROKE = 0.45   # engraved stroke width on walls; 0.55 on faces printed on the bed
                    # (elephant's foot narrows the first layers)

# ---------------------------------------------------------------- parameters
PCB_W, PCB_H, PCB_T = 66.5, 49.0, 1.6
CL = 0.3            # PCB-to-wall clearance
W = 2.4             # wall thickness
FLOOR = 2.0         # floor thickness
STAND = 5.0         # PCB height above the floor (THT leads protrude 3.3 mm below)
Z_PCB = FLOOR + STAND          # PCB bottom face
Z_TOP = Z_PCB + PCB_T          # PCB top face
Z_LID = 26.0        # lid bottom face (K1 reaches 24.3: 1.7 mm air gap)
LT = 2.5            # lid thickness
LEDGE = 1.5         # width of the perimeter support ledge
FIT = 0.25          # skirt-to-wall clearance

cx0, cy0 = -CL, -CL
cx1, cy1 = PCB_W + CL, PCB_H + CL
ox0, oy0 = cx0 - W, cy0 - W
ox1, oy1 = cx1 + W, cy1 + W

# Lid screw bosses (M3 self-tapping): outside the PCB outline,
# 0.64 mm from its rounded corners (r = 2 mm).
BOSS_R, BOSS_PILOT, BOSS_DEPTH = 3.3, 2.5, 12.0
BOSSES = [(-2.2, -2.2), (PCB_W + 2.2, -2.2), (-2.2, PCB_H + 2.2), (PCB_W + 2.2, PCB_H + 2.2)]

# PCB M2 holes (MH1, MH2) and support pillars under the push buttons
MH = [(51.2, 8.4), (63.9, 2.6)]
SUPPORTS = [(61.0, 23.8), (57.2, 3.0)]    # pillars under SW1/SW2 (central PCB support)
LED = [(55.3, 25.0), (48.0, 4.7)]         # D2 (relay), D3 (WiFi)
LED_TOP = Z_PCB + 2.7

# J1 terminal block: cable entries (center measured on the 3D model: 5.1 mm above the
# PCB bottom face, 2.8 x 3.0 mm opening)
J1_X = [3.34, 8.42, 13.50]
J1_Z = Z_PCB + 5.1
WIRE_D = 3.8


# ---------------------------------------------------------------- helpers
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
    """Outer outline: rectangle + corner bosses."""
    b = box(ox0, ox1, oy0, oy1, z0, z1)
    vert = [e for e in b.Edges if abs(e.Vertexes[0].Z - e.Vertexes[1].Z) > 1e-6]
    b = b.makeFillet(fillet, vert)
    return fuse([b] + [cyl(x, y, BOSS_R, z0, z1) for x, y in BOSSES])


def at_sign(cx, cy):
    """Printable "@" (~5.6 mm): no system font has one at this size, the arms of the
    spiral end up < 0.3 mm apart. 0.65 mm strokes, >= 0.6 mm of material between them."""
    t, ra = 0.65, 1.2                    # stroke, bowl outer radius
    ri = (ra ** 2 + (ra + 0.6) ** 2) ** 0.5   # outer ring inner radius: 0.6 mm to the stem ends

    def disc(x, y, r):
        return Part.Face(Part.Wire(Part.makeCircle(r, V(x, y, 0))))

    def ring(x, y, r0, r1):
        return disc(x, y, r1).cut(disc(x, y, r0))

    def wedge(a0, a1):                   # angular sector a0 -> a1 (degrees, CCW)
        import math
        n = int((a1 - a0) / 5) + 1
        pts = [V(0, 0, 0)] + [V(9 * math.cos(math.radians(a0 + (a1 - a0) * k / n)),
                                9 * math.sin(math.radians(a0 + (a1 - a0) * k / n)), 0)
                              for k in range(n + 1)] + [V(0, 0, 0)]
        return Part.Face(Part.makePolygon(pts))
    bowl = ring(0, 0, ra - t, ra)
    stem = Part.Face(Part.makePolygon([V(ra - t, -ra, 0), V(ra, -ra, 0), V(ra, ra, 0),
                                       V(ra - t, ra, 0), V(ra - t, -ra, 0)]))
    # foot: U below y = -ra whose legs match exactly the stem and the outer ring band
    xi, xo = (ri ** 2 - ra ** 2) ** 0.5, ((ri + t) ** 2 - ra ** 2) ** 0.5
    below = Part.Face(Part.makePolygon([V(-9, -ra, 0), V(9, -ra, 0), V(9, -9, 0),
                                        V(-9, -9, 0), V(-9, -ra, 0)]))
    foot = disc((ra - t + xo) / 2, -ra, (xo - ra + t) / 2).cut(
        disc((ra + xi) / 2, -ra, (xi - ra) / 2)).common(below)
    outer = ring(0, 0, ri, ri + t).cut(below.common(wedge(-90, 0)))   # opening: lower right
    f = bowl.fuse([stem, foot, outer]).removeSplitter()
    f.translate(V(cx, cy, 0))
    return Part.Compound(f.Faces)


def text_faces(txt, size):
    """Glyph faces with natural spacing, then each letter pushed right only as far as
    needed to leave LETTER_GAP of material to the previous ones (kerned pairs such as
    "LA" or "VA" nearly touch at these sizes)."""
    glyphs = []
    for c, ch in zip(txt, Part.makeWireString(txt, FONT_DIR, FONT, size, 0)):
        if ch:
            g = Part.Compound([Part.makeFace(ch, "Part::FaceMakerBullseye")])
            if c == "@":                 # same place, printable geometry
                g = at_sign(g.BoundBox.Center.x, g.BoundBox.Center.y)
            glyphs.append(g)
    for k in range(1, len(glyphs)):
        while True:
            d = min(glyphs[k].distToShape(g)[0] for g in glyphs[max(0, k - 3):k])
            if d >= LETTER_GAP:
                break
            for g in glyphs[k:]:
                g.translate(V(LETTER_GAP - d + 0.01, 0, 0))
    return Part.Compound(glyphs)             # one child compound per letter


def check_text(comp, txt, min_stroke):
    """Fails the build if an engraved label is not printable. Morphological test on the
    2D glyphs: dilating them by MIN_GAP/2 must not merge letters or close counters,
    and eroding them by min_stroke/2 must not break any stroke."""
    from shapely.geometry import Polygon
    from shapely.ops import unary_union

    def pts(w):
        return [(p.x, p.y) for p in w.discretize(Deflection=0.002)]
    polys = [unary_union([Polygon(pts(f.OuterWire), [pts(w) for w in f.Wires
                                                      if not w.isSame(f.OuterWire)]).buffer(0)
                          for f in letter.Faces]) for letter in comp.childShapes()]
    # +-2 um closes the seams between adjacent faces of one glyph (discretization)
    g = unary_union(polys).buffer(0.002, quad_segs=32).buffer(-0.002, quad_segs=32)
    parts =list(getattr(g, "geoms", [g]))
    holes = [Polygon(h) for p in parts for h in p.interiors]

    def nholes(s):
        return sum(len(p.interiors) for p in getattr(s, "geoms", [s]))

    def single(s):
        return not s.is_empty and s.geom_type == "Polygon"
    # gap: no letters merge, every counter survives as one piece, and no new enclosed
    # void appears (e.g. the arms of the "@" spiral fusing)
    r = MIN_GAP / 2
    dil = g.buffer(r, quad_segs=32)
    ok_gap = (len(getattr(dil, "geoms", [dil])) == len(parts)
              and all(single(h.buffer(-r, quad_segs=32)) for h in holes)
              and nholes(dil) == len(holes))
    # stroke: every stroke survives erosion without splitting or opening into a counter
    r = min_stroke / 2
    ok_stroke = all(single(e) and len(e.interiors) == len(p.interiors)
                    for p in parts for e in [p.buffer(-r, quad_segs=32)])
    letter = min((a.distance(b) for k, a in enumerate(polys) for b in polys[k + 1:]
                  if not a.intersects(b)), default=9.0)
    TEXT_REPORT.append((txt, round(letter, 2)))
    if not (ok_gap and ok_stroke and letter >= LETTER_GAP - 0.01):
        raise RuntimeError("label not printable: %r (letter gap %.2f, gap ok %s, stroke ok %s)"
                           % (txt, letter, ok_gap, ok_stroke))


TEXT_REPORT = []


def text_solid(txt, size, depth, min_stroke=MIN_STROKE):
    comp = text_faces(txt, size)
    check_text(comp, txt, min_stroke)
    return comp.extrude(V(0, 0, depth)), comp.BoundBox


def text_top(txt, size, cx, cy, ztop, depth=0.6, align="center"):
    """Text engraved on an upward-facing horizontal face. (cx, cy) is the center, or
    the right end (vertically centered) if align == "right". The lid prints upside
    down, so this face lies on the bed."""
    s, bb = text_solid(txt, size, depth + 0.2, min_stroke=0.55)
    x0 = cx - bb.XMax if align == "right" else cx - (bb.XMin + bb.XMax) / 2
    s.translate(V(x0, cy - (bb.YMin + bb.YMax) / 2, ztop - depth))
    return s


def text_front(txt, size, cx, cz, yface, depth=0.5):
    """Text engraved on the front face (normal -Y), readable from the front."""
    s, bb = text_solid(txt, size, depth + 0.2)
    s.translate(V(-(bb.XMin + bb.XMax) / 2, -(bb.YMin + bb.YMax) / 2, -(depth + 0.2)))
    s.rotate(V(0, 0, 0), V(1, 0, 0), 90)       # x->x, y->z, z->-y  => Y in [0, depth+0.2]
    s.translate(V(cx, yface - 0.2, cz))        # from 0.2 mm outside to 'depth' inside the wall
    return s


# ---------------------------------------------------------------- BASE
def make_base():
    shell = outline(0, Z_LID)
    cavity = box(cx0, cx1, cy0, cy1, FLOOR, Z_LID + 1)
    base = shell.cut(cavity)

    adds = []
    # full bosses (lost when the cavity is cut)
    adds += [cyl(x, y, BOSS_R, 0, Z_LID) for x, y in BOSSES]
    # perimeter ledge: the PCB rests on 1.2 mm of its edge
    ring = box(cx0, cx1, cy0, cy1, FLOOR, Z_PCB).cut(
        box(cx0 + LEDGE, cx1 - LEDGE, cy0 + LEDGE, cy1 - LEDGE, FLOOR - 1, Z_PCB + 1))
    adds.append(ring)
    # M2 standoffs at MH1/MH2 and support pillars under SW1/SW2 (the buttons can be
    # pressed with the lid removed without flexing the board)
    adds += [cyl(x, y, 2.75, FLOOR - 0.1, Z_PCB) for x, y in MH]
    adds += [cyl(x, y, 2.0, FLOOR - 0.1, Z_PCB) for x, y in SUPPORTS]
    # mounting tabs at both ends (Ø4 screw)
    ym = PCB_H / 2
    for side in (-1, 1):
        xe = ox0 if side < 0 else ox1
        tab = box(min(xe, xe + side * 9), max(xe, xe + side * 9), ym - 6, ym + 6, 0, 3)
        tab = tab.fuse(cyl(xe + side * 9, ym, 6, 0, 3))
        tab = tab.cut(cyl(xe + side * 9, ym, 2.2, -1, 4))
        adds.append(tab)
        # tab reinforcement ribs (triangular gussets against the wall)
        for dy in (-5.6, 4.4):
            pts = [V(xe, ym + dy, 3), V(xe + side * 4, ym + dy, 3), V(xe, ym + dy, 7), V(xe, ym + dy, 3)]
            adds.append(Part.Face(Part.makePolygon(pts)).extrude(V(0, 1.2, 0)))
    # strain-relief apron in front of J1
    apron = box(ox0, 20.0, oy0 - 13, oy0 + 0.1, 0, 3)
    adds.append(apron)
    # apron side stops (guide the cables)
    adds.append(box(ox0, ox0 + 2.0, oy0 - 13, oy0, 3, 6))
    adds.append(box(18.0, 20.0, oy0 - 13, oy0, 3, 6))
    base = fuse([base] + adds)

    cuts = []
    # M3 pilot holes in the bosses
    cuts += [cyl(x, y, BOSS_PILOT / 2, Z_LID - BOSS_DEPTH, Z_LID + 1) for x, y in BOSSES]
    cuts += [cone(x, y, BOSS_PILOT / 2, BOSS_PILOT / 2 + 0.6, Z_LID - 0.6, Z_LID + 0.01)
             for x, y in BOSSES]
    # M2 pilot holes in the standoffs
    cuts += [cyl(x, y, 0.85, Z_PCB - 6, Z_PCB + 1) for x, y in MH]
    # J1 cable entries (with outer countersink)
    for x in J1_X:
        cuts.append(Part.makeCylinder(WIRE_D / 2, W + 2, V(x, oy0 - 1, J1_Z), V(0, 1, 0)))
        cuts.append(Part.makeCone(WIRE_D / 2 + 0.8, WIRE_D / 2, 0.8, V(x, oy0 - 0.01, J1_Z), V(0, 1, 0)))
    # cable-tie slots (strain relief) in the apron
    for x in (ox0 + 3.2, 16.8):
        cuts.append(box(x - 1.0, x + 1.0, oy0 - 10.5, oy0 - 6.0, -1, 4))
    # ventilation: low inlet at the front (below the relay), high outlet at the back (above PS1).
    # 1.5 mm slots: neither a finger nor a 2.5 mm probe can pass.
    for i in range(6):
        x = 25.0 + i * 3.5
        cuts.append(box(x, x + 1.5, oy0 - 1, cy0 + 0.1, FLOOR + 1.0, Z_PCB - 0.6))
    for i in range(8):
        x = 6.0 + i * 3.5
        cuts.append(box(x, x + 1.5, cy1 - 0.1, oy1 + 1, 15.0, 23.0))
    for i in range(5):
        y = 31.0 + i * 3.5
        cuts.append(box(cx1 - 0.1, ox1 + 1, y, y + 1.5, 13.0, 22.0))
    # terminal block labels. At a printable size "OUT" is wider than the 5.08 mm pitch
    # allows between N and L, so it sits one row higher with an engraved leader to its hole.
    cuts.append(text_front("N", 3.5, J1_X[0], 17.6, oy0))
    cuts.append(text_front("L", 3.5, J1_X[2], 17.6, oy0))
    cuts.append(text_front("OUT", 3.5, J1_X[1], 22.0, oy0))
    cuts.append(box(J1_X[1] - 0.3, J1_X[1] + 0.3, oy0 - 0.2, oy0 + 0.5, 15.4, 19.8))
    # rating and handle, centered on the flat face between the L entry and the corner boss.
    # Rating in capitals: the bowl of a lowercase "a" is too thin at any size that fits.
    cuts.append(text_front("110 VAC  MAX 10 A", 3.2, 41.2, 22.0, oy0))
    cuts.append(text_front("@techmigue", 5.3, 41.2, 15.3, oy0))
    # bottom label
    s, bb = text_solid("Smart Rele", 7, 0.8, min_stroke=0.55)   # printed on the bed
    s.rotate(V(0, 0, 0), V(0, 1, 0), 180)        # readable when looking at the bottom face
    bb = s.BoundBox
    s.translate(V(PCB_W / 2 - (bb.XMin + bb.XMax) / 2, PCB_H / 2 - (bb.YMin + bb.YMax) / 2,
                  -bb.ZMin - 0.2))                     # Z in [-0.2, 0.6]: 0.6 mm engraving
    cuts.append(s)
    base = base.cut(fuse(cuts))
    return base.removeSplitter()


# ---------------------------------------------------------------- LID
PIPE_R, PIPE_BORE = 2.2, 1.3           # LED light pipe
# LED marking: the same module for each one (concentric ring + label at the same
# distance, same size, right-aligned and vertically centered on the hole).
# The holes do not move: they stay above D2 and D3.
LED_LABELS = ("RELAY", "WiFi")
RING_R0, RING_R1 = 2.1, 2.8            # engraved ring around the hole (0.7 mm: on the bed)
LABEL_GAP = 1.4                        # ring -> end of the text
LABEL_SIZE = 5.0


def make_lid():
    z1 = Z_LID + LT
    lid = outline(Z_LID, z1)
    adds = []
    # centering skirt
    skirt = box(cx0 + FIT, cx1 - FIT, cy0 + FIT, cy1 - FIT, Z_LID - 2.5, Z_LID + 0.1).cut(
        box(cx0 + FIT + 1.2, cx1 - FIT - 1.2, cy0 + FIT + 1.2, cy1 - FIT - 1.2, Z_LID - 3, Z_LID + 1))
    skirt = skirt.cut(fuse([cyl(x, y, BOSS_R + 0.3, Z_LID - 3, Z_LID + 1) for x, y in BOSSES]))
    adds.append(skirt)
    # PCB hold-down posts (0.2 mm above the top face), in component-free areas
    inner = box(cx0 + FIT, cx1 - FIT, cy0 + FIT, cy1 - FIT, 0, Z_LID + 0.1)
    for x, y, d in [(1.2, 17.0, 3.0), (39.0, 48.0, 2.6), (26.0, 2.4, 3.0), (65.6, 28.8, 2.4)]:
        post = cyl(x, y, d / 2, Z_TOP + 0.2, Z_LID + 0.1).fuse(
            cone(x, y, d / 2, d / 2 + 1.5, Z_LID - 1.5, Z_LID + 0.1))           # reinforced root
        adds.append(post.common(inner))
    # stops above PS1 (top 23.7) and K1 (top 24.3): 0.5 mm clearance
    adds.append(box(14.0, 24.0, 33.0, 41.0, 23.7 + 0.5, Z_LID + 0.1))
    adds.append(box(27.0, 35.0, 9.5, 14.0, 24.29 + 0.5, Z_LID + 0.1))
    # light pipes
    for x, y in LED:
        adds.append(cyl(x, y, PIPE_R, LED_TOP + 1.5, Z_LID + 0.1))
    lid = fuse([lid] + adds)

    cuts = []
    for x, y in BOSSES:
        cuts.append(cyl(x, y, 1.7, Z_LID - 1, z1 + 1))                 # M3 clearance hole
        cuts.append(cyl(x, y, 3.1, z1 - 1.0, z1 + 1))                  # screw head recess
    for x, y in LED:
        cuts.append(cyl(x, y, PIPE_BORE, LED_TOP, z1 + 1))
    lid = lid.cut(fuse(cuts))

    # LED marking
    marks = []
    for (x, y), t in zip(LED, LED_LABELS):
        marks.append(cyl(x, y, RING_R1, z1 - 0.4, z1 + 1).cut(cyl(x, y, RING_R0, z1 - 1, z1 + 2)))
        marks.append(text_top(t, LABEL_SIZE, x - RING_R1 - LABEL_GAP, y, z1, align="right"))
    lid = lid.cut(fuse(marks))
    return lid.removeSplitter()


# ---------------------------------------------------------------- export
def print_pose(shape, flip):
    """Print orientation: resting on Z = 0, centered in XY."""
    s = shape.copy()
    if flip:
        s.rotate(V(0, 0, 0), V(1, 0, 0), 180)
    bb = s.BoundBox
    s.translate(V(-(bb.XMin + bb.XMax) / 2, -(bb.YMin + bb.YMax) / 2, -bb.ZMin))
    return s


def export(objs, pcb_step=None):
    import Mesh, MeshPart
    poses = {"Base": False, "Lid": True}
    stl_dir = os.path.join(OUT, "stl")
    os.makedirs(stl_dir, exist_ok=True)
    for k, flip in poses.items():
        s = print_pose(objs[k].Shape, flip)
        # Use the finest mesh that comes out clean. With very fine chords, tessellating the
        # B-spline curves of the labels produces self-intersections. Every value in this
        # list is well below FDM resolution (~0.1 mm).
        for ld, ad in [(0.03, 0.2), (0.04, 0.25), (0.05, 0.3), (0.06, 0.35)]:
            m = MeshPart.meshFromShape(Shape=s, LinearDeflection=ld, AngularDeflection=ad, Relative=False)
            if m.isSolid() and not m.hasNonManifolds() and not m.getSelfIntersections():
                break
        else:
            raise RuntimeError("invalid mesh: " + k)
        print(k, "STL with %.2f mm deflection, %d facets" % (ld, m.CountFacets))
        m.write(os.path.join(stl_dir, "enclosure_%s.stl" % k.lower()))
    Part.Compound([objs[k].Shape for k in poses]).exportStep(
        os.path.join(OUT, "enclosure_rele-esp12f_assembly.step"))


# ---------------------------------------------------------------- document
def build():
    name = "Enclosure"
    if name in App.listDocuments():
        App.closeDocument(name)
    doc = App.newDocument(name)
    base, lid = make_base(), make_lid()
    parts = {"Base": base, "Lid": lid}
    objs = {}
    for k, s in parts.items():
        o = doc.addObject("Part::Feature", k)
        o.Shape = s
        objs[k] = o
    # assembled PCB as a fit reference (not exported)
    pcb_step = os.path.join(OUT, "rele-esp12f_pcb.step")
    if os.path.exists(pcb_step):
        pcb = Part.read(pcb_step)
        pcb.translate(V(0, 0, Z_PCB))
        doc.addObject("Part::Feature", "PCB_reference").Shape = pcb
    doc.recompute()
    doc.saveAs(os.path.join(OUT, "enclosure_rele-esp12f.FCStd"))
    return doc, objs


if True:   # FreeCAD runs the script with exec(): always build
    doc, objs = build()
    export(objs)
    for t, gap in TEXT_REPORT:
        print("label %-20r printable, closest letters %.2f mm apart" % (t, gap))
    for k, o in objs.items():
        s = o.Shape
        print(k, "valid", s.isValid(), "solids", len(s.Solids), "shells", len(s.Shells), "vol %.1f cm3" % (s.Volume / 1000),
              "bb", [round(v, 2) for v in (s.BoundBox.XMin, s.BoundBox.XMax, s.BoundBox.YMin,
                                           s.BoundBox.YMax, s.BoundBox.ZMin, s.BoundBox.ZMax)])
