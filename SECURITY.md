# Security policy

This repository contains open hardware design sources, simulation harnesses,
and CI scripts. There is no deployed service, but the scripts and workflows
run on contributors' machines and in CI, so issues there matter.

## Reporting a vulnerability

Please report privately through GitHub's
[private vulnerability reporting](https://github.com/2AMLogic/gf180-pll/security/advisories/new)
rather than a public issue. Include what you found, how to reproduce it, and
the affected files.

We aim to acknowledge reports within a week. Fixes are made on a best-effort
basis, and we will credit reporters who want it.

## Scope

In scope: scripts, CI workflows, and tooling in this repository (for example
command injection, unsafe handling of untrusted input, or leaked credentials).

Out of scope: design or functional defects in the PLL itself. Report those
through the normal [issue tracker](https://github.com/2AMLogic/gf180-pll/issues/new/choose).
