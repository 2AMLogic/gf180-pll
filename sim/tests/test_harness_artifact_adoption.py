#!/usr/bin/env python3
"""Unit tests for the artifact-store adoption flow (issue #1048).

Under ``--artifact-store`` the harness banks each completed point's raw
logs in the fleet artifact store as it finishes, keyed by the run's grid
fingerprint, and a fresh invocation on any host adopts those stored points
(sha256-verified, replay-qualified) instead of re-simulating them. The store
is faked end to end here -- a fake ``artifact-put.sh`` writer that mirrors
bytes into a directory a fake ``klt artifact get`` reads back -- so no
broker and no ngspice is needed.

    python3 -m unittest discover -s sim/tests -v
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

SIM_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SIM_DIR))

from harness import artifacts, cli, corners, report, runner  # noqa: E402
from harness import testbench as tb_mod  # noqa: E402
from _fixtures import ManifestFixture, fake_pdk  # noqa: E402

MEASURE_OK = "m_vout = 1.65000e+00\n"


def sha256_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _dead_pid() -> int:
    """A pid that belonged to a process which has already exited -- what
    makes a reservation read back ``interrupted`` instead of ``running``."""
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    proc.wait()
    return proc.pid


# The fake writer + fake get are one contract, shared by both test classes:
# `artifact-put.sh <bench> <run-id> [--manifest P] <file>...` mirrors each
# file's bytes into $FAKE_STORE_DIR/<sha256> and merges one manifest entry
# per file (name = the staged path, exactly what klt records); the fake get
# hands back those bytes for a sha256, or fails when the object is absent.
FAKE_PUT = """#!/usr/bin/env python3
import hashlib, json, os, sys
from pathlib import Path
fail_after = os.environ.get('FAKE_PUT_FAIL_AFTER')
if fail_after is not None:
    marker = Path(os.environ['FAKE_STORE_DIR']) / '.put-calls'
    n = (int(marker.read_text()) + 1) if marker.exists() else 1
    marker.write_text(str(n))
    if n > int(fail_after):
        sys.stderr.write('fake writer failed\\n')
        sys.exit(3)
if {exit_code} != 0:
    sys.stderr.write('fake writer failed\\n')
    sys.exit({exit_code})
args = sys.argv[1:]
manifest = None
rest = []
i = 0
while i < len(args):
    if args[i] == '--manifest':
        manifest = args[i + 1]; i += 2
    else:
        rest.append(args[i]); i += 1
bench, run_id, files = rest[0], rest[1], rest[2:]
default_dir = os.environ['FAKE_MANIFEST_DIR']
mp = Path(manifest or (Path(default_dir) / f'{{bench}}-{{run_id}}.manifest.json'))
entries = []
if mp.exists():
    entries = json.loads(mp.read_text()).get('entries', [])
store = os.environ['FAKE_STORE_DIR']
for f in files:
    data = Path(f).read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    entries.append({{'sha256': digest, 'size': len(data),
        'kind': 'evidence',
        'producer': {{'tool': 'fake', 'version': '0',
                     'loom.repo': 't/t', 'commit': 'c'}},
        'uri': 'artifact:fake/' + digest,
        'name': str(f)}})
    (Path(store) / digest).write_bytes(data)
mp.parent.mkdir(parents=True, exist_ok=True)
mp.write_text(json.dumps({{'schema_version': 1, 'entries': entries}}, indent=2))
"""


class AdoptionHelperTests(unittest.TestCase):
    """The artifacts-module primitives, against a fake writer and store."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="artifact-adoption-"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        patcher = unittest.mock.patch.object(artifacts, "STAGE_DIR", self.root / "stage")
        patcher.start()
        self.addCleanup(patcher.stop)
        self.manifest_dir = self.root / "manifests" / "artifacts"
        self.manifest_dir.mkdir(parents=True)
        self.store_dir = self.root / "fake-store"
        self.store_dir.mkdir()
        self.calls = self.root / "calls.txt"

        self.tb = tb_mod.load(self._write_tb(self.root / "an-experiment"))
        self.points = corners.build_grid(
            corners.resolve_corners(["typical"]), (27,), [3.3]
        )
        self.fingerprint = "f" * 64

    def _write_tb(self, root: Path) -> Path:
        tb_dir = root / "testbench"
        tb_dir.mkdir(parents=True, exist_ok=True)
        (tb_dir / "x.spice").write_text("v1 out 0 dc {vdd_val}\n")
        (tb_dir / "tb.json").write_text(json.dumps(
            {"name": root.name, "netlist": "x.spice", "measure": {"vout": "v(out)"}}
        ))
        return tb_dir

    def fake_writer(self, exit_code: int = 0) -> Path:
        script = self.root / "fake-put.py"
        script.write_text(
            "#!/usr/bin/env python3\n"
            "import hashlib, json, os, sys\n"
            f"calls = open({str(self.calls)!r}, 'a')\n"
            "calls.write(repr(sys.argv[1:]) + chr(10))\n"
            "calls.close()\n"
            + FAKE_PUT.format(exit_code=exit_code)
        )
        script.chmod(script.stat().st_mode | stat.S_IXUSR)
        return script

    def seed_stored_point(
        self, corner_id: str, run_id: str, text: str, *, fingerprint: str | None = None
    ) -> str:
        """Store one log the way a prior attempt would have, returning its sha."""
        fp = fingerprint or self.fingerprint
        staged = artifacts.STAGE_DIR / f"{self.tb.experiment}-perpoint" / fp / corner_id
        staged.mkdir(parents=True, exist_ok=True)
        src = staged / f"{run_id}.log"
        src.write_text(text)
        digest = sha256_of(text.encode())
        (self.store_dir / digest).write_text(text)
        manifest = self.manifest_dir / f"{self.tb.experiment}-perpoint-rid-1.manifest.json"
        doc = {"schema_version": 1, "entries": []}
        if manifest.exists():
            doc = json.loads(manifest.read_text())
        doc["entries"].append({
            "sha256": digest, "size": len(text), "kind": "evidence",
            "producer": {"tool": "fake", "version": "0", "loom.repo": "t/t",
                         "commit": "c"},
            "uri": f"artifact:fake/{digest}",
            "name": str(src),
        })
        manifest.write_text(json.dumps(doc, indent=2))
        return digest

    def test_require_store_fails_closed_without_broker(self):
        env = {k: v for k, v in os.environ.items() if k != "KLT_ARTIFACT_BROKER"}
        with unittest.mock.patch.dict(os.environ, env, clear=True):
            with self.assertRaises(artifacts.ArtifactUploadError):
                artifacts.require_store("--artifact-store")

    def test_require_store_fails_closed_without_klt_subcommands(self):
        def _no_klt(cmd, **kwargs):
            return subprocess.CompletedProcess(args=cmd, returncode=2,
                                               stdout="", stderr="")

        with unittest.mock.patch.dict(os.environ, {"KLT_ARTIFACT_BROKER": "http://b"}), \
                unittest.mock.patch.object(artifacts.subprocess, "run",
                                           side_effect=_no_klt):
            with self.assertRaises(artifacts.ArtifactUploadError):
                artifacts.require_store("--artifact-store")

    def test_require_store_fails_closed_without_klt_binary(self):
        # `klt` not on PATH raises FileNotFoundError from subprocess.run
        # itself; the preflight must convert that to the same clean refusal
        # as a klt lacking the subcommand, not an unhandled traceback (#1049).
        def _no_binary(cmd, **kwargs):
            raise FileNotFoundError(2, "No such file or directory", cmd[0])

        with unittest.mock.patch.dict(os.environ, {"KLT_ARTIFACT_BROKER": "http://b"}), \
                unittest.mock.patch.object(artifacts.subprocess, "run",
                                           side_effect=_no_binary):
            with self.assertRaises(artifacts.ArtifactUploadError) as ctx:
                artifacts.require_store("--artifact-store")
        self.assertIn("klt not found on PATH", str(ctx.exception))

    def test_store_point_logs_uploads_and_cleans_stage(self):
        log_dir = self.root / "corners" / "rid-9"
        log_dir.mkdir(parents=True)
        corner_id = self.points[0].corner_id
        run_id = self.tb.run_phases[0].run_id(corner_id)
        (log_dir / f"{run_id}.log").write_text(MEASURE_OK)
        env = {"FAKE_STORE_DIR": str(self.store_dir),
               "FAKE_MANIFEST_DIR": str(self.manifest_dir)}
        with unittest.mock.patch.dict(os.environ, env):
            artifacts.store_point_logs(
                self.tb.experiment, "rid-9", self.fingerprint, corner_id,
                [log_dir / f"{run_id}.log"], put_script=self.fake_writer(0),
                manifest_dir=self.manifest_dir,
            )
        argv = eval(self.calls.read_text().splitlines()[0])  # noqa: S307 - fixture
        self.assertEqual(argv[0], self.tb.experiment)
        self.assertEqual(argv[1], "perpoint-rid-9")
        self.assertIn("--manifest", argv)
        self.assertTrue(
            (self.manifest_dir
             / f"{self.tb.experiment}-perpoint-rid-9.manifest.json").is_file()
        )
        # The staged copy is gone; the log_dir source stays for the
        # end-of-run store.
        self.assertEqual(list((self.root / "stage").rglob("*.log")), [])
        self.assertTrue((log_dir / f"{run_id}.log").exists())

    def test_store_point_logs_fails_closed_on_writer_failure(self):
        log_dir = self.root / "corners" / "rid-10"
        log_dir.mkdir(parents=True)
        corner_id = self.points[0].corner_id
        run_id = self.tb.run_phases[0].run_id(corner_id)
        (log_dir / f"{run_id}.log").write_text(MEASURE_OK)
        env = {"FAKE_STORE_DIR": str(self.store_dir),
               "FAKE_MANIFEST_DIR": str(self.manifest_dir)}
        with unittest.mock.patch.dict(os.environ, env):
            with self.assertRaises(artifacts.ArtifactUploadError) as ctx:
                artifacts.store_point_logs(
                    self.tb.experiment, "rid-10", self.fingerprint, corner_id,
                    [log_dir / f"{run_id}.log"], put_script=self.fake_writer(7),
                    manifest_dir=self.manifest_dir,
                )
        self.assertIn("writer exit 7", str(ctx.exception))
        self.assertFalse(
            (self.manifest_dir
             / f"{self.tb.experiment}-perpoint-rid-10.manifest.json").exists()
        )

    def test_store_point_logs_refuses_a_missing_log(self):
        corner_id = self.points[0].corner_id
        run_id = self.tb.run_phases[0].run_id(corner_id)
        with unittest.mock.patch.dict(os.environ,
                                      {"FAKE_STORE_DIR": str(self.store_dir),
                                       "FAKE_MANIFEST_DIR": str(self.manifest_dir)}):
            with self.assertRaises(artifacts.ArtifactUploadError):
                artifacts.store_point_logs(
                    self.tb.experiment, "rid-11", self.fingerprint, corner_id,
                    [self.root / "no-such" / f"{run_id}.log"],
                    put_script=self.fake_writer(0), manifest_dir=self.manifest_dir,
                )
        self.assertFalse(self.calls.exists())

    def test_lookup_matches_only_this_fingerprints_entries(self):
        corner_id = self.points[0].corner_id
        run_id = self.tb.run_phases[0].run_id(corner_id)
        self.seed_stored_point(corner_id, run_id, MEASURE_OK)
        self.seed_stored_point(corner_id, run_id, MEASURE_OK,
                               fingerprint="a" * 64)
        stored, sources = artifacts.lookup_stored_points(
            self.tb.experiment, self.fingerprint, self.manifest_dir
        )
        self.assertEqual(stored,
                         {corner_id: {run_id: sha256_of(MEASURE_OK.encode())}})
        self.assertEqual(sources, ["rid-1"])
        # A different fingerprint must adopt nothing.
        stored, sources = artifacts.lookup_stored_points(
            self.tb.experiment, "b" * 64, self.manifest_dir
        )
        self.assertEqual(stored, {})
        self.assertEqual(sources, [])

    def test_two_attempts_storing_the_same_point_is_idempotent(self):
        """Two concurrent attempts banking the same completed point write
        the same content-addressed object twice; both succeed and each
        attempt's manifest carries its own entry."""
        log_dir = self.root / "corners" / "rid-12"
        log_dir.mkdir(parents=True)
        corner_id = self.points[0].corner_id
        run_id = self.tb.run_phases[0].run_id(corner_id)
        (log_dir / f"{run_id}.log").write_text(MEASURE_OK)
        env = {"FAKE_STORE_DIR": str(self.store_dir),
               "FAKE_MANIFEST_DIR": str(self.manifest_dir)}
        with unittest.mock.patch.dict(os.environ, env):
            for record_id in ("rid-12", "rid-13"):
                artifacts.store_point_logs(
                    self.tb.experiment, record_id, self.fingerprint, corner_id,
                    [log_dir / f"{run_id}.log"], put_script=self.fake_writer(0),
                    manifest_dir=self.manifest_dir,
                )
        objects = [p for p in self.store_dir.iterdir()]
        self.assertEqual(len(objects), 1, "the store is content-addressed")
        stored, sources = artifacts.lookup_stored_points(
            self.tb.experiment, self.fingerprint, self.manifest_dir
        )
        self.assertEqual(stored, {corner_id: {run_id: sha256_of(MEASURE_OK.encode())}})
        self.assertEqual(sources, ["rid-12", "rid-13"])

    def test_lookup_skips_malformed_and_foreign_manifests(self):
        (self.manifest_dir / "broken.manifest.json").write_text("{not json")
        (self.manifest_dir / "wrongshape.manifest.json").write_text(
            '{"schema_version": 1}')
        corner_id = self.points[0].corner_id
        run_id = self.tb.run_phases[0].run_id(corner_id)
        digest = self.seed_stored_point(corner_id, run_id, MEASURE_OK)
        # An entry of another bench must stay invisible to this bench's scan.
        other = self.manifest_dir / "other-bench-perpoint-rid-2.manifest.json"
        other.write_text(json.dumps({"schema_version": 1, "entries": [{
            "sha256": digest, "size": 1, "kind": "evidence",
            "producer": {"tool": "fake", "version": "0", "loom.repo": "t/t",
                         "commit": "c"},
            "uri": f"artifact:fake/{digest}",
            "name": "other-bench-perpoint/"
                    f"{self.fingerprint}/{corner_id}/{run_id}.log",
        }]}))
        stored, sources = artifacts.lookup_stored_points(
            self.tb.experiment, self.fingerprint, self.manifest_dir
        )
        self.assertEqual(list(stored), [corner_id])
        self.assertEqual(sources, ["rid-1"])

    def test_fetch_verifies_bytes_and_cleans_up_on_mismatch(self):
        digest = sha256_of(MEASURE_OK.encode())
        (self.store_dir / digest).write_text(MEASURE_OK)
        dest = self.root / "fetched" / "x.log"

        def _klt_get(cmd, **kwargs):
            self.assertEqual(cmd[:3], ["klt", "artifact", "get"])
            sha = cmd[3]
            out = Path(cmd[cmd.index("-o") + 1])
            obj = self.store_dir / sha
            if not obj.exists():
                return subprocess.CompletedProcess(args=cmd, returncode=1,
                                                   stdout="", stderr="no object")
            out.write_bytes(obj.read_bytes())
            return subprocess.CompletedProcess(args=cmd, returncode=0,
                                               stdout="", stderr="")

        with unittest.mock.patch.object(artifacts.subprocess, "run",
                                        side_effect=_klt_get):
            self.assertTrue(artifacts.fetch_stored_log(digest, dest))
            self.assertEqual(dest.read_text(), MEASURE_OK)
            # A stored object whose bytes come back corrupted: refused, and
            # nothing is left on disk to be mistaken for evidence.
            (self.store_dir / digest).write_text("corrupted")
            self.assertFalse(artifacts.fetch_stored_log(digest, dest))
            self.assertFalse(dest.exists())
            # An object the broker has lost: refused, clean.
            (self.store_dir / digest).unlink()
            self.assertFalse(artifacts.fetch_stored_log(digest, dest))
            self.assertFalse(dest.exists())


class CliAdoptionTests(ManifestFixture):
    """The end-to-end adoption flow through ``cli.run()``, against a faked
    ``run_grid`` (which writes real per-point logs, so the per-point uploads
    have something real to bank) and a faked store."""

    def setUp(self):
        super().setUp()
        self.write({"measure": {"vout": "v(out)"}})
        self.pdk = fake_pdk(self.root / "gf180mcuD")
        self.tb = tb_mod.load(self.tb_dir)
        self.shared = Path(tempfile.mkdtemp(prefix="artifact-adoption-shared-"))
        self.addCleanup(shutil.rmtree, self.shared, ignore_errors=True)
        self.manifest_dir = self.shared / "manifests" / "artifacts"
        self.manifest_dir.mkdir(parents=True)
        self.store_dir = self.shared / "fake-store"
        self.store_dir.mkdir()
        self.stage_dir = self.shared / "stage"
        self.fake_store_env = {
            "FAKE_STORE_DIR": str(self.store_dir),
            "FAKE_MANIFEST_DIR": str(self.manifest_dir),
            "SIM_MOSCAP_PROBE_RESULT": "ok",
            "KLT_ARTIFACT_BROKER": "http://broker.invalid",
        }
        for patch in (
            unittest.mock.patch.object(artifacts, "MANIFEST_DIR", self.manifest_dir),
            unittest.mock.patch.object(artifacts, "STAGE_DIR", self.stage_dir),
        ):
            patch.start()
            self.addCleanup(patch.stop)

    # -- shared scaffolding ----------------------------------------------

    def _args(self, *extra):
        return cli.build_parser().parse_args(
            [
                self.slug,
                "--corners", "typical",
                "--temps", "27", "125",
                "--supply-tol", "0",
                "--subset-reason", "unit test: exercising the adoption flow",
                "-j", "1",
                *extra,
            ]
        )

    def _install_fake_writer(self, exit_code: int = 0) -> Path:
        script = self.shared / "fake-put.py"
        script.write_text(FAKE_PUT.format(exit_code=exit_code))
        script.chmod(script.stat().st_mode | stat.S_IXUSR)
        patcher = unittest.mock.patch.object(artifacts, "PUT_SCRIPT", script)
        patcher.start()
        self.addCleanup(patcher.stop)
        return script

    def _run_cli(self, args, fake_run_grid, *, sim_dir=None, broker="set"):
        """Drive ``cli.run()``. ``broker``: "set" patches a broker URL into
        the environment; any other value replaces it (empty string = unset,
        for the preflight test). The ``klt artifact get`` calls adoption
        makes are routed to the fake store; every other subprocess (the
        fake writer script, git) runs for real."""
        buf_out, buf_err = io.StringIO(), io.StringIO()
        env = dict(self.fake_store_env)
        if broker != "set":
            env["KLT_ARTIFACT_BROKER"] = broker
        real_run = subprocess.run

        def _proc_router(cmd, **kwargs):
            if cmd[:4] in (["klt", "artifact", "put", "--help"],
                           ["klt", "artifact", "get", "--help"]):
                # require_store's preflight probe: this klt has the flow's
                # subcommands, so the run proceeds to the fake store below.
                return subprocess.CompletedProcess(
                    args=cmd, returncode=0, stdout="", stderr="")
            if cmd[:3] == ["klt", "artifact", "get"] and "-o" in cmd:
                sha = cmd[3]
                out = Path(cmd[cmd.index("-o") + 1])
                obj = self.store_dir / sha
                if not obj.exists():
                    return subprocess.CompletedProcess(
                        args=cmd, returncode=1, stdout="", stderr="no object")
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_bytes(obj.read_bytes())
                return subprocess.CompletedProcess(
                    args=cmd, returncode=0, stdout="", stderr="")
            return real_run(cmd, **kwargs)

        patches = [
            unittest.mock.patch.object(cli, "find_pdk", return_value=self.pdk),
            unittest.mock.patch.object(runner, "ngspice_version",
                                       return_value="ngspice-46"),
            unittest.mock.patch.object(report, "klt_env_provenance_lines",
                                       return_value=["host: host-00000000"]),
            unittest.mock.patch.object(runner, "run_grid",
                                       side_effect=fake_run_grid),
            unittest.mock.patch.object(cli, "SIM_DIR", sim_dir or self.root),
            unittest.mock.patch.dict(os.environ, env),
            unittest.mock.patch.object(artifacts.subprocess, "run",
                                       side_effect=_proc_router),
        ]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)
        with contextlib.redirect_stdout(buf_out), contextlib.redirect_stderr(buf_err):
            status = cli.run(args)
        return status, buf_out.getvalue(), buf_err.getvalue()

    @staticmethod
    def _measure_for(corner_id: str) -> str:
        """Distinct raw log text per corner -- with one shared text, both
        points would hash to ONE stored object (the store is
        content-addressed) and corrupting it would corrupt both."""
        value = 1.65 if "27c" in corner_id else 1.75
        return f"m_vout = {value:.5e}\n"

    @classmethod
    def _ok_result(cls, point):
        value = 1.65 if "27c" in point.corner_id else 1.75
        return runner.PointResult(
            point=point, status="ok", measurements={"vout": value}
        )

    def _fake_grid(self, *, fail_after=None, state):
        """A run_grid stand-in: "simulates" every point not supplied by
        ``replay`` (writing its real per-phase log into ``log_dir``), hands
        replayed points back untouched, and aborts before simulating more
        than ``fail_after`` fresh points, the way a mid-grid kill would."""
        def fake_run_grid(tb, pdk, points, workdir, jobs=1, timeout_s=300,
                          on_result=None, log_dir=None, backend=None, replay=None):
            replay = replay or {}
            state["replayed"] = sorted(replay)
            state["simulated"] = []
            results = []
            for point in points:
                if fail_after is not None and len(state["simulated"]) >= fail_after:
                    raise OSError(2, "simulated mid-grid kill")
                adopted = replay.get(point.corner_id)
                if adopted is not None:
                    results.append(adopted)
                    if on_result:
                        on_result(adopted)
                    continue
                state["simulated"].append(point.corner_id)
                result = self._ok_result(point)
                for phase in tb.run_phases:
                    run_id = phase.run_id(point.corner_id)
                    (log_dir / f"{run_id}.log").write_text(
                        self._measure_for(point.corner_id))
                results.append(result)
                if on_result:
                    on_result(result)
            return results
        return fake_run_grid

    def _grid_points(self):
        """The exact grid ``cli.run()`` builds from this fixture's args."""
        return corners.build_sweep_grid(
            corners.resolve_corners(["typical"]), (27, 125),
            corners.supply_points(self.tb.nominal_supply_v, 0),
            axes=self.tb.sweeps, blocks=self.tb.grid_blocks,
        )

    def _fingerprint(self):
        return report.grid_fingerprint(self.tb, self._grid_points())

    def _records(self, root: Path) -> list[Path]:
        return sorted((root / self.slug / "records").glob("*.md"))

    def _second_host(self, tag: str) -> Path:
        """A fresh checkout (another host's tree) sharing only the store,
        the manifests and the testbench manifest content."""
        root = Path(tempfile.mkdtemp(prefix=f"adoption-{tag}-"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        shutil.copytree(self.root / self.slug / "testbench",
                        root / self.slug / "testbench")
        return root

    # -- the acceptance scenarios ----------------------------------------

    def test_interrupted_attempt_is_adopted_across_a_fresh_workdir(self):
        """The #827 shape: attempt 1 dies mid-grid with --supersedes (so no
        record), its completed points are banked per point, and attempt 2 --
        a fresh run in a *different* workdir, i.e. another host -- simulates
        only the remainder and discloses the adoption."""
        self._install_fake_writer()
        state1: dict = {}
        args1 = self._args("--artifact-store", "--supersedes",
                           "20260101-000000-0000000a")
        status1, _, err1 = self._run_cli(
            args1, self._fake_grid(fail_after=1, state=state1)
        )
        # Attempt 1: aborted mid-grid, minted nothing, banked exactly one.
        self.assertEqual(status1, cli.EXIT_ENVIRONMENT)
        self.assertEqual(self._records(self.root), [])
        self.assertIn("partial record must not stand in for a full re-take", err1)
        reservation = json.loads(
            (self.root / self.slug / "work" / self._sole_reservation()
             / "reservation.json").read_text()
        )
        self.assertEqual(reservation["grid_sha256"], self._fingerprint())
        stored, _ = artifacts.lookup_stored_points(
            self.tb.experiment, reservation["grid_sha256"], self.manifest_dir
        )
        self.assertEqual(len(stored), 1)
        first_manifest = next(self.manifest_dir.glob("*perpoint-*.manifest.json"))
        source_id = first_manifest.name[:-len(".manifest.json")].replace(
            f"{self.tb.experiment}-perpoint-", "")

        # Attempt 2: another host's checkout, same grid arguments, fresh id.
        root2 = self._second_host("host-b")
        self._install_fake_writer()
        state2: dict = {}
        status2, out2, err2 = self._run_cli(
            self._args("--artifact-store"), self._fake_grid(state=state2),
            sim_dir=root2,
        )
        self.assertEqual(status2, cli.EXIT_OK, f"ERR={err2}")
        self.assertEqual(state2["replayed"], state1["simulated"])
        self.assertEqual(len(state2["simulated"]), 1, "only the remainder runs")
        self.assertIn("adopted   : 1 point(s) fetched from the artifact store", out2)
        text = self._records(root2)[0].read_text()
        self.assertIn("**Artifact-adopted points**", text)
        self.assertIn(f"`{source_id}`", text)
        self.assertIn("(replayed)", text)
        self.assertIn("1 point(s) were simulated by this attempt", text)

    def _sole_reservation(self) -> str:
        work = self.root / self.slug / "work"
        dirs = [p for p in work.iterdir() if p.is_dir()]
        self.assertEqual(len(dirs), 1, "exactly one reserved id expected")
        return dirs[0].name

    def test_a_fully_stored_grid_runs_no_simulator(self):
        """Pure adoption: every point already in the store under this
        fingerprint, so the fresh run simulates nothing and still mints a
        full, structurally ordinary record."""
        self._install_fake_writer()
        state1: dict = {}
        status1, _, err1 = self._run_cli(
            self._args("--artifact-store"), self._fake_grid(state=state1)
        )
        self.assertEqual(status1, cli.EXIT_OK, f"ERR={err1}")
        self.assertEqual(len(self._records(self.root)), 1)

        root2 = self._second_host("host-b")
        state2: dict = {}
        status2, out2, err2 = self._run_cli(
            self._args("--artifact-store"), self._fake_grid(state=state2),
            sim_dir=root2,
        )
        self.assertEqual(status2, cli.EXIT_OK, f"ERR={err2}")
        self.assertEqual(sorted(state2["replayed"]), sorted(state1["simulated"]))
        self.assertEqual(state2["simulated"], [], "nothing left to simulate")
        self.assertIn("2 point(s) fetched from the artifact store", out2)
        text = self._records(root2)[0].read_text()
        self.assertIn("0 point(s) were simulated by this attempt", text)

    def test_fingerprint_mismatch_re_simulates_everything(self):
        """The store's entries are keyed by the grid fingerprint: a run whose
        grid differs -- here by one temperature -- adopts nothing."""
        self._install_fake_writer()
        state1: dict = {}
        self._run_cli(self._args("--artifact-store"), self._fake_grid(state=state1))

        root2 = self._second_host("host-b")
        state2: dict = {}
        args2 = cli.build_parser().parse_args(
            [self.slug, "--corners", "typical", "--temps", "27", "150",
             "--supply-tol", "0",
             "--subset-reason", "unit test: different grid, must adopt nothing",
             "-j", "1", "--artifact-store"]
        )
        status2, out2, err2 = self._run_cli(
            args2, self._fake_grid(state=state2), sim_dir=root2
        )
        self.assertEqual(status2, cli.EXIT_OK, f"ERR={err2}")
        self.assertEqual(state2["replayed"], [], "a mismatched grid adopts nothing")
        self.assertNotIn("adopted   :", out2)
        text = self._records(root2)[0].read_text()
        self.assertNotIn("**Artifact-adopted points**", text)

    def test_a_corrupted_stored_object_is_refused_and_re_simulated(self):
        """A fetched object whose bytes fail the sha256 re-check is never
        mixed in: the point re-simulates and the record stays ordinary."""
        self._install_fake_writer()
        state1: dict = {}
        self._run_cli(self._args("--artifact-store"), self._fake_grid(state=state1))
        # Corrupt one stored object in place -- exactly the "broker handed
        # back different bytes" failure the re-check exists for.
        stored, _ = artifacts.lookup_stored_points(
            self.tb.experiment, self._fingerprint(), self.manifest_dir
        )
        victim = next(iter(next(iter(stored.values())).values()))
        (self.store_dir / victim).write_text("bit-rotted\n")

        root2 = self._second_host("host-b")
        state2: dict = {}
        status2, _, err2 = self._run_cli(
            self._args("--artifact-store"), self._fake_grid(state=state2),
            sim_dir=root2,
        )
        self.assertEqual(status2, cli.EXIT_OK, f"ERR={err2}")
        # The corrupted point re-simulated; its neighbour was still adopted.
        self.assertEqual(len(state2["simulated"]), 1)
        self.assertEqual(len(state2["replayed"]), 1)

    def test_a_stored_killed_deck_log_never_qualifies(self):
        """The timeout banner is written FIRST: even a stored log whose
        output looks complete can never pass the replay gate (#973's rule,
        unchanged for adoption)."""
        self._install_fake_writer()
        points = self._grid_points()
        fingerprint = self._fingerprint()
        corner_id = points[0].corner_id
        run_id = self.tb.run_phases[0].run_id(corner_id)
        poisoned = (
            "TIMEOUT after 300s\n--- partial simulator output ---\n"
            + MEASURE_OK
        )
        digest = sha256_of(poisoned.encode())
        (self.store_dir / digest).write_text(poisoned)
        staged = self.stage_dir / f"{self.tb.experiment}-perpoint" \
            / fingerprint / corner_id
        staged.mkdir(parents=True, exist_ok=True)
        (staged / f"{run_id}.log").write_text(poisoned)
        manifest = self.manifest_dir / \
            f"{self.tb.experiment}-perpoint-rid-dead.manifest.json"
        manifest.write_text(json.dumps({"schema_version": 1, "entries": [{
            "sha256": digest, "size": len(poisoned), "kind": "evidence",
            "producer": {"tool": "fake", "version": "0", "loom.repo": "t/t",
                         "commit": "c"},
            "uri": f"artifact:fake/{digest}",
            "name": str(staged / f"{run_id}.log"),
        }]}))

        state: dict = {}
        status, _, _ = self._run_cli(
            self._args("--artifact-store"), self._fake_grid(state=state)
        )
        self.assertEqual(status, cli.EXIT_OK)
        self.assertEqual(state["replayed"], [], "a killed deck's log is not evidence")
        self.assertEqual(state["simulated"], [p.corner_id for p in points])

    def test_upload_failure_fails_closed_with_no_record(self):
        """The first per-point upload failure stops the run: exit 3, no
        record minted, and the points banked before the failure stay
        adoptable by the next attempt."""
        self._install_fake_writer()
        # The writer succeeds for the first point's upload, then "breaks".
        self.fake_store_env["FAKE_PUT_FAIL_AFTER"] = "1"
        state: dict = {}
        status, _, err = self._run_cli(
            self._args("--artifact-store", "--supersedes",
                       "20260101-000000-0000000b"),
            self._fake_grid(state=state),
        )
        self.assertEqual(status, cli.EXIT_ENVIRONMENT)
        self.assertEqual(self._records(self.root), [], "fail closed: no record")
        self.assertIn("no summary record will be published", err)
        self.assertIn("storing point", err)
        # The failure fired on the second point: the first is banked.
        stored, _ = artifacts.lookup_stored_points(
            self.tb.experiment, self._fingerprint(), self.manifest_dir
        )
        self.assertEqual(len(stored), 1)

    def test_upload_failure_stops_even_without_supersedes(self):
        """#271's partial-record rescue must not swallow an artifact-upload
        failure: raw output that could not be banked means the record would
        hide a gap, so nothing is minted either way."""
        self._install_fake_writer(exit_code=3)
        status, _, err = self._run_cli(
            self._args("--artifact-store"), self._fake_grid(state={})
        )
        self.assertEqual(status, cli.EXIT_ENVIRONMENT)
        self.assertEqual(self._records(self.root), [])
        self.assertIn("no summary record will be published", err)

    def test_no_stored_points_runs_ordinarily(self):
        """Zero stored points: the flow degrades to an ordinary run -- no
        adoption line, no adoption note, nothing fetched."""
        self._install_fake_writer()
        state: dict = {}
        status, out, _ = self._run_cli(
            self._args("--artifact-store"), self._fake_grid(state=state)
        )
        self.assertEqual(status, cli.EXIT_OK)
        self.assertEqual(state["replayed"], [])
        self.assertNotIn("adopted   :", out)
        text = self._records(self.root)[0].read_text()
        self.assertNotIn("**Artifact-adopted points**", text)

    def test_broker_checked_before_dispatch(self):
        """The broker is needed for uploads and fetches alike; a run that
        will need it must fail before spending a single point."""
        self._install_fake_writer()
        state: dict = {}
        status, _, err = self._run_cli(
            self._args("--artifact-store"), self._fake_grid(state=state),
            broker="",
        )
        self.assertEqual(status, cli.EXIT_ENVIRONMENT)
        self.assertIn("KLT_ARTIFACT_BROKER is unset", err)
        self.assertEqual(state.get("simulated"), None, "nothing was dispatched")
        self.assertEqual(self._records(self.root), [])

    def test_resume_composes_with_per_point_uploads(self):
        """--resume (same host) keeps its own replay accounting while
        --artifact-store banks the fresh points; both prior attempts become
        adoption sources for a later cross-host run."""
        self._install_fake_writer()
        # Attempt 1: interrupted after 1 point, supersedes => no record.
        state1: dict = {}
        args1 = self._args("--artifact-store", "--supersedes",
                           "20260101-000000-0000000c")
        self._run_cli(args1, self._fake_grid(fail_after=1, state=state1))
        record_id = self._sole_reservation()
        # The test process owns attempt 1's reservation and is still alive,
        # so it reads back "running"; mark its pid dead the way a real
        # step death would leave it.
        ownership = self.root / self.slug / "work" / record_id / "reservation.json"
        info = json.loads(ownership.read_text())
        info["pid"] = _dead_pid()
        ownership.write_text(json.dumps(info))

        # Attempt 2: --resume the same id on this host; replays the banked
        # point, simulates the other, banks the fresh one.
        state2: dict = {}
        status2, out2, err2 = self._run_cli(
            self._args("--artifact-store", "--resume", record_id),
            self._fake_grid(state=state2),
        )
        self.assertEqual(status2, cli.EXIT_OK, f"ERR={err2}")
        self.assertEqual(len(state2["replayed"]), 1)
        self.assertIn("resume    : 1 point(s) replayed from the earlier", out2)
        text = self._records(self.root)[0].read_text()
        self.assertIn("**Resumed run**", text)
        self.assertNotIn("**Artifact-adopted points**", text,
                         "same-host resume is not store adoption")

        # A later, different-host run can now adopt BOTH corners: the one
        # attempt 1 banked and the one attempt 2 banked.
        root3 = self._second_host("host-b")
        state3: dict = {}
        status3, out3, err3 = self._run_cli(
            self._args("--artifact-store"), self._fake_grid(state=state3),
            sim_dir=root3,
        )
        self.assertEqual(status3, cli.EXIT_OK, f"ERR={err3}")
        self.assertEqual(len(state3["replayed"]), 2)
        self.assertEqual(state3["simulated"], [])
        self.assertIn("adopted   : 2 point(s) fetched from the artifact store", out3)


if __name__ == "__main__":
    unittest.main()
