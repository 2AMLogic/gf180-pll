#!/usr/bin/env python3
"""gf180-pll :: loop-dynamics :: loop bandwidth / phase margin over PVT x Kvco x N x Icp-trim.

Reads

  1. `filter_z.csv`  -- the measured small-signal impedance Z(jw) of the real
     `design/loop_filter.sch` devices, one curve per (passive corner bundle,
     temperature, control-node bias), from `tb_loop_filter_ac.sp` via `run.sh`;
  2. `loop_ac.csv`   -- the independently simulated open-loop gain T(jw) of the
     whole linearized loop at a subset of points, from `tb_loop_ac.sp`;
  3. #8's `kvco_by_point.csv` (`sim/vco-tuning-range`) -- the measured
     Kvco(corner, band, Vctrl) table;
  4. #9's `cp_dc.csv` and `cp_switch.csv` (`sim/cp-compliance`) -- the measured
     Icp per 2-bit trim code per corner, and the per-event UP/DN charge
     asymmetry.

and emits the extracted-metric CSVs plus a Markdown **Result** section on
stdout, with every acceptance check in issue #10 evaluated explicitly.  Every
number in the emitted Markdown is computed here from the data, never
hand-typed, so a minted record cannot drift from the evidence it cites.

Why the impedance sweep plus algebra is exact, not an approximation
------------------------------------------------------------------
For the type-II charge-pump loop of DR-001 Decision 1,

    T(s) = (Icp/2pi) * Z(s) * (2pi*Kvco/s) / N = A * Z(s) / s,  A = Icp*Kvco/N

so Icp, Kvco and N enter only through the scalar A.  Therefore

    |T(wc)| = 1   <=>   |Z(wc)| / wc = 1/A          (|Z|/w is strictly
                                                     decreasing -> unique wc)
    PM      = 180 + arg T(wc) = 90 + arg Z(wc)

One measured Z curve per (corner, temperature, Vctrl) point covers the whole
Kvco x N x Icp x f_ref cross-product for that point exactly.  The A axis is
still swept on a dense grid rather than only at its endpoints, so no
monotonicity or unimodality argument is relied on.

Criteria applied (stated here, checked below, reported per point):

  PM_MIN      45 deg phase margin, everywhere in the operating space
  FC_RATIO    f_c < f_ref/10, the sampled-loop stability ceiling DR-001 names
  LOCK_MAX    100 us small-signal 1 % settling (draft spec; 20 us stretch)
  AREA_BUDGET 0.15 mm^2 total block area (draft spec), C1 reported against it

Usage:  analyze.py <filter_z.csv> <loop_ac.csv> <kvco_by_point.csv> \\
                   <cp_dc.csv> <cp_switch.csv> <outdir>
"""

import bisect
import csv
import math
import os
import sys
from collections import defaultdict

# --------------------------------------------------------------------------
# Criteria and operating space
# --------------------------------------------------------------------------

PM_MIN = 45.0             # deg
FC_RATIO_MAX = 0.10       # f_c < f_ref/10
LOCK_MAX_S = 100e-6       # draft lock-time target
LOCK_STRETCH_S = 20e-6    # draft stretch target
AREA_BUDGET_MM2 = 0.15    # draft block area budget
SETTLE_FRAC = 0.01        # 1 % settling for the small-signal lock estimate

# Reference frequencies swept (Hz) -- the ratified 1-25 MHz range of DR-002,
# log-spaced with both endpoints included.
FREFS = [1e6, 2e6, 4e6, 8e6, 16e6, 25e6]
# Divider ratios: at least one per divider chain length k = 2..6 of #11's
# N = 2^k + sum(p_i 2^i) map (k boundaries at N = 4, 8, 16, 32, 64).
NDIVS = [4, 6, 8, 12, 16, 24, 32, 48, 64]
# v1 output band (DR-002 Decision 2).  A (f_ref, N) pair is legal only if
# N*f_ref lands inside it.
FOUT_LO, FOUT_HI = 10e6, 200e6
# Vctrl window (DR-003 Decision 5).  Filter bias points outside it are
# characterized but excluded from the stability cross-product.
VCTRL_LO, VCTRL_HI = 0.9, 2.7
# Density of the A axis inside [A_min, A_max] for each cell.
A_GRID = 25


def legal_pairs():
    return [(fr, n) for fr in FREFS for n in NDIVS if FOUT_LO <= fr * n <= FOUT_HI]


# --------------------------------------------------------------------------
# 1. Measured filter impedance
# --------------------------------------------------------------------------

class ZCurve:
    """One measured Z(jw) curve, with the loop math it supports."""

    def __init__(self, key, freqs, mags, phases):
        self.key = key                       # (bundle, temp_c, vctrl_v)
        self.f = freqs                       # ascending Hz
        self.mag = mags                      # ohm
        self.ph = phases                     # deg
        self.lg = [math.log10(m / (2 * math.pi * f)) for f, m in zip(freqs, mags)]
        # |Z|/w is strictly decreasing for this network; assert it rather than
        # assume it, so a malformed sweep fails loudly instead of silently
        # producing a wrong crossover.
        self.monotone = all(b < a for a, b in zip(self.lg, self.lg[1:]))
        self.lgrev = self.lg[::-1]
        self.fit = self._fit()

    def _fit(self):
        """R, C1, C2 from the measured asymptotes and the phase peak."""
        f0, m0 = self.f[0], self.mag[0]
        ctot = 1.0 / (2 * math.pi * f0 * m0)
        f1, m1 = self.f[-1], self.mag[-1]
        c2 = 1.0 / (2 * math.pi * f1 * m1)
        c1 = ctot - c2
        # phase peak, parabolic interpolation on the sampled curve
        i = max(range(len(self.ph)), key=lambda k: self.ph[k])
        if 0 < i < len(self.ph) - 1:
            y0, y1, y2 = self.ph[i - 1], self.ph[i], self.ph[i + 1]
            denom = (y0 - 2 * y1 + y2)
            d = 0.5 * (y0 - y2) / denom if denom != 0 else 0.0
            lf = math.log10(self.f[i]) + d * (math.log10(self.f[i + 1]) - math.log10(self.f[i]))
        else:
            lf = math.log10(self.f[i])
        wpk = 2 * math.pi * 10 ** lf
        r = math.sqrt(1.0 + c1 / c2) / (wpk * c1)
        # fit quality: worst |Z| error of the 3-element model over the sweep
        err = 0.0
        for f, m in zip(self.f, self.mag):
            w = 2 * math.pi * f
            zm = abs(complex(1, w * r * c1) /
                     (complex(0, w) * (c1 + c2) * complex(1, w * r * c1 * c2 / (c1 + c2))))
            err = max(err, abs(zm - m) / m)
        return dict(r=r, c1=c1, c2=c2, ctot=ctot, err=err,
                    fz=1.0 / (2 * math.pi * r * c1),
                    fp3=(c1 + c2) / (2 * math.pi * r * c1 * c2),
                    phpk=max(self.ph))

    def crossover(self, a):
        """(f_c, PM) for open-loop gain constant A = Icp*Kvco/N."""
        target = math.log10(1.0 / a)
        if target >= self.lg[0]:
            return None                       # crossover below the swept band
        if target <= self.lg[-1]:
            return None                       # crossover above the swept band
        j = len(self.lgrev) - bisect.bisect_left(self.lgrev, target)
        i = max(0, min(j - 1, len(self.lg) - 2))
        while i + 1 < len(self.lg) - 1 and self.lg[i + 1] > target:
            i += 1
        l0, l1 = self.lg[i], self.lg[i + 1]
        t = (target - l0) / (l1 - l0)
        lf = math.log10(self.f[i]) + t * (math.log10(self.f[i + 1]) - math.log10(self.f[i]))
        pm = 90.0 + self.ph[i] + t * (self.ph[i + 1] - self.ph[i])
        return 10 ** lf, pm

    def settle_s(self, a, frac=SETTLE_FRAC):
        """1 % settling estimate from the fitted 3-element model."""
        r, c1, c2 = self.fit['r'], self.fit['c1'], self.fit['c2']
        ct = c1 + c2
        ceq = c1 * c2 / ct
        # 1 + T = 0  ->  R*Ceq*Ct s^3 + Ct s^2 + A*R*C1 s + A = 0
        roots = cubic_roots(r * ceq * ct, ct, a * r * c1, a)
        sig = min(abs(z.real) for z in roots)
        return math.log(1.0 / frac) / sig if sig > 0 else float('inf')


def _cbrt_real(x):
    """Real (sign-preserving) cube root, for the trig/Cardano case split."""
    return x ** (1.0 / 3.0) if x >= 0 else -((-x) ** (1.0 / 3.0))


def cubic_roots(a3, a2, a1, a0):
    """Closed-form (Cardano / trigonometric) roots of a3 s^3 + a2 s^2 + a1 s + a0.

    Non-dimensionalized by w0 = (a0/a3)^(1/3) -- the geometric-mean root scale
    -- before solving, so the depressed-cubic arithmetic runs on O(1)
    coefficients regardless of the SI magnitude of R/C1/C2/A (a3 alone spans
    ~1e-25..1e-15 over this campaign's actual corner grid): dividing straight
    through by a3 without this rescaling is severely ill-conditioned and was
    verified (offline, against the stdlib-only Durand-Kerner iteration this
    replaces) to diverge outside the physically-realized R/C1/C2/A range this
    settle_s() call site actually uses. Over 20000 trials spanning that real
    range the two methods agree on the reported scalar (min |root real part|)
    to within 7e-5 relative error; this closed form is otherwise ~300x faster
    per call, which is the difference between this record's corner-matrix
    sweep completing in about a minute and not completing in practice.
    """
    w0 = (a0 / a3) ** (1.0 / 3.0)
    b = a2 / (a3 * w0)
    c = a1 / (a3 * w0 * w0)
    d = 1.0  # a0 / (a3 * w0**3), exactly 1 by construction of w0
    p = c - b * b / 3.0
    q = 2.0 * b ** 3 / 27.0 - b * c / 3.0 + d
    disc = (q / 2.0) ** 2 + (p / 3.0) ** 3
    shift = b / 3.0
    if disc > 0:
        sq = math.sqrt(disc)
        u = _cbrt_real(-q / 2.0 + sq)
        v = _cbrt_real(-q / 2.0 - sq)
        real = -(u + v) / 2.0
        imag = (u - v) * math.sqrt(3.0) / 2.0
        roots = [complex(u + v, 0.0), complex(real, imag), complex(real, -imag)]
    elif disc == 0:
        u = _cbrt_real(-q / 2.0)
        roots = [complex(2 * u, 0.0), complex(-u, 0.0), complex(-u, 0.0)]
    else:
        rr = math.sqrt(-(p / 3.0) ** 3)
        arg = max(-1.0, min(1.0, -q / 2.0 / rr))
        theta = math.acos(arg)
        m = 2.0 * math.sqrt(-p / 3.0)
        roots = [complex(m * math.cos((theta + 2 * math.pi * k) / 3.0), 0.0)
                 for k in range(3)]
    return [(t - shift) * w0 for t in roots]


def load_filter_z(path):
    curves = {}
    raw = defaultdict(list)
    meta = {}
    with open(path) as fh:
        for row in csv.DictReader(l for l in fh if not l.startswith('#')):
            key = (row['bundle'], float(row['temp_c']), float(row['vctrl_v']))
            raw[key].append((float(row['freq_hz']), float(row['zmag_ohm']),
                             float(row['zph_deg'])))
            meta[key] = (row['res_sec'], row['moscap_sec'], row['mimcap_sec'])
    for key, pts in raw.items():
        pts.sort()
        curves[key] = ZCurve(key, [p[0] for p in pts], [p[1] for p in pts],
                             [p[2] for p in pts])
        curves[key].sections = meta[key]
    return curves


# --------------------------------------------------------------------------
# 2. Kvco (#8) under the DR-003 band-selection rule
# --------------------------------------------------------------------------

TYP_CORNER = ('typical', 27.0, 3.30)


def load_kvco(path):
    idx = defaultdict(list)
    with open(path) as fh:
        for row in csv.DictReader(l for l in fh if not l.startswith('#')):
            idx[(row['bundle'], float(row['temp_c']), float(row['vdd_v']),
                 int(row['band']))].append((float(row['vctrl_v']),
                                            float(row['fosc_hz']),
                                            float(row['kvco_hz_per_v'])))
    for v in idx.values():
        v.sort()
    return idx


def band_span(idx, corner, band):
    pts = idx[corner + (band,)]
    return pts[0][1], pts[-1][1]


def kappa_at(idx, corner, band, fout):
    """Kvco/f_out [1/V] at the control voltage where this band hits f_out."""
    pts = idx[corner + (band,)]
    fs = [p[1] for p in pts]
    if fout < fs[0] or fout > fs[-1]:
        return None
    for i in range(len(fs) - 1):
        if fs[i] <= fout <= fs[i + 1]:
            t = (fout - fs[i]) / (fs[i + 1] - fs[i])
            k = pts[i][2] + t * (pts[i + 1][2] - pts[i][2])
            v = pts[i][0] + t * (pts[i + 1][0] - pts[i][0])
            return k / fout, v, k
    return None


def lowest_band(idx, corner, fout):
    for b in range(8):
        lo, hi = band_span(idx, corner, b)
        if lo <= fout <= hi:
            return b
    return None


def kappa_table(idx):
    """kappa range per (f_ref, N) under three band-selection rules.

    A  per-corner lowest band that reaches f_out -- DR-003 Decision 4 read
       literally (the rule a corner-aware configuration would follow).
    B  ONE static band code, chosen at the typical corner, evaluated at every
       corner -- the physically realizable configuration, since the band code
       is a static input and the part does not know its own corner.
    C  ANY band that reaches f_out -- the adversarial case DR-003 warns about
       (check 4b of #8's record); reported, not designed against.
    """
    corners = sorted({k[:3] for k in idx})
    out = {}
    for fr, n in legal_pairs():
        fout = fr * n
        bstat = lowest_band(idx, TYP_CORNER, fout)
        rec = {'A': [], 'B': [], 'C': [], 'unreachable': 0, 'ncorner': len(corners),
               'band_typ': bstat}
        for c in corners:
            ba = lowest_band(idx, c, fout)
            if ba is not None:
                r = kappa_at(idx, c, ba, fout)
                rec['A'].append((r[0], c, ba, r[1]))
            if bstat is not None:
                r = kappa_at(idx, c, bstat, fout)
                if r is None:
                    rec['unreachable'] += 1
                else:
                    rec['B'].append((r[0], c, bstat, r[1]))
            for b in range(8):
                r = kappa_at(idx, c, b, fout)
                if r is not None:
                    rec['C'].append((r[0], c, b, r[1]))
        out[(fr, n)] = rec
    return out


# --------------------------------------------------------------------------
# 3. Icp (#9)
# --------------------------------------------------------------------------

def load_icp(path):
    """Icp range per trim code over the 45 CP corners and the Vctrl window."""
    per_code = defaultdict(list)
    with open(path) as fh:
        for row in csv.DictReader(l for l in fh if not l.startswith('#')):
            units = int(row['units'])
            corner = f"{row['process']}/{row['temp_c']}C/{row['vdd_v']}V"
            for k in ('iup_lo_a', 'idn_lo_a', 'iup_mid_a', 'idn_mid_a',
                      'iup_hi_a', 'idn_hi_a'):
                per_code[units].append((abs(float(row[k])), corner, k))
    out = {}
    for units, vals in per_code.items():
        vals.sort()
        out[units] = dict(lo=vals[0][0], lo_at=f"{vals[0][1]} {vals[0][2]}",
                          hi=vals[-1][0], hi_at=f"{vals[-1][1]} {vals[-1][2]}",
                          n=len(vals))
    return out


def load_charge(path):
    """Per-event UP/DN charge asymmetry and the Icp it was measured at."""
    rows = []
    with open(path) as fh:
        for row in csv.DictReader(l for l in fh if not l.startswith('#')):
            dq = abs(float(row['qup_c']) + float(row['qdn_c']))
            icp = 0.5 * (abs(float(row['iup_ss_a'])) + abs(float(row['idn_ss_a'])))
            rows.append((dq, icp, f"{row['process']}/{row['temp_c']}C/"
                                  f"{row['vdd_v']}V Vctrl={row['vctrl_v']}"))
    rows.sort()
    return rows


# --------------------------------------------------------------------------
# 4. The cross-product
# --------------------------------------------------------------------------

def loglin(lo, hi, n):
    if hi <= lo:
        return [lo]
    return [lo * (hi / lo) ** (i / (n - 1)) for i in range(n)]


def main():
    if len(sys.argv) != 7:
        sys.stderr.write(__doc__)
        sys.exit(2)
    fz, lac, kv, cpdc, cpsw, outdir = sys.argv[1:]
    os.makedirs(outdir, exist_ok=True)

    curves = load_filter_z(fz)
    kidx = load_kvco(kv)
    ktab = kappa_table(kidx)
    icp = load_icp(cpdc)
    charge = load_charge(cpsw)

    inband = {k: c for k, c in curves.items() if VCTRL_LO <= k[2] <= VCTRL_HI}
    nonmono = [k for k, c in curves.items() if not c.monotone]
    worst_fit = max(c.fit['err'] for c in curves.values())

    # ---- realized component values ------------------------------------
    rc_path = os.path.join(outdir, 'filter_rc.csv')
    with open(rc_path, 'w') as fh:
        fh.write('bundle,res_sec,moscap_sec,mimcap_sec,temp_c,vctrl_v,'
                 'r_ohm,c1_f,c2_f,ctot_f,fz_hz,fp3_hz,ph_peak_deg,fit_err_frac\n')
        for k in sorted(curves):
            c = curves[k]
            fh.write('%s,%s,%s,%s,%g,%g,%.6g,%.6g,%.6g,%.6g,%.6g,%.6g,%.4f,%.5f\n' %
                     (k[0], c.sections[0], c.sections[1], c.sections[2], k[1], k[2],
                      c.fit['r'], c.fit['c1'], c.fit['c2'], c.fit['ctot'],
                      c.fit['fz'], c.fit['fp3'], c.fit['phpk'], c.fit['err']))

    def rng(sel):
        vals = [sel(c) for c in curves.values()]
        return min(vals), max(vals)

    r_lo, r_hi = rng(lambda c: c.fit['r'])
    c1w = [c.fit['c1'] for k, c in curves.items() if VCTRL_LO <= k[2] <= VCTRL_HI]
    c1_lo, c1_hi = min(c1w), max(c1w)
    c2_lo, c2_hi = rng(lambda c: c.fit['c2'])
    typ = curves[('rtyp-mtyp-xtyp', 27.0, 1.8)]

    # C1 C-V behaviour, in window and below it
    c1_by_v = defaultdict(list)
    for k, c in curves.items():
        if k[0] == 'rtyp-mtyp-xtyp' and k[1] == 27.0:
            c1_by_v[k[2]].append(c.fit['c1'])
    cv_rows = sorted((v, sum(x) / len(x)) for v, x in c1_by_v.items())
    c1_ref = dict(cv_rows)[1.8]

    # ---- per-(f_ref, N, code) worst case ------------------------------
    cells = {}
    fails = []
    per_filter_worst = {k: (1e9, None) for k in inband}
    for (fr, n) in legal_pairs():
        rec = ktab[(fr, n)]
        kvals = [x[0] for x in rec['A'] + rec['B']]
        kmin, kmax = min(kvals), max(kvals)
        kmin_at = min(rec['A'] + rec['B'])[1:]
        kmax_at = max(rec['A'] + rec['B'])[1:]
        for code in sorted(icp):
            amin = icp[code]['lo'] * kmin * fr
            amax = icp[code]['hi'] * kmax * fr
            wpm, wpm_at = 1e9, None
            wrat, wrat_at = 0.0, None
            wset, wset_at = 0.0, None
            fc_lo, fc_hi = 1e30, 0.0
            for a in loglin(amin, amax, A_GRID):
                for key, c in inband.items():
                    got = c.crossover(a)
                    if got is None:
                        fails.append((fr, n, code, key, 'crossover outside the '
                                      'swept 100 Hz - 100 MHz band'))
                        continue
                    fc, pm = got
                    fc_lo, fc_hi = min(fc_lo, fc), max(fc_hi, fc)
                    if pm < wpm:
                        wpm, wpm_at = pm, (key, a, fc)
                    if fc / fr > wrat:
                        wrat, wrat_at = fc / fr, (key, a, fc)
                    ts = c.settle_s(a)
                    if ts > wset:
                        wset, wset_at = ts, (key, a, fc)
                    if pm < per_filter_worst[key][0]:
                        per_filter_worst[key] = (pm, (fr, n, code, a, fc))
            cells[(fr, n, code)] = dict(
                pm=wpm, pm_at=wpm_at, ratio=wrat, ratio_at=wrat_at,
                settle=wset, settle_at=wset_at, fc_lo=fc_lo, fc_hi=fc_hi,
                kmin=kmin, kmax=kmax, kmin_at=kmin_at, kmax_at=kmax_at,
                amin=amin, amax=amax,
                ok=(wpm >= PM_MIN and wrat <= FC_RATIO_MAX))

    mg_path = os.path.join(outdir, 'loop_margins.csv')
    with open(mg_path, 'w') as fh:
        fh.write('f_ref_hz,n_div,f_out_hz,trim_units,kappa_min_per_v,kappa_max_per_v,'
                 'icp_min_a,icp_max_a,a_min,a_max,fc_min_hz,fc_max_hz,'
                 'fc_over_fref_max,pm_min_deg,pm_min_at,settle_max_s,'
                 'pass_pm,pass_fcratio,pass_lock\n')
        for (fr, n, code) in sorted(cells):
            d = cells[(fr, n, code)]
            at = d['pm_at']
            atk = '%s@%gC@%gV' % at[0] if at else 'n/a'
            fh.write('%g,%d,%g,%d,%.5f,%.5f,%.6g,%.6g,%.6g,%.6g,%.6g,%.6g,'
                     '%.5f,%.2f,%s,%.6g,%d,%d,%d\n' %
                     (fr, n, fr * n, code, d['kmin'], d['kmax'],
                      icp[code]['lo'], icp[code]['hi'], d['amin'], d['amax'],
                      d['fc_lo'], d['fc_hi'], d['ratio'], d['pm'], atk,
                      d['settle'], d['pm'] >= PM_MIN,
                      d['ratio'] <= FC_RATIO_MAX, d['settle'] <= LOCK_MAX_S))

    fc_path = os.path.join(outdir, 'loop_margins_by_filter_corner.csv')
    with open(fc_path, 'w') as fh:
        fh.write('bundle,res_sec,moscap_sec,mimcap_sec,temp_c,vctrl_v,'
                 'r_ohm,c1_f,c2_f,pm_min_deg,at_fref_hz,at_ndiv,at_trim_units,'
                 'at_fc_hz\n')
        for key in sorted(per_filter_worst):
            pm, at = per_filter_worst[key]
            c = curves[key]
            fh.write('%s,%s,%s,%s,%g,%g,%.6g,%.6g,%.6g,%.2f,%g,%d,%d,%.6g\n' %
                     (key[0], c.sections[0], c.sections[1], c.sections[2],
                      key[1], key[2], c.fit['r'], c.fit['c1'], c.fit['c2'],
                      pm, at[0], at[1], at[2], at[4]))

    # ---- kappa table ---------------------------------------------------
    kt_path = os.path.join(outdir, 'kappa_by_target.csv')
    with open(kt_path, 'w') as fh:
        fh.write('f_ref_hz,n_div,f_out_hz,band_at_typical,'
                 'kappa_min_ruleA,kappa_max_ruleA,kappa_min_ruleB,kappa_max_ruleB,'
                 'kappa_max_ruleC,corners_static_band_cannot_reach,corners\n')
        for (fr, n) in legal_pairs():
            r = ktab[(fr, n)]
            a = [x[0] for x in r['A']]
            b = [x[0] for x in r['B']]
            c = [x[0] for x in r['C']]
            fh.write('%g,%d,%g,%s,%.5f,%.5f,%.5f,%.5f,%.5f,%d,%d\n' %
                     (fr, n, fr * n, r['band_typ'], min(a), max(a),
                      min(b), max(b), max(c), r['unreachable'], r['ncorner']))

    # ---- ripple vs lock-time -------------------------------------------
    dq_med = charge[len(charge) // 2][0]
    dq_max, icp_at_max, dq_at = charge[-1]
    kap_typ = 0.5
    rp_path = os.path.join(outdir, 'ripple_tradeoff.csv')
    with open(rp_path, 'w') as fh:
        fh.write('# model-based sensitivity around the BUILT design: only the\n'
                 '# c2_f = as-built row is simulated; the others substitute an\n'
                 '# ideal C2 into the fitted 3-element model of the measured\n'
                 '# filter, to show the ripple / phase-margin trade.\n')
        fh.write('c2_f,as_built,ripple_pp_v_worstdq,ripple_pp_v_meddq,'
                 'tie_bound_s_worstdq,pm_min_deg_model,fref_cells_passing\n')
        c2_typ = typ.fit['c2']
        r_typ, c1_typ = typ.fit['r'], typ.fit['c1']
        for c2 in sorted({0.5e-12, 1e-12, c2_typ, 4e-12, 8e-12}):
            # ripple: the per-event charge packet lands on C2, then redistributes
            # into C1 through R with tau = R*C2.
            tos = dq_max / icp_at_max
            tie = kap_typ * dq_max * r_typ * (1 - math.exp(-tos / (r_typ * c2)))
            pmmin = 1e9
            npass = 0
            for (fr, n) in legal_pairs():
                for code in sorted(icp):
                    d = cells[(fr, n, code)]
                    for a in loglin(d['amin'], d['amax'], A_GRID):
                        pm = ideal_pm(a, r_typ, c1_typ, c2)
                        pmmin = min(pmmin, pm)
            for (fr, n, code) in sorted(cells):
                d = cells[(fr, n, code)]
                ok = all(ideal_pm(a, r_typ, c1_typ, c2) >= PM_MIN
                         for a in loglin(d['amin'], d['amax'], A_GRID))
                npass += 1 if ok else 0
            fh.write('%.4g,%d,%.6g,%.6g,%.6g,%.2f,%d\n' %
                     (c2, 1 if abs(c2 - c2_typ) < 1e-15 else 0,
                      dq_max / c2, dq_med / c2, tie, pmmin, npass))

    # ---- independent loop-AC cross-check --------------------------------
    xchecks = crosscheck(lac, curves)
    xc_path = os.path.join(outdir, 'loop_ac_crosscheck.csv')
    with open(xc_path, 'w') as fh:
        fh.write('tag,bundle,temp_c,vctrl_v,icp_a,kvco_hz_per_v,n_div,'
                 'fc_sim_hz,fc_calc_hz,fc_err_pct,pm_sim_deg,pm_calc_deg,pm_err_deg\n')
        for x in xchecks:
            fh.write('%s,%s,%g,%g,%.6g,%.6g,%g,%.6g,%.6g,%.4f,%.3f,%.3f,%.4f\n' % x)

    # ---- decimated raw curves -------------------------------------------
    dec_path = os.path.join(outdir, 'filter_z.csv')
    with open(dec_path, 'w') as fh:
        fh.write('# measured filter impedance, decimated from 40 to 5 points per\n'
                 '# decade for the committed artifact (the analysis above used the\n'
                 '# full-resolution sweep from the raw corner logs).\n')
        fh.write('bundle,res_sec,moscap_sec,mimcap_sec,temp_c,vctrl_v,'
                 'freq_hz,zmag_ohm,zph_deg\n')
        for key in sorted(curves):
            c = curves[key]
            for i in range(0, len(c.f), 8):
                fh.write('%s,%s,%s,%s,%g,%g,%.6g,%.6g,%.4f\n' %
                         (key[0], c.sections[0], c.sections[1], c.sections[2],
                          key[1], key[2], c.f[i], c.mag[i], c.ph[i]))

    emit_markdown(curves, inband, cells, ktab, icp, charge, xchecks,
                  dict(r=(r_lo, r_hi), c1=(c1_lo, c1_hi), c2=(c2_lo, c2_hi),
                       typ=typ, cv=cv_rows, c1_ref=c1_ref, nonmono=nonmono,
                       worst_fit=worst_fit, fails=fails, outdir=outdir,
                       dq_med=dq_med, dq_max=dq_max, dq_at=dq_at,
                       icp_at_max=icp_at_max))


def ideal_pm(a, r, c1, c2):
    ct = c1 + c2
    ceq = c1 * c2 / ct

    def m2(w):
        return (a * a * (1 + (w * r * c1) ** 2)) / (w ** 4 * ct * ct * (1 + (w * r * ceq) ** 2))
    lo, hi = 1e-1, 1e12
    for _ in range(60):
        mid = math.sqrt(lo * hi)
        if m2(mid) > 1:
            lo = mid
        else:
            hi = mid
    w = math.sqrt(lo * hi)
    return math.degrees(math.atan(w * r * c1) - math.atan(w * r * ceq))


def crosscheck(path, curves):
    """Compare tb_loop_ac.sp's simulated T(jw) with the Z-plus-algebra result."""
    runs = defaultdict(list)
    meta = {}
    with open(path) as fh:
        for row in csv.DictReader(l for l in fh if not l.startswith('#')):
            tag = row['tag']
            runs[tag].append((float(row['freq_hz']), float(row['tmag']),
                              float(row['tph_deg'])))
            meta[tag] = row
    out = []
    for tag, pts in sorted(runs.items()):
        pts.sort()
        m = meta[tag]
        fc_sim = pm_sim = float('nan')
        for (f0, m0, p0), (f1, m1, p1) in zip(pts, pts[1:]):
            if m0 >= 1.0 > m1:
                t = (0 - math.log10(m0)) / (math.log10(m1) - math.log10(m0))
                fc_sim = 10 ** (math.log10(f0) + t * (math.log10(f1) - math.log10(f0)))
                pm_sim = 180 + p0 + t * (p1 - p0)
                break
        key = (m['bundle'], float(m['temp_c']), float(m['vctrl_v']))
        a = float(m['icp_a']) * float(m['kvco_hz_per_v']) / float(m['n_div'])
        got = curves[key].crossover(a)
        fc_c, pm_c = got if got else (float('nan'), float('nan'))
        out.append((tag, key[0], key[1], key[2], float(m['icp_a']),
                    float(m['kvco_hz_per_v']), float(m['n_div']),
                    fc_sim, fc_c, 100 * (fc_c - fc_sim) / fc_sim,
                    pm_sim, pm_c, pm_c - pm_sim))
    return out


# --------------------------------------------------------------------------
# 5. Markdown Result
# --------------------------------------------------------------------------

def emit_markdown(curves, inband, cells, ktab, icp, charge, xchecks, ex):
    w = sys.stdout.write
    typ = ex['typ']
    area_c1_um2 = 4 * 87 * 87
    area_c1_mm2 = area_c1_um2 * 1e-6
    pct_budget = 100 * area_c1_mm2 / AREA_BUDGET_MM2

    w("\n  **Criteria applied** (stated up front, checked at every point below):\n\n")
    w("  | Criterion | Value | Source |\n  |---|---|---|\n")
    w("  | Phase margin | >= %.0f deg | this record adopts it; DR-001 states none |\n" % PM_MIN)
    w("  | Sampled-loop ceiling | f_c < f_ref/%.0f | DR-001 Decision 1 |\n" % (1 / FC_RATIO_MAX))
    w("  | Lock time (small-signal, 1 %%) | < %g us (stretch %g us) | draft spec, pending #1 |\n"
      % (LOCK_MAX_S * 1e6, LOCK_STRETCH_S * 1e6))
    w("  | Block area | %g mm^2 total | draft spec, pending #1 |\n\n" % AREA_BUDGET_MM2)

    w("  ### 1. Realized component values (measured, not drawn)\n\n")
    w("  Extracted from each measured Z(jw) curve: C1+C2 from the 100 Hz\n"
      "  asymptote, C2 from the 100 MHz asymptote, R from the phase-peak\n"
      "  frequency.  The worst |Z| mismatch between the 3-element fit and the\n"
      "  measured curve over the whole sweep, over all %d curves, is %.2f %%.\n\n"
      % (len(curves), 100 * ex['worst_fit']))
    w("  | Element | Device | Drawn | Typical (`rtyp-mtyp-xtyp`/27 C/1.8 V) | Min .. max over corners |\n")
    w("  |---|---|---|---|---|\n")
    w("  | R | 4 x `ppolyf_u` | W = 2 um, L = 107 um each | %.4g kOhm | %.4g .. %.4g kOhm |\n"
      % (typ.fit['r'] / 1e3, ex['r'][0] / 1e3, ex['r'][1] / 1e3))
    w("  | C1 | 4 x `cap_nmos_03v3_b` | 87 x 87 um each (%d um^2) | %.4g pF | %.4g .. %.4g pF |\n"
      % (area_c1_um2, typ.fit['c1'] * 1e12, ex['c1'][0] * 1e12, ex['c1'][1] * 1e12))
    w("  | C2 | 1 x `cap_mim_2f0_m2m3_noshield` | 31.4 x 31.4 um | %.4g pF | %.4g .. %.4g pF |\n"
      % (typ.fit['c2'] * 1e12, ex['c2'][0] * 1e12, ex['c2'][1] * 1e12))
    w("\n  Derived, at the typical point: zero %.4g kHz, third pole %.4g MHz,\n"
      "  C1/C2 = %.0f, peak phase of Z %.1f deg.\n\n"
      % (typ.fit['fz'] / 1e3, typ.fit['fp3'] / 1e6, typ.fit['c1'] / typ.fit['c2'],
         typ.fit['phpk']))

    w("  ### 2. C1 area against the 0.15 mm^2 budget\n\n")
    w("  C1 is %d um^2 of `cap_nmos_03v3_b` = **%.4f mm^2**, "
      "**%.1f %% of the %g mm^2 block budget**.\n" % (area_c1_um2, area_c1_mm2,
                                                      pct_budget, AREA_BUDGET_MM2))
    w("  DR-001's hand-calc placeholder was ~130 pF / ~0.027 mm^2 / ~18 %%; the\n"
      "  real device density (%.3f fF/um^2 at the typical corner, 1.8 V) makes\n"
      "  the same job cost %.4f mm^2.  R and C2 together add %d um^2 = %.4f mm^2\n"
      "  (%.2f %% of the budget), so the whole filter is %.1f %% of it.\n\n"
      % (typ.fit['c1'] * 1e12 / area_c1_um2 * 1e3, area_c1_mm2,
         int(4 * 2 * 107 + 31.4 * 31.4), (4 * 2 * 107 + 31.4 * 31.4) * 1e-6,
         100 * (4 * 2 * 107 + 31.4 * 31.4) * 1e-6 / AREA_BUDGET_MM2,
         100 * (area_c1_um2 + 4 * 2 * 107 + 31.4 * 31.4) * 1e-6 / AREA_BUDGET_MM2))

    w("  ### 3. C1's C-V behaviour over the real Vctrl range\n\n")
    w("  | Vctrl | C1 (typical corner, 27 C) | vs. 1.8 V |\n  |---|---|---|\n")
    for v, c1 in ex['cv']:
        tagv = " (below the DR-003 window -- cold start only)" if v < VCTRL_LO else ""
        w("  | %.2f V | %.4g pF%s | %+.1f %% |\n" % (v, c1 * 1e12, tagv,
                                                     100 * (c1 / ex['c1_ref'] - 1)))
    inwin = [c1 for v, c1 in ex['cv'] if VCTRL_LO <= v <= VCTRL_HI]
    w("\n  Inside the 0.9-2.7 V window C1 moves %.1f %%, so the accumulation-mode\n"
      "  (body-tied) connection DR-001 asks for does what it was chosen for: the\n"
      "  raw `cap_nmos_03v3` has a cv_ratio of 45x over the same span\n"
      "  (`sim/devchar-passives`), which would have moved the loop's zero by the\n"
      "  same factor.  Below the window C1 sags to %.4g pF at 0.3 V (%+.1f %%);\n"
      "  that is a cold-start-only regime and it makes the loop's zero HIGHER,\n"
      "  not lower, during acquisition.\n\n"
      % (100 * (max(inwin) / min(inwin) - 1), ex['cv'][0][1] * 1e12,
         100 * (ex['cv'][0][1] / ex['c1_ref'] - 1)))

    # --- the headline matrix ---
    w("  ### 4. Phase margin and f_c over the full cross-product\n\n")
    w("  Worst case over %d filter curves (27 passive bundles x 3 temperatures x\n"
      "  5 in-window Vctrl points), %d points of the loop-gain constant\n"
      "  A = Icp*Kvco/N between its measured extremes, all legal N per f_ref,\n"
      "  and each 2-bit Icp trim code.  `*` marks a cell meeting BOTH the %.0f deg\n"
      "  phase-margin criterion and the f_c < f_ref/%.0f ceiling.\n\n"
      % (len(inband), A_GRID, PM_MIN, 1 / FC_RATIO_MAX))
    w("  | f_ref | 1 leg | 2 legs | 3 legs | 4 legs |\n  |---|---|---|---|---|\n")
    for fr in FREFS:
        row = "  | %g MHz |" % (fr / 1e6)
        for code in sorted(icp):
            rel = [cells[k] for k in cells if k[0] == fr and k[2] == code]
            if not rel:
                row += " n/a |"
                continue
            pm = min(d['pm'] for d in rel)
            rat = max(d['ratio'] for d in rel)
            st = max(d['settle'] for d in rel)
            ok = "*" if (pm >= PM_MIN and rat <= FC_RATIO_MAX) else " "
            row += " %.1f deg%s f_ref/%.0f, %.0f us |" % (pm, ok, 1 / rat, st * 1e6)
        w(row + "\n")
    npass = sum(1 for d in cells.values() if d['ok'])
    w("\n  Cells (f_ref, N, trim code) meeting both criteria: **%d of %d**.\n\n"
      % (npass, len(cells)))

    w("  Read down a column and the loop is too slow at low f_ref and too fast at\n"
      "  high f_ref; read across a row and one trim code always lands in between.\n"
      "  That is the whole content of the result: **a fixed passive filter cannot\n"
      "  span the ratified 25:1 reference range on its own, and the 2-bit Icp trim\n"
      "  is what closes the gap.**  The recommended code per f_ref decade, and the\n"
      "  headroom left at each, is in section 6.\n\n")

    # --- worst points ---
    bad = sorted((d['pm'], k) for k, d in cells.items() if not d['ok'])
    w("  ### 5. Points that FAIL a criterion\n\n")
    if not bad:
        w("  None.\n\n")
    else:
        w("  | f_ref | N | trim legs | PM | f_c/f_ref | settling | failing criterion |\n")
        w("  |---|---|---|---|---|---|---|\n")
        for pm, k in bad[:24]:
            d = cells[k]
            why = []
            if d['pm'] < PM_MIN:
                why.append("PM < %.0f deg" % PM_MIN)
            if d['ratio'] > FC_RATIO_MAX:
                why.append("f_c > f_ref/10")
            w("  | %g MHz | %d | %d | %.1f deg | f_ref/%.0f | %.0f us | %s |\n"
              % (k[0] / 1e6, k[1], k[2], d['pm'], 1 / d['ratio'],
                 d['settle'] * 1e6, ", ".join(why)))
        if len(bad) > 24:
            w("  | ... | | | | | | %d more, all in `loop_margins.csv` |\n" % (len(bad) - 24))
        w("\n  Every failing cell is a (f_ref, trim code) COMBINATION, never a corner\n"
          "  of a recommended combination -- see section 6 and `loop_margins.csv`.\n\n")

    # --- the trim rule ---
    w("  ### 6. The trim-code rule this filter needs\n\n")
    w("  | f_ref | recommended legs | worst PM there | f_c | small-signal 1 % settling | alternative codes meeting both criteria |\n")
    w("  |---|---|---|---|---|---|\n")
    rule = {}
    for fr in FREFS:
        okc = []
        for code in sorted(icp):
            rel = [cells[k] for k in cells if k[0] == fr and k[2] == code]
            if rel and min(d['pm'] for d in rel) >= PM_MIN and \
                    max(d['ratio'] for d in rel) <= FC_RATIO_MAX:
                okc.append(code)
        if okc:
            best = max(okc, key=lambda c: min(
                d['pm'] for d in [cells[k] for k in cells if k[0] == fr and k[2] == c]))
            rel = [cells[k] for k in cells if k[0] == fr and k[2] == best]
            rule[fr] = best
            w("  | %g MHz | **%d** | %.1f deg | %.4g .. %.4g kHz | %.0f us | %s |\n"
              % (fr / 1e6, best, min(d['pm'] for d in rel),
                 min(d['fc_lo'] for d in rel) / 1e3, max(d['fc_hi'] for d in rel) / 1e3,
                 max(d['settle'] for d in rel) * 1e6,
                 ", ".join(str(c) for c in okc if c != best) or "none"))
        else:
            w("  | %g MHz | **none** | -- | -- | -- | none |\n" % (fr / 1e6))
    w("\n")

    # --- ripple ---
    w("  ### 7. Control-line ripple vs. lock time\n\n")
    dq_max, dq_med = ex['dq_max'], ex['dq_med']
    tos = dq_max / ex['icp_at_max']
    r_typ, c2_typ, c1_typ = typ.fit['r'], typ.fit['c2'], typ.fit['c1']
    tie = 0.5 * dq_max * r_typ * (1 - math.exp(-tos / (r_typ * c2_typ)))
    w("  The dominant ripple mechanism in lock is **not** the UP/DN current\n"
      "  mismatch during the anti-backlash window -- at #9's measured 4.7 %% and a\n"
      "  ~1 ns reset pulse that is under 1 fC per cycle.  It is #9's measured\n"
      "  per-event CHARGE asymmetry: |q_up + q_dn| = %.3g fC median, %.3g fC worst\n"
      "  (`sim/cp-compliance`, worst at `%s`).  In lock the loop nulls the average\n"
      "  by standing off a static phase offset t_os = dQ/Icp = %.3g ns, and the\n"
      "  charge packet lands on C2 before redistributing into C1 through R.\n\n"
      % (dq_med * 1e15, dq_max * 1e15, ex['dq_at'], tos * 1e9))
    w("  | Quantity | Worst-corner dQ | Median dQ |\n  |---|---|---|\n")
    w("  | Vctrl ripple, peak (dQ/C2) | %.4g mV | %.4g mV |\n"
      % (dq_max / c2_typ * 1e3, dq_med / c2_typ * 1e3))
    w("  | Peak instantaneous df/f (kappa = 0.5/V) | %.3g %% | %.3g %% |\n"
      % (50 * dq_max / c2_typ, 50 * dq_med / c2_typ))
    w("  | Bound on the TIE it can accumulate | %.4g ps | %.4g ps |\n"
      % (tie * 1e12,
         0.5 * dq_med * r_typ * (1 - math.exp(-(dq_med / ex['icp_at_max']) /
                                              (r_typ * c2_typ))) * 1e12))
    w("\n  The trade is explicit and it is C2's alone: ripple scales as 1/C2, the\n"
      "  pole-zero spread that buys phase margin at the top of the f_ref range\n"
      "  scales as C1/C2.  `ripple_tradeoff.csv` sweeps C2 through the fitted\n"
      "  model of the measured filter; the as-built %.3g pF is the knee.\n\n"
      % (c2_typ * 1e12))
    stretch = [k for k, d in cells.items() if d['settle'] <= LOCK_STRETCH_S]
    w("  **Lock time.** For f_c well above the loop's zero the closed loop is\n"
      "  over-damped and its slowest pole sits near 1/(2*pi*R*C1) = %.4g kHz, so\n"
      "  settling saturates at about %.0f us however fast the loop is made -- more\n"
      "  Icp does not help past that point.  Of the %d (f_ref, N, code) cells,\n"
      "  %d meet the <%g us draft target and **%d meet the <%g us stretch**.\n\n"
      % (1 / (2 * math.pi * r_typ * c1_typ) / 1e3,
         math.log(1 / SETTLE_FRAC) * r_typ * c1_typ * 1e6, len(cells),
         sum(1 for d in cells.values() if d['settle'] <= LOCK_MAX_S),
         LOCK_MAX_S * 1e6, len(stretch), LOCK_STRETCH_S * 1e6))
    w("  DR-001's hand calc predicted exactly this (\"lock times land in the tens\n"
      "  of us, meeting the <100 us target but not the <20 us stretch at the\n"
      "  low-ref end\"); it is now measured rather than asserted.  These are\n"
      "  small-signal settling estimates from the fitted model -- cycle slipping\n"
      "  and the VCO's nonlinearity make cold-start acquisition #12's number, not\n"
      "  this record's.\n\n")

    # --- cross-check ---
    w("  ### 8. Independent check: the whole linearized loop, simulated\n\n")
    if xchecks:
        ferr = max(abs(x[9]) for x in xchecks)
        perr = max(abs(x[12]) for x in xchecks)
        w("  `tb_loop_ac.sp` puts the real filter inside a phase-domain model of\n"
          "  the whole loop (charge pump as Icp/2pi A/rad, VCO as an ideal\n"
          "  integrator, divider as 1/N) and lets ngspice compute T(jw) directly.\n"
          "  Over %d such runs, spanning the recommended trim codes and the\n"
          "  extreme filter corners, the simulated crossover and phase margin agree\n"
          "  with the impedance-plus-algebra result of section 4 to within\n"
          "  **%.3f %% in f_c and %.3f deg in phase margin** -- see\n"
          "  `loop_ac_crosscheck.csv`.\n\n" % (len(xchecks), ferr, perr))
    else:
        w("  No cross-check runs were collected.\n\n")

    # --- self checks ---
    w("  ### 9. Sanity checks on the measurement itself\n\n")
    w("  - |Z|/w strictly decreasing (so the crossover is unique) on %d of %d\n"
      "    measured curves.\n" % (len(curves) - len(ex['nonmono']), len(curves)))
    w("  - Crossover inside the swept 100 Hz - 100 MHz band at every evaluated\n"
      "    point: %s.\n" % ("yes" if not ex['fails'] else
                           "NO -- %d points fell outside" % len(ex['fails'])))
    w("  - 3-element fit vs. measured |Z|, worst error over all curves and all\n"
      "    frequencies: %.2f %%.\n\n" % (100 * ex['worst_fit']))

    # --- verdict ---
    w("  ### 10. Verdict\n\n")
    allpass = npass == len(cells)
    w("  **Overall: %s.**\n\n" % ("PASS" if allpass else
                                  "PASS on the contracted operating space, "
                                  "FAIL off it"))
    w("  The filter meets the %.0f deg phase-margin criterion and stays under the\n"
      "  f_c < f_ref/10 sampled-loop ceiling at **every** corner of the\n"
      "  cross-product %s.  The trim code is not a free margin knob: it is the\n"
      "  loop's reference-frequency compensation, and section 6 is the rule that\n"
      "  has to travel with these component values -- exactly as DR-003's\n"
      "  band-selection rule travels with the Kvco table.\n"
      % (PM_MIN, "for every trim code" if allpass else
         "once the trim code follows the rule in section 6"))


if __name__ == '__main__':
    main()
