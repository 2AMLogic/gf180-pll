#!/usr/bin/env bash
# gf180-pll :: supply-sensitivity :: campaign settings and shared helpers
#
# The ONE place the campaign's settings are declared: the operating point,
# the transient and step/ramp profiles and their escalation budgets, the
# in-loop calibration constants, the acceptance thresholds, the cited
# records, and the two window-trim helpers (window_trim_code_of /
# window_trim_tag_suffix) that turn the trim setting into a code and a
# work-directory tag suffix.
#
# Sourcing contract: every consumer -- run.sh, report.sh, reexamine.sh --
# sources this file AFTER it has established ROOT and loaded
# sim/lib/simenv.sh, because VCO_TUNING is rooted at ${ROOT} and the KTMAX
# guard below reads ${SIMENV_CLOSED_LOOP_TMAX}.  A threshold change is made
# here once and is then what all three processes apply and quote -- no
# reader re-derives settings by parsing another script's text.
#
# SC2034 ("appears unused") is disabled for this file: each constant is
# consumed by at least one of the three sourcing scripts, and shellcheck
# reads this file on its own.  The assignments are deliberately not
# exported -- every consumer must read what THIS FILE declares, not
# whatever happens to be in the environment (a sourced assignment
# overwrites an inherited variable of the same name; an exported one would
# let the environment pre-empt the record's stated criterion).
# shellcheck disable=SC2034
# shellcheck shell=bash

# ---------------------------------------------------------------------------
# The operating point, and where every number comes from.
# ---------------------------------------------------------------------------
# KFOUT   100 MHz output -- the frequency #14's power criterion names, and
#         inside DR-002 Decision 2's ratified 10-200 MHz v1 band.
# KN      N = 8, mid of the ratified 4-64 range (DR-001 Decision 3).
# KFREF   12.5 MHz reference (= 100 MHz / 8), inside DR-002 Decision 1's
#         ratified 1-25 MHz range.
# KTRIM   Icp trim code 2 (three unit legs), the nominal setting
#         design/README.md characterises the charge pump at, and the setting
#         sim/loop-dynamics shows meeting both the 45 deg phase-margin
#         criterion and the f_c < f_ref/10 ceiling across the 8-16 MHz
#         reference decade this operating point sits in.
KFOUT=100e6
KN=8
KFREF=12.5e6
KTRIM=2
# Lock-detector window trim code (DR-014, #411).
#
#   rule     program each corner bundle at the code `spec/pll.md`'s
#            [Lock-detector window trim-code rule] selects for it -- i.e. run
#            the loop against the window a REAL part of that bundle would
#            carry.  This is the default, and it is what makes this campaign's
#            `lock` column a statement about the shipped detector rather than
#            about an arbitrary code.
#   <0..15>  force one fixed code at every corner.  `8`, the centre code, is
#            what every OTHER closed-loop campaign in the tree runs (see
#            CLOOP_WINDOW_TRIM_NOMINAL); forcing it here reproduces the
#            untrimmed-comparison rows.
#
# Which code the rule selects is sim/lock-window-trim's measured answer, not
# this file's -- window_trim_code_of() below is a transcription of that
# record's code table and cites it.
KWINTRIM=${SIM_WINTRIM:-rule}

# window_trim_tag_suffix -> the work-directory tag suffix this run's window-trim
# setting earns ("" at the default, "_W<code>" at a forced code).
#
# The trim code is a THIRD axis of the same kind as the transient length and the
# timestep ceiling below: moving it produces a different run of the same corner,
# which the campaign then wants to compare against the run it replaced.  The
# `.sig` guard already invalidates the cached run when the code changes, but
# invalidating it is not enough -- without a tag suffix the re-run lands in the
# SAME work directory and overwrites the ngspice.log of the run it is being
# compared with (#425).  So the suffix is what makes a trim-code cross-check ADD
# evidence rather than destroy it, exactly as "_X${KTSTOP}" does for a settling
# re-run.
#
# THE SUFFIX TAGS THE `KWINTRIM` SETTING, NOT THE PER-CORNER RESOLVED CODE
# (`window_trim_code_of`'s output).  Both were on the table; the setting wins
# for two reasons:
#
#   1. `rule` MUST stay unsuffixed.  Tagging the resolved code would rename
#      every default run's directory ("..._W3", "..._W7", ... per bundle) and
#      so force a full re-simulation of every `work/` tree already on disk --
#      hours of ngspice per corner, to rename directories holding runs that
#      are still perfectly valid.
#   2. Where a suffix IS emitted the two choices agree by construction:
#      window_trim_code_of() returns ${KWINTRIM} verbatim at every corner once
#      ${KWINTRIM} is a forced code, so "_W8" IS the resolved code of every run
#      under it.  The setting-vs-code distinction bites only in the `rule`
#      case, where the suffix is deliberately absent.
#
# What that costs, stated plainly rather than hidden: an unsuffixed directory
# means "the rule-selected code for this bundle", which is per-bundle rather
# than one code -- recoverable, since the bundle is in the tag and
# window_trim_code_of() maps it, and since the run's own `.sig` records the
# resolved code that was actually passed to the deck.  And forcing a code that
# the rule would have picked anyway (`SIM_WINTRIM=3` on `ss`) re-simulates into
# "_W3" beside an identical unsuffixed `rule` run: one redundant run, never a
# collision.  Losing a log is the failure worth designing against here; paying
# for an occasional duplicate one is not.
#
# report.sh reconstructs these same tags to archive each run's log, and picks
# this same function up from this file -- so the two cannot drift.
window_trim_tag_suffix() {
  if [ "${KWINTRIM}" = "rule" ]; then printf ''; else printf '_W%s' "${KWINTRIM}"; fi
}

# DR-013's window-vs-offset crossing, and the corners it is asked at (#417).
#
# DR-013 Decision 4 / §Consequences compared the lock flag's own window against
# the loop's settled static phase offset and found the window had risen PAST
# that offset at one corner and to within 6 % of it at another -- and said, in
# as many words, that the comparison was "inferred across two campaigns, not
# measured in one loop", because every committed row of THIS campaign was at
# the untrimmed W = 8 um cell and at a different f_ref from
# `sim/lock-detector`'s.  With the trim landed (DR-014, #411) the window has
# moved again, so the comparison has to be re-made -- this time with both
# halves of it read out of the SAME closed-loop transient.
#
# XING_PICKS names the `<bundle>|<temp>|<vdd>` cells the record answers that
# question at, and CITE_DR013_XING carries, per cell, WHAT DR-013 INFERRED, so
# that "confirmed / refuted / moved" is a comparison the record computes rather
# than a word someone types.  Fields, colon-separated:
#
#   <bundle>|<temp>|<vdd> : <crossed|not-crossed> : <window_ns> : <offset_ns>
#
#   crossed / not-crossed  DR-013's inference for that cell: did the flag's
#                          window sit ABOVE the loop's settled offset (so the
#                          flag would assert) or not?
#   window_ns              the in-situ window DR-013 read at W = 9.5 um
#                          (untrimmed), from `sim/lock-detector`.
#   offset_ns              the settled static phase offset DR-012 measured at
#                          that same cell, from THIS campaign's own committed
#                          grid at the untrimmed cell.
#
# Both numbers are DR-013's, transcribed so the record can print what it is
# being compared against; neither sets a verdict here.  What sets the verdict
# is this run's own `lock` column against this run's own `phi_b`.
XING_PICKS="${SIM_XING_PICKS:-typical|-40|3.63 ff|27|3.63}"
CITE_DR013_XING="typical|-40|3.63:crossed:1.140:1.049 ff|27|3.63:not-crossed:1.155:1.227"
# `sim/lock-detector`'s TRIMMED in-situ characterization (#411): the record
# whose `raw_measures.csv` carries t_win at the code the trim rule selects for
# each bundle.  Read, not re-derived; it is the independent magnitude beside
# this campaign's in-loop above/below verdict, and it is a DIFFERENT campaign
# at a DIFFERENT f_ref -- which is exactly the limitation #417 exists to stop
# the crossing verdict resting on, so the record labels it as corroboration
# and never as the measurement.
CITE_LD_RECORD=20260919-002812-1b12179

# Why this run is a subset of the default grid, in this run's own words.
#
# report.sh states a subset reason whenever fewer than 45 steady-state points
# were collected.  Until #417 that reason was one hardcoded paragraph
# describing ONE historical reduction (the 2026-08-01 run, which cut the
# process axis and kept temperature and supply whole).  Any later subset with a
# different shape -- #417's own two named cells, for instance -- would have
# been described by text that did not fit it, which is a record stating
# something untrue about its own coverage.  So the reason travels with the run
# that made the choice.  Unset falls back to that historical paragraph, so a
# re-run of the old reduction still describes itself correctly.
SUBSET_NOTE="${SIM_SUBSET_NOTE:-}"

# The SECOND frequency point, used only for the quiescent/dynamic power split
# (see "Quiescent vs. dynamic" below).  Same N, half the reference, so f_ref
# and f_out scale together and a two-point fit in f_out is unambiguous.
KFOUT2=50e6
KFREF2=6.25e6

# Transient controls, shared by every steady-state run.
# KTMAX   The ceiling on the ngspice INTERNAL timestep is NOT this campaign's to
#         choose: it is a property of the PFD every closed-loop deck in this repo
#         inherits, and it lives in one place -- `SIMENV_CLOSED_LOOP_TMAX` in
#         `sim/lib/simenv.sh`, documented in `sim/README.md`.  The bound is set
#         by `design/edgedet.sch`'s INTERNAL set pulse (0.33-0.39 ns), not by the
#         1.1-1.9 ns UP/DN OUTPUT pulse this campaign used to derive it from and
#         not by f_out; an integrator whose step is comparable to the set pulse
#         steps clean over it on a large fraction of feedback edges and the loop
#         reads as jammed with UP asserted -- a false "does not lock", not a
#         noisy one (#52/PR #64 measured it, #65/PR #75 hoisted it).
#         This campaign's previous 400 ps and its "set by the CHARGE PUMP"
#         rationale were reasoning from the output pulse, i.e. from the wrong
#         pulse, and are replaced here by the shared constant rather than by a
#         second derivation of it.  **The 9-corner record this campaign already
#         has on `main` (20260801-024935-c4fe724) was taken at 400 ps and is
#         therefore qualified by that bound**; re-examining it is #69's scope,
#         and nothing here edits it.
# KTSTOP  12 us.  Short because the warm start in tb_supply_lock.sp
#         pre-charges BOTH loop-filter nodes -- the control node AND the
#         series capacitor C1 that actually holds the loop's state -- so the
#         run does not contain an acquisition ramp.  (Pre-charging only VCTRL
#         costs 122 pF x V_lock / Icp = tens of microseconds of pure ramp at
#         every corner; that is a real trap and the deck documents it.)  What
#         is left is the residual settling of the loop's slowest pole,
#         1/(2*pi*R*C1) = 17.1 kHz => tau = 9.3 us, from whatever error the
#         predicted lock point carries.  KTA at 6.4 us and KTB at 9.6 us are
#         0.69 tau and 1.03 tau, so this record is NOT entitled to assume the
#         residual away: `ferr` measures it directly and the lock criterion is
#         applied to the measured value at every corner.  The run has 2.4 us
#         left after KTB for the frequency measurements (100 CLK cycles = 1 us
#         at 100 MHz, 2 us at 50 MHz; 10 FB cycles = 0.8 us / 1.6 us).
# KTA/KTB Both are whole multiples of 160 ns, which places them on a reference
#         HALF-period for BOTH reference frequencies (12.5 MHz: tstart = 40 ns;
#         6.25 MHz: tstart = 80 ns), so "the first REF rise after t" and "the
#         first FB rise after t" are the same cycle's pair at either setting.
#
# KTSTOP/KTA/KTB are OVERRIDABLE (`SIM_TSTOP`/`SIM_TA`/`SIM_TB`) because a
# corner reported as still converging has to be re-runnable at a longer
# transient instead of being reported as a design result.  KTSTOP_BASE is the
# unoverridden default, kept separately for two reasons: a run at a
# non-default length gets its OWN work directory (so the long run does not
# destroy the default-length run it is being compared against), and every
# emitted summary row carries the length it was actually run at, so the
# record's `tstop` column is per-row truth rather than a script constant.
KTSTOP_BASE=12.0u
KTSTOP="${SIM_TSTOP:-${KTSTOP_BASE}}"
KTSTEP=20n
# KTMAX_BASE is the shared closed-loop BOUND; KTMAX is what THIS invocation
# actually runs at.  They differ only under `SIM_TMAX`, whose one sanctioned use
# (`sim/lib/simenv.sh`) is a deliberate bound-sensitivity study -- and they have
# to stay distinguishable, because a run at a non-bound ceiling gets its own
# work directory and carries its ceiling in every summary row it emits, so that
# such a run can never be quietly mistaken for a compliant one.
#
# The literal is restated here rather than derived, because `simenv.sh` folds
# the SIM_TMAX override into `SIMENV_CLOSED_LOOP_TMAX` itself and there is then
# no expression left that yields the unoverridden bound.  The guard below makes
# the duplication safe: if the shared constant moves and this one does not, the
# campaign refuses to run rather than minting a record against a stale bound.
KTMAX_BASE=100p
KTMAX="${SIMENV_CLOSED_LOOP_TMAX}"
if [ -z "${SIM_TMAX:-}" ] && [ "${KTMAX}" != "${KTMAX_BASE}" ]; then
  echo "ERROR: KTMAX_BASE (${KTMAX_BASE}) has drifted from sim/lib/simenv.sh's" >&2
  echo "       SIMENV_CLOSED_LOOP_TMAX (${KTMAX}).  Update this settings file" >&2
  echo "       to the shared bound; do not mint a record against a stale one." >&2
  exit 1
fi
# The ceiling the cross-check re-runs at is the BOUND itself: the cross-check
# exists for the case where the grid was deliberately run coarser than the
# bound, and its job is to say whether that choice, rather than the loop, is
# what produced a lock-criterion failure.  When the grid already ran AT the
# bound the two are equal and the stage is a no-op, which is the normal case.
KTMAX_X="${SIM_FINE_TMAX:-${KTMAX_BASE}}"
KTA="${SIM_TA:-6.4u}"
KTB="${SIM_TB:-9.6u}"

# The settling escalation (see "Settling escalation" in Main).  A corner whose
# measured residual frequency error exceeds ACC_FERR at KTSTOP has NOT been
# shown to be a design failure -- it has been shown to be unsettled -- so the
# runner re-runs it automatically at KTSTOP_X and the record reports the pair.
# 36.8u is 3.96 KTAU with the late window at 3.35/3.70 KTAU, against
# 0.69/1.03 KTAU at the default length: an exponentially-settling loop drops
# its residual by e^-2.7 (~x0.07) between the two, and one that does not is
# not merely slow.  Both instants stay whole multiples of 160 ns, so they
# remain on a reference half-period for both reference frequencies.
KTSTOP_X="${SIM_EXTEND_TSTOP:-36.8u}"
KTA_X="${SIM_EXTEND_TA:-31.2u}"
KTB_X="${SIM_EXTEND_TB:-34.4u}"
# The loop's own settling time constant, 1/(2*pi*R*C1) = 17.1 kHz => 9.3 us,
# derived above.  Named here so report.sh states one number everywhere it
# compares a rate or a window against "the loop", rather than restating it.
KTAU=9.3u

# Supply step/ramp profile (criterion 3).  One transient carries both events.
# Both rates are stated against the loop's own settling time constant KTAU
# (9.3 us, see above) because that is the only timescale the loop has, and
# because #14's acceptance criterion requires the record to name the rates.
# KD_STEP  a 3.30 -> 3.63 V step with a 100 ns edge.  100 ns is KTAU/93, and
#          ~1/18 of the 1.76 us period of the nominal closed-loop crossover
#          (f_c ~ f_ref/22 = 570 kHz), so it is a step as far as the loop is
#          concerned, while staying slow enough that the rail is not a delta
#          function the integrator cannot resolve.
# KD_RAMP  3.63 -> 2.97 V over 6.4 us (16.0u..22.4u), i.e. 103 mV/us.  That is
#          0.69 KTAU -- 64x slower than the step edge, but still FASTER than
#          the loop's own settling, so it is NOT a quasi-static tracking test:
#          it moves the rail on the same timescale the loop responds on, which
#          is where a loop with no margin visibly lags.  The two events
#          therefore probe rejection at two rates a factor of 64 apart, one far
#          above the loop's response and one just above it; a true tracking
#          test needs a ramp of several KTAU and is NOT part of this profile.
#          (Do not "fix" this by editing the constants below without re-running:
#          the frozen -dyn.spice snapshot and every recorded number are taken
#          at the values coded here.)
KD_LO=3.30
KD_HI=3.63
KD_END=2.97
KD_TSTEP=5.6u
KD_TEDGE=100n
# KD_TRAMP/_TREND/_TSTOP and the high-plateau measurement window KD_TA_HI/
# _TB_HI are OVERRIDABLE (SIM_DYN_TRAMP/_TREND/_TSTOP/_TA_HI/_TB_HI) for
# exactly the reason KTSTOP/KTA/KTB are (#253): a corner whose high-plateau
# residual frequency error misses ACC_FERR at the DEFAULT hold has not been
# shown to fail the stays-locked criterion, only to still be settling, and it
# has to be re-runnable at a longer hold instead of being reported as a
# design result. KD_*_BASE are the unoverridden defaults -- kept separately
# so a non-default run gets its own work directory (see the "_X" tag in
# --one-dyn below) and never overwrites the run it is being compared against.
# Do not "fix" a FAIL by editing the _BASE values without re-running: the
# frozen -dyn.spice snapshot and every recorded default-hold number are taken
# at these values.
KD_TRAMP_BASE=16.0u
KD_TRAMP="${SIM_DYN_TRAMP:-${KD_TRAMP_BASE}}"
KD_TREND_BASE=22.4u
KD_TREND="${SIM_DYN_TREND:-${KD_TREND_BASE}}"
KD_TSTOP_BASE=30.4u
KD_TSTOP="${SIM_DYN_TSTOP:-${KD_TSTOP_BASE}}"
# The high-plateau ferr_hi/lock_hi/vc_hi measurement window (probes p7/p8),
# stated directly rather than as a fixed offset from KD_TSTEP, because the
# escalated run moves this window far later than a "+7.2u/+8.8u from the
# step" offset would reach.
KD_TA_HI_BASE=12.8u
KD_TA_HI="${SIM_DYN_TA_HI:-${KD_TA_HI_BASE}}"
KD_TB_HI_BASE=14.4u
KD_TB_HI="${SIM_DYN_TB_HI:-${KD_TB_HI_BASE}}"
KD_DECIM=20e-9

# The criterion-3 high-plateau settling escalation (#253).  Mirrors the
# criterion-1 escalation (KTSTOP_X/KTA_X/KTB_X above) at the same settling
# budget: KD_TB_HI_X sits KTB_X (34.4u = 3.70 KTAU) after the step edge ends
# (KD_TSTEP+KD_TEDGE = 5.7u), i.e. 5.7u + 34.4u = 40.1u, so a corner that
# fails the default 8.7 us-after-the-edge window (KD_TB_HI - 5.7u) gets the
# SAME settling budget criterion 1's own escalation already gives a
# still-converging corner, not a shorter one. KD_TRAMP_X/_TREND_X/_TSTOP_X
# push the ramp (and everything after it) out by the same amount, preserving
# the ramp's own rate and duration and the end-plateau hold length.
KD_TA_HI_X="${SIM_DYN_EXTEND_TA:-36.9u}"
KD_TB_HI_X="${SIM_DYN_EXTEND_TB:-40.1u}"
KD_TRAMP_X="${SIM_DYN_EXTEND_TRAMP:-41.1u}"
KD_TREND_X="${SIM_DYN_EXTEND_TREND:-47.5u}"
KD_TSTOP_X="${SIM_DYN_EXTEND_TSTOP:-55.5u}"

# The END-plateau (post-RAMP) measurement instants p11/p12.  Unset means
# "derive them from the profile", which is what this deck has always done
# (t_rend + 1.6 us and tstop - 1.6 us, i.e. the literal 24.0e-6 / 28.8e-6 of
# the default profile); SIM_DYN_P11/_P12 state them directly, in seconds, so
# the END-plateau escalation below can push the post-ramp hold out without a
# second, hand-duplicated probe list.
KD_P11="${SIM_DYN_P11:-}"
KD_P12="${SIM_DYN_P12:-}"

# The criterion-3 END-plateau settling escalation (#255).  #253's escalation
# immediately above resolves this ambiguity for the HIGH plateau (the hold
# after the STEP); this is the SAME ambiguity for the END plateau (the hold
# after the RAMP, measured by p11/p12 and reported as ferr_end): a corner
# whose |ferr_end| misses ACC_FERR at the default 8.0 us post-ramp hold has
# not been shown to FAIL the stays-locked criterion, only to still be
# converging after the ramp.  #58's originating record
# (sim/supply-sensitivity/records/20260831-133708-35c5a33.md, section 3)
# reported that FAIL at all 3 sampled corners without ruling this out.
#
# Rather than deriving a second settling window independently, the extended
# END-plateau probes and hold reuse the SAME KTA_X/KTB_X/KTSTOP_X window
# criterion 1 already defines above, as OFFSETS FROM t_rend rather than from
# t = 0: t_rend is where the loop's post-RAMP convergence starts, the same
# role t = 0 plays for the steady-state deck's warm start.  They are offsets,
# not absolute instants, precisely so this escalation composes with #253's --
# a corner that needed BOTH is re-run on the high-plateau-escalated profile
# (whose t_rend is KD_TREND_X, not KD_TREND_BASE) and still gets the same
# post-ramp settling budget, measured from ITS OWN t_rend.  On the default
# profile they reduce to the instants #255's originating record used:
#   p11   = 22.4u + 31.2u = 53.6u  (3.35 KTAU after t_rend)
#   p12   = 22.4u + 34.4u = 56.8u  (3.70 KTAU after t_rend)
#   tstop = 22.4u + 36.8u = 59.2u  (3.96 KTAU after t_rend)
# Both probes stay whole multiples of 160 ns, so they remain on a reference
# half-period for both reference frequencies, same as every other instant in
# this deck -- and snap() re-snaps them regardless, exactly as it does the
# default 12 probes.
KD_DEND_TA="${SIM_DYN_END_TA:-${KTA_X}}"
KD_DEND_TB="${SIM_DYN_END_TB:-${KTB_X}}"
KD_DEND_TSTOP="${SIM_DYN_END_TSTOP:-${KTSTOP_X}}"

# In-loop control-voltage calibration (the `rforce` pre-pass).  Two forced
# points per corner, KVPRE_D apart, straddling #8's standalone-VCO prediction;
# the runner then solves the measured in-loop f(Vctrl) line for the control
# voltage that gives the target output frequency.  A short transient suffices:
# with VCTRL held by an ideal source there is no loop to settle, only the VCO's
# own bias generator, and KVPRE_TB is 4 reference periods in.
#
# The length of that transient is NOT a free constant.  tb_supply_lock.sp
# measures f_out over a fixed COUNT of output cycles (100 of them, because
# ngspice's `.meas ... rise=` index is not an expression context) starting at
# `tb`, so the run time a calibration point needs scales as 1/f_out -- and the
# deck says so in as many words, asking the runner for "at least 2.4 us of run
# after tb".  KVPRE_TSTOP below states that length for KFOUT and KFOUT only.
# Used unscaled at the HALF-frequency point of the power split it is not merely
# tight, it is impossible: 100 cycles at KFOUT2 need 2.0 us and the window is
# 1.12 us, so `fout` measures `failed`, the solve returns nan, and every split
# corner is silently dropped -- which is exactly why the campaign that
# introduced the split reported it as NOT MEASURED.  Hence vpre_tstop_for().
KVPRE_D=0.25
KVPRE_TSTOP=1.44u
KVPRE_TA=0.16u
KVPRE_TB=0.32u
KVPRE_RON=1m
KVPRE_ROFF=1e15
# The retry window, as a multiple of the 100 output cycles the deck counts.
# 2.4 is the headroom tb_supply_lock.sp asks for, against the 1.12 the nominal
# window carries; a point whose f_out could not be measured in the nominal
# window is re-run here rather than being reported as nan.  Same principle as
# the settling escalation below: a measurement that did not fit its window is
# re-measured in a bigger one, not recorded as a result.
KVPRE_RETRY_K=2.4

# vpre_tstop_for <f_out> -- the calibration transient for a target frequency.
# At KFOUT it returns KVPRE_TSTOP verbatim (same string, so a run cached at the
# documented length stays cached); elsewhere it scales the post-tb part of that
# window by KFOUT/f_out, which holds the cycle-count margin CONSTANT rather
# than holding the seconds constant.
vpre_tstop_for() {
  if [ "$1" = "${KFOUT}" ]; then printf '%s' "${KVPRE_TSTOP}"; return; fi
  awk -v ts="${KVPRE_TSTOP%u}" -v tb="${KVPRE_TB%u}" -v f0="${KFOUT}" -v f="$1" \
    'BEGIN{ printf "%.6gu", tb + (ts - tb) * f0 / f }'
}
# vpre_tstop_retry_for <f_out> -- the longer window a failed point is re-run at.
vpre_tstop_retry_for() {
  awk -v tb="${KVPRE_TB%u}" -v k="${KVPRE_RETRY_K}" -v f="$1" \
    'BEGIN{ printf "%.6gu", tb + k * 100 / f * 1e6 }'
}
# Where the solved control voltage is allowed to land.  Outside this the
# solution is not a control voltage, it is an extrapolation off the end of the
# measured line, and the runner says so rather than simulating it.
KVPRE_LO=0.40
KVPRE_HI=2.95

# Acceptance thresholds.  Stated here, before the run, not discovered from it.
ACC_FERR=1e-3          # |residual fractional frequency error| in lock
# |static phase error at the PFD inputs|, an ABSOLUTE bound in seconds.
#
# THIS IS `spec/pll.md`'S RATIFIED LOCK CRITERION, CITED (#394).  It used to be
# `ACC_PHI_FRAC=0.02` -- 2 % of a reference period -- which is 1.6 ns at this
# campaign's 12.5 MHz and 3.2 ns at its 6.25 MHz power-split bundle, i.e. 1.6x
# and 3.2x looser than the criterion the spec ratifies.  Record
# `20260901-155456-46b92f8` consequently wrote `PASS` on 15 corners standing
# off more static phase than the ratified bound allows (see
# `static_phase_reconciliation.sh` and the record it backs).  A testbench whose
# acceptance threshold is looser than the ratified spec cannot substantiate a
# claim about that spec, so the fraction is replaced by the bound itself.
#
# It is absolute rather than fractional because the ratified criterion is: the
# spec bounds the static phase error in seconds at the PFD inputs, with no
# reference to f_ref.  A scale-free 2 % was the right shape for a criterion
# that had no ratified value yet; it is the wrong shape for one that does.
ACC_PHI_S=1e-9
# How far the "static" phase is allowed to MOVE across the run's own late
# window before the measurement is treated as unsettled rather than as a
# result.  A tenth of the criterion the row is being judged against: a phase
# that shifted by more than that between `ta` and `tb` has not been shown to
# be the offset the loop stands off, only to be on its way somewhere.  See the
# settling escalation in Main, which this gates.
ACC_PHI_SETTLE_S=1e-10
ACC_NTOL=0.01          # |f_out/f_fb - N|
ACC_LOCK_FRAC=0.90     # LOCK flag level in the late window, fraction of the rail
# Criterion 1b grades Budget 2 at the 1.2 V DR-037 proposes (binding on
# ratification; DR-037 is `proposed`) and the measured window (#525), not the
# deck's earlier proxy.  Per DR-012 Decision 5, where spec/pll.md ratifies a
# value the deck cites that value.
#   (i)  Budget 2 (spec/pll.md row 12): a DC rail excursion over the FULL
#        2.97-3.63 V range (0.66 V) consumes <= ACC_BUDGET2_V of the Vctrl
#        window.  1.2 V is derived in DR-037 (twice the 0.6 V that priced a
#        0.33 V half-excursion), not fitted to any measurement.
#   (ii) The control-voltage RIPPLE PEAKS stay inside DR-003 Decision 5's
#        MEASURED 0.9-2.7 V window.  This used to be DR-001 Decision 2's
#        predicted 0.9-2.4 V, which DR-003 Decision 5 superseded.  The tightest
#        margin to it is the quantity DR-037 says must not erode (53 mV at
#        ss/-40C/3.63V in the 20260901-155456-46b92f8 grid).
# ACC_BUDGET2_LEGACY_V is the superseded 0.6 V figure.  It is REPORTED, never
# graded, so the 9-of-15 history stays visible in every future record.
ACC_VCTRL_LO=0.9
ACC_VCTRL_HI=2.7
ACC_BUDGET2_V=1.2
ACC_BUDGET2_LEGACY_V=0.6
ACC_RAIL_LO=2.97
ACC_RAIL_HI=3.63
ACC_PWR_MW=5.0         # draft power target (placeholder pending #1)
ACC_FDEV_PPM=1000      # |f_out(vdd) - f_out(3.30 V)| / f_out(3.30 V), ppm

# #8's open-loop VCO supply-pushing figures, CITED not re-derived (#14's
# acceptance criterion says so in as many words).  Source:
# sim/vco-tuning-range/records/20260731-184845-0a12e6c.md, sections 1 and 2.
CITE_VCO_RECORD=20260731-184845-0a12e6c
CITE_PUSH_WORST=-50.7          # %/V, static, ss/-40C band 4
CITE_PUSH_MEDIAN=-39.4         # %/V, static, median over the grid
CITE_STEP_WORST=-47.7          # MHz/V, transient, 0.1 V step, band 5 ~100 MHz

# #8's measured f(Vctrl) table -- the source of both the band code and the
# warm-start control voltage for every corner below.  Using the committed
# evidence rather than a fresh sweep is the point: the operating point this
# campaign runs at is derived from a citable record, and a reader can check the
# derivation without re-simulating anything.
VCO_TUNING="${ROOT}/sim/vco-tuning-range/corners/20260731-175947-0a12e6c/vco_tuning.csv"

# Passive sections.  Named explicitly rather than defaulted: sim/README.md
# warns that a MOS-only sweep silently pins the passives at typical, and this
# DUT contains the loop filter whose R and C set the loop bandwidth.  Here they
# ARE all typical -- the point is that the record says so because the run put
# them there.  The justification for not sweeping them is in the record.
PASSIVES="res_typical,moscap_typical,mimcap_typical"

libs_for() { echo "$1,${PASSIVES}"; }

# window_trim_code_of <bundle> -> the 4-bit LDT code that bundle's parts carry
#
# A TRANSCRIPTION of sim/lock-window-trim/records/20260917-185928-8adff3d.md's
# code table, which is itself what `spec/pll.md`'s normative Lock-detector
# window trim-code rule produces when the rule is applied to the thirteen
# simulated bundles -- measure t_win at 27 C / 3.30 V, program the code whose
# t_win there is nearest 1.343 ns.  Nothing is decided here; if the table and
# that record ever disagree, the record is right.
#
# ${KWINTRIM} = <0..15> bypasses this entirely and forces one code everywhere.
window_trim_code_of() {
  [ "${KWINTRIM}" = "rule" ] || { echo "${KWINTRIM}"; return 0; }
  case "$1" in
    ss|all-slow)                  echo 3  ;;
    fs)                           echo 6  ;;
    ff|all-fast)                  echo 11 ;;
    typical|sf|res_*|moscap_*|mimcap_*) echo 7 ;;
    *) echo "ERROR: window_trim_code_of: no trim-rule code for bundle '$1'" >&2; exit 2 ;;
  esac
}
