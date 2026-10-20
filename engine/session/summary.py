#!/usr/bin/env python3
"""Read-only trace summaries; preserve outcomes, failed attempts and authored-fixture labels."""
from pathlib import Path
import argparse, csv, hashlib, json, math, sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from media import within, validate_seal


def read(p, default=None):
    return json.loads(p.read_text()) if p.is_file() else default


def union_length(intervals):
    total, end = 0.0, float('-inf')
    for start, stop in sorted(intervals):
        if stop > start:
            total += max(0.0, stop - max(start, end))
            end = max(end, stop)
    return total


def aggregate_trace(trace, records, block_map, manifest):
    """Account for clocks and exposure without interpreting dwell as interest."""
    by_block = {b['block_id']: b.get('section_id', 'unallocated') for b in block_map}
    placement_sections, asset_sections = {}, {}
    for p in manifest.get('placements', []):
        placement_sections[p['placement_id']] = p['section_id']
        placement_sections['link-' + p['block_id']] = p['section_id']
        asset_sections.setdefault(p['asset_id'], set()).add(p['section_id'])
    sections, path, errors, played, samples = {}, [], [], {}, {}
    previous, seen, overlay_section = set(), set(), None
    interactions, content_total = 0.0, 0.0

    def row(sid):
        return sections.setdefault(sid, {'section_id': sid, 'visits': 0, 'backtrack_revisits': 0,
            'skip_actions': 0, 'reading_seconds': 0.0, 'overlay_inspection_seconds': 0.0,
            'playback_seconds': 0.0, 'overlap_seconds': 0.0, 'active_content_seconds': 0.0,
            'visible_block_ids': set()})

    def visible(state):
        ids = {by_block.get(t['block_id'], 'unallocated') for t in state.get('texts', [])}
        if state.get('overlay'):
            return set()
        return ids

    def observe(state, backtrack=False):
        nonlocal previous, seen
        # Repeated observations of the same viewport do not create new visits.
        current = visible(state)
        for sid in current - previous:
            row(sid)['visits'] += 1
            if backtrack and sid in seen:
                row(sid)['backtrack_revisits'] += 1
        for t in state.get('texts', []):
            if not state.get('overlay'):
                row(by_block.get(t['block_id'], 'unallocated'))['visible_block_ids'].add(t['block_id'])
        seen |= current
        previous = current
        return current

    if records:
        observe(records[0]['execution']['before'])
    for i, record in enumerate(records):
        proposed, execution, event = record['proposed'], record['execution'], record['event']
        name, clock = proposed['action'], event['clock']
        before, after = execution['before'], execution['after']
        context = visible(before)
        if before.get('overlay') is False:
            overlay_section = None
        target = next((t for t in before.get('targets', []) if t['id'] == proposed.get('target')), {})
        if name in {'inspect_image', 'open_media', 'open_gif'} and after.get('overlay'):
            overlay_section = placement_sections.get(proposed.get('target'))
        reading, playback, overlap = (float(clock.get(k, 0)) for k in ['reading_seconds', 'playback_seconds', 'overlap_seconds'])
        active = float(clock['active_union_seconds'])
        interaction = float(clock['interaction_seconds'])
        content = reading + playback - overlap
        if content < -1e-6 or not math.isclose(active, interaction + content, abs_tol=1e-5):
            raise ValueError('Clock accounting mismatch at action ' + str(i))
        interactions += interaction
        content_total += content
        media = execution.get('playback')
        media_set = asset_sections.get(media.get('asset_id'), set()) if media else set()
        if name == 'read' and before.get('overlay'):
            allocation = overlay_section or 'unallocated'
        elif reading and playback:
            combined = context | media_set
            allocation = next(iter(combined)) if len(combined) == 1 else 'unallocated'
        elif playback:
            allocation = next(iter(media_set)) if len(media_set) == 1 else (overlay_section or 'unallocated')
        else:
            allocation = next(iter(context)) if len(context) == 1 else 'unallocated'
        r = row(allocation)
        r['active_content_seconds'] += content
        r['overlay_inspection_seconds' if before.get('overlay') and name == 'read' else 'reading_seconds'] += reading
        r['playback_seconds'] += playback
        r['overlap_seconds'] += overlap
        if name == 'skip':
            r['skip_actions'] += 1
        if not execution['success']:
            errors.append({'action_index': i, 'action': name, 'error': execution.get('error'), 'reader_disinterest_inferred': False})
        if media and execution['success']:
            aid = media['asset_id']
            played.setdefault(aid, []).append([float(media['start']), float(media['end'])])
            samples.setdefault(aid, []).extend(float(f['source_time']) for f in execution.get('frames', []))
            if media['advanced_seconds'] <= 0 and target.get('duration') and target.get('current_time', 0) < target['duration'] - .1:
                errors.append({'action_index': i, 'action': name, 'error': 'Successful play reported no source advancement before the end', 'reader_disinterest_inferred': False})
        after_sections = observe(after, backtrack=name == 'scroll_back')
        path.append({'action_index': i, 'action': name, 'success': execution['success'],
                     'start_seconds': clock['session_start'], 'end_seconds': clock['session_end'],
                     'before_sections': sorted(context), 'after_sections': sorted(after_sections),
                     'allocated_section': allocation, 'overlay': before.get('overlay', False),
                     'model_or_fixture_reason': proposed.get('reason'),
                     'reason_interpretation': 'not classified as reflection, confusion or disinterest automatically'})
    accounted = content_total + interactions
    if not math.isclose(accounted, trace.get('clock', {}).get('simulated_active_seconds', accounted), abs_tol=1e-4):
        raise ValueError('Section accounting does not reconcile to the executor clock')
    for value in sections.values():
        value['visible_block_ids'] = sorted(value['visible_block_ids'])
        for key in ['reading_seconds', 'overlay_inspection_seconds', 'playback_seconds', 'overlap_seconds', 'active_content_seconds']:
            value[key] = round(value[key], 6)
    media_rows = [{'asset_id': aid, 'play_intervals': intervals,
                   'total_playback_source_seconds': round(sum(max(0, b-a) for a, b in intervals), 6),
                   'unique_playback_source_seconds': round(union_length(intervals), 6),
                   'sampled_frame_source_times': samples.get(aid, []),
                   'meaning': 'Browser source advancement; model saw only sampled frames, not continuous video or audio.'}
                  for aid, intervals in played.items()]
    return {'sections': list(sections.values()), 'reading_path': path, 'technical_events': errors,
            'media': media_rows, 'unplayed_motion_asset_ids': [a['asset_id'] for a in manifest.get('assets', []) if a.get('mime_type') in {'video/mp4', 'image/gif'} and a['asset_id'] not in played], 'interaction_seconds': round(interactions, 6),
            'active_content_seconds': round(content_total, 6), 'accounted_active_seconds': round(accounted, 6),
            'technical_event_count': len(errors),
            'natural_finish_event_recorded': any(x['event']['action'] == 'finish' and x['execution']['success'] for x in records)}


def summarize_run(out):
    out = Path(out).resolve()
    config = read(out / 'config.json', {})
    status = read(out / 'status.json', {})
    persona = read(out / 'persona.json', {})
    trace = read(out / 'trace.json')
    validation = read(out / 'validation.json', {})
    result = {'run_path': str(out), 'session_id': config.get('session_id'), 'persona_id': config.get('persona_id', persona.get('id')),
              'execution_mode': status.get('execution_mode', 'not_attempted'), 'raw_status': status.get('status', 'missing_assigned_run'),
              'termination': trace.get('termination') if trace else None, 'interest_rating': None, 'finish_time_seconds': None,
              'provider_calls': status.get('provider_calls', 0 if status.get('status') == 'prepared_not_a_simulated_read' else None), 'calibration_status': 'not_calibrated', 'confidence_interval': None,
              'exit_reason': 'unknown', 'human_outcomes': 0, 'audit_status': validation.get('status', 'not_audited')}
    integrity_errors = []
    for seal_name in ['seal.json', 'raw-output-seal.json']:
        seal = read(out / seal_name, {})
        for rel, expected in seal.get('files', {}).items():
            p = within(out, rel)
            if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest() != expected:
                integrity_errors.append(rel)
    if trace:
        try:
            bundle = Path(config['bundle'])
            validate_seal(bundle)
            if hashlib.sha256((bundle / 'seal.json').read_bytes()).hexdigest() != config['bundle_seal_sha256']:
                integrity_errors.append('Bundle lineage changed')
        except (KeyError, ValueError, OSError) as exc:
            integrity_errors.append('Bundle check: ' + str(exc))
    result['integrity_errors'] = integrity_errors
    sealed_audit = bool((out / 'seal.json').is_file() and 'validation.json' in read(out / 'raw-output-seal.json', {}).get('files', {}))
    result['eligible_live_trace'] = bool(sealed_audit and validation.get('status') == 'verified_simulated_read_with_limits' and status.get('status') == validation.get('status') and status.get('execution_mode') == 'live_api' and not integrity_errors)
    result['data_kind'] = 'authored_software_fixture_not_audience_result' if status.get('execution_mode') == 'authored_fixture' else 'audited_live_simulated_trace' if result['eligible_live_trace'] else 'prepared_missing_failed_or_unverified'
    if not trace:
        result.update(sections=[], reading_path=[], technical_events=[], media=[], timing_status='unavailable_not_zero')
        return result
    bundle = Path(config['bundle'])
    records = [read(p) for p in sorted((out / 'actions').glob('*.json'))]
    try:
        result.update(aggregate_trace(trace, records, read(bundle / 'block-map.json', []), read(bundle / 'bundle-manifest.json', {})))
    except (KeyError, ValueError) as exc:
        result.update(summary_error=str(exc), eligible_live_trace=False, sections=[], reading_path=[], technical_events=[], media=[])
    feedback = read(out / 'feedback.json', {})
    result['interest_rating'] = feedback.get('interest_rating')
    result['interest_origin'] = 'authored fixture value' if status.get('execution_mode') == 'authored_fixture' else 'uncalibrated retrospective model self-rating'
    result['feedback_rationale'] = feedback.get('reason')
    terminal = next((r for r in reversed(records) if r['proposed']['action'] in {'finish', 'abandon'} and r['execution']['success']), None)
    result['exit_rationale'] = terminal['proposed'].get('reason') if terminal else None
    result['exit_rationale_origin'] = 'raw action reason; reviewer classification pending, no motive inferred'
    result['retrospective_feedback'] = {k: feedback[k] for k in ['reason', 'useful_takeaway', 'confusing_claims', 'suggested_revision', 'likely_drop_off'] if k in feedback}
    result['cap_censored'] = str(trace['termination']).endswith('_cap')
    result['simulated_active_seconds'] = trace['clock']['simulated_active_seconds']
    result['timing_status'] = trace['clock'].get('timing_status', 'authored_simulation_not_human_measurement')
    result['system_wall_seconds'] = status.get('system_wall_seconds')
    if result['eligible_live_trace'] and trace['termination'] == 'finish':
        result['finish_time_seconds'] = trace['clock']['simulated_active_seconds']
    return result


def write_report(runs, out):
    out = Path(out)
    if out.exists():
        raise ValueError('Use a fresh summary directory')
    results = [summarize_run(p) for p in runs]
    unknown_calls = sum(r['provider_calls'] is None for r in results)
    known_calls = sum(r['provider_calls'] for r in results if r['provider_calls'] is not None)
    rollup = {'assigned_runs': len(results), 'eligible_live_traces': sum(r['eligible_live_trace'] for r in results),
              'authored_fixture_traces': sum(r['execution_mode'] == 'authored_fixture' for r in results),
              'not_attempted_or_missing': sum(r['execution_mode'] == 'not_attempted' for r in results),
              'provider_calls': None if unknown_calls else known_calls, 'known_provider_calls': known_calls,
              'provider_calls_unknown_runs': unknown_calls, 'human_outcomes': 0,
              'completion_probability': None, 'calibrated_confidence_interval': None}
    groups = {}
    for r in results:
        key = (r['persona_id'], r['data_kind'])
        group = groups.setdefault(key, {'persona_id': key[0], 'data_kind': key[1], 'assigned': 0, 'raw_terminations': {}, 'eligible_finish_times': []})
        group['assigned'] += 1
        stop = r['termination'] or r['raw_status']
        group['raw_terminations'][stop] = group['raw_terminations'].get(stop, 0) + 1
        if r['finish_time_seconds'] is not None:
            group['eligible_finish_times'].append(r['finish_time_seconds'])
    document = {'version': 'trace-summary-0.1', 'implementation_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                'rollup': rollup, 'role_outcomes_by_evidence_kind': list(groups.values()), 'runs': results,
                'interpretation': 'Preserved assigned denominator. Authored fixtures are software evidence only. Dwell and exit motives are not inferred human behavior; retrospective interest is uncalibrated. Ambiguous section time stays unallocated.'}
    out.mkdir(parents=True)
    (out / 'summary.json').write_text(json.dumps(document, indent=2, ensure_ascii=False) + '\n')
    fields = ['run_path', 'persona_id', 'data_kind', 'termination', 'cap_censored', 'interest_rating', 'finish_time_seconds', 'simulated_active_seconds', 'system_wall_seconds', 'technical_event_count', 'provider_calls', 'audit_status']
    with (out / 'runs.csv').open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(results)
    with (out / 'sections.csv').open('w', newline='') as f:
        fields2 = ['session_id', 'section_id', 'visits', 'backtrack_revisits', 'skip_actions', 'reading_seconds', 'overlay_inspection_seconds', 'playback_seconds', 'overlap_seconds', 'active_content_seconds']
        writer = csv.DictWriter(f, fieldnames=fields2, extrasaction='ignore')
        writer.writeheader()
        for r in results:
            for section in r['sections']:
                writer.writerow({'session_id': r['session_id'], **section})
    lines = ['# Reading trace summary', '', document['interpretation'], '',
             f"Assigned: {rollup['assigned_runs']}; audited live traces: {rollup['eligible_live_traces']}; authored fixtures: {rollup['authored_fixture_traces']}; provider calls: {rollup['provider_calls']}; measured human outcomes: 0.", '',
             '| Role | Evidence kind | Raw termination | Active simulated seconds | Technical events |', '| --- | --- | --- | --- | --- |']
    for r in results:
        lines.append('| ' + ' | '.join(str(r.get(k, 'unavailable')) for k in ['persona_id', 'data_kind', 'termination', 'simulated_active_seconds', 'technical_event_count']) + ' |')
    lines += ['', 'Section accounting and ordered actions are in summary.json and sections.csv. No completion probability, reader confidence interval or editorial winner is computed. Fixture interest values and clocks must not be interpreted as audience predictions.', '']
    (out / 'README.md').write_text('\n'.join(lines))
    return document


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--runs', nargs='+', required=True)
    p.add_argument('--out', required=True)
    args = p.parse_args()
    print(json.dumps(write_report(args.runs, args.out)['rollup'], indent=2))
