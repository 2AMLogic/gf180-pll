"""Negative control for ../PROOF-erc.md: cut the routing metal/vias inside a box.

usage: python -I make_cut.py <in.gds> <out.gds> <label-ignored> x0 y0 x1 y1   (database units, nm)

Flattens the top cell and subtracts the box from Metal2..Metal5 and Via2..Via4.
The box used in PROOF-erc.md happens to sever the VSS routing, which `klt erc`
must report as a second VSS island. The cut GDS is not committed (3.9 MB,
regenerable from this script).
"""
import sys
import klayout.db as db

src, dst, _name = sys.argv[1:4]
x0, y0, x1, y1 = map(int, sys.argv[4:8])
l = db.Layout()
l.read(src)
t = l.top_cell()
t.flatten(True)
cut = db.Region(db.Box(x0, y0, x1, y1))
for ln, dt in [(36, 0), (38, 0), (40, 0), (41, 0), (42, 0), (46, 0), (81, 0)]:
    li = l.find_layer(ln, dt)
    reg = db.Region(t.shapes(li))
    t.shapes(li).clear()
    t.shapes(li).insert(reg - cut)
l.write(dst)
