#!/usr/bin/env python3
"""Track host-read articles and audit learning records; never fetch or infer reading."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import unicodedata
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

SKILL_ROOT = Path(__file__).resolve().parents[1]
NOTE_FIELDS = ('topic_type', 'reader_promise', 'hook', 'argument_or_case_sequence',
               'concrete_detail', 'short_anchor', 'transferable_lesson', 'limit', 'media_review')
STATES = {'lead_only', 'blocked', 'read_complete'}


def now():
    return datetime.now(timezone.utc).isoformat()


def read(path, default=None):
    path = Path(path)
    return json.loads(path.read_text(encoding='utf-8-sig')) if path.is_file() else default


def save(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def public_url(value):
    if not isinstance(value, str):
        return False
    parts = urlsplit(value)
    return parts.scheme in ('http', 'https') and bool(parts.netloc) and not parts.username and not parts.password


def article_url(value):
    parts = urlsplit(value)
    query = parts.query
    if parts.hostname == 'mp.weixin.qq.com' and parts.path.rstrip('/') == '/s' and query:
        query = urlencode(sorted((k, v) for k, v in parse_qsl(query) if k in ('__biz', 'mid', 'idx', 'sn')))
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip('/'), query, ''))


def title_key(value):
    return ''.join(c.lower() for c in unicodedata.normalize('NFKC', value) if c.isalnum())


def init_study(workspace, request, run=None):
    workspace = Path(workspace).resolve()
    targets = request.get('targets', [])
    names = [target.get('account') for target in targets]
    if not request.get('request') or not targets or len(set(names)) != len(names):
        raise ValueError('request and distinct target accounts are required')
    for target in targets:
        if not isinstance(target.get('account'), str) or not target['account'].strip() or type(target.get('count')) is not int or target['count'] <= 0:
            raise ValueError('each target needs an account label and positive count')
    if request.get('approval_policy', 'review_first') not in ('review_first', 'explicit_delegation'):
        raise ValueError('unsupported approval policy')
    if request.get('mode', 'content') not in ('content', 'writing-style'):
        raise ValueError('mode must be content or writing-style')
    run = Path(run).resolve() if run else workspace / 'wechat-content-study' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    if not run.is_relative_to(workspace) or run.is_relative_to(SKILL_ROOT):
        raise ValueError('learning run must stay in the workspace, outside the distributable skill')
    if (run / 'study.json').exists() or (run / 'articles.json').exists() or (run / 'lessons.json').exists():
        raise ValueError('study already exists; use status and record to resume')
    config = {**request, 'schema_version': 1, 'workspace': str(workspace), 'created_at': now(),
              'approval_policy': request.get('approval_policy', 'review_first')}
    save(run / 'study.json', config)
    save(run / 'articles.json', [])
    save(run / 'lessons.json', [])
    return {'run': str(run), 'targets': targets, 'status': 'collecting', 'skill_modified': False}


def body_path(run, workspace, value):
    if not isinstance(value, str) or not value:
        raise ValueError('full_text_file missing')
    path = Path(value)
    if not path.is_absolute():
        choices = (run / path, workspace / path)
        path = next((p for p in choices if p.is_file()), choices[0])
    path = path.resolve()
    if not path.is_relative_to(workspace) or path.is_relative_to(SKILL_ROOT):
        raise ValueError('body file must be in the research workspace, outside the skill package')
    return path


def audit(run, articles=None):
    run = Path(run).resolve()
    config = read(run / 'study.json')
    if not isinstance(config, dict):
        raise ValueError('study.json missing; initialize or provide an existing learning run')
    workspace = Path(config['workspace']).resolve()
    if not run.is_relative_to(workspace) or run.is_relative_to(SKILL_ROOT):
        raise ValueError('invalid research directory')
    expected = {target['account']: target['count'] for target in config['targets']}
    records = articles if articles is not None else read(run / 'articles.json', [])
    if not isinstance(records, list):
        raise ValueError('articles.json must be an array')
    errors, inspected, seen_ids, titles, hashes, links = [], [], set(), {}, {}, {}
    verified, statuses = Counter(), Counter()
    valid_ids = set()
    for record in records:
        if not isinstance(record, dict):
            errors.append({'id': None, 'issues': ['record must be an object']})
            continue
        ident, target = record.get('id'), record.get('target', record.get('account'))
        status, issues = record.get('status'), []
        if not isinstance(ident, str) or not ident.strip() or ident in seen_ids:
            issues.append('missing or duplicate article id')
        seen_ids.add(ident)
        if target not in expected:
            issues.append('unknown target label')
        if status not in STATES:
            issues.append('unknown reading status')
        statuses[str(status)] += 1
        if status == 'read_complete':
            for field in ('account', 'author', 'title', 'date_kind', 'completion_basis'):
                if not isinstance(record.get(field), str) or not record[field].strip():
                    issues.append('missing ' + field)
            source_kind = record.get('source_kind', 'web')
            if source_kind == 'user-file':
                if not str(record.get('input_label', '')).strip() or record.get('read_url'):
                    issues.append('user-file requires an actual input label and no invented read_url')
            elif source_kind != 'web' or not public_url(record.get('read_url')):
                issues.append('missing or invalid public read_url')
            if record.get('original_url') and not public_url(record['original_url']):
                issues.append('invalid original_url')
            if record.get('title') and isinstance(record['title'], str):
                key = (record.get('account'), title_key(record['title']))
                if key in titles:
                    issues.append('duplicate article title: ' + str(titles[key]))
                titles[key] = ident
            source = record.get('original_url') or record.get('read_url')
            if public_url(source):
                key = article_url(source)
                if key in links:
                    issues.append('duplicate article link: ' + str(links[key]))
                links[key] = ident
            notes = record.get('notes')
            if not isinstance(notes, dict):
                notes = {}
            for field in NOTE_FIELDS:
                if not notes.get(field):
                    issues.append('missing note ' + field)
            try:
                path = body_path(run, workspace, record.get('full_text_file'))
                data = path.read_bytes()
                digest = hashlib.sha256(data).hexdigest()
                if record.get('hash') != digest:
                    issues.append('body hash changed or missing')
                if digest in hashes:
                    issues.append('duplicate body: ' + str(hashes[digest]))
                hashes[digest] = ident
                body = data.decode('utf-8-sig')
                anchor = notes.get('short_anchor')
                if not body.strip() or not isinstance(anchor, str) or not anchor.strip() or anchor not in body:
                    issues.append('short anchor absent from saved body')
            except (ValueError, OSError, UnicodeError) as exc:
                issues.append('body unavailable: ' + str(exc))
        if issues:
            errors.append({'id': ident, 'issues': issues})
        if status == 'read_complete' and not issues:
            verified[target] += 1
            valid_ids.add(ident)
        inspected.append({'id': ident, 'status': status, 'valid_read_complete': status == 'read_complete' and not issues})
    article_error_count = len(errors)
    lessons = read(run / 'lessons.json', [])
    lesson_ids = set()
    if not isinstance(lessons, list):
        errors.append({'issues': ['lessons.json must be an array']})
        lessons = []
    for lesson in lessons:
        if not isinstance(lesson, dict):
            errors.append({'issues': ['lesson must be an object']})
            continue
        ident, issues = lesson.get('id'), []
        if not ident or ident in lesson_ids:
            issues.append('missing or duplicate lesson id')
        lesson_ids.add(ident)
        for field in ('rule', 'why', 'applicability', 'limits', 'proposed_location'):
            if not isinstance(lesson.get(field), str) or not lesson[field].strip():
                issues.append('missing lesson ' + field)
        evidence = lesson.get('evidence_ids')
        if not isinstance(evidence, list) or not evidence or not set(evidence) <= valid_ids:
            issues.append('lesson evidence must refer to valid actually-read records')
        if issues:
            errors.append({'lesson_id': ident, 'issues': issues})
    counts = [{'target': target, 'expected': count, 'verified_read_complete': verified[target],
               'remaining': max(0, count - verified[target])} for target, count in expected.items()]
    complete = all(verified[target] == count for target, count in expected.items())
    return {'scope': 'reading-record-consistency', 'checked_at': now(), 'passed': complete and not errors,
            'reading_complete': complete and article_error_count == 0,
            'counts': counts, 'valid_read_complete': sum(verified.values()), 'statuses': dict(statuses),
            'lesson_count': len(lessons), 'errors': errors, 'articles': inspected,
            'approval_policy': config.get('approval_policy', 'review_first'),
            'limitation': '仅核对记录、目标数量、去重、哈希与笔记锚点；不证明全文理解、媒体核验或阅读量效果。'}


def record_articles(run, incoming):
    run = Path(run).resolve()
    batch = incoming if isinstance(incoming, list) else [incoming]
    if not batch or any(not isinstance(item, dict) or not item.get('id') for item in batch):
        raise ValueError('incoming articles need distinct ids')
    if len({item['id'] for item in batch}) != len(batch):
        raise ValueError('duplicate ids in incoming batch')
    old = read(run / 'articles.json', [])
    merged = {item['id']: item for item in old}
    for item in batch:
        if item['id'] in merged and item.get('account') != merged[item['id']].get('account'):
            raise ValueError('same article id cannot silently change account')
        merged[item['id']] = item
    records = list(merged.values())
    report = audit(run, records)
    if report['errors']:
        return {**report, 'saved': False}
    save(run / 'articles.json', records)
    return {**report, 'saved': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    init = commands.add_parser('init')
    init.add_argument('--workspace', required=True, type=Path)
    init.add_argument('--request-file', required=True, type=Path)
    init.add_argument('--run', type=Path)
    record = commands.add_parser('record')
    record.add_argument('--run', required=True, type=Path)
    record.add_argument('--file', required=True, type=Path)
    for name in ('status', 'check'):
        cmd = commands.add_parser(name)
        cmd.add_argument('--run', required=True, type=Path)
    args = parser.parse_args()
    try:
        if args.command == 'init':
            result = init_study(args.workspace, read(args.request_file), args.run)
        elif args.command == 'record':
            result = record_articles(args.run, read(args.file))
        else:
            result = audit(args.run)
            if args.command == 'check':
                save(args.run / 'learning-check.json', result)
        compact = {key: value for key, value in result.items() if key != 'articles'}
        print(json.dumps(compact, ensure_ascii=False, indent=2))
        return 2 if (args.command == 'check' and not result['passed']) or result.get('saved') is False else 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(json.dumps({'error': str(exc)}, ensure_ascii=False))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
