"""Bounded local playground contracts; no browser or external Engine needed."""
from __future__ import annotations

import json
import hashlib
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import run_interactive_demo as demo


class InteractiveDemoTests(unittest.TestCase):
    def test_uptake_acceptance_rejection_replay_and_export(self):
        session = demo.DemoSession(None)
        config = dict(demo.MODES["uptake"].defaults, horizon_steps=2)
        session.reset({"mode": "uptake", "configuration": config})
        first = session.step({"rate_mol_s": 0.1})
        self.assertEqual(first["status"], "accepted")
        checkpoint = session.episode.checkpoint()
        revision = session.revision
        rejected = session.step({"rate_mol_s": 10.0})
        self.assertEqual(rejected["status"], "rejected")
        self.assertTrue(rejected["event"]["state_unchanged"])
        self.assertEqual(session.episode.checkpoint(), checkpoint)
        self.assertEqual(session.revision, revision)
        self.assertTrue(session.replay()["last_replay"]["equal"])
        with self.assertRaisesRegex(ValueError, "complete"):
            session.session_export()
        self.assertEqual(session.step({"rate_mol_s": 0.1})["status"], "accepted")
        exported = session.session_export()
        self.assertEqual(exported["rates_mol_s"], [0.1, 0.1])
        self.assertEqual(exported["horizon_steps"], 2)
        self.assertNotIn("attempted_rates_mol_s", exported)

    def test_arena_one_and_five_cell_controls_preserve_private_state(self):
        for count in (1, 5):
            with self.subTest(count=count):
                session = demo.DemoSession(None)
                config = dict(demo.MODES["arena"].defaults, cell_count=count, horizon_steps=2)
                session.reset({"mode": "arena", "configuration": config})
                ids = [cell["cell_id"] for cell in session.episode.observe()["cells"]]
                rates = {cid: 0.01 for cid in ids}
                accepted = session.step({"rates_mol_s": rates})
                self.assertEqual(accepted["status"], "accepted")
                self.assertEqual(set(accepted["event"]["transition"]["info"]["transfers_mol_by_cell"]), set(ids))
                checkpoint = session.episode.checkpoint()
                rejected = session.step({"rates_mol_s": {cid: 10.0 for cid in ids}})
                self.assertEqual(rejected["status"], "rejected")
                self.assertTrue(rejected["event"]["state_unchanged"])
                self.assertEqual(session.episode.checkpoint(), checkpoint)
                self.assertTrue(session.replay()["last_replay"]["equal"])

    def test_configuration_binds_recordable_step_range(self):
        supplied = dict(demo.MODES["uptake"].defaults)
        supplied["step_s"] = 0.0009
        with self.assertRaisesRegex(ValueError, "step_s"):
            demo.MODES["uptake"].configuration(supplied)
        supplied["step_s"] = 0.001
        self.assertEqual(demo.MODES["uptake"].configuration(supplied)["step_s"], 0.001)
        supplied["initial_memory"] = 11.0
        with self.assertRaisesRegex(ValueError, "initial memory"):
            demo.MODES["uptake"].configuration(supplied)

    def test_nfkb_typed_delivery_rejection_and_replay(self):
        session = demo.DemoSession(None)
        config = dict(demo.MODES["nfkb"].defaults, cell_count=5, horizon_steps=2)
        session.reset({"mode": "nfkb", "configuration": config})
        rates = {f"cell_{i}": 0.001 for i in range(1, 6)}
        proposal = {"stimulus_code": "T", "stimulus_admin_mol": 0.02,
                    "stimulus_withdraw_mol": 0.0, "payload_admin_mol": 0.01,
                    "payload_uptake_rates_mol_min_by_cell": rates}
        accepted = session.step(proposal)
        self.assertEqual(accepted["status"], "accepted")
        observation = accepted["event"]["transition"]["observation"]
        self.assertEqual(len(observation["cells"]), 5)
        self.assertGreater(observation["cells"][0]["nuclear_proxy"], 0)
        self.assertLessEqual(accepted["event"]["transition"]["info"]["maximum_amount_residual_mol"], 1e-12)
        checkpoint = session.episode.checkpoint()
        bad = dict(proposal, payload_admin_mol=0.2)
        rejected = session.step(bad)
        self.assertEqual(rejected["status"], "rejected")
        self.assertTrue(rejected["event"]["state_unchanged"])
        self.assertEqual(checkpoint, session.episode.checkpoint())
        self.assertTrue(session.replay()["last_replay"]["equal"])

    def test_completed_engine_receipt_precedes_newer_direct_smoke(self):
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            runs = root / "runs"
            direct = runs / "integrated_demo_direct_later"
            engine = runs / "integrated_demo_engine_earlier"
            direct.mkdir(parents=True)
            (engine / "workload").mkdir(parents=True)
            payload = {"status": "pass", "components": {"symbolic": {}, "self_play": {}}}
            (direct / "results.json").write_text(json.dumps(payload), encoding="utf-8")
            (engine / "workload/results.json").write_text(json.dumps(payload), encoding="utf-8")
            (engine / "receipt.json").write_text(json.dumps({"engine_run_id": "engine-receipt",
                                                              "oss_atom_id": "atom-receipt"}), encoding="utf-8")
            os.utime(direct / "results.json", (3_000_000_000, 3_000_000_000))
            with patch.object(demo, "ROOT", root):
                chosen = demo._latest_evidence(None)
        self.assertEqual(chosen["engine_run_id"], "engine-receipt")
        self.assertEqual(chosen["oss_atom_id"], "atom-receipt")

    def test_nfkb_paired_schedule_is_bounded_and_does_not_mutate_session(self):
        session = demo.DemoSession(None)
        config = dict(demo.MODES["nfkb"].defaults, cell_count=2)
        session.reset({"mode": "nfkb", "configuration": config})
        checkpoint = session.episode.checkpoint()
        request = {"sequence_key": "TIPL", "stimulus_admin_mol_per_switch": 0.1,
                   "payload_start_min": 120.0, "payload_admin_mol_at_start": 0.02,
                   "payload_uptake_rate_mol_min": 0.001}
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            (root / "runs").mkdir()
            with patch.object(demo, "SESSION", session), patch.object(demo, "ROOT", root):
                result = demo._nfkb_compare(request)
                self.assertTrue(Path(result["artifact_path"]).is_file())
        self.assertEqual(session.episode.checkpoint(), checkpoint)
        self.assertEqual(set(result["arms"]), {"stimulus_only", "stimulus_plus_generic_payload"})
        for arm in result["arms"].values():
            self.assertEqual(len(arm["observations"]), 83)
            self.assertLessEqual(arm["maximum_amount_residual_mol"], 1e-12)
        control = result["arms"]["stimulus_only"]["observations"][-1]["cells"][0]["nuclear_proxy"]
        treated = result["arms"]["stimulus_plus_generic_payload"]["observations"][-1]["cells"][0]["nuclear_proxy"]
        self.assertLess(treated, control)
        bad = dict(request, sequence_key="TTTT")
        with patch.object(demo, "SESSION", session):
            with self.assertRaisesRegex(ValueError, "permutation"):
                demo._nfkb_compare(bad)

    def test_frozen_predictor_is_read_only_and_matches_stored_condition(self):
        path = demo.ROOT / "runs/nfkb_model_20260926_02/frozen_candidate.json"
        candidate = json.loads(path.read_text(encoding="utf-8"))
        frozen = {"candidate": candidate, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                  "path": str(path)}
        with patch.object(demo, "FROZEN", frozen):
            result = demo._nfkb_predict({"sequence_key": "TIPL", "dose_tier": "high"})
            with self.assertRaisesRegex(ValueError, "dose_tier"):
                demo._nfkb_predict({"sequence_key": "TIPL", "dose_tier": "mol"})
        overlay = json.loads((demo.ROOT / "runs/nfkb_model_20260926_02/comparison_overlay.json").read_text(encoding="utf-8"))
        stored = next(item for item in overlay["conditions"] if item["condition_id"] == 2)
        self.assertEqual(len(result["predicted_reporter"]), 83)
        self.assertLess(max(abs(a - b) for a, b in zip(result["predicted_reporter"],
                                                       stored["model_prediction"])), 1e-12)
        self.assertIsNone(result["drug_response"])

    def test_local_pixel_stylesheet_is_allowed_by_page_policy(self):
        # The stylesheet can return HTTP 200 yet still be blocked by CSP.
        self.assertIn('href="/pixel_renderer.css"', demo.PAGE)
        self.assertIn("style-src 'self' 'unsafe-inline'", demo.PAGE)

    def test_pixel_inspector_table_overrides_global_table_minimum(self):
        # The page's global table width otherwise stretches a 250px inspector.
        self.assertIn(".csim-inspector-table{min-width:0}", demo.PAGE)

    def test_initial_scene_redraws_after_layout_is_ready(self):
        # First draw can size the canvas before its external stylesheet applies.
        self.assertIn("requestAnimationFrame(()=>{if(state)renderScene();})", demo.APP_JS)


if __name__ == "__main__":
    unittest.main()
