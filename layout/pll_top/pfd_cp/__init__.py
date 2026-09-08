"""Real transistor-level layout for the PFD/CP block family (issue #294).

``design/pfd.sch`` / ``design/pfd_cp.sch`` / their leaf cells
(``pfdcp_inv_3v3.sch``, ``pfdcp_nand2_3v3.sch``, ...) are the schematics this
family's layout implements. See ``devgen.py`` for the reusable
device-list-driven leaf-cell generator issue #299 (Part 1 of #294) proves
out and hands to Parts 2-4 (#300-#302: the PFD chains, the CP arrays, the
dump-buffer isolated well).
"""
