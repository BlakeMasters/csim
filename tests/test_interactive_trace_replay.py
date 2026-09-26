"""Accepted browser-action replay and retained failure evidence."""
from __future__ import annotations

import math
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import replay_interactive_trace as replay
from replay_interactive_trace import SCHEMA, replay_trace, validate_export


def session(*, rates=(0.1, 0.1, 0.05, 0.0)) -> dict:
    return {
        "schema": SCHEMA,
        "initial_concentration_mol_m3": 1.0,
        "initial_memory": 0.0,
        "step_s": 0.25,
        "target_response_index": 0.5,
        "horizon_steps": len(rates),
        "rates_mol_s": list(rates),
    }


class InteractiveTraceReplayTests(unittest.TestCase):
    def test_accepted_trace_is_deterministic_and_amount_balanced(self):
        result = replay_trace(session())
        repeat = replay_trace(session())
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["accepted_steps"], 4)
        self.assertTrue(result["final_observation"]["terminated"])
        self.assertEqual(result["final_checkpoint_sha256"], repeat["final_checkpoint_sha256"])
        self.assertEqual(result["trace"], repeat["trace"])
        self.assertEqual(result["biological_qualification"], "unqualified")
        for row in result["trace"]:
            self.assertEqual(row["action"]["quantity_type"], "vmax_mol_s")
            self.assertAlmostEqual(row["field_loss_mol"], row["cell_gain_mol"], places=12)
            self.assertAlmostEqual(row["cell_gain_mol"], row["integrated_transfer_mol"], places=12)
            self.assertLessEqual(row["absolute_balance_error_mol"], 1e-12)

    def test_export_rejects_mismatched_or_unsafe_inputs(self):
        upper = session(rates=(10.0,))
        upper.update(initial_concentration_mol_m3=10.0, initial_memory=10.0,
                     step_s=2.0, target_response_index=10.0)
        self.assertEqual(validate_export(upper), upper)
        bad = session()
        bad["rates_mol_s"] = [0.1]
        with self.assertRaisesRegex(ValueError, "one accepted rate"):
            validate_export(bad)
        bad = session()
        bad["rates_mol_s"][0] = math.nan
        with self.assertRaisesRegex(ValueError, "finite"):
            validate_export(bad)
        bad = session()
        bad["rates_mol_s"][0] = -0.1
        with self.assertRaisesRegex(ValueError, "finite"):
            validate_export(bad)
        bad = session()
        bad["unsupported"] = "command"
        with self.assertRaisesRegex(ValueError, "unsupported"):
            validate_export(bad)

    def test_physical_overdraw_keeps_accepted_prefix_and_failure(self):
        result = replay_trace(session(rates=(0.1, 1.0)))
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["accepted_steps"], 1)
        self.assertEqual(result["rejected_attempt"]["step"], 2)
        self.assertTrue(result["rejected_attempt"]["checkpoint_unchanged"])
        self.assertEqual(result["rejected_attempt"]["error_type"], "EpisodeRejected")
        self.assertEqual(result["final_observation"], result["trace"][-1]["after"])

    def test_oss_only_receipt_preserves_replay_and_verified_log_ids(self):
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            source = root / "session.json"
            source.write_text(json.dumps(session()), encoding="utf-8")
            (root / "ocura-oss.exe").write_bytes(b"fixed test CLI")
            (root / "python.exe").write_bytes(b"fixed test interpreter")
            output = root / "oss-record"
            logs = root / ".ocura-oss/logs"
            logs.mkdir(parents=True)
            (logs / "stdout.log").write_text("replay complete", encoding="utf-8")
            (logs / "stderr.log").write_text("", encoding="utf-8")
            oss_result = {"atom_id": "atom-test", "chokepoint_id": "chokepoint-test",
                          "outcome": "passed", "stdout_log": ".ocura-oss/logs/stdout.log",
                          "stderr_log": ".ocura-oss/logs/stderr.log"}
            verification = {"status": "ok", "problems": [], "counts": {"logs_checked": 2}}
            commands = []
            def fake_call(argv, *, timeout_s):
                commands.append(argv)
                if len(commands) == 1:
                    workload = output / "workload"
                    workload.mkdir()
                    (workload / "results.json").write_text(json.dumps({
                        "status": "pass", "input_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                        "accepted_steps": 4, "source_hashes_stable": True}), encoding="utf-8")
                    return {"exit_code": 0, "stdout": json.dumps(oss_result), "stderr": "", "timed_out": False}
                return {"exit_code": 0, "stdout": json.dumps(verification), "stderr": "", "timed_out": False}
            with patch.object(replay, "ROOT", root), patch.object(replay, "_source_hashes", return_value={"stable": "hash"}), patch.object(replay, "_call", side_effect=fake_call):
                receipt = replay.run_oss(source, output, root / "ocura-oss.exe", root / "python.exe")
        self.assertEqual(receipt["status"], "passed")
        self.assertEqual(receipt["oss_atom_id"], "atom-test")
        self.assertEqual(receipt["oss_chokepoint_id"], "chokepoint-test")
        self.assertNotIn("engine_run_id", receipt)
        self.assertEqual(commands[0][1], "run")
        self.assertEqual(commands[1][1], "verify")


if __name__ == "__main__":
    unittest.main()
