#!/usr/bin/env python3
"""gf180-pll :: loop-dynamics :: choose the loop-AC cross-check points.

`tb_loop_ac.sp` re-simulates the whole linearized loop at a handful of points as
an independent check on `tb_loop_filter_ac.sp` + `analyze.py`.  Those points must
carry REAL Icp and Kvco values, not invented ones, so this helper reads #8's
`kvco_by_point.csv` and #9's `cp_dc.csv` and emits one job line per point:

    <tag> <bundle> <libs> <temp_c> <vctrl_v> <icp_a> <kvco_hz_per_v> <n_div>

The Kvco is the measured value at the typical VCO corner, in the lowest band
that reaches the target f_out (DR-003 Decision 4's band-selection rule); the Icp
is the measured mean of both polarities at that trim code at the typical CP
corner.  The filter corner/temperature/Vctrl triples span the passive corner box.

Usage:  pick_xcheck.py <kvco_by_point.csv> <cp_dc.csv>
"""

import csv
import sys
from collections import defaultdict

# (f_ref Hz, N, trim legs) -- one per reference decade, at the trim code the
# loop is expected to use there.  f_out = f_ref*N must be inside 10-200 MHz.
POINTS = [(1e6, 32, 4), (2e6, 32, 3), (4e6, 16, 3), (8e6, 12, 2),
          (16e6, 8, 2), (25e6, 6, 1)]
# filter corner points: (bundle, lib sections, temp, Vctrl)
FILTERS = [
    ('rtyp-mtyp-xtyp', 'res_typical,moscap_typical,mimcap_typical', 27, 1.8),
    ('rss-mss-xss', 'res_ss,moscap_ss,mimcap_ss', -40, 0.9),
    ('rff-mff-xff', 'res_ff,moscap_ff,mimcap_ff', 125, 2.7),
]
TYP = ('typical', 27.0, 3.30)


def main():
    kpath, cpath = sys.argv[1], sys.argv[2]
    idx = defaultdict(list)
    with open(kpath) as fh:
        for row in csv.DictReader(l for l in fh if not l.startswith('#')):
            idx[(row['bundle'], float(row['temp_c']), float(row['vdd_v']),
                 int(row['band']))].append((float(row['vctrl_v']),
                                            float(row['fosc_hz']),
                                            float(row['kvco_hz_per_v'])))
    for v in idx.values():
        v.sort()

    def kvco(fout):
        for b in range(8):
            pts = idx[TYP + (b,)]
            fs = [p[1] for p in pts]
            if not (fs[0] <= fout <= fs[-1]):
                continue
            for i in range(len(fs) - 1):
                if fs[i] <= fout <= fs[i + 1]:
                    t = (fout - fs[i]) / (fs[i + 1] - fs[i])
                    return pts[i][2] + t * (pts[i + 1][2] - pts[i][2])
        return None

    icp = {}
    with open(cpath) as fh:
        for row in csv.DictReader(l for l in fh if not l.startswith('#')):
            if row['process'] == 'typical' and float(row['temp_c']) == 27 and \
                    abs(float(row['vdd_v']) - 3.30) < 1e-9:
                icp[int(row['units'])] = 0.5 * (abs(float(row['iup_mid_a'])) +
                                                abs(float(row['idn_mid_a'])))

    for fr, n, legs in POINTS:
        k = kvco(fr * n)
        if k is None:
            sys.stderr.write('ERROR: no band reaches f_out=%g at the typical '
                             'corner\n' % (fr * n))
            sys.exit(1)
        for bundle, libs, temp, vctrl in FILTERS:
            tag = 'loop_%s_T%s_F%g_N%d_L%d' % (bundle, temp, fr / 1e6, n, legs)
            tag = tag.replace('.', 'p')
            print('%s %s %s %s %s %.6g %.6g %d' %
                  (tag, bundle, libs, temp, vctrl, icp[legs], k, n))


if __name__ == '__main__':
    main()
