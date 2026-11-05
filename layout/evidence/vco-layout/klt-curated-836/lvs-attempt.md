# `klt lvs` on `vco_block` -- not runnable against the committed reference (#836)

Date: 2026-10-30. `klt 0.8.1.dev849+gf05774458ae2`, `--deck gf180mcu`.
Request: `lvs-request.json` (this directory; layout `../vco_block.gds`,
reference `../lvs-clean/vco_block.spice`, unmodified).

`klt lvs --format json lvs-request.json` exits with an error before any compare,
for both `reference.form` values tried (`plain-element`, the default, and
`subckt-call`):

    could not parse reference netlist '.../lvs-clean/vco_block.spice':
    Can't find a value for a R, C or L device in ...vco_block.spice, line 64

Line 64 is `R_RCG NC GND_VCO GND_VCO ppolyf_u_3k W=1.0u L=5.6u`: the committed
reference writes its three poly resistors in the foundry deck's form (three
terminals, model name, W/L, no value token), which klt's SPICE reader rejects.

Per the issue, the reference was not edited and no verdict is claimed.
**No curated LVS result exists for `vco_block`; "match, 43/43 nets" is not
re-established here.** The recorded foundry-deck match (`../lvs-clean/`) is
unchanged and predates #837's strap.
