"""Interrupted submits, fleet cache identity, and per-run archive membership."""

import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SIM = Path(__file__).resolve().parents[1]
BENCH = SIM / "mc-cp-mismatch" / "testbench"
sys.path.insert(0, str(BENCH))
import fleet_archive
import fleet_batch as fleet


class Transport(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name)
        self.batch = self.work / "batch/full"
        decks = self.batch / "decks"
        decks.mkdir(parents=True)
        self.tags = ["dff_ff_seed001", "dff_ss_seed001"]
        rows = []
        for corner, tag in zip(("ff", "ss"), self.tags):
            (decks / f"{tag}.spice").write_text(f"* seed 1, {corner}\n")
            rows.append(f"{tag}\tdff\t{corner}\t900\tdut_dff.spice\n")
        (self.batch / "units.tsv").write_text("".join(rows))
        for root in (decks, self.work):
            (root / "dut_dff.spice").write_text("DUT")
        self.units = fleet.expected_units(self.batch)
        self.worker = {"capture": "ok", "pdk": {"variant": fleet.PDK["variant"],
                       "stamp_scope": "executed", "stamp_text": "open_pdks " + fleet.PDK["open_pdks"]},
                       "simulator": {"version_probe": "ok", "version_banner": "** ngspice-47 :"}}

    def test_interrupted_submit_keeps_accepted_request_until_inputs_change(self):
        fleet.main("compose", self.batch)
        names = fleet.load(self.batch / "requests.json")["requests"]
        calls = []
        def accept(cmd, **kwargs):
            name = Path(cmd[2]).name
            calls.append(name)
            if len(calls) == 2:
                return subprocess.CompletedProcess(cmd, 1, "capacity refused")
            return subprocess.CompletedProcess(cmd, 0, json.dumps({"job_id": f"job-{len(calls)}"}))
        errors = io.StringIO()
        with patch.object(subprocess, "run", side_effect=accept), contextlib.redirect_stderr(errors):
            with self.assertRaisesRegex(ValueError, "refused"):
                fleet.main("submit", self.batch)
            self.assertEqual(fleet.load(self.batch / "accepted.json"), {names[0]: "job-1"})
            fleet.main("compose", self.batch)
            fleet.main("submit", self.batch)
            self.assertEqual(calls, [names[0], names[1], names[1]])
            self.assertIn("capacity refused", errors.getvalue())
            (self.batch / "decks" / f"{self.tags[0]}.spice").write_text("* revised deck")
            with self.assertRaisesRegex(ValueError, "recompose"):
                fleet.main("submit", self.batch)
            fleet.main("compose", self.batch)
            fleet.main("submit", self.batch)
            self.assertNotIn(calls[-1], names)
            self.assertEqual(len(calls), 4)

    def test_interruption_after_klt_wrote_receipt_does_not_submit_again(self):
        fleet.main("compose", self.batch)
        names = fleet.load(self.batch / "requests.json")["requests"]
        for name in names:
            out = self.batch / Path(name).stem
            out.mkdir()
            fleet.save(out / "batch-receipt.json", {"job_id": "job-" + out.name})
        with patch.object(subprocess, "run", side_effect=AssertionError("duplicate submit")):
            fleet.main("submit", self.batch)
        self.assertEqual(set(fleet.load(self.batch / "accepted.json")), set(names))

    def test_collect_cache_and_verify_share_worker_and_input_checks(self):
        fleet.main("compose", self.batch)
        names = fleet.load(self.batch / "requests.json")["requests"]
        jobs = dict(zip(names, ["job-1", "job-2"]))
        fleet.save(self.batch / "accepted.json", jobs)
        def attach(cmd):
            job = cmd[cmd.index("--attach") + 1]
            out = Path(cmd[cmd.index("-o") + 1])
            tag = fleet.load(Path(cmd[2]))["decks"][0]["id"]
            key = self.units[tag]["key"]
            row = {"id": tag, "deck_sha256": key["deck_sha256"], "status": "pass", "exit_code": 0}
            (out / tag).mkdir(parents=True, exist_ok=True)
            (out / tag / "stdout.bin").write_text("tcq_r = 1.2e-9\ntcq_f = 2.4e-9\n")
            fleet.save(out / tag / "unit.json", {"key": key, "result": row})
            return json.dumps({"backend": "batch", "status": "pass", "units": [row],
                               "environment": {"remote": {"job_id": job, "worker_environment": self.worker}}})
        with patch.object(subprocess, "check_output", side_effect=attach):
            fleet.main("collect", self.batch)
        fleet.main("compose", self.batch)
        self.assertEqual(fleet.load(self.batch / "requests.json")["requests"], [])
        fleet.main("verify", self.batch)
        directory = self.work / self.tags[0]
        receipt = fleet.load(directory / "fleet.json")
        for field, wrong in [("stamp_scope", "image"), ("stamp_text", "open_pdks different")]:
            with self.subTest(field=field):
                altered = json.loads(json.dumps(receipt))
                altered["worker_environment"]["pdk"][field] = wrong
                fleet.save(directory / "fleet.json", altered)
                with self.assertRaisesRegex(ValueError, "worker PDK"):
                    fleet.main("verify", self.batch)
        altered = json.loads(json.dumps(receipt))
        altered["worker_environment"]["simulator"]["version_banner"] = "ngspice-46"
        fleet.save(directory / "fleet.json", altered)
        with self.assertRaisesRegex(ValueError, "simulator"):
            fleet.main("verify", self.batch)
        fleet.save(directory / "fleet.json", receipt)
        (directory / "ngspice.log").write_text("unrelated nonempty text")
        with self.assertRaisesRegex(ValueError, "stdout"):
            fleet.main("verify", self.batch)
        (directory / "fleet.json").unlink()
        fleet.main("compose", self.batch)
        self.assertEqual(fleet.load(self.batch / "requests.json")["requests"], [names[0]])
        for root in (self.work, self.batch / "decks"):
            (root / "dut_dff.spice").write_text("different DUT")
        with self.assertRaisesRegex(ValueError, "deck/DUT"):
            fleet.cached(self.work, self.tags[1], fleet.expected_units(self.batch)[self.tags[1]])

    def test_nominal_csv_selects_only_its_stage_corner_and_seed(self):
        (self.work / "negative_control.csv").write_text(
            "stage,corner,run\ndc,typical,mc1_seedA_run1\ndc,typical,mc1_seedA_run1\n")
        for name in fleet_archive.SAMPLES.values():
            (self.work / name).write_text("corner,seed\ntypical,1\n")
        (self.work / "pfd_ss_seed001_d0.log").touch()
        tags, _ = fleet_archive.record_tags(self.work, samples=True)
        self.assertEqual(tags, {"ctl_dc_typical_mc1_seedA_run1", "dc_typical_seed001",
                                "dff_typical_seed001", "sw_typical_seed001",
                                "pfd_typical_seed001_dm1n", "pfd_typical_seed001_d0",
                                "pfd_typical_seed001_d1n"})


    def test_published_archive_round_trips_and_rejects_changed_bytes(self):
        rid = "20261120-000000-abcdef0"
        path = self.work / "manifest.json"
        stored = self.work / "stored"
        contents = [("negative_control.csv", b"stage,corner"), ("fleet.json", b"{}")]

        def store_or_fetch(cmd, *, cwd, check):
            if cmd[0].endswith("artifact-put.sh"):
                self.assertEqual(cmd[1:3], ["mc-cp-mismatch", rid])
                shutil.copyfile(Path(cwd) / cmd[3], stored)
                fleet.save(path, {"entries": [{"sha256": fleet.sha(stored.read_bytes())}]})
            elif cmd[1:3] == ["artifact", "get"]:
                shutil.copyfile(stored, cmd[-1])
            else:
                self.assertEqual(cmd, ["klt", "artifact", "verify", str(path)])

        with (
            patch.object(fleet_archive, "WORK", self.work),
            patch.object(fleet_archive, "manifest", return_value=path),
            patch.object(fleet_archive, "members", return_value=contents),
            patch.object(subprocess, "run", side_effect=store_or_fetch),
        ):
            fleet_archive.publish(self.work, "control", rid)
            fleet_archive.publish(self.work, "control", rid)
            dest = self.work / "restored"
            fleet_archive.restore(rid, dest)
            self.assertEqual({p.name: p.read_bytes() for p in dest.iterdir()}, dict(contents))
            stored.write_bytes(b"unrelated archive")
            with self.assertRaisesRegex(ValueError, "checksum"):
                fleet_archive.restore(rid, self.work / "corrupt")


class ReplayGuard(unittest.TestCase):
    def test_vco_standalone_control_refuses_batch_with_replay_set(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            runner = repo / "sim/vco-tuning-range/testbench/run_mismatch.sh"
            runner.parent.mkdir(parents=True)
            shutil.copyfile(SIM / runner.relative_to(repo / "sim"), runner)
            lib = repo / "sim/lib/simenv.sh"
            lib.parent.mkdir()
            # Only stub the tools and the engine. Run the production entry
            # point, callback registration and shared guard in the fixture.
            lib.write_text((SIM / "lib/simenv.sh").read_text() + """
simenv_require_tools() { :; }
simenv_apply_omp_pin() { :; }
simenv_record_id() { echo fixture; }
simenv_run_deck_retried() { echo 'engine reached' >&2; exit 98; }
""")
            dut = repo / "design/netlist/vco.spice"
            dut.parent.mkdir(parents=True)
            dut.touch()
            proc = subprocess.run(["bash", str(runner), "--control"], text=True,
                                  capture_output=True, check=False, timeout=10,
                                  env={**os.environ, "KLT_SIM_BACKEND": "batch",
                                       "SIM_ALLOW_LOCAL_GRID": "", "SIM_FLEET_REPLAY": "1"})
            self.assertEqual(proc.returncode, 2, proc.stderr)
            self.assertIn("SIM_ALLOW_LOCAL_GRID", proc.stderr)
            self.assertNotIn("engine reached", proc.stderr)
