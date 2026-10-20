import importlib.util, json, tempfile, unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('trace_summary', Path(__file__).resolve().parents[1] / 'engine/session/summary.py')
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)


def state(*sections, overlay=False):
    return {'texts': [{'block_id': sid, 'text': sid} for sid in sections], 'targets': [], 'overlay': overlay}


def record(name, before, after, start=0, reading=0, playback=0, overlap=0, interaction=0.8, success=True, interval=(0, 0)):
    active = interaction + reading + playback - overlap
    media = {'asset_id': 'clip', 'start': interval[0], 'end': interval[1], 'advanced_seconds': playback} if playback else None
    return {'proposed': {'action': name, 'target': None, 'reason': 'Authored reason; no human motive established'},
            'execution': {'before': before, 'after': after, 'success': success, 'playback': media, 'frames': [], 'error': None if success else 'Media decode failed'},
            'event': {'action': name, 'success': success, 'clock': {'session_start': start, 'session_end': start+active, 'interaction_seconds': interaction, 'reading_seconds': reading, 'playback_seconds': playback, 'overlap_seconds': overlap, 'active_union_seconds': active}}}


def aggregate(records, total):
    return s.aggregate_trace({'clock': {'simulated_active_seconds': total}}, records,
        [{'block_id': 'a', 'section_id': 'a'}, {'block_id': 'b', 'section_id': 'b'}],
        {'placements': [{'placement_id': 'placement-picture', 'block_id': 'picture', 'asset_id': 'clip', 'section_id': 'a'}]})


class SummaryTests(unittest.TestCase):
    def test_overlap_reconciles_once_with_separate_interaction_time(self):
        r = record('read_while_playing', state('a'), state('a'), reading=4, playback=4, overlap=4, interaction=.3, interval=(1, 5))
        result = aggregate([r], 4.3)
        self.assertEqual(result['active_content_seconds'], 4)
        self.assertEqual(result['interaction_seconds'], .3)
        self.assertEqual(result['sections'][0]['overlap_seconds'], 4)
        self.assertEqual(result['media'][0]['unique_playback_source_seconds'], 4)

    def test_repeat_playback_is_time_but_not_duplicate_unique_coverage(self):
        rs = [record('play', state('a'), state('a'), playback=4, interaction=.3, interval=(0, 4)),
              record('play', state('a'), state('a'), start=4.3, playback=4, interaction=.3, interval=(2, 6))]
        result = aggregate(rs, 8.6)
        self.assertEqual(result['media'][0]['total_playback_source_seconds'], 8)
        self.assertEqual(result['media'][0]['unique_playback_source_seconds'], 6)

    def test_ambiguous_multi_section_dwell_stays_unallocated(self):
        r = record('read', state('a', 'b'), state('a', 'b'), reading=20, interaction=0)
        result = aggregate([r], 20)
        rows = {x['section_id']: x for x in result['sections']}
        self.assertEqual(rows['unallocated']['reading_seconds'], 20)
        self.assertEqual(rows['a']['reading_seconds'], 0)
        self.assertEqual(rows['b']['reading_seconds'], 0)

    def test_failed_play_is_a_technical_event_not_watched_time_or_disinterest(self):
        result = aggregate([record('play', state('a'), state('a'), success=False, interaction=.3)], .3)
        self.assertEqual(result['technical_event_count'], 1)
        self.assertFalse(result['technical_events'][0]['reader_disinterest_inferred'])
        self.assertEqual(result['active_content_seconds'], 0)
        self.assertEqual(result['media'], [])

    def test_success_without_source_advancement_before_end_is_technical(self):
        before = state('a')
        before['targets'] = [{'id': 'player', 'kind': 'player', 'duration': 10, 'current_time': 1}]
        r = record('play', before, before, interaction=.3)
        r['proposed']['target'] = 'player'
        r['execution']['playback'] = {'asset_id': 'clip', 'start': 1, 'end': 1, 'advanced_seconds': 0}
        result = aggregate([r], .3)
        self.assertEqual(result['technical_event_count'], 1)
        self.assertFalse(result['technical_events'][0]['reader_disinterest_inferred'])
        self.assertEqual(result['active_content_seconds'], 0)
        self.assertEqual(result['media'][0]['unique_playback_source_seconds'], 0)

    def test_backtracking_counts_revisit_without_inflating_every_snapshot(self):
        rs = [record('scroll_next', state('a'), state('b')),
              record('scroll_back', state('b'), state('a'), start=.8),
              record('read', state('a'), state('a'), start=1.6, reading=2, interaction=0)]
        rows = {x['section_id']: x for x in aggregate(rs, 3.6)['sections']}
        self.assertEqual(rows['a']['visits'], 2)
        self.assertEqual(rows['a']['backtrack_revisits'], 1)

    def test_overlay_inspection_is_separate_from_article_text_reading(self):
        before = state('a'); before['targets'] = [{'id': 'placement-picture'}]
        opening = record('inspect_image', before, state(overlay=True), interaction=1)
        opening['proposed']['target'] = 'placement-picture'
        reading = record('read', state(overlay=True), state(overlay=True), start=1, reading=4, interaction=0)
        rows = {x['section_id']: x for x in aggregate([opening, reading], 5)['sections']}
        self.assertEqual(rows['a']['overlay_inspection_seconds'], 4)
        self.assertEqual(rows['a']['reading_seconds'], 0)

    def test_clock_disagreement_is_not_silently_repaired(self):
        with self.assertRaisesRegex(ValueError, 'reconcile'):
            aggregate([record('read', state('a'), state('a'), reading=2, interaction=0)], 99)

    def test_missing_assignments_keep_the_denominator_and_unknown_usage(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            pending = p / 'prepared'; pending.mkdir()
            (pending / 'status.json').write_text(json.dumps({'status': 'prepared_not_a_simulated_read', 'model_calls': 0}))
            result = s.write_report([pending, p / 'missing'], p / 'summary')
            self.assertEqual(json.loads((p / 'summary/summary.json').read_text()), result)
            self.assertIn('\n\n', (p / 'summary/README.md').read_text())
            self.assertEqual(result['rollup']['assigned_runs'], 2)
            self.assertEqual(result['rollup']['eligible_live_traces'], 0)
            self.assertIsNone(result['rollup']['provider_calls'])
            self.assertEqual(result['rollup']['provider_calls_unknown_runs'], 1)
            self.assertIsNone(result['rollup']['completion_probability'])
            self.assertIsNone(result['runs'][0]['finish_time_seconds'])
            self.assertFalse((pending / 'summary.json').exists())

    def test_a_claimed_validation_without_its_seal_is_not_eligible(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            for name, value in [('status.json', {'status': 'verified_simulated_read_with_limits', 'execution_mode': 'live_api', 'provider_calls': 0}), ('validation.json', {'status': 'verified_simulated_read_with_limits'})]:
                (p / name).write_text(json.dumps(value))
            self.assertFalse(s.summarize_run(p)['eligible_live_trace'])
