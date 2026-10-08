# Work Log

Chronological record of merged pull requests and closed issues. Maintained by the Loom Guide role.

### 2026-10-08

- **PR #730**: Record batch image ngspice-46 sign-off and wedge probe 6/6 (DR-039)
- **PR #732**: sim/period-jitter: route runner deck execution and provenance through the harness (#712 step 1)
- **PR #729**: docs(sim): active-solver check and controlled DC comparison for the #533 batch mismatch
- **PR #723**: sim: capture batch executor environment; diagnose batch-vs-local divergence (#533)
- **PR #721**: sim/harness: atomically reserve record ids before execution
- **PR #719**: ci: run sim/lib simenv bash regression tests in the checks job
- **PR #717**: sim: retain simulator diagnostics in timeout evidence logs
- **PR #716**: sim: fail batch points when output collection fails, retaining partial outputs
- **PR #711**: Consolidate duplicated devgen helpers into _canvas.py (#707)
- **PR #710**: README: cut Status to a scannable table; move campaign narrative under sim/ and layout/ (#703)
- **Issue #720** (closed): sim/harness: atomically reserve record IDs before execution to protect append-only evidence
- **Issue #718** (closed): CI: run the sim/lib simenv bash regression tests (never wired in)
- **Issue #715** (closed): sim: retain simulator diagnostics in timeout evidence logs
- **Issue #714** (closed): sim: fail batch points when evidence collection fails, retaining partial outputs
- **Issue #707** (closed): Consolidate duplicated devgen helpers (_connect_pads, well_tap, Device) into _canvas.py
- **Issue #703** (closed): README: cut the 1,200-word Status wall to a scannable summary; move campaign narrative under sim/

### 2026-10-07

- **PR #708**: Add CONTRIBUTING/SECURITY, fix issue templates and package metadata
- **Issue #704** (closed): Add an outsider on-ramp: CONTRIBUTING, SECURITY, correct issue-template contact link, repo metadata
- **PR #706**: harness: fail a point when the execution layer reports a terminal failure
- **PR #705**: Normalise host paths in layout evidence + CI guard (#701)
- **Issue #702** (closed): sim: preserve failed and interrupted backend outcomes when measurements are complete
- **Issue #701** (closed): CI guard + capture-time normalization: layout evidence bundles still embed host-absolute paths (58/270 files)
- **Issue #696** (closed): Remove four duplicate pdk_models() helpers: harness Pdk.ngspice_dir already provides this
- **PR #694**: refactor(sim): resolve PDK models via find_pdk() in period-jitter runners
- **Issue #692** (closed): Replace four copies of pdk_models() in period-jitter run.py with harness find_pdk()

### 2026-10-03

- **PR #691**: Consolidate Metal2 track packing and nwell_over into _canvas.py
- **PR #689**: docs: state #525 as closed in challenge-5 supply-sensitivity row
- **PR #688**: sim/harness: name the executing ngspice in --no-write summaries; #503 pilot mismatch confirmed executor-side (0/45 recorded)
- **Issue #690** (closed): Consolidate duplicated Metal2 track-packing and nwell_over helpers into _canvas.py
- **Issue #687** (closed): docs: challenge-5-proposal.md:1508 hands work to closed #542 -- check-issue-reference-state.sh fails on main

### 2026-10-02

- **PR #686**: spec: Budget 2 governs the full rail range, re-derived as 1.2 V (DR-037)
- **PR #685**: spec: derate Output band to the static-code ceiling, DR-038 proposed (#534)
- **PR #684**: spec: band-selection rule is evaluated over the measured 0.9-2.7 V window (DR-036)
- **PR #683**: spec: re-stamp decision records ratified through #1; document Status convention (#446)
- **PR #682**: Consolidate duplicate mosfet()/MosfetPorts into _canvas.py
- **PR #681**: sim: the REF input contract's grid is blocked by the job image's ngspice-42, not by compute — batch ceiling-abort fixed, cross-version divergence measured (DR-035, issue #499)
- **Issue #542** (closed): spec/pll.md band-selection rule does not name the control window "reaches f" is evaluated over, and the two candidate windows select different bands
- **Issue #534** (closed): spec/pll.md Output band: at 200 MHz no single STATIC band code covers the ratified temp/supply box at four of the five MOS bundles
- **Issue #525** (closed): Budget 2 prices a ±0.33 V rail excursion but row 12 specifies the 0.66 V full range — 9 of 15 measured cells exceed 0.6 V under the row's own reading
- **Issue #446** (closed): spec: decision-record Status fields still read "proposed" after #1 ratified spec/pll.md
- **Issue #444** (closed): Consolidate pfd_cp/devgen.py and divider_chain/devgen.py's duplicate mosfet()/MosfetPorts into _canvas.py

### 2026-10-01

- **Issue #640** (closed): loom-daemon: issue #127 re-dispatched 4-5x in ~10 minutes despite unchanged repo state and noop-cooldown
- **Issue #442** (closed): Layout: the drawn blocks are ~2.0x over the 0.15 mm2 area target -- close it or amend the target
- **Issue #407** (closed): Lower-spread lock-detector delay reference: meet DR-013's 1.65x observable-window spread target
- **Issue #294** (closed): Layout: real transistor-level layout for the PFD + charge-pump block (incl. dump buffer)

### 2026-09-30

- **PR #679**: layout/evidence: commit on-pin --offgrid DRC bundles for nine cells
- **PR #678**: refactor(tests): share the throwaway-tree write() via a TreeWriter mixin in signoff/ and docs/
- **PR #676**: docs(evidence): strike unattested --offgrid DRC claims and grade them
- **PR #674**: refactor(tests): dedup spec/design tests' identical _Tree.write() into a TreeWriter mixin
- **PR #672**: feat(layout-check): grade the KLayout pin per top cell, and re-derive the five VCO sub-cell verdicts on it
- **PR #668**: feat(layout-check): grade every PROOF-*.md layer_indexes() census against the GDS it names
- **PR #238**: fix(ratification): remove unwrapped private-repo reference from market-key/SKILL.md
- **Issue #677** (closed): Dedup signoff/docs tests' identical _Tree.write() into a TreeWriter mixin
- **Issue #675** (closed): layout/evidence: commit on-pin `--offgrid` DRC bundles for the nine cells whose off-grid claims #671 could only disclose
- **Issue #673** (closed): Dedup spec/design tests' identical _Tree.write() into the TreeWriter mixin sim/tests already has
- **Issue #671** (closed): layout/evidence: seven VCO PROOF documents claim a `--offgrid` signoff DRC run whose own committed log records `Offgrid enabled: false`
- **Issue #670** (closed): Dedup pfd_cp/cp_dumpbuf.py's _riser() into cp_array.py's (already aliased elsewhere)
- **Issue #663** (closed): check-layout-status-claims.sh cannot grade a layer_indexes() census against the GDS it names

### 2026-09-29

- **PR #669**: refactor: share cp_array/cp_dumpbuf riser plumbing via _canvas
- **PR #667**: docs(evidence): correct PROOF-erc.md supply-text digest
- **PR #665**: fix(vco-layout): correct metal2 layer census in erc-supply-spec.json, regen erc-report.json
- **PR #664**: docs(evidence): correct PROOF-erc.md's vco_block layer census to 15 layers
- **PR #659**: refactor: remove dead K_B/T0_K/kelvin in rb_deck.py and sid_deck.py
- **PR #657**: refactor: import read_wrdata from rb_extract in isf_extract
- **PR #656**: docs(signoff): correct case 1 klt-envelope claim (#654)
- **PR #653**: refactor: consolidate sid_extract helpers into rb_extract
- **PR #652**: sim: use load_module in test_lock_window_proxy_derive
- **PR #651**: refactor: share sim/tests _Tree write and _TreeTest setUp via _fixtures
- **PR #647**: sim: consolidate four duplicated _join_continuations into isf_deck
- **PR #646**: sim: consolidate duplicated _geomean into harness/derived.py
- **Issue #666** (closed): Consolidate cp_dumpbuf.py/cp_array.py's duplicate _riser()/_rect_extra()/_EXTRA_LAYER
- **Issue #662** (closed): PROOF-erc.md's 43-supply-text bullet cites the superseded vco_block.gds digest (b1798bf8) as 'the hash pinned under Provenance'
- **Issue #661** (closed): erc-supply-spec.json's metal2 _comment repeats the same wrong 14-layer census #660 corrects in PROOF-erc.md
- **Issue #660** (closed): PROOF-erc.md's layer_indexes() census of vco_block.gds lists 14 layers; the file has 15 (the (0,0) decap marker layer is omitted)
- **Issue #658** (closed): Remove dead K_B/T0_K/kelvin definitions in rb_deck.py and sid_deck.py
- **Issue #655** (closed): Remove isf_extract.py's duplicate read_wrdata(): import from rb_extract
- **Issue #654** (closed): signoff/README.md falsely states no klt --format json envelope is committed anywhere (four klt erc reports have been in-tree since 2026-09-26)
- **Issue #650** (closed): Remove duplicate K_B/T0_K/kelvin/read_wrdata: consolidate sid_extract.py into rb_extract.py
- **Issue #649** (closed): Remove duplicate module-loader in test_lock_window_proxy_derive.py: use harness.derived.load_module
- **Issue #648** (closed): Dedup sim/tests _TreeTest.setUp / write() boilerplate into _fixtures.py
- **Issue #645** (closed): Consolidate duplicate _join_continuations() in period-jitter deck builders
- **Issue #644** (closed): Consolidate duplicate _geomean() in lock-window-proxy/lock-window-trim derive.py into harness/derived.py

### 2026-09-28

- **PR #643**: sim: consolidate duplicated derive.py helpers into harness/derived.py
- **PR #642**: layout: consolidate pfd_cp/divider_chain devgen.py's duplicate LeafCell into _canvas.py
- **PR #638**: sim: drop the unused _si() SI-prefix formatter from isf-bringup summarize.py
- **PR #637**: refactor: remove the dead count_cells() from the in-band-bound deck builder
- **PR #635**: fix(signoff): require klt to be the pinned release, not merely present
- **PR #633**: docs+ci: name the engine behind section 6's DRC/LVS verdicts, and grade every document that states the KLayout pin
- **PR #632**: ci: grade section 5.1's narration of this check's own OK-line counts
- **PR #631**: docs(§8): the EDA-flow bullet deferred layout to the future three pages after §6 recorded four drawn blocks
- **PR #629**: layout: re-derive every block-level DRC/LVS verdict on the pinned KLayout (#127 part 28)
- **PR #628**: layout: re-run all four klt erc reports on the pinned release, and make the version rule exact
- **PR #627**: docs: grade the Output band row's adjacent-band overlap under device mismatch
- **Issue #641** (closed): Consolidate duplicated derive.py helpers into sim/harness/derived.py
- **Issue #639** (closed): Consolidate pfd_cp/devgen.py and divider_chain/devgen.py's duplicate LeafCell dataclass into _canvas.py
- **Issue #636** (closed): Remove dead _si() helper in sim/period-jitter/isf-bringup/summarize.py
- **Issue #634** (closed): Remove dead count_cells() in sim/period-jitter/in-band-bound/ib_deck.py
- **Issue #630** (closed): signoff/run-signoff.sh --check reports a false 'stale' when klt on PATH is a source build rather than the pinned release
- **Issue #626** (closed): docs(§5.1): the proposal's narration of CI's own OK-line counts is ungraded, and drifted

### 2026-09-27

- **PR #625**: sim/vco-tuning-range: widen the band-pair mismatch draw to an 11-point grid covering all five MOS bundles
- **PR #624**: layout: gate the committed LVS reference netlists on their own generators
- **PR #623**: docs: grade "tracked as #N" as an ownership claim, and fix the stale owner it hid
- **PR #621**: layout: dedup reference_netlist() comment boilerplate across 8 leaf cells
- **PR #619**: sim: flag an unquoted sw_stat_mismatch=1 override in the switches-note guard, and pin simenv_provenance's default
- **PR #618**: docs: reprice term-4 mismatch bullet to the 21-point corner axis
- **PR #616**: spec: re-price DR-018's reference-spur charge stack at the widened 21-point corner axis (DR-034)
- **PR #615**: docs(sim): scope the recorded-seed reproducibility claim to one host/build
- **PR #613**: docs: drop stale #580 references now that DR-033 superseded it
- **PR #612**: sim+docs: grade DR-033's in-band jitter bound and assert its 45-point coverage
- **PR #609**: sim: close T1 item 6's corner-combination gap by widening both Monte Carlo axes (#597)
- **PR #608**: sim: give both Monte Carlo campaigns a committed negative control (item 6(c))
- **PR #607**: sim: give simenv_provenance() the switches-note override simenv_env_block() already had (issue #601)
- **PR #604**: sim: bound the in-band generators' random period jitter DR-032 left as an argument
- **PR #603**: sim+docs: the last §5 figure excused by a guard had the guard's own "work owed" note attached (issue #237)
- **PR #600**: docs: name the reason when check-issue-reference-state.sh's forge lookup fails
- **PR #599**: sim+docs: grade the period-jitter margin whose obstacle was the operand order, not the evidence (issue #237)
- **PR #598**: signoff: name and record T1 item 6's klt yield gap
- **PR #596**: sim+docs: the last §5 row excused as "not a record" had 45 points of committed evidence (issue #237)
- **PR #593**: sim: restore the execute bit its own "# Usage:" line promises, and grade the whole check family for it
- **Issue #622** (closed): sim/vco-tuning-range: the band-select mirror Monte Carlo samples 2 of 45 PVT points — the last T1 item 6(d) gap after #597
- **Issue #620** (closed): Remove duplicated reference_netlist() comment boilerplate across 8 leaf-cell files
- **Issue #617** (closed): docs(design): the term-4 bullet in the mismatch-budget section still quotes the superseded 3-point axis (0.864 / 0.871 / 1.39 ns), contradicting the comparison table 37 lines above it
- **Issue #614** (closed): sim: the new switches-note guard misses an unquoted `sw_stat_mismatch=1` shell override, and does not pin `simenv_provenance`'s default at all
- **Issue #611** (closed): sim: the recorded-seed reproducibility claim is host-scoped — the same rndseed draws a different Monte Carlo sample on a different host, and nothing says so
- **Issue #610** (closed): spec: re-price DR-018's reference-spur charge stack — term 3's statistical residual is 5.57 fC at the widened corner axis, not the 4.25 fC the derivation assumes
- **Issue #606** (closed): sim: DR-033's in-band period-jitter bound is quoted in a graded §5 row but absent from the value-provenance manifest — its figures are ungated where DR-032's are
- **Issue #605** (closed): docs: main CI is red — challenge-5-proposal §5 still annotates `#580 (open)` after DR-033 closed it, and random-bound/README.md still calls it the owner
- **Issue #602** (closed): sim: T1 item 6 also fails sub-criterion (c) — the negative control is prose-only for mc-cp-mismatch and absent for vco-tuning-range, and #597 scopes only (d)
- **Issue #601** (closed): sim: every Monte Carlo CSV says "sw_stat_mismatch=0 -> no Monte Carlo" — simenv_provenance never got the override simenv_env_block has
- **Issue #597** (closed): sim: T1 item 6 fails on corner combination and is unowned — the 3-of-45 Monte Carlo subset has no ratified justification, and #482 closed on the samples-per-corner half
- **Issue #595** (closed): docs: check-issue-reference-state.sh's honest SKIP reports the reason as "{" — and its own stub gh is the one shape where that expression works
- **Issue #594** (closed): signoff/: T1 item 6's machine-checkable evidence (a `klt yield` JSON report) is absent, unrecorded, and unreachable from the pinned klt install
- **Issue #580** (closed): sim/period-jitter: bound the random jitter of the in-band generators (charge pump, PFD, divider, lock detector) the VCO-side bound does not inject

### 2026-09-26

- **PR #592**: sim: the noise-referral gap's owner closed on a bound, so the row narrates it as history instead of naming it open (issue #237)
- **PR #591**: sim+spec: bound the random period jitter at all 45 corners -- at most 0.338 % RMS, 1.48x inside its 0.50 % allocation (DR-032)
- **PR #590**: signoff: re-derive item 11's paragraph against PR #587's 4-of-4 ERC evidence
- **PR #589**: sim+docs: grade the last two §5 figures whose only obstacle was the grading language — a magnitude bound and a ratio of two measurements (issue #237)
- **PR #587**: layout: extend klt erc supply evidence to 4 of 4 blocks, on the pinned klt, and gate it
- **PR #586**: spec+docs: re-derive the reference-spur charge totals' last three ingredients (Icp, T_ov, systematic asymmetry) from their own campaigns (issue #573)
- **PR #585**: sim: fail a reduction that names a column its evidence does not have, instead of silently matching zero rows
- **PR #584**: sim+docs: grade the reference spur's two cold corners as distances from the ratified line, which meant §5 writing a range as two figures (issue #237)
- **PR #583**: sim+docs: fail adjacent-overlap on a gapped axis run, and write down the unit-spacing it requires (issue #566)
- **PR #582**: sim+docs: grade the two §5 figures that are a measurement over a ratified line, and refuse a range as a figure (issue #237)
- **PR #581**: sim+docs: grade the Supply sensitivity — DC row's own UNMET verdict and every figure its three findings rest on (issue #237)
- **PR #578**: sim+docs: three §5 rows were ungraded because "no CSV" was read as "no evidence" — grade them against the per-point tables the records committed all along (issue #237)
- **PR #577**: signoff: grade against klt 0.6.0's bundled checklist and correct the stale README (issue #564)
- **PR #576**: layout: extract shared metal-connectivity l2n setup into vco/primitives.py
- **PR #575**: sim+docs: grade the one §5 figure that is a statistic, not an extremum — term 1's signed |mean|+3σ (issue #237)
- **PR #574**: spec: grade the reference-spur charge totals against sim/mc-cp-mismatch's own raw samples (issue #237)
- **PR #572**: docs+spec: make section 5's unmet roll call the table's UNMET set, and machine-check it (issue #237)
- **PR #571**: test: dedup layout/tests' sys.path/klayout-availability boilerplate into _env.py
- **PR #569**: sim: build the ISF route's other two ingredients and measure the stationary-approximation bound #520's option (B) was refused for want of (DR-031)
- **PR #568**: spec+docs: grade the derived spur figures too — the reference-spur hand derivation now reproduces itself in CI (issue #237)
- **PR #563**: sim+docs: grade the two Output band figures that are curve properties, and make the ungraded-figure list an artefact CI maintains (issue #237)
- **PR #562**: spec+sim: reference-phase-transfer ran the lock detector at effective code 0, and a CI check now grades records against their own netlist snapshots
- **PR #561**: spec: re-point the Lock detector owed cell off #527's closure — route 1 is measured and does not work, route 2 is the only candidate left and is unowned (issue #558)
- **PR #560**: sim+docs: grade the measured value itself — re-derive every quoted §5 figure from the cited record's committed CSV (issue #237)
- **PR #559**: sim: bring up the ISF route's Γ ingredient and show it converges — #520's load-bearing risk is retired, the gap moves to the other two ingredients (DR-030)
- **PR #556**: docs: close out the REF phase-step bisection with DR-029's negative result instead of owing it to closed #527
- **PR #535**: sim: measure the 20·log₁₀(N) reference-to-output phase transfer the source-quality exclusion asserts, and fix three batch-backend defects it exposed (DR-027)
- **Issue #588** (closed): signoff/README.md item 11 cites the now-closed #565 as its open owner, failing check-issue-reference-state.sh on every PR
- **Issue #579** (closed): check-quoted-value-provenance.sh: a reduction naming a nonexistent column silently matches zero rows instead of failing
- **Issue #573** (closed): Re-derive the reference-spur charge totals' last three ingredients (Icp, T_ov, systematic asymmetry) from their own campaigns
- **Issue #570** (closed): Extract shared metal-connectivity l2n setup from block.py and mirror.py
- **Issue #567** (closed): Dedup layout/tests' sys.path.insert + klayout.db-availability boilerplate into a shared helper
- **Issue #566** (closed): check-quoted-value-provenance: adjacent-overlap skips a gapped axis step instead of failing, and its unit-spacing requirement is undocumented
- **Issue #565** (closed): T1 item 11 (power delivery): no open owner, 1 of 4 blocks ERC-checked, and the committed spec's rationale cites a fixed upstream bug
- **Issue #564** (closed): signoff/: the vendored T1 checklist and its README have both gone stale against the klt 0.6.0 CI pins
- **Issue #558** (closed): spec/pll.md: the Lock detector owed-table cell still names closed #527 as a live route and owner after DR-029 closed it negative
- **Issue #557** (closed): sim/reference-phase-transfer: all three records ran the lock detector at code 0 (pre-DR-026 netlist), not the programmed code 8 -- the 'lock does not assert' remark is about the wrong code
- **Issue #554** (closed): docs: check-issue-reference-state.sh is red on main — challenge-5-proposal.md:320 owes work to closed #527
- **Issue #520** (closed): sim/period-jitter: measure the random (noise-driven) component, or record that this toolchain cannot — the calibration input exists, the cyclostationary bridge does not
- **Issue #509** (closed): sim: the reference-source-quality exclusion has no measured transfer and no owner — no testbench perturbs the REF edge in time

### 2026-09-25

- **PR #555**: fix: collect each batch job's outputs into its own per-job directory
- **PR #553**: sim: correct the stale vco-tuning-range band-0 verdict and grade the aggregation's reverse direction
- **PR #552**: sim+spec: the REF phase-step bisection measures the wrong quantity — DR-022 route 1 closed with a negative result (DR-029)
- **PR #551**: sim: correct stale "32-port" to "36-port" in testbench header comments (issue #539)
- **PR #550**: spec: ratify the batch image's ngspice-42 divergence from the ngspice-46 pin (DR-028)
- **PR #548**: docs: re-point the Chipalooza proposal's #510 reference off its closure (issue #237)
- **PR #547**: design: connect the lock-detector trim MSB at pll_top, and correct what the ff cell measured (DR-026)
- **PR #545**: docs: re-point the Chipalooza proposal's #511 references off its closure (issue #237)
- **PR #543**: sim: grade the non-MOS-axis and non-rectangular-sample grid claims (issue #516)
- **PR #541**: spec: eliminate band selection as the Lock-criterion resolution, on measurement (DR-025)
- **PR #538**: docs: grade the sim/ reports' issue owners too, and re-point three stale ones off closed #505 (issue #237)
- **PR #537**: feat: declare the 200 MHz reference-spur campaign and re-point its owed spec row
- **PR #532**: sim: grade what the proposal says about how the bias pins are driven, and the Limitations it quotes (issue #237)
- **PR #531**: docs: grade the Challenge slot budget's totals against the pad table's own rows (issue #237)
- **PR #530**: layout: grade spec/pll.md's own Area section against the footprint audit (issue #237)
- **PR #529**: spec: measure whether the pads can execute the lock-detector trim rule, and record that they cannot (DR-022)
- **PR #526**: sim: grade supply-sensitivity's three FAILing criteria against the ratified spec lines, and give each an open owner (issue #506)
- **PR #524**: sim: grade the reproduction commands a document offers as its own proof (issue #237)
- **PR #523**: sim: grade that a row claiming the whole mandated PVT grid cites evidence covering it
- **PR #522**: spec: give the random period-jitter component a live owner, and locate the gap that kept it unmeasured (DR-020, issue #505)
- **PR #521**: spec: give the random half of the period-jitter row an owner and a written-down reason it has no number (DR-020, issue #505)
- **PR #519**: sim/harness: stop handing subprocess.run the same keyword twice on batch launch (issue #512)
- **PR #518**: sim: measure the REF input contract instead of budgeting it — campaign declared, batch submission path repaired, spec row re-pointed off a closed issue (issue #499)
- **PR #517**: sim: grade the grid a row's evidence sits on, not just the grid its quoted corner sits on (issue #237)
- **PR #514**: sim: grade which PVT grid a quoted corner belongs to, and name the superset four proposal rows were measured on (issue #237)
- **PR #513**: spec: grade that the proposal carries the decision records each spec row rests on, and report three it did not
- **PR #508**: docs: grade the proposal's issue references against the forge, and re-point four dead owners
- **PR #504**: sim/harness: an off-host execution backend, so a 45-point closed-loop grid can be run at all (#496)
- **PR #502**: docs: grade the proposal's I/O list against the exported port list, and give the bench plan the two pins it never named (issue #237)
- **PR #500**: spec: grade the proposal's spec table for row coverage, and report the omitted Reference input row
- **Issue #546** (closed): docs: multiple '#511' citations still say (open) after #541 closed it, breaking check-issue-reference-state.sh on main
- **Issue #544** (closed): sim/CHARACTERIZATION.md still reports band 0's mismatch finding as open two days after the record that closed it landed — and nothing grades the aggregation's reverse direction
- **Issue #539** (closed): sim: two closed-loop spur decks claim a "32-port instance line" where cloop_instance produces 36
- **Issue #536** (closed): sim: the batch job image runs ngspice-42 while this repository pins ngspice-46 — batch-executed records are not comparable with the rest of sim/
- **Issue #528** (closed): docs: check-issue-reference-state.sh is red on main — the proposal names #505 and #506 as owners, both closed today
- **Issue #527** (closed): sim: characterize the symmetric REF phase-step bisection — the one pad-referred route to the lock-detector trim rule that needs no design change
- **Issue #516** (closed): sim: grade the two grid-shape claims the PVT coverage check still takes on trust (non-MOS corner axes, non-rectangular cross-products)
- **Issue #515** (closed): pll_top leaves the lock-detector trim MSB (LDT3) unconnected — only 8 of the rule's 16 codes are reachable
- **Issue #512** (closed): sim/harness batch backend: every real submission dies with `TypeError: subprocess.run() got multiple values for keyword argument 'capture_output'`
- **Issue #511** (closed): design: the loop misses the ratified <= 1 ns Lock criterion at 2 of 45 corners (DR-012) and no issue owns the design resolution
- **Issue #510** (closed): sim/reference-spur: the 200 MHz binding point and 40 of 45 PVT points have no owner — spec names the closed #145, and DR-018 left 1.6 dB of margin
- **Issue #507** (closed): sim/harness: BatchBackend can misattribute logs/rc/host across concurrent points sharing a rundir
- **Issue #506** (closed): sim/supply-sensitivity: the three FAILing criteria are routed to #9/#10/#11, all closed — the findings have no open owner
- **Issue #505** (closed): sim/period-jitter: the random/noise-driven component has no open owner — #13 closed and three documents still name it
- **Issue #501** (closed): Lock-detector window trim rule has no stated route to execution on silicon (its measurand is an internal node)
- **Issue #496** (closed): sim/period-jitter-band-top: 0 of 45 points measured — the harness has no batch/remote backend to run it on fleet hardware

### 2026-09-24

- **PR #498**: sim: grade cited evidence against the supersession graph, and re-point four stale citations
- **PR #497**: docs(status): grade the aggregation report's own record count, not its rows alone
- **PR #495**: docs(status): grade every occurrence of a drawn/LVS count, not just its first
- **PR #494**: ci(signoff): bump klt pin to 0.6.0 and re-render the tier report
- **PR #492**: docs(status): grade the stated block footprints against the area audit, not memory
- **PR #445**: docs(status): grade every absence-of-layout claim, not three remembered sentences
- **Issue #493** (closed): signoff/run-signoff.sh --check fails locally on klt 0.6.0: bump the CI pin and re-render the tier report deliberately

### 2026-09-23

- **PR #491**: spec(DR-018 A1): reference-spur "measured" term-1 row follows the signed statistic (17.4798 %, ≈ −57.0 dBc)
- **PR #489**: sim(mc-cp-mismatch): report term 1 as a real 3σ, not a fold-then-tail (13.22 % → 17.48 %) (issue #487)
- **PR #488**: spec(DR-018): derive charge-pump term 1's mismatch budget from the −55 dBc spur line, ±12 % → ±20 % (issue #483)
- **PR #486**: layout: give the nine leaf cells' duplicated CLI main() one shared home (issue #485)
- **PR #484**: sim(mc): raise Monte Carlo n per corner — term 1's 2.3% budget margin was sampling noise and does not survive (13.22% vs ±12%)
- **PR #481**: spec: refresh the area row's measured table to the committed GDS and hold the row at 0.30 mm² (DR-017, issue #476)
- **PR #480**: layout: consolidate the four duplicate pad_center() copies into _canvas.py
- **PR #478**: layout(pfd_cp): interleave cp_output_stage's glue inverters with the switches they drive — 26,406 → 25,630 µm² (−2.9 %) (issue #473)
- **Issue #490** (closed): spec(pll): the reference-spur table's "term 1 at its measured 13.2172 %" row quotes the statistic #487 replaced (17.4798 % signed → ≈ −57.0 dBc)
- **Issue #487** (closed): sim(mc-cp-mismatch): term 1's `mean(|x|) + 3·sd(|x|)` on folded samples is not the 3σ the budget table's header claims (13.22 % folded vs 17.48 % signed)
- **Issue #485** (closed): Consolidate duplicated leaf-cell CLI main() boilerplate
- **Issue #483** (closed): spec: charge-pump term 1 exceeds its stated ±12 % mismatch budget at adequate sample size (13.22 % worst corner, 4.4σ out) — needs a decision record
- **Issue #482** (closed): sim: Monte Carlo campaigns are not corner-combined enough to score T1 item 6 (3-of-45 corners at n=2, and the VCO band-0 record is nominal-only)
- **Issue #476** (closed): Spec: refresh spec/pll.md#area's measured table after #458 (0.2733 -> 0.2267 mm2), via a DR-016 successor record
- **Issue #475** (closed): Consolidate duplicated pad_center() into _canvas.py
- **Issue #473** (closed): Layout: interleave cp_output_stage's glue inverters with the switches they drive (the placement half of the glue band's 13-track clique)

### 2026-09-22

- **PR #477**: layout(divider_chain): route both levels' Metal2 tracks into the plane over the device rows — 92,618 → 55,329 µm² (−40.3 %)
- **PR #474**: layout(pfd_cp): pack cp_output_stage's glue-bus track band — 26,665 → 26,406 µm² (issue #469)
- **PR #472**: spec: amend the area row to 0.30 mm² on the measured post-lever total (DR-016)
- **PR #471**: layout(lock_detector): pin the block LVS verdict with a test, re-derived on a second KLayout (issue #440)
- **PR #470**: layout(pfd_cp): fold pfd into cp's own empty band and pack the trunk band — 35,281 → 26,665 µm² (−24.4 %)
- **PR #468**: spec: add a Consumers section and a structured integrator manifest
- **PR #466**: layout(lock_detector): draw DR-014's trim network, block now LVS-matched
- **Issue #469** (closed): Layout: pack cp_output_stage's glue-bus track band (the 9,744 um^2 #455 left below pfd_cp's own level)
- **Issue #465** (closed): 2am: reuse rule 9 — this block's consumers are not in its spec; gf180-tmds-tx needs ≥270 MHz against a 10–200 MHz band
- **Issue #458** (closed): Layout: route the divider chain's remaining Metal2 tracks over its device rows (-54 % area ceiling)
- **Issue #456** (closed): Spec: amend or close spec/pll.md#area once the measured post-lever floor exists
- **Issue #455** (closed): Layout: fold pfd_cp and route its track band over its own cells (-58 % area ceiling)
- **Issue #449** (closed): Layout: lock_detector's delaywin has no DR-014 trim network — LDT0-3 missing entirely, blocks LVS-clean
- **Issue #440** (closed): Layout: block-level LVS for pfd_cp and lock_detector (the two blocks with no LVS claim)

### 2026-09-21

- **PR #464**: layout(floorplan): regenerate the skeleton artifact and register it against its generator (issue #461)
- **PR #462**: layout(lock_detector): make the riser router a DRC model, and guard every committed GDS against its generator (issue #451)
- **PR #460**: layout: extend #452's inherited-label guard to divider_chain, and to Metal2 pin purposes
- **PR #459**: layout(divider_chain): pack the div23_cell macro's own track band — 2.03x to 1.70x (issue #454)
- **PR #457**: layout: measure where every drawn block's area goes, and size each remaining area lever
- **PR #452**: layout(pfd_cp): root-cause the block LVS mismatch to stray net labels — now matched
- **PR #450**: layout: block-level LVS attempt for pfd_cp and lock_detector
- **PR #447**: docs(spec): expose the lock-detector window trim in the Challenge #5 pad table
- **PR #443**: docs(status): make the README/proposal layout claims match the tree, and CI-check them
- **Issue #463** (closed): Rebase PR #459 (issue #454 div23_cell track-packing) onto main past PR #460's divider_chain relabeling — regenerate GDS/DRC/LVS, not a text merge
- **Issue #461** (closed): Layout: floorplan-skeleton's committed GDS does not reproduce from skeleton.py — the plan moved three times without it
- **Issue #454** (closed): Layout: route the divider chain's Metal2 track bands over its device rows, not above them (-45 % area ceiling)
- **Issue #453** (closed): Layout: extend #452's inherited-label guard to divider_chain, and to Metal2 pin purposes
- **Issue #451** (closed): Layout: lock_detector's committed GDS no longer reproduces from its generator, and the current generator is not DRC-clean (141 violations)
- **Issue #448** (closed): Layout: pfd_cp block-level LVS mismatch (84/93 nets, 69/168 devices) — root-cause and fix
- **Issue #441** (closed): Challenge #5 pad table has no way to set the normative lock-detector window trim (LDT3:LDT0)

### 2026-09-20

- **PR #438**: layout(vco): feed every n-well from the VDD_VCO trunk, not every sub-block (issue #433)
- **PR #436**: sim(supply-sensitivity): measure DR-013's window-vs-offset crossing inside one closed loop
- **PR #435**: test(layout): guard _canvas.NetTracks' pitch against METAL2_TRACK_PITCH_UM drift
- **PR #434**: layout(vco): land the first klt erc supply spec + report (T1 item 11, issue #427)
- **PR #431**: feat(signoff): commit a klt block manifest so this block's T1 state is graded, not hand-read
- **PR #430**: refactor(layout): consolidate NetTracks into _canvas.py
- **PR #426**: fix(supply-sensitivity): give each window-trim code its own work directory
- **Issue #433** (closed): vco_block: klt erc reports VDD_VCO as 3 disconnected islands despite a clean 43/43-net LVS match — needs investigation (T1 item 11)
- **Issue #432** (closed): NetTracks' pitch default is now a bare 0.75 literal, severing the per-module METAL2_TRACK_PITCH_UM binding that _canvas.v_wire deliberately preserves
- **Issue #429** (closed): Consolidate 4 byte-identical NetTracks classes into _canvas.py
- **Issue #428** (closed): Commit a klt signoff block manifest so this block's T1 state is graded, not hand-read
- **Issue #427** (closed): T1 item 11 (power delivery, structural): no klt erc supply spec or report in this repo
- **Issue #425** (closed): sim/supply-sensitivity: the lock-detector trim code is not in the work-directory tag, so two trim codes of one corner overwrite each other
- **Issue #417** (closed): [Parent #411] sim/supply-sensitivity re-run at the trimmed lock-detector window

### 2026-09-19

- **PR #424**: fix(simenv): stop the OMP pin from collapsing simenv_jobs() to 1
- **PR #423**: ci: pin pdk-checks' xschem to 3.4.7 instead of apt's drifting package
- **PR #420**: ci: run pdk-checks on any PR that touches design/, and declare the ci:full label
- **PR #418**: Implement the lock-detector window trim (DR-014) and re-characterize T1'-T5: both targets now met
- **Issue #422** (closed): sim/lib/simenv.sh: simenv_apply_omp_pin collapses simenv_jobs() to 1, serializing every campaign that opts into the OMP pin
- **Issue #421** (closed): CI: nightly pdk-checks has been red on main since at least 2026-09-14 — runner's xschem is 3.4.4, the committed netlists were generated with 3.4.7
- **Issue #419** (closed): CI: the ci:full opt-in label doesn't exist, so pdk-checks (netlist drift) can never run on a PR
- **Issue #411** (closed): [Parent #407] Implement the lock-detector trim mechanism and re-characterize T1'-T5

### 2026-09-16

- **PR #416**: cp_dumpbuf riser helpers: alias RISER_MIN_PITCH_UM to cp_array's and pin the cp_dumpbuf: error prefix with a test
- **PR #414**: refactor(pfd_cp): consolidate cp_dumpbuf's duplicated riser-column helpers into cp_array
- **PR #412**: Lock-detector window spread: size the T2' miss, pick the trim mechanism (DR-014)
- **PR #410**: fix: avoid SIGPIPE false-negative in verify-proposal-refs.sh full_tree check
- **PR #408**: spec: DR-013 — T2′'s reach stays at 2×, the lock-detector window's PVT spread comes down instead (#401)
- **PR #406**: fix(sim/pll-top-smoke): gate check 2 on the ratified absolute Lock criterion
- **PR #404**: sim(supply-sensitivity): testable re-lock phase-trace instrumentation, repointed at the post-DR-010 lock-detector record (#395)
- **PR #403**: Reconcile the static phase offset against the ratified Lock criterion: the axis is Vctrl, not the corner (#394)
- **PR #402**: feat(design,layout,sim): implement DR-010 lock-detector resize, re-characterize T1'/T2'
- **Issue #415** (closed): cp_dumpbuf riser helpers: alias RISER_MIN_PITCH_UM to cp_array's and pin the cp_dumpbuf: error prefix with a test
- **Issue #413** (closed): Consolidate duplicated declutter_riser_x/_verify_riser_plan/check_riser_columns: cp_dumpbuf ported verbatim from cp_array
- **Issue #409** (closed): verify-proposal-refs.sh: pipefail + grep -qFx SIGPIPE gives false MISSING FILE for real paths
- **Issue #401** (closed): DR-010's W=9.5um lock-detector fix meets T1' but exceeds T2' under in-situ re-characterization (#393)
- **Issue #400** (closed): pll-top-smoke gates the ratified static-phase criterion on a 2.2x looser per-period proxy (DR-012 Decision 5)
- **Issue #394** (closed): ff/125C/3.63V stands off 1.796 ns of static phase against a ratified 1 ns Lock criterion
- **Issue #393** (closed): Implement DR-010: re-size delaywin_3v3 to W = 9.5 um and re-characterize the lock detector

### 2026-09-15

- **PR #398**: feat(layout/pfd_cp): assemble pfd + complete cp block into pfd_cp, replace floorplan placeholder
- **PR #397**: feat(layout/pfd_cp): assemble cp_output_stage + cp_dumpbuf into complete cp block
- **PR #396**: lock_detector T1/T2 window gap + post-supply-step settling: DR-010/DR-011 (#387)
- **PR #392**: layout/pfd_cp: declutter cp_dumpbuf riser columns across nets (issue #391)
- **PR #390**: fix(sim/supply-sensitivity): correct the furthest-from-settled ranking
- **PR #388**: sim/supply-sensitivity: disambiguate the HIGH-plateau not-locked verdict (#384)
- **Issue #391** (closed): cp_dumpbuf.py: Metal1-3 riser columns collide across nets -- whole cell shorts to one net (netcheck-detected, DRC-invisible)
- **Issue #389** (closed): sim/supply-sensitivity record 20260915-105055-2d6ab99: inverted comparative in the ss/-40C 'furthest from settled' claim
- **Issue #387** (closed): lock_detector T1/T2 window gap + post-supply-step phase-settling tail, per-corner (from #384)
- **Issue #386** (closed): [Parent #294] Part 5b: Assemble PFD + complete cp block into pfd_cp, replace floorplan placeholder (depends on Part 5a #385)
- **Issue #385** (closed): [Parent #294] Part 5a: Assemble cp_output_stage + cp_dumpbuf into complete cp block (design/cp.sch)
- **Issue #384** (closed): sim/supply-sensitivity: LOCK flag never re-asserts on the high plateau after the 3.30 -> 3.63 V step at any sampled corner (3/3 `not-locked` at the escalated 40.08 us hold)
- **Issue #303** (closed): [Parent #294] Part 5: Integrate PFD+CP+dump-buffer into pfd_cp block, replace floorplan placeholder (depends on #300, #301, #302)
- **Issue #301** (closed): [Parent #294] Part 3: Charge-pump common-centroid N/P current-source array layout (depends on #299)
- **Issue #253** (closed): sim/supply-sensitivity: disambiguate criterion-3 (step/ramp) FAIL at ss/-40C(high) -- settling-budget artifact or genuine margin?

### 2026-09-14

- **Issue #233** (closed): refactor(sim): dedup read_columns() into vco-tuning-range's _numeric.py

### 2026-09-11

- **PR #382**: layout(vco): draw the bias resistors as the ppolyf_u_3k high-Rs device the schematic specifies (issue #381)
- **PR #380**: layout(vco): fix vco_block resistor LVS device class, reach clean vco_block LVS match (issue #378)
- **PR #379**: layout(vco): fix vtoi_core.py PMOS-row escape Metal1 short over VDD_VCO tap band (issue #376)
- **PR #377**: layout(vco): fix ring.py Metal1 shorts + VBP/VBN Metal2 trunk (issue #371)
- **PR #375**: layout(vco): dedup escape/jog_escape/rail_stub/_y_bottom between vtoi_core.py and mirror.py
- **PR #373**: layout(vco): fix buffer.py Metal1 shorts + device-to-guard-ring straps (issue #372)
- **PR #370**: docs: root-cause the vco_block LVS connectivity short (issue #368)
- **Issue #381** (closed): VCO bias resistors are drawn as unmarked ppolyf_u (350 ohm/sq) where the schematic specifies ppolyf_u_3k (3000 ohm/sq)
- **Issue #378** (closed): vco_block LVS: NC/NOFF/NVI spurious circuit pins + GND_VCO mismatch, newly exposed by #376's VBP0 fix
- **Issue #376** (closed): vco_block LVS: VBP0/VDD_VCO short, pre-existing, unrelated to ring.py/buffer.py
- **Issue #374** (closed): Dedup layout _Builder escape/jog_escape/rail_stub between vtoi_core.py and mirror.py
- **Issue #372** (closed): [Part of #368] Fix vco_block buffer.py: Metal1 shorts + missing device-to-guard-ring straps
- **Issue #371** (closed): [Part of #368] Fix vco_block ring.py: Metal1 shorts + missing device-to-guard-ring straps
- **Issue #368** (closed): layout: root-cause and fix a real connectivity short found by vco_block's first LVS attempt (issue #367)
- **Issue #367** (closed): layout: block-level LVS for the assembled VCO block (`vco_block.gds` vs `design/netlist/vco.spice`), reconciling the recorded cascade-B fold

### 2026-09-10

- **PR #369**: layout(vco): block-level LVS reference netlist + net-labelling fix (issue #367)

### 2026-09-09

- **PR #366**: layout: fix EN/ENB riser column short in cp_array (issue #359)
- **PR #365**: layout: dedup shorted_pairs()/disconnected_nets() connectivity checks into _canvas.py (issue #364)
- **PR #363**: fix: fail-loud KLayout version drift from LVS-evidence pin
- **PR #362**: lock_detector: converge RiserLanes on xor2's dense riser graph
- **PR #361**: layout: assemble the CP output stage — glue inverters, steering/dump switches (issue #321)
- **PR #358**: layout: fold divider_chain's six-instance row into two rows (issue #344)
- **PR #357**: refactor: consolidate duplicated v_wire() geometry helper into _canvas.py
- **PR #356**: ci: install klayout pip wheel in checks job so gated tests actually run
- **PR #355**: layout: remove dead m3_link() from pfd_cp/rowgen.py
- **PR #354**: layout: VCO band mirror — 2-D common-centroid array for cascades A/C (issue #336)
- **PR #351**: layout: CP N/P common-centroid array placement + bias branch (issue #320)
- **PR #348**: layout: fix lock_detector's Metal1/Metal3 riser routing to eliminate cross-net shorts (issue #322)
- **PR #346**: layout: pack divider_chain's top-level routing tracks, cut footprint 39% (issue #341)
- **PR #345**: layout: add a geometric verification gate for the VCO block n-well ring
- **PR #343**: layout: consolidate divider_chain/devgen.py's duplicated Canvas/_r into _canvas.py (issue #327)
- **PR #342**: layout: assemble the divider_chain block, reconcile DIVIDER_LOCK (issue #310)
- **PR #340**: refactor: consolidate duplicated pll_top geometry helpers into _canvas.py
- **PR #338**: layout: div23_cell composite macro layout, 8 sub-cells / 60 transistors (issue #309)
- **PR #337**: layout: fold the VCO band mirror into two banks + add the block-level n-well guard ring (issue #324)
- **PR #335**: layout: cp_leg_n/cp_leg_p charge-pump unit-leg composite device layout (issue #319)
- **PR #334**: sim/supply-sensitivity: dedup dend_at() into simenv_dend_at()
- **PR #331**: layout: divider_chain row cells nand2/nand3/nor2/inv2x (issue #307)
- **PR #330**: layout: dff_tg_3v3 composite flop layout, 6x inv_3v3 + 4x tgate_3v3 (issue #308)
- **PR #328**: layout: consolidate duplicated Canvas/_r layout helper (issue #317)
- **PR #326**: layout: dump-buffer isolated-n-well common-centroid layout (issue #302)
- **PR #325**: layout: assemble the whole VCO block (5 sub-blocks, one guard ring, issue #293)
- **PR #323**: layout: mirror-symmetric transistor-level PFD block layout
- **Issue #364** (closed): Dedup shorted_pairs()/disconnected_nets() connectivity-check helpers into _canvas.py
- **Issue #360** (closed): Local KLayout install newer than evidence (0.30.9 vs 0.28.16) produces false LVS mismatches
- **Issue #359** (closed): cp_array (#320) shorts B0/B0B and B1/B1B/VDD/VSS: declutter_riser_x collapses two different nets onto one riser column
- **Issue #353** (closed): Consolidate duplicated v_wire() geometry helper across pll_top submodules
- **Issue #352** (closed): Remove dead m3_link() in pfd_cp/rowgen.py: superseded by pfd.py's own _draw_link()
- **Issue #349** (closed): CI's headless checks job never installs klayout, so all @skipUnless(_HAVE_KLAYOUT) tests are skipped, not run
- **Issue #347** (closed): lock_detector: RiserLanes' Metal1 conflict-repair doesn't converge on xor2's denser riser graph
- **Issue #344** (closed): divider_chain: fold the six div23_cell row now that #341 packs routing tracks locally
- **Issue #341** (closed): divider_chain block footprint is 0.2471 mm^2 (2634x94 um) — a 2.9x whole-chip area overrun; reduce it
- **Issue #339** (closed): layout: no gate catches an n-well drawn over a block's own devices (DRC and connectivity both pass it)
- **Issue #336** (closed): layout: VCO band mirror — 2-D common-centroid array for cascade C (the remaining area lever after #324's row fold)
- **Issue #332** (closed): Consolidate duplicated bbox_union/_contact_positions/_via_square geometry helpers across pll_top submodules
- **Issue #329** (closed): sim/supply-sensitivity: dedup dend_at() into simenv.sh
- **Issue #327** (closed): Fourth duplicate Canvas/_r in divider_chain/devgen.py, not covered by #317
- **Issue #324** (closed): layout: VCO block — fold single-row sub-blocks into multiple rows, add block-level n-well guard-ring band
- **Issue #322** (closed): lock_detector layout: route_net()'s Metal3 risers short VDD to VSS (114 cross-net overlaps, invisible to DRC)
- **Issue #321** (closed): [Parent #301] Part 3c: CP glue inverters + steering/dump switches + output-stage assembly
- **Issue #320** (closed): [Parent #301] Part 3b: CP N/P common-centroid array placement + bias branch
- **Issue #319** (closed): [Parent #301] Part 3a: CP N/P unit-leg composite device layout (cp_leg_n / cp_leg_p)
- **Issue #317** (closed): Consolidate duplicated Canvas/_r layout helper across pll_top submodules
- **Issue #310** (closed): [Parent #295] Part 5: Assemble divider_chain block, replace floorplan placeholder (depends on #309, #308; coordinate with #296)
- **Issue #309** (closed): [Parent #295] Part 4: div23_cell composite macro layout (depends on #307, #308)
- **Issue #308** (closed): [Parent #295] Part 3: dff_tg_3v3 composite flop layout (depends on #306)
- **Issue #307** (closed): [Parent #295] Part 2: Remaining divider-chain leaf cells (nand2_3v3, nand3_3v3, nor2_3v3, inv2x_3v3) (depends on #306)
- **Issue #302** (closed): [Parent #294] Part 4: Dump-buffer isolated-n-well common-centroid layout (depends on #299)
- **Issue #300** (closed): [Parent #294] Part 2: PFD mirror-symmetric transistor-level layout (depends on #299)
- **Issue #295** (closed): Layout: real transistor-level layout for the divider_chain block
- **Issue #293** (closed): Layout: real transistor-level layout for the VCO block (ring + bias gen + band-select mirror + output buffer)

### 2026-09-08

- **PR #318**: layout: full-custom device-layout methodology proof (divider_chain inv_3v3/tgate_3v3, issue #306)
- **PR #316**: layout: VCO bias-generator V-to-I core (13 transistors, issue #293)
- **PR #315**: docs(sim): investigate 131 non-rail-excursion relock FAILs (#284)
- **PR #314**: layout: ppolyf_u_3k poly-resistor primitive + VCO bias-generator resistors (#293)
- **PR #313**: layout: VCO band-select mirror (common-centroid) + 3-stage output buffer
- **PR #312**: layout: full-custom device-layout methodology proof (PFD/CP pfdcp_inv_3v3, issue #299)
- **PR #311**: layout: real transistor-level layout for the lock_detector block
- **PR #305**: layout: real transistor-level VCO ring block (5-stage ring + guard ring + decap)
- **PR #298**: sim/vco-tuning-range: dedup run.sh's bundle_libs()/f_est() into common.sh
- **PR #291**: test: dedup assert_contains() into test_helpers.sh
- **PR #289**: layout: PLL floorplan record + block-placement GDS skeleton
- **PR #288**: docs: cite the landed #13 closed-loop period-jitter grid
- **PR #286**: docs: cite the landed #163 lock-time grid instead of the stale not-yet-taken gap
- **PR #283**: spec: ratify spec/pll.md v1 with amendments, per DR-007
- **Issue #306** (closed): [Parent #295] Part 1: Full-custom device-layout methodology + DRC/LVS proof (divider-chain inv_3v3 + tgate_3v3)
- **Issue #304** (closed): Layout: real transistor-level layout for the VCO bias generator, band-select mirror, and output buffer
- **Issue #299** (closed): [Parent #294] Part 1: Full-custom device-layout methodology + DRC/LVS proof (one representative PFD/CP leaf cell)
- **Issue #296** (closed): Layout: real transistor-level layout for the lock_detector block
- **Issue #290** (closed): sim/vco-tuning-range/testbench/run.sh duplicates common.sh's bundle_libs() and f_est() instead of sourcing it
- **Issue #287** (closed): Dedup assert_contains(): test_simenv_ngspice_pin.sh vs test_simenv_run_deck_retried.sh have swapped argument order
- **Issue #285** (closed): spec/pll.md's period-jitter row and Verification-owed table are stale against the already-landed closed-loop period-jitter grid
- **Issue #284** (closed): sim/lock-time: 131 non-rail-excursion relock FAILs unattributed -- window-limited or genuine convergence defect?
- **Issue #282** (closed): sim/CHARACTERIZATION.md and spec/pll.md's lock-time row are stale against the already-landed #163 cold-start grid
- **Issue #17** (closed): Layout: floorplan (VCO isolation, supply routing, loop-filter cap, guard rings)
- **Issue #13** (closed): Testbench: period jitter at transistor level, with ngspice methodology limits recorded
- **Issue #1** (closed): Ratify the target spec

### 2026-09-06

- **PR #281**: refactor(sim): dedup supplies_of() across period-jitter, period-jitter-band-top, reference-spur
- **PR #279**: sim: make the closed-loop ferr lock gate wrap-safe, and re-measure the two corners it falsely failed
- **PR #278**: sim/period-jitter: close the fs and sf temperature x supply planes, completing the 45-point matrix
- **PR #277**: sim/lib: dedup check_config.sh field/instance-line verification helpers
- **PR #275**: sim/period-jitter: close the ff and ss temperature x supply planes
- **PR #274**: fix: keep a per-point log-write failure from discarding a whole grid run
- **PR #272**: fix: --check-env warns instead of OK on ngspice-47 (#153)
- **PR #269**: sim: declare period-jitter at the 200 MHz top of the band, and report what its derivation already found (part of #237, #13)
- **PR #267**: sim/period-jitter: open the temperature and supply axes (part of #237, #13)
- **PR #266**: sim/harness: budget ngspice's internal threads against -j fan-out (part of #237)
- **PR #265**: sim: extend period-jitter to the process-corner extremes (part of #237)
- **Issue #280** (closed): refactor(sim): dedup supplies_of() across period-jitter, period-jitter-band-top, reference-spur
- **Issue #276** (closed): Dedup check_config.sh boilerplate: reference-spur vs period-jitter-band-top
- **Issue #273** (closed): sim/period-jitter: the ferr lock gate is not wrap-safe and fails two locked corners
- **Issue #271** (closed): sim/harness: one failed per-corner log write discards every completed point of a grid run
- **Issue #268** (closed): sim/harness: run_corners.py --check-env reports ngspice-47 as OK on a host where no closed-loop campaign can run (#153)
- **Issue #264** (closed): Champion: Merge-Risk Hold Digest
- **Issue #240** (closed): Champion: Merge-Risk Hold Digest
