# Contributing to gf180-pll

An integer-N ring-oscillator PLL on gf180mcu, designed with xschem and
ngspice and laid out with KLayout. Start with [README.md](README.md) for the
block's status and [spec/pll.md](spec/pll.md) for the ratified spec.

## Two rules

1. **No claim without a testbench.** Every performance claim needs a testbench
   under `sim/`, run across PVT corners.
2. **`sim/` results are append-only evidence.** Add new records; never edit or
   delete existing ones. Spec changes go through [spec/](spec/README.md) with a
   decision record. Do not relax the spec to make a result pass.

## From clone to a green self-test

```sh
git clone https://github.com/2AMLogic/gf180-pll.git && cd gf180-pll
pip install klayout          # lets the layout tests run instead of skipping
bash sim/selftest.sh         # headless harness check; needs ngspice on PATH
```

`bash sim/selftest.sh` ends with `PASS: harness is functional end to end.`
Without a PDK it runs the headless path. Add `--require-pdk` once the PDK is
installed. The PDK variant and search roots are in [sim/pdk.json](sim/pdk.json);
`source sim/env.sh` exports the environment the harness resolved.

Tool and PDK versions are pinned in [.github/workflows/ci.yml](.github/workflows/ci.yml)
(see the `pdk-checks` job for the PDK, and the signoff step for the layout
tooling). The simulator version is recorded in each evidence record; see
[sim/README.md](sim/README.md). Please do not copy version numbers into other
documents; point at those locations.

## Tests CI runs

```sh
python3 -m unittest discover -s layout/tests  -t layout/tests
python3 -m unittest discover -s spec/tests    -t spec/tests
python3 -m unittest discover -s design/tests  -t design/tests
python3 -m unittest discover -s signoff/tests -t signoff/tests
python3 -m unittest discover -s docs/tests    -t docs/tests
```

Prefer running only the suite for the area you touched.

## Pull requests

Open an issue first for anything non-trivial (use the issue templates), keep
changes focused, and include the evidence or test output that supports them.
Contributions are accepted under the [Apache-2.0 license](LICENSE).
Report security problems as described in [SECURITY.md](SECURITY.md).
