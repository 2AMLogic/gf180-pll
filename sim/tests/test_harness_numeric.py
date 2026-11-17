"""``sim/harness/numeric`` -- the shared crossing and linfit primitives.

What is pinned here is exactly the edge behaviour the consolidation (#985)
had to preserve: the two DIFFERENT windowing conventions (a ``tmin`` that
gates the straddling pair's earlier sample, a ``window`` that gates its later
one), the strict straddle test that makes a flat segment at the level produce
no crossing, and the slew variants' increasing-time requirement.  A future
"simplification" that merged the window conventions or loosened the straddle
test would move the first kept crossing of real recorded data and silently
change derived jitter numbers -- these tests are what makes that loud.

No PDK, no ngspice, no network.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SIM_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SIM_DIR))

from harness.numeric import crossings, linfit  # noqa: E402


class RisingCrossings(unittest.TestCase):
    def test_straddle_interpolates_on_the_chord(self):
        t = [0, 1, 2, 3, 4]
        y = [0, 2, 0, 2, 0]
        self.assertEqual(crossings(t, y, 1.0), [0.5, 2.5])

    def test_a_sample_on_the_level_belongs_to_the_arriving_crossing(self):
        # level <= y[i] is inclusive, y[i-1] < level is strict: a sample
        # sitting exactly on the level ENDS a rising crossing (at the sample
        # itself) and cannot start another one.
        t = [0, 1, 2, 3]
        y = [0, 1, 2, 0]
        self.assertEqual(crossings(t, y, 1.0), [1.0])

    def test_a_flat_segment_at_the_level_adds_no_crossing(self):
        # The zero-slope guards the old copies carried were dead code; this is
        # the input class they were presumably fearing, and the strict
        # straddle test alone excludes it -- the crossing is the arrival at
        # t=1, never a mid-segment one.
        t = [0, 1, 2, 3, 4, 5]
        y = [0, 1, 1, 1, 2, 0]
        self.assertEqual(crossings(t, y, 1.0), [1.0])

    def test_non_monotonic_time_still_interpolates_without_slew(self):
        t = [1, 0, 2]
        y = [0, 2, 0]
        self.assertEqual(crossings(t, y, 1.0), [0.5])


class TminWindow(unittest.TestCase):
    """`tmin` gates the pair's EARLIER sample -- the settle-window convention."""

    def test_ungated(self):
        t = [0, 1, 2, 3, 4]
        y = [0, 2, 0, 2, 0]
        self.assertEqual(crossings(t, y, 1.0, tmin=0.0), [0.5, 2.5])

    def test_earlier_sample_exactly_at_tmin_is_kept(self):
        t = [0, 1, 2, 3, 4]
        y = [0, 2, 0, 2, 0]
        self.assertEqual(crossings(t, y, 1.0, tmin=2.0), [2.5])

    def test_pair_whose_earlier_sample_precedes_tmin_is_dropped(self):
        # The crossing at 2.5 comes from the pair (2, 3); its interpolated
        # time 2.5 is inside the window, but the convention gates the EARLIER
        # sample (2 < 2.5), so the pair is gone -- a later-sample gate would
        # have kept it.  This is the boundary case that keeps the two window
        # arguments separate.
        t = [0, 1, 2, 3, 4]
        y = [0, 2, 0, 2, 0]
        self.assertEqual(crossings(t, y, 1.0, tmin=2.5), [])


class BandWindow(unittest.TestCase):
    """`window` gates the pair's LATER sample, inclusively -- the TIE window."""

    def test_pair_whose_later_sample_is_inside_is_kept(self):
        # The crossing at 2.5 comes from the pair (2, 3): its earlier sample
        # 2 is BELOW t0=3 and the crossing itself lies before t0, but the
        # convention gates the LATER sample -- the mirror of the tmin case.
        t = [0, 1, 2, 3, 4]
        y = [0, 2, 0, 2, 0]
        self.assertEqual(crossings(t, y, 1.0, window=(3.0, 4.0)), [2.5])

    def test_bounds_are_inclusive(self):
        t = [0, 1, 2, 3, 4]
        y = [0, 2, 0, 2, 0]
        self.assertEqual(crossings(t, y, 1.0, window=(1.0, 1.0)), [0.5])
        self.assertEqual(crossings(t, y, 1.0, window=(2.0, 3.0)), [2.5])

    def test_later_sample_above_t1_is_dropped(self):
        # crossing 2.5 lies inside [2, 2.99] but the later sample 3 does not
        t = [0, 1, 2, 3, 4]
        y = [0, 2, 0, 2, 0]
        self.assertEqual(crossings(t, y, 1.0, window=(2.0, 2.99)), [])


class SlewVariants(unittest.TestCase):
    def test_rising_slew_is_the_chord_slope(self):
        t = [10, 11]
        y = [0.0, 2.0]
        self.assertEqual(crossings(t, y, 0.5, slew=True),
                         [{"t": 10.25, "slew": 2.0}])

    def test_non_increasing_time_is_dropped_only_when_slew_is_asked_for(self):
        t = [1, 0, 2]
        y = [0, 2, 0]
        self.assertEqual(crossings(t, y, 1.0), [0.5])
        self.assertEqual(crossings(t, y, 1.0, slew=True), [])

    def test_falling_mirror(self):
        t = [0, 1, 2, 3]
        y = [2, 0, 2, 0]
        self.assertEqual(crossings(t, y, 1.0, slew=True, falling=True),
                         [{"t": 0.5, "slew": 2.0}, {"t": 2.5, "slew": 2.0}])

    def test_falling_straddle_test_is_the_mirror(self):
        # inclusive on the earlier side, strict on the later one
        self.assertEqual(crossings([0, 1], [1.0, 0.0], 1.0, falling=True), [0.0])
        self.assertEqual(crossings([0, 1], [1.0, 1.0], 1.0, falling=True), [])


class Linfit(unittest.TestCase):
    def test_exact_line(self):
        slope, intercept, r2 = linfit([0, 1, 2, 3], [2.0, 5.0, 8.0, 11.0])
        self.assertEqual((slope, intercept), (3.0, 2.0))
        self.assertEqual(r2, 1.0)

    def test_flat_ys_report_a_perfect_fit(self):
        self.assertEqual(linfit([0, 1, 2], [4.0, 4.0, 4.0]), (0.0, 4.0, 1.0))

    def test_too_few_points_or_no_x_spread_is_not_a_fit(self):
        self.assertEqual(linfit([1], [1.0]), (None, None, None))
        self.assertEqual(linfit([], []), (None, None, None))
        self.assertEqual(linfit([2, 2, 2], [1.0, 2.0, 3.0]), (None, None, None))

    def test_r2_falls_when_the_model_does_not_hold(self):
        xs = [2.5, 1.9, 1.5, 1.1, 0.9, 0.7]
        ys = [9e-4 + 3e-4 * (q ** 3) for q in xs]
        _, _, r2 = linfit(xs, ys)
        self.assertLess(r2, 0.999)


if __name__ == "__main__":
    unittest.main()
