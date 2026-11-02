#!/usr/bin/env python3
"""Plan host-tool searches and check evidence-backed editorial records; never pretend to search."""
import argparse
import json
from pathlib import Path
import re
import workflow as w

PLATFORMS = {'web': None, 'github': 'github.com', 'x': 'x.com', 'douyin': 'douyin.com',
             'bilibili': 'bilibili.com', 'xiaohongshu': 'xiaohongshu.com', 'zhihu': 'zhihu.com',
             'wechat': 'mp.weixin.qq.com'}
ACCESS = {'full_text', 'author_caption', 'video_segment', 'artifact', 'human_supplied'}
KINDS = {'case', 'comparison', 'finding', 'mechanism', 'procedure', 'synthesis'}
FILES = ['body.md', 'sources.json', 'claims.json', 'cases.json', 'research-plan.json', 'research-log.json']


def plan(run, topic=None, platforms=None, questions=None, aliases=None):
    run = Path(run)
    brief = w.read(run / 'brief.json', {})
    topic = topic or brief.get('topic')
    if not topic:
        raise ValueError('research plan needs a topic')
    platforms = platforms or ['web', 'github', 'x', 'douyin', 'bilibili', 'xiaohongshu']
    if any(p not in PLATFORMS for p in platforms):
        raise ValueError('unknown research platform')
    queries = []
    entity = ' '.join([topic] + (aliases or []))
    for platform in dict.fromkeys(platforms):
        for angle in ('真实案例 操作结果 失败 限制', 'case study input output benchmark limitations'):
            queries.append({'id': f'Q{len(queries) + 1}', 'platform': platform,
                            'query': f'{entity} {angle}', 'domain': PLATFORMS[platform],
                            'status': 'planned', 'purpose': '找原始案例、产出或反例；摘要仅为线索'})
    result = {'created_at': w.now(), 'topic': topic,
              'reader_questions': questions or ['有哪些可核验的具体结果？怎么复用？哪些条件下会失败？'],
              'news_window_days': 7, 'background_cases': '允许更早，但记录原始日期及当时版本',
              'queries': queries, 'execution': 'host web/browser tools; this CLI only creates a plan'}
    w.save(run / 'research-plan.json', result)
    return result


def substantive(value, minimum=8):
    return isinstance(value, str) and len(value.strip()) >= minimum


def research_errors(run):
    run = Path(run)
    errors, warnings = [], []
    plan_data = w.read(run / 'research-plan.json', {})
    log = w.read(run / 'research-log.json', {})
    queries = plan_data.get('queries', [])
    records = log.get('queries', [])
    planned = {q.get('id'): q for q in queries}
    actual = {r.get('id'): r for r in records}
    if not queries or not plan_data.get('reader_questions') or len(planned) != len(queries):
        errors.append('research plan missing, lacks reader questions or has duplicate query IDs')
    if len(actual) != len(records) or set(actual) != set(planned):
        errors.append('research log must account for every planned query exactly once')
    for key, record in actual.items():
        query = planned.get(key, {})
        status = record.get('status')
        if record.get('platform') != query.get('platform') or not w.date(record.get('observed_at')):
            errors.append(f'{key}: platform/date observation missing')
        if status not in ('read', 'lead_only', 'no_results', 'login_required', 'blocked', 'skipped'):
            errors.append(f'{key}: planned search is not actual execution')
        if not substantive(record.get('observation')):
            errors.append(f'{key}: actual observation/reason missing')
        if status in ('read', 'lead_only') and not record.get('source_ids'):
            errors.append(f'{key}: results lack source IDs')
        if status != 'skipped' and record.get('method') not in ('host_search', 'browser', 'authorized_api', 'public_http', 'user_link'):
            errors.append(f'{key}: actual retrieval method missing')
        if status in ('lead_only', 'login_required', 'blocked', 'skipped'):
            warnings.append(f"{key}: {query.get('platform')} {status}; do not claim full platform coverage")
    sources = {s['id']: s for s in w.read(run / 'sources.json', [])}
    if not any(record.get('status') == 'read' for record in records):
        errors.append('research has no actually read original material')
    for record in records:
        if any(sid not in sources for sid in record.get('source_ids', [])):
            errors.append(f"{record.get('id')}: unknown research source")
        if record.get('status') == 'read':
            read_sources = [sources[sid] for sid in record.get('source_ids', []) if sid in sources]
            if not any(s.get('verified') and s.get('kind') != 'lead' and s.get('read_record', {}).get('access') in ACCESS for s in read_sources):
                errors.append(f"{record.get('id')}: read status lacks an original reading record")
    cases = w.read(run / 'cases.json', [])
    if len({c.get('id') for c in cases}) != len(cases):
        errors.append('duplicate case IDs')
    for case in cases:
        cid = case.get('id', '?')
        if case.get('origin') not in ('author_report', 'vendor_demo', 'synthetic_demo', 'own_experiment'):
            errors.append(f'{cid}: case origin must distinguish reporting, demo and own experiment')
        case_type = case.get('case_type', 'task')
        if case_type not in ('task', 'human_or_organization'):
            errors.append(f'{cid}: unknown case type')
        fields = ('actor', 'goal', 'context', 'choices', 'perspectives', 'outcome', 'limitations', 'application') if case_type == 'human_or_organization' else ('actor', 'task', 'input', 'process', 'outcome', 'limitations', 'application')
        for field in fields:
            if not substantive(case.get(field)):
                errors.append(f'{cid}: concrete case {field} missing')
        evidence = case.get('evidence', [])
        if not evidence:
            errors.append(f'{cid}: original observation missing')
        for item in evidence:
            source = sources.get(item.get('source_id'), {})
            record = source.get('read_record', {})
            if not source.get('verified') or source.get('kind') == 'lead' or record.get('access') not in ACCESS:
                errors.append(f'{cid}: search snippet/platform summary cannot prove a case')
            if not item.get('locator') or not substantive(item.get('observation_quote')):
                errors.append(f'{cid}: source locator/observed passage missing')
            try:
                path = w.within(run, record.get('artifact_path', ''))
                text = path.read_text(encoding='utf-8') if path.is_file() else ''
            except (ValueError, OSError):
                text = ''
            if not text or item.get('observation_quote', '') not in text:
                errors.append(f'{cid}: observed passage missing from saved original reading record')
            if text and record.get('artifact_sha256') != w.file_hash(path):
                errors.append(f'{cid}: original reading record changed or hash missing')
        if case.get('origin') == 'own_experiment':
            experiments = w.read(run / 'experiments.json', [])
            exp = next((e for e in experiments if e.get('id') == case.get('experiment_id')), {})
            try:
                exists = w.within(run, exp.get('output_path', '')).is_file()
            except ValueError:
                exists = False
            if not exp.get('actions') or not exp.get('observations') or not exists:
                errors.append(f'{cid}: own experiment was not actually recorded')
    return errors, warnings


def title_errors(run):
    run = Path(run)
    errors, warnings = [], []
    titles = w.read(run / 'titles.json', {})
    body = (run / 'body.md').read_text(encoding='utf-8') if (run / 'body.md').is_file() else ''
    candidates = titles.get('candidates', [])
    fixed = titles.get('user_fixed', {})
    fixed_valid = fixed.get('origin') == 'user' and substantive(fixed.get('instruction')) and any(
        c.get('id') == titles.get('selected') and c.get('title') == fixed.get('title') for c in candidates)
    if titles.get('body_sha256') != w.file_hash(run / 'body.md'):
        errors.append('title promises must bind to current body')
    if not fixed_valid and (len(candidates) < 12 or len({c.get('method') for c in candidates if c.get('method')}) < 6):
        errors.append('need at least 12 titles across 6 genuinely different angles')
    if len({c.get('title') for c in candidates}) != len(candidates):
        errors.append('duplicate titles')
    ids = {c.get('id') for c in candidates}
    shortlist = titles.get('shortlist', [])
    if not fixed_valid and (len(shortlist) != 3 or len(set(shortlist)) != 3 or not set(shortlist) <= ids or titles.get('selected') not in shortlist):
        errors.append('present 3 distinct supported title choices and select one of them')
    for candidate in candidates:
        cid, title = candidate.get('id', '?'), candidate.get('title', '')
        if not title or len(title) > 64:
            errors.append(f'{cid}: title empty or exceeds skill 64-character ceiling')
        visible = len(re.sub(r'\s+', '', title))
        if not 26 <= visible <= 42:
            warnings.append(f'{cid}: {visible} visible characters outside editorial preference 26–42')
            if not substantive(candidate.get('length_reason')):
                errors.append(f'{cid}: short/long title requires a content-specific reason')
        for field in ('reader', 'hook', 'promise', 'opening_reason'):
            if not substantive(candidate.get(field)):
                errors.append(f'{cid}: specific title {field} missing')
        quote = candidate.get('body_quote', '')
        if not substantive(quote) or quote not in body:
            errors.append(f'{cid}: headline promise is unsupported by current article')
        # Actual first-person experience needs explicit linkage, not a title formula.
        if re.search(r'我(?:实测|亲测|试了|用了)|亲测', title) and not candidate.get('experiment_ids'):
            errors.append(f'{cid}: first-person title lacks actual experiment IDs')
        for eid in candidate.get('experiment_ids', []):
            exp = next((e for e in w.read(run / 'experiments.json', []) if e.get('id') == eid), {})
            try:
                exists = w.within(run, exp.get('output_path', '')).is_file()
            except ValueError:
                exists = False
            if not exp.get('actions') or not exp.get('observations') or not exists:
                errors.append(f'{cid}: headline experiment not recorded')
    return errors, warnings


def depth_errors(run):
    run = Path(run)
    errors, warnings = [], []
    body = (run / 'body.md').read_text(encoding='utf-8') if (run / 'body.md').is_file() else ''
    brief = w.read(run / 'brief.json', {})
    review = w.read(run / 'depth-review.json', {})
    if review.get('input_hashes') != {name: w.file_hash(run / name) for name in FILES}:
        errors.append('depth review missing or stale against body, evidence and actual search log')
    records = review.get('sections', [])
    headings = re.findall(r'(?m)^##\s+(.+)$', body) or (['全文'] if body else [])
    if not headings or sorted(r.get('section', '') for r in records) != sorted(headings):
        errors.append('depth ledger must cover each actual article section exactly once')
    valid_ids = {c.get('id') for c in w.read(run / 'claims.json', [])} | {c.get('id') for c in w.read(run / 'cases.json', [])}
    for record in records:
        heading = record.get('section', '')
        segment = body if heading == '全文' else next((part for part in re.split(r'(?m)^##\s+', body)[1:] if part.split('\n', 1)[0] == heading), '')
        if record.get('kind') not in KINDS or not all(substantive(record.get(k)) for k in ('question', 'reader_gain', 'body_quote')):
            errors.append(f'{heading}: section lacks a specific reader gain and evidence type')
        if record.get('body_quote', '') not in segment:
            errors.append(f'{heading}: section gain not present in this article section')
        ids = record.get('supporting_ids', [])
        if record.get('kind') != 'synthesis' and (not ids or not set(ids) <= valid_ids):
            errors.append(f'{heading}: substantive section lacks known claims/cases')
        for sid in ids:
            claim = next((c for c in w.read(run / 'claims.json', []) if c.get('id') == sid), None)
            if claim and claim.get('body_quote', '') not in segment:
                errors.append(f'{heading}: supporting fact belongs to another section')
            case = next((c for c in w.read(run / 'cases.json', []) if c.get('id') == sid), None)
            if case and (not substantive(case.get('body_quote')) or case['body_quote'] not in segment):
                errors.append(f'{heading}: cited case lacks a current passage in this section')
    if brief.get('length_preset') == 'deep' or brief.get('min_chars', 0) >= 5000:
        units = [r for r in records if r.get('kind') != 'synthesis']
        if len(units) < 2 or not any(r.get('kind') in ('case', 'comparison') for r in units):
            errors.append('long article needs substantive evidence plus a concrete case or comparison; length alone is not depth')
    for key in ('counterevidence', 'transferability', 'non_generic'):
        check = review.get('checks', {}).get(key, {})
        if check.get('status') != 'pass' or not substantive(check.get('reason')) or not substantive(check.get('body_quote')) or check.get('body_quote', '') not in body:
            errors.append(f'depth semantic review missing current passage: {key}')
    return errors, warnings


def check(run, scope='all'):
    errors, warnings = [], []
    for name, validator in [('research', research_errors), ('titles', title_errors), ('depth', depth_errors)]:
        if scope in (name, 'all'):
            e, warn = validator(run)
            errors += e
            warnings += warn
    report = {'passed': not errors, 'scope': scope, 'checked_at': w.now(), 'errors': errors,
              'warnings': warnings, 'limitation': '检查文件、溯源与当前段落；案例真实性、标题吸引力和文章深度仍需实际阅读审稿。'}
    w.save(Path(run) / 'editorial-check.json', report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='cmd', required=True)
    planner = sub.add_parser('plan')
    planner.add_argument('--run', required=True, type=Path)
    planner.add_argument('--topic')
    planner.add_argument('--platforms', nargs='+', choices=tuple(PLATFORMS))
    planner.add_argument('--question', action='append')
    planner.add_argument('--alias', action='append')
    checker = sub.add_parser('check')
    checker.add_argument('--run', required=True, type=Path)
    checker.add_argument('--scope', choices=('all', 'research', 'titles', 'depth'), default='all')
    args = parser.parse_args()
    try:
        result = plan(args.run, args.topic, args.platforms, args.question, args.alias) if args.cmd == 'plan' else check(args.run, args.scope)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2 if result.get('passed') is False else 0
    except (ValueError, OSError, KeyError) as exc:
        print(json.dumps({'error': str(exc)}, ensure_ascii=False))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
