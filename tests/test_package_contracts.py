from pathlib import Path
import hashlib,json,unittest
R=Path(__file__).resolve().parents[1]

class PackageContractTests(unittest.TestCase):
    def test_unimplemented_capabilities_not_advertised(self):
        c=json.loads((R/'configs/capabilities.json').read_text())
        for k in ('integrated_tumor_model','biological_validation','clinical_use','live_solver_coupling',
                  'online_fidelity_controller','generalized_error_guarantee','gpu_execution_tested'):
            self.assertFalse(c[k],k)
        self.assertEqual(c['working_external_adapters'],[])
    def test_candidates_are_not_claimed_tested_builds(self):
        c=json.loads((R/'configs/backend_candidates.json').read_text())
        for entry in c['candidates']:
            self.assertFalse(entry['runnable']); self.assertIsNone(entry['commit'])
            self.assertEqual(entry['passing_case_artifacts'],[])
    def test_templates_nonrunnable(self):
        for p in (R/'configs').glob('*.template.json'):
            with self.subTest(file=p.name): self.assertFalse(json.loads(p.read_text())['runnable'])
    def test_historical_input_hashes_preserved(self):
        records=json.loads((R/'provenance/inputs.json').read_text())
        for record in records:
            p=R/'provenance'/record['file']
            self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(),record['sha256'])
    def test_proposed_benchmark_has_no_execution_command(self):
        b=json.loads((R/'benchmarks/campaign.json').read_text())
        for case in b['cases']:
            if case['status']=='planned': self.assertIsNone(case['command'])
    def test_candidate_source_ids_resolve(self):
        ids={s['id'] for s in json.loads((R/'evidence/inherited_source_registry.json').read_text())}
        c=json.loads((R/'configs/backend_candidates.json').read_text())
        for entry in c['candidates']:
            self.assertTrue(set(entry['source_ids'])<=ids)
