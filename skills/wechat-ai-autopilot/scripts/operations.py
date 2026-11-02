"""Stage timers and bounded retry history, without account/session data."""
import argparse
from contextlib import contextmanager
from pathlib import Path
import time
import uuid
import workflow as w

STAGES = ('research', 'writing', 'screenshots', 'imagegen', 'layout', 'workshop',
          'preflight', 'assets', 'paste', 'save', 'readback', 'reader', 'draft_transport')


def start(run, stage):
    if stage not in STAGES:
        raise ValueError('unknown stage')
    records = w.read(Path(run) / 'timings.json', {'schema_version': 1, 'events': []})
    token = uuid.uuid4().hex
    records['events'].append({'id': token, 'stage': stage, 'started_at': w.now(),
                              'started_epoch': time.time(), 'status': 'running'})
    w.save(Path(run) / 'timings.json', records)
    return token


def stop(run, token, status='success', reused=False, clock=None):
    if status not in ('success', 'failed', 'blocked', 'awaiting_user'):
        raise ValueError('invalid stage status')
    target = Path(run) / 'timings.json'
    records = w.read(target, {})
    event = next((x for x in records.get('events', []) if x['id'] == token), None)
    if not event or event['status'] != 'running':
        raise ValueError('unknown or already finished timer')
    event.update(status=status, reused=bool(reused), ended_at=w.now(),
                 elapsed_seconds=round(max(0, (clock or time.time()) - event['started_epoch']), 3))
    w.save(target, records)
    return event


@contextmanager
def measure(run, stage):
    token = start(run, stage)
    try:
        yield
    except BaseException:
        stop(run, token, 'failed')
        raise
    else:
        stop(run, token)


def retry(run, resource_id, outcome, attempt_limit=2):
    if not resource_id or not all(c.isalnum() or c in '-_.' for c in resource_id) or len(resource_id) > 80:
        raise ValueError('Use an opaque resource ID, not URL or credential')
    if outcome not in ('success', 'failed', 'access_denied', 'login_required'):
        raise ValueError('invalid outcome')
    path = Path(run) / 'retry-ledger.json'
    data = w.read(path, {'resources': {}})
    previous = data['resources'].get(resource_id, {'attempts': 0})
    if previous.get('next') in ('reuse', 'fallback_or_report_missing'):
        return previous
    previous.update(attempts=previous['attempts'] + 1, outcome=outcome, at=w.now())
    previous['next'] = ('reuse' if outcome == 'success' else 'fallback_or_report_missing'
                        if outcome in ('access_denied', 'login_required') or previous['attempts'] >= attempt_limit else 'targeted_repair')
    data['resources'][resource_id] = previous
    w.save(path, data)
    return previous


def summary(run):
    data = w.read(Path(run) / 'timings.json', {})
    totals = {}
    for event in data.get('events', []):
        if event['status'] == 'running':
            continue
        totals[event['stage']] = round(totals.get(event['stage'], 0) + event['elapsed_seconds'], 3)
    return {'stage_seconds': totals, 'unfinished': [x['stage'] for x in data.get('events', []) if x['status'] == 'running'],
            'limits': 'Stage totals may overlap; not end-to-end wall time and not a speed guarantee.'}


if __name__ == '__main__':
    import json
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=('start', 'stop', 'summary', 'retry'))
    p.add_argument('--run', type=Path, required=True)
    p.add_argument('--stage', choices=STAGES)
    p.add_argument('--token')
    p.add_argument('--status', default='success')
    p.add_argument('--resource')
    p.add_argument('--outcome', choices=('success', 'failed', 'access_denied', 'login_required'))
    a = p.parse_args()
    value = start(a.run, a.stage) if a.command == 'start' else stop(a.run, a.token, a.status) if a.command == 'stop' else retry(a.run, a.resource, a.outcome) if a.command == 'retry' else summary(a.run)
    print(json.dumps(value, ensure_ascii=False))
