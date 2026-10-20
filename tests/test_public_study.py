"""Check the published derivative preserves denominators, accounting and evidence limits."""
import csv
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]

class PublicStudyTests(unittest.TestCase):
    def setUp(self):
        self.study=json.loads((ROOT/'results/3dcodeverse-2026-10-20/study.json').read_text())

    def test_all_nine_assignments_and_two_errors_retained(self):
        d=self.study
        self.assertEqual(len({r['cell_id'] for r in d['runs']}),9)
        for role in {r['role'] for r in d['runs']}:
            self.assertEqual(sorted(r['repetition'] for r in d['runs'] if r['role']==role),[1,2,3])
        self.assertTrue(all(r['termination']=='finish' for r in d['runs']))
        self.assertEqual(sum(r['rejected_actions'] for r in d['runs']),2)
        self.assertEqual(len(d['blockers']),2)
        self.assertEqual(sum(r['provider_calls'] for r in d['runs']),253)

    def test_clock_overlap_and_section_allocation_reconcile(self):
        for r in self.study['runs']:
            c=r['clock']
            self.assertAlmostEqual(c['reading_seconds']+c['playback_seconds']+c['interaction_seconds']-c['overlap_seconds'],r['simulated_active_seconds'],places=5)
            self.assertAlmostEqual(sum(s['active_content_seconds'] for s in r['sections'])+c['interaction_seconds'],r['simulated_active_seconds'],places=5)
            self.assertTrue(any(s['section_id']=='unallocated' for s in r['sections']))
            self.assertTrue(all(s['backtrack_revisits']==0 for s in r['sections']))
        self.assertAlmostEqual(sum(r['clock']['overlap_seconds'] for r in self.study['runs']),4.049586,places=5)

    def test_unknown_human_outcomes_cannot_become_zero_mismatches(self):
        v=self.study['validation']
        self.assertEqual(self.study['accounting']['human_outcomes'],0)
        for key in ['confidence_interval','reader_mismatches','prediction_accuracy','completion_probability','causal_uplift']:
            self.assertIsNone(v[key])
        self.assertEqual(v['calibration_status'],'not_calibrated')
        self.assertEqual(v['coverage'],'unknown')
        self.assertFalse(v['candidate_b'])

    def test_site_and_download_derivatives_are_identical(self):
        for name in ['study.json','runs.csv']:
            self.assertEqual((ROOT/'site'/name).read_bytes(),(ROOT/'results/3dcodeverse-2026-10-20'/name).read_bytes())
        rows=list(csv.DictReader((ROOT/'site/runs.csv').open()))
        self.assertEqual(len(rows),9)
        self.assertEqual({r['cell_id'] for r in rows},{r['cell_id'] for r in self.study['runs']})

    def test_public_derivative_contains_no_local_raw_record_identifiers(self):
        text=json.dumps(self.study)
        for forbidden in ['/'+'Users/','execution_path','run_path','session_id','request.json','notes.'+'granola.ai','notion-file-block://']:
            self.assertNotIn(forbidden,text)
        self.assertEqual(self.study['cost']['new_inference_for_publication'],0)

    def test_all_nine_metric_definitions_have_origin_limit_and_study(self):
        d=json.loads((ROOT/'site/definitions.json').read_text())
        self.assertEqual(len(d['metrics']),9)
        for m in d['metrics']:
            self.assertTrue(all(m[k] for k in ['id','name','origin','definition','limit','study']))
        self.assertEqual(len(d['enhancements']),7)

if __name__=='__main__':unittest.main()
