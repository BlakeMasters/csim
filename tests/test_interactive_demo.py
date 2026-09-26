"""Bounded local playground contracts; no browser or external Engine needed."""
from __future__ import annotations

import json
import hashlib
import os
import re
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from http.server import ThreadingHTTPServer

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

    def test_nfkb_one_click_pair_preset_completes_for_one_three_five_cells(self):
        match = re.search(r'\["payload_uptake_rate_mol_min","Per-cell payload uptake \(mol/min\)",([0-9.]+),"number"\]', demo.APP_JS)
        self.assertIsNotNone(match, "pair preset uptake rate must remain inspectable")
        rate = float(match.group(1))
        for count in (1, 3, 5):
            with self.subTest(cell_count=count), tempfile.TemporaryDirectory() as scratch:
                root = Path(scratch)
                (root / "runs").mkdir()
                session = demo.DemoSession(None)
                session.reset({"mode": "nfkb", "configuration":
                               dict(demo.MODES["nfkb"].defaults, cell_count=count)})
                request = {"sequence_key": "TIPL", "stimulus_admin_mol_per_switch": 0.1,
                           "payload_start_min": 120.0, "payload_admin_mol_at_start": 0.02,
                           "payload_uptake_rate_mol_min": rate}
                with patch.object(demo, "SESSION", session), patch.object(demo, "ROOT", root):
                    result = demo._nfkb_compare(request)
                self.assertEqual(result["status"], "pass")
                self.assertEqual(len(result["arms"]["stimulus_only"]["observations"]), 83)
                self.assertEqual(len(result["arms"]["stimulus_plus_generic_payload"]["observations"]), 83)
                self.assertLessEqual(max(arm["maximum_amount_residual_mol"]
                                         for arm in result["arms"].values()), 1e-12)

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

    def test_live_guide_has_nfkb_cell_presets_and_actual_readiness(self):
        page = demo.PAGE
        self.assertIn('id="live-guide"', page)
        self.assertIn("2-minute path", page)
        self.assertIn('href="http://127.0.0.1:8765/"', page)
        for count in (1, 3, 5):
            self.assertIn(f'data-cell-preset="{count}"', page)
            session = demo.DemoSession(None)
            config = dict(demo.MODES["nfkb"].defaults, cell_count=count)
            state = session.reset({"mode": "nfkb", "configuration": config})
            self.assertEqual(len(state["observation"]["cells"]), count)
        self.assertIn("campaign_report_available", session.snapshot())
        self.assertIn('"/api/reset","POST"', demo.APP_JS)

    def test_board_link_accepts_only_explicit_loopback_port(self):
        with patch.object(demo, "BOARD_URL", "http://127.0.0.1:8875/", create=True):
            self.assertIn(b'href="http://127.0.0.1:8875/"', demo._page_html())
        self.assertEqual(demo._validate_board_url("http://localhost:8875/"),
                         "http://localhost:8875/")
        for bad in ("https://example.org/", "http://localhost:8875/other",
                    "http://localhost:8875/?file=secret", "http://user@localhost:8875/",
                    "http://0.0.0.0:8875/", "http://localhost/"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                demo._validate_board_url(bad)

    def test_coupled_arena_artifact_is_hash_bound_and_read_only(self):
        with tempfile.TemporaryDirectory() as scratch:
            result_path = Path(scratch) / "results.json"
            cells = [{"cell_id": f"cell_{i}", "model_id": f"model:{i}",
                      "position_m": [i * 0.1, 0.1, 0.1], "nuclear_proxy": 0.1,
                      "feedback": 0.0, "reporter_index": 0.0,
                      "mediator_inventory_mol": 0.01} for i in range(1, 4)]
            trace = [{"time_min": time, "stimulus_code": "T",
                      "mediator_field_amount_mol": 0.0001 * index,
                      "mediator_field_concentration_mol_m3": 0.0008 * index,
                      "mediator_waste_amount_mol": 0.0, "cells": cells}
                     for index, time in enumerate((0.0, 6.0))]
            payload = {"status": "pass", "source_test_tool_sha256": "source-hash",
                       "configuration": {"cell_count": 3, "seed": 7, "sequence_key": "TIPL",
                                         "horizon_steps": 1, "step_min": 6},
                       "cases": {name: {"trace": trace, "accepted_steps": 1}
                                 for name in ("baseline", "coupled")},
                       "comparison": {"same_seed": True, "same_stimulus_schedule": True,
                                      "cell_3_second_interval_nuclear_delta": 0.0},
                       "maximum_amount_residual_mol": 0.0}
            result_path.write_text(json.dumps(payload), encoding="utf-8")
            receipt = {"status": "passed", "atom_id": "atom-test", "chokepoint_id": "cp-test",
                       "verification": {"status": "ok", "logs_checked": 2, "problems": []},
                       "results_sha256": hashlib.sha256(result_path.read_bytes()).hexdigest(),
                       "source_test_tool_sha256": "source-hash"}
            sidecar = result_path.with_name("oss_record.json")
            sidecar.write_text(json.dumps(receipt), encoding="utf-8")
            loaded = demo._load_coupled_arena(result_path)
            self.assertEqual(loaded["oss_atom_id"], "atom-test")
            self.assertEqual(len(loaded["cases"]["coupled"]["trace"]), 2)
            session = demo.DemoSession(None)
            with patch.object(demo, "COUPLED_ARENA", loaded), patch.object(demo, "SESSION", session):
                self.assertTrue(session.snapshot()["coupled_arena_available"])
                server = ThreadingHTTPServer(("127.0.0.1", 0), demo.Handler)
                worker = threading.Thread(target=server.serve_forever, daemon=True)
                worker.start()
                try:
                    with patch.object(demo, "PORT", server.server_port):
                        with urlopen(f"http://127.0.0.1:{server.server_port}/api/coupled-arena") as response:
                            self.assertEqual(json.load(response)["oss_atom_id"], "atom-test")
                finally:
                    server.shutdown(); server.server_close(); worker.join(timeout=2)
            receipt["results_sha256"] = "wrong"
            sidecar.write_text(json.dumps(receipt), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                demo._load_coupled_arena(result_path)

    def test_campaign_route_serves_only_configured_read_only_html(self):
        with tempfile.TemporaryDirectory() as scratch:
            report = Path(scratch) / "index.html"
            report.write_bytes(b"<!doctype html><title>review</title>")
            secret = Path(scratch) / "secret.txt"
            secret.write_text("private", encoding="utf-8")
            server = ThreadingHTTPServer(("127.0.0.1", 0), demo.Handler)
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            try:
                base = f"http://127.0.0.1:{server.server_port}"
                with patch.object(demo, "PORT", server.server_port), \
                     patch.object(demo, "CAMPAIGN_HTML", report.read_bytes(), create=True):
                    with urlopen(base + "/") as response:
                        self.assertIn(b'href="/campaign"', response.read())
                    with urlopen(base + "/campaign") as response:
                        self.assertEqual(response.read(), report.read_bytes())
                        self.assertEqual(response.headers["Content-Type"],
                                         "text/html; charset=utf-8")
                        self.assertIn("script-src 'none'",
                                      response.headers["Content-Security-Policy"])
                    for path in ("/campaign?file=secret.txt", "/campaign/../secret.txt"):
                        with self.subTest(path=path), self.assertRaises(HTTPError) as error:
                            urlopen(base + path)
                        self.assertEqual(error.exception.code, 404)
                    with self.assertRaises(HTTPError) as denied:
                        urlopen(Request(base + "/campaign",
                                        headers={"Origin": "http://example.org"}))
                    self.assertEqual(denied.exception.code, 403)
                with patch.object(demo, "PORT", server.server_port), \
                     patch.object(demo, "CAMPAIGN_HTML", None, create=True):
                    with urlopen(base + "/") as response:
                        self.assertNotIn(b'href="/campaign"', response.read())
                    with self.assertRaises(HTTPError) as missing:
                        urlopen(base + "/campaign")
                    self.assertEqual(missing.exception.code, 404)
            finally:
                server.shutdown()
                server.server_close()
                worker.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
