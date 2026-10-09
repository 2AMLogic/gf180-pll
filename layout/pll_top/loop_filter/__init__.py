"""Physical layout of the PLL's passive loop filter (issue #748).

``design/netlist/loop_filter.spice`` (sized by DR-006) is drawn here as one
standalone, flat cell, ``loop_filter``:

* ``devices.py``    -- the device table, transcribed from the netlist (no KLayout).
* ``primitives.py`` -- the three device generators (``cap_nmos_03v3_b`` MOS
                       capacitor, ``cap_mim_2f0_m2m3_noshield`` MIM capacitor,
                       plain ``ppolyf_u`` poly resistor) plus substrate-tap strips.
* ``block.py``      -- places and wires the nine devices; CLI entry point.
* ``netcheck.py``   -- connectivity extracted from the *exported GDS*, with
                       the MIM capacitor's two plates kept apart, plus an
                       independent device census read back from the GDS.

Evidence: ``layout/evidence/loop-filter-layout/PROOF.md``.
"""
