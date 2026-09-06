#!/usr/bin/env python3
"""Unit tests for the harness's ngspice internal-thread budget.

    python3 -m unittest discover -s sim/tests -v

No PDK and no ngspice required: detection is driven through the same
``SIMENV_NGSPICE_LDD_OUTPUT`` override ``sim/lib/test_simenv_omp_pin.sh`` uses
for the shell half of the same fix (#241/#244), so both halves are tested
against literal ``ldd`` output rather than against whatever binary happens to
be installed on the test host.

The failure being guarded against is *self-oversubscription*: an OpenMP-linked
``ngspice`` spawns its own threads per process, so a grid run that fans out
``jobs`` processes demands ``jobs x threads`` of an ``ncpu``-core host. The
shell campaign path was fixed in #241/#244; the Python harness path -- what
``sim/run_corners.py`` drives, and therefore what every migrated campaign now
runs through -- was not, and its default ``jobs`` is ``min(8, ncpu)``.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SIM_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SIM_DIR))

from harness import omp, report  # noqa: E402

# Literal `ldd` output shapes, in the spirit of sim/lib/test_simenv_omp_pin.sh.
LDD_OPENMP = (
    "\tlinux-vdso.so.1 (0x00007ffd8b5f0000)\n"
    "\tlibgomp.so.1 => /lib/x86_64-linux-gnu/libgomp.so.1 (0x00007f0e3c000000)\n"
    "\tlibm.so.6 => /lib/x86_64-linux-gnu/libm.so.6 (0x00007f0e3bf00000)\n"
)
LDD_NO_OPENMP = (
    "\tlinux-vdso.so.1 (0x00007ffd8b5f0000)\n"
    "\tlibm.so.6 => /lib/x86_64-linux-gnu/libm.so.6 (0x00007f0e3bf00000)\n"
    "\tlibc.so.6 => /lib/x86_64-linux-gnu/libc.so.6 (0x00007f0e3bc00000)\n"
)


def env(ldd: str | None = None, **extra: str) -> dict[str, str]:
    base = dict(extra)
    if ldd is not None:
        base[omp.LDD_OVERRIDE_ENV] = ldd
    return base


class DetectionTests(unittest.TestCase):
    def test_libgomp_counts_as_openmp_linked(self):
        self.assertTrue(omp.ngspice_openmp_linked(env=env(LDD_OPENMP)))

    def test_llvm_and_intel_runtimes_count_too(self):
        for soname in ("libomp.so", "libiomp5.so"):
            with self.subTest(soname=soname):
                self.assertTrue(
                    omp.ngspice_openmp_linked(env=env(f"\t{soname} => /lib/{soname}\n"))
                )

    def test_a_build_without_an_openmp_runtime_is_not_linked(self):
        self.assertFalse(omp.ngspice_openmp_linked(env=env(LDD_NO_OPENMP)))

    def test_empty_probe_output_is_treated_as_not_linked(self):
        # "cannot tell" and "no" collapse deliberately: both must lead to the
        # same leave-the-environment-alone behavior.
        self.assertFalse(omp.ngspice_openmp_linked(env=env("")))


class ThreadBudgetTests(unittest.TestCase):
    def test_serial_runs_get_no_budget_at_all(self):
        # jobs<=1 cannot self-oversubscribe, so the harness must not serialize
        # a single ngspice's own model evaluation for zero benefit.
        self.assertIsNone(omp.thread_budget(1, cpu_count=8))
        self.assertIsNone(omp.thread_budget(0, cpu_count=8))

    def test_budget_divides_the_machine_between_workers(self):
        self.assertEqual(omp.thread_budget(2, cpu_count=8), 4)
        self.assertEqual(omp.thread_budget(4, cpu_count=8), 2)

    def test_total_thread_demand_never_exceeds_the_core_count(self):
        for cpus in (1, 2, 4, 8, 16, 64):
            for jobs in range(2, 2 * cpus + 3):
                budget = omp.thread_budget(jobs, cpu_count=cpus)
                with self.subTest(cpus=cpus, jobs=jobs):
                    self.assertGreaterEqual(budget, 1)
                    if jobs <= cpus:
                        self.assertLessEqual(jobs * budget, cpus)

    def test_oversubscribed_job_count_floors_at_one_thread(self):
        # This is simenv_apply_omp_pin's literal `1`, reached as the limiting
        # case of the same rule rather than as a separate special case.
        self.assertEqual(omp.thread_budget(8, cpu_count=8), 1)
        self.assertEqual(omp.thread_budget(32, cpu_count=8), 1)


class EnvOverrideTests(unittest.TestCase):
    def test_parallel_run_on_an_openmp_build_pins_both_variables(self):
        self.assertEqual(
            omp.omp_env_overrides(4, env=env(LDD_OPENMP), cpu_count=8),
            {"OMP_NUM_THREADS": "2", "OMP_THREAD_LIMIT": "2"},
        )

    def test_non_openmp_build_is_left_completely_alone(self):
        self.assertEqual(
            omp.omp_env_overrides(8, env=env(LDD_NO_OPENMP), cpu_count=8), {}
        )

    def test_serial_run_is_left_completely_alone_even_on_an_openmp_build(self):
        self.assertEqual(
            omp.omp_env_overrides(1, env=env(LDD_OPENMP), cpu_count=8), {}
        )

    def test_caller_set_values_are_respected_independently(self):
        # #244: OMP_NUM_THREADS and OMP_THREAD_LIMIT are NOT interchangeable,
        # so setting one must never suppress defaulting the other.
        self.assertEqual(
            omp.omp_env_overrides(
                4, env=env(LDD_OPENMP, OMP_NUM_THREADS="3"), cpu_count=8
            ),
            {"OMP_THREAD_LIMIT": "2"},
        )
        self.assertEqual(
            omp.omp_env_overrides(
                4, env=env(LDD_OPENMP, OMP_THREAD_LIMIT="3"), cpu_count=8
            ),
            {"OMP_NUM_THREADS": "2"},
        )
        self.assertEqual(
            omp.omp_env_overrides(
                4,
                env=env(LDD_OPENMP, OMP_NUM_THREADS="3", OMP_THREAD_LIMIT="3"),
                cpu_count=8,
            ),
            {},
        )


class ExecutionProvenanceTests(unittest.TestCase):
    """The record has to disclose the budget, not just apply it.

    ``sim/README.md``'s Environment-provenance rule is that the environment be
    reconstructable from the record alone; on an internally-threaded build the
    per-point wall clock is not reproducible from ``jobs`` alone.
    """

    def test_pinned_run_reports_both_variables(self):
        lines = report._execution_lines(
            {"jobs": 8, "omp": {"OMP_NUM_THREADS": "1", "OMP_THREAD_LIMIT": "1"}}
        )
        self.assertEqual(len(lines), 1)
        self.assertIn("8 parallel ngspice job(s)", lines[0])
        self.assertIn("`OMP_NUM_THREADS=1`", lines[0])
        self.assertIn("`OMP_THREAD_LIMIT=1`", lines[0])

    def test_unpinned_run_says_so_rather_than_staying_silent(self):
        lines = report._execution_lines({"jobs": 1, "omp": {}})
        self.assertEqual(len(lines), 1)
        self.assertIn("none applied", lines[0])

    def test_records_predating_this_field_render_unchanged(self):
        # Append-only evidence: an older record carries no execution block and
        # must not grow a line claiming anything about how it was scheduled.
        self.assertEqual(report._execution_lines({}), [])


if __name__ == "__main__":
    unittest.main()
