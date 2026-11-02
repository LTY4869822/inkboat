"""User intake, preview selection and non-secret account memory. No network or publication."""
import argparse
import datetime as dt
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

import workflow as w


def questions(known=None, workspace='.'):
    known = known or {}
    from style_library import catalog
    styles = catalog(workspace)
    options = [x['name'] for x in styles['writing_styles'].values()]
    items = [
        ('topic_mode', '这次有自己的选题吗？有的话直接写题目；没有的话，我会搜索最近7天的五个热点供你选择。', ['我有自己的选题', '没有，先推荐五个热点']),
        ('length_preset', '文章想写多长？也可以直接填写字数或让我根据内容自由发挥。', ['标准：3000—4500字', '短篇：1800—2500字', '长篇：5000—7000字', '根据内容自由发挥']),
        ('font', '正文想用什么字体？也可填写自己的字体名称。', ['系统无衬线（推荐）', '正楷 / 楷体', '宋体', '微软雅黑', '苹方']),
        ('writing_style', '这次用哪种文风？可以选择已学习的风格，也可以提供文章学习新风格。', options),
    ]
    return {'questions': [{'key': k, 'title': title, 'options': opts} for k, title, opts in items if not known.get(k)],
            'writing_styles': styles['writing_styles'], 'unavailable_styles': styles['unavailable'],
            'note': '合并询问缺项；用户明确让助手决定的字段可以记录委托。答复未到不能当作同意。排版在成稿后预览选择。'}


def validate_candidates(data):
    checked = w.date(data.get('searched_at'))
    items = data.get('candidates', [])
    if not checked or len(items) != 5 or len({x.get('id') for x in items}) != 5:
        raise ValueError('Need exactly five distinct candidates and the actual search time')
    for item in items:
        published = w.date(item.get('published_at'))
        retrieved = w.date(item.get('retrieved_at'))
        signal = item.get('hot_signal', {})
        signal_time = w.date(signal.get('observed_at'))
        if (not item.get('id') or not published or not retrieved or not signal_time or
                not dt.timedelta(0) <= checked - published <= dt.timedelta(days=7) or
                abs((checked - retrieved).total_seconds()) > 86400 or
                not dt.timedelta(0) <= checked - signal_time <= dt.timedelta(days=7)):
            raise ValueError('Candidate dates must use real publication/retrieval/attention times within the search window')
        for key in ('title', 'angle', 'reader_benefit'):
            if not str(item.get(key, '')).strip():
                raise ValueError('Candidate missing ' + key)
        url = urlsplit(item.get('primary_url', ''))
        if url.scheme != 'https' or not url.hostname or url.username or url.password:
            raise ValueError('Candidate requires a primary HTTPS source')
        if not signal.get('platform') or not signal.get('description'):
            raise ValueError('Describe the actual attention signal and platform; do not invent popularity counts')
    return data


def apply(run, answers):
    run = Path(run).resolve()
    if answers.get('answer_origin') not in ('user', 'explicit_user_delegation') or not answers.get('user_instruction', '').strip():
        raise ValueError('Record the actual user answers or explicit delegation, not inferred silence')
    for key in ('topic_mode', 'length_preset', 'font', 'writing_style'):
        if key not in answers:
            raise ValueError('Missing pre-writing answer: ' + key)
    from style_library import resolve
    brief = w.read(run / 'brief.json')
    style = resolve(brief['workspace'], answers['writing_style'])
    if answers['topic_mode'] == 'own':
        topic = answers.get('topic', '').strip()
        if not topic:
            raise ValueError('Own topic must be preserved verbatim')
    elif answers['topic_mode'] == 'candidates':
        data = validate_candidates(w.read(run / 'topic-candidates.json', {}))
        if w.date(w.now()) - w.date(data['searched_at']) > dt.timedelta(days=1):
            raise ValueError('Refresh candidates searched more than one day ago')
        item = next((x for x in data['candidates'] if x['id'] == answers.get('selected_candidate')), None)
        if not item:
            raise ValueError('Wait for the user to choose a candidate or explicitly delegate selection')
        topic = item['title']
    else:
        raise ValueError('topic_mode must be own or candidates')
    brief = w.read(run / 'brief.json')
    preset = answers['length_preset']
    if preset not in ('light', 'standard', 'deep', 'auto', 'custom'):
        raise ValueError('Unknown length preset')
    if preset == 'custom' and not answers.get('chars'):
        raise ValueError('Custom length requires minimum/maximum chars')
    chosen, bounds = w.length_choice(brief.get('profile', {}), brief['type'],
                                   None if preset == 'custom' else preset, answers.get('chars') if preset == 'custom' else None)
    custom = answers.get('custom_font', '')
    w.font_choice(answers['font'], custom)
    record = {**answers, 'schema_version': 1, 'status': 'ready_to_write', 'topic': topic,
              'length_preset': chosen, 'min_chars': bounds[0], 'max_chars': bounds[1],
              'custom_font': custom, 'recorded_at': w.now()}
    brief.update(schema_version=3, topic=topic, length_preset=chosen, min_chars=bounds[0], max_chars=bounds[1],
                 font=answers['font'], custom_font=custom, writing_style=style['id'])
    for key, value in (('writing_style_version', style['version']),
                       ('writing_style_manifest_sha256', style.get('manifest_sha256'))):
        if style['kind'] == 'distilled':
            brief[key] = record[key] = value
        else:
            brief.pop(key, None)
            record.pop(key, None)
    w.save(run / 'intake.json', record)
    w.save(run / 'brief.json', brief)
    return {'status': 'ready_to_write', 'topic': topic, 'next': 'verify evidence, plan outline and write'}


def ready(run):
    run = Path(run)
    brief, record = w.read(run / 'brief.json', {}), w.read(run / 'intake.json', {})
    keys = ('topic', 'font', 'custom_font', 'writing_style', 'writing_style_version',
            'writing_style_manifest_sha256', 'length_preset', 'min_chars', 'max_chars')
    if record.get('status') != 'ready_to_write' or any(record.get(k) != brief.get(k) for k in keys):
        raise ValueError('Pre-writing answers missing or changed; record the current user answers first')
    from style_library import resolve
    style = resolve(brief['workspace'], brief['writing_style'], brief.get('writing_style_version'),
                    brief.get('writing_style_manifest_sha256'))
    if style['kind'] == 'distilled' and (not brief.get('writing_style_version') or not brief.get('writing_style_manifest_sha256')):
        raise ValueError('Distilled writing style must preserve the user-selected version and manifest hash')
    return record


def select_layout(run, theme, decision, no_pending_edits=False):
    run = Path(run).resolve()
    if not decision.strip():
        raise ValueError('Need the actual human layout decision')
    manifest = w.read(run / 'layout-variants.json', {})
    brief = w.read(run / 'brief.json', {})
    if manifest.get('article_sha256') != w.file_hash(run / 'article.md') or manifest.get('body_sha256') != w.file_hash(run / 'body.md'):
        raise ValueError('Preview set is stale; rebuild the complete comparison set before choosing')
    if manifest.get('font') != w.font_choice(brief.get('font', 'theme'), brief.get('custom_font', '')):
        raise ValueError('Preview font differs from the current user selection')
    if any(w.file_hash(w.within(run, path)) != sha for path, sha in manifest.get('asset_hashes', {}).items()):
        raise ValueError('Preview image changed; rebuild the complete comparison set')
    variants = manifest.get('variants', [])
    available = set(w.read(w.ROOT / 'assets/preferences.json')['themes'])
    expected = set(manifest.get('theme_ids', available))
    legacy = {'green-white-clean', 'ink-blue-editorial', 'graphite-dossier', 'sand-gold-journal', 'mist-purple-story'}
    if manifest.get('schema_version') == 1 and 'theme_ids' not in manifest and {x['theme'] for x in variants} == legacy:
        expected = legacy
    if not expected or not expected <= available or len(variants) != len(expected) or {x['theme'] for x in variants} != expected:
        raise ValueError('Need the complete actual layout preview set')
    if manifest.get('schema_version', 1) >= 2 and expected != available:
        raise ValueError('Theme catalog changed; rebuild the comparison set')
    for variant in variants:
        if w.file_hash(w.within(run, variant['preview'])) != variant.get('preview_sha256'):
            raise ValueError('Actual preview changed; rebuild the comparison set')
    selected = next((x for x in variants if x['theme'] == theme), None)
    if not selected:
        raise ValueError('Unknown layout selection')
    record = {'schema_version': 1, 'theme': theme, 'user_decision': decision, 'decision_origin': 'user',
              'no_pending_edits': bool(no_pending_edits), 'article_sha256': manifest['article_sha256'],
              'body_sha256': manifest['body_sha256'], 'variants_sha256': w.file_hash(run / 'layout-variants.json'),
              'selected_preview_sha256': selected['preview_sha256'], 'font': manifest['font'], 'selected_at': w.now()}
    w.configure(run, theme=theme)
    w.save(run / 'layout-selection.json', record)
    return {**record, 'next': 'layout/export/review/audit, then draft' if no_pending_edits else 'resolve requested revisions before draft'}


def selection_current(run):
    run = Path(run)
    selection = w.read(run / 'layout-selection.json', {})
    if selection.get('selection_backend') == 'studio-saved-final':
        from studio_state import selection_current as studio_selection
        return studio_selection(run)
    brief = w.read(run / 'brief.json', {})
    if (selection.get('decision_origin') != 'user' or not selection.get('user_decision') or
            not selection.get('no_pending_edits') or selection.get('theme') != brief.get('theme') or
            selection.get('article_sha256') != w.file_hash(run / 'article.md') or
            selection.get('body_sha256') != w.file_hash(run / 'body.md') or
            selection.get('variants_sha256') != w.file_hash(run / 'layout-variants.json') or
            selection.get('font') != w.font_choice(brief.get('font', 'theme'), brief.get('custom_font', ''))):
        raise ValueError('Layout approval is missing, stale or has pending revisions')
    manifest = w.read(run / 'layout-variants.json', {})
    variant = next((x for x in manifest.get('variants', []) if x['theme'] == selection['theme']), {})
    if any(w.file_hash(w.within(run, path)) != sha for path, sha in manifest.get('asset_hashes', {}).items()):
        raise ValueError('Preview image changed after user approval')
    if not variant or w.file_hash(w.within(run, variant['preview'])) != selection.get('selected_preview_sha256'):
        raise ValueError('Selected preview changed after user approval')
    return selection


def account_path(workspace):
    return Path(workspace).resolve() / '.wechat-ai' / 'account.json'


def bind_account(workspace, name, account_id, authorization, observation):
    if (not name.strip() or not re.fullmatch(r'gh_[A-Za-z0-9]{4,64}', account_id) or
            not authorization.strip() or not observation.strip()):
        raise ValueError('Need observed account name, public original ID (gh_...), user standing instruction and verification note')
    record = {'schema_version': 1, 'account_name': name.strip(), 'account_id': account_id,
              'backend': 'browser', 'auto_push_after_selection': True, 'published_by': 'user',
              'standing_authorization': authorization.strip(), 'verification_note': observation.strip(), 'verified_at': w.now()}
    w.save(account_path(workspace), record)
    return record


def draft_authorization(run, observed_name, observed_id):
    run = Path(run)
    brief = w.read(run / 'brief.json')
    ready(run)
    selection_current(run)
    account = w.read(account_path(brief['workspace']), {})
    if (account.get('account_name') != observed_name or account.get('account_id') != observed_id or
            not account.get('auto_push_after_selection') or not account.get('standing_authorization')):
        raise ValueError('Connected account differs or standing draft instruction is absent; verify the target account')
    return account['standing_authorization']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    q = commands.add_parser('questions'); q.add_argument('--known', type=Path); q.add_argument('--workspace', type=Path, default=Path.cwd())
    a = commands.add_parser('apply'); a.add_argument('--run', required=True, type=Path); a.add_argument('--answers', required=True, type=Path)
    c = commands.add_parser('candidates'); c.add_argument('--run', required=True, type=Path); c.add_argument('--file', required=True, type=Path)
    s = commands.add_parser('select-layout'); s.add_argument('--run', required=True, type=Path); s.add_argument('--theme', required=True); s.add_argument('--decision', required=True); s.add_argument('--no-pending-edits', action='store_true')
    b = commands.add_parser('bind-account'); b.add_argument('--workspace', required=True); b.add_argument('--name', required=True); b.add_argument('--account-id', required=True); b.add_argument('--authorization', required=True); b.add_argument('--observation', required=True)
    show = commands.add_parser('account'); show.add_argument('--workspace', required=True)
    args = parser.parse_args()
    try:
        if args.command == 'questions': result = questions(w.read(args.known, {}) if args.known else {}, args.workspace)
        elif args.command == 'apply': result = apply(args.run, w.read(args.answers))
        elif args.command == 'candidates':
            result = validate_candidates(w.read(args.file)); w.save(args.run / 'topic-candidates.json', result)
        elif args.command == 'select-layout': result = select_layout(args.run, args.theme, args.decision, args.no_pending_edits)
        elif args.command == 'bind-account': result = bind_account(args.workspace, args.name, args.account_id, args.authorization, args.observation)
        else: result = w.read(account_path(args.workspace), {'status': 'not_connected'})
        print(json.dumps(result, ensure_ascii=False, indent=2)); return 0
    except (ValueError, KeyError, OSError, TypeError, json.JSONDecodeError) as exc:
        print(json.dumps({'error': str(exc)}, ensure_ascii=False)); return 1


if __name__ == '__main__':
    raise SystemExit(main())
