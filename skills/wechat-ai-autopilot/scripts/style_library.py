#!/usr/bin/env python3
"""Persist host-distilled writing styles and bind five-document contexts to drafts.

Scripts check records and hashes. The host reads, distils and reviews; no script
claims to understand an article or to measure resemblance objectively.
"""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile

import learning

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / 'references/vendor/writing-dna-skill'
DOCS = {
    'zh': ('语言DNA.md', '文章结构模板.md', '写作视角与认知框架.md', '视觉风格指南.md', 'Writing-DNA.md'),
    'en': ('language-dna.md', 'structure-patterns.md', 'cognitive-framework.md', 'visual-style-guide.md', 'Writing-DNA.md'),
}
META_FIELDS = ('article_type', 'topic_tags', 'hook_type', 'structure_pattern', 'source_types', 'word_count')
DIMENSIONS = {'language', 'structure', 'topics', 'sources', 'cognition', 'media'}
SCORES = ('language', 'structure', 'viewpoint', 'material', 'readability')


def read(path, default=None):
    return learning.read(path, default)


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    os.replace(temp, path)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inside(root, value):
    root = Path(root).resolve()
    path = (root / value).resolve()
    if not path.is_relative_to(root) or path == root:
        raise ValueError('style artifact must stay inside its directory')
    return path


def library(workspace):
    workspace = Path(workspace).resolve()
    path = workspace / '.wechat-ai/writing-styles'
    if path.resolve().is_relative_to(ROOT):
        raise ValueError('personal styles must stay outside the distributable skill')
    return path


def builtins():
    return {key: {**item, 'id': key, 'kind': 'builtin', 'version': 'builtin'}
            for key, item in read(ROOT / 'assets/preferences.json')['writing_styles'].items()}


def validate_id(ident):
    if not isinstance(ident, str) or not re.fullmatch(r'[a-z][a-z0-9-]{1,63}', ident) or ident in builtins():
        raise ValueError('use a new lowercase hyphenated style id; built-in styles cannot be overwritten')


def seed(study, ident, name, language='zh'):
    study = Path(study).resolve()
    config = read(study / 'study.json', {})
    learning.audit(study)
    if config.get('mode', 'content') != 'writing-style':
        raise ValueError('content study does not add a style; initialize an explicit writing-style study')
    validate_id(ident)
    if not isinstance(name, str) or not name.strip() or len(name) > 80 or language not in DOCS:
        raise ValueError('need a style display name and zh/en artifact language')
    if len(config['targets']) > 1 and not config.get('blend'):
        raise ValueError('distil each author separately, or record the user request for a blended style')
    if (study / 'style.json').exists():
        raise ValueError('style study exists; resume instead of overwriting')
    for filename in DOCS[language]:
        target = study / 'dna' / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ENGINE / 'templates/author-corpus' / language / filename, target)
    save(study / 'style.json', {'schema_version': 1, 'id': ident, 'name': name.strip(),
                              'language': language, 'created_at': learning.now(),
                              'visual_scope': 'image-purpose-only', 'minimum_full_articles': 20,
                              'engine': read(ENGINE / 'origin.json')['revision']})
    save(study / 'article-metadata.json', [])
    return {'status': 'awaiting_host_distillation', 'style_id': ident, 'dna_directory': str(study / 'dna'),
            'next': 'read complete articles, annotate metadata, fill five documents and review an original sample'}


def language_stats(study):
    study = Path(study).resolve()
    report = learning.audit(study)
    valid = {x['id'] for x in report['articles'] if x['valid_read_complete']}
    workspace = Path(read(study / 'study.json')['workspace'])
    results, han_pairs, english = [], Counter(), Counter()
    for item in read(study / 'articles.json', []):
        if item.get('id') not in valid:
            continue
        text = learning.body_path(study, workspace, item['full_text_file']).read_text(encoding='utf-8-sig')
        text = re.sub(r'```.*?```|!\[[^\]]*\]\([^)]*\)', '', text, flags=re.S)
        paragraphs = [p.strip() for p in re.split(r'\n\s*\n', text) if p.strip()]
        sentences = [re.sub(r'\s+', '', s) for s in re.split(r'[。！？!?]+|(?<=[A-Za-z])\.(?:\s+|$)', text) if s.strip()]
        lengths = [len(s) for s in sentences]
        han_count = len(re.findall(r'[\u4e00-\u9fff]', text))
        for token in re.findall(r'[\u4e00-\u9fff]+', text):
            han_pairs.update(token[n:n+2] for n in range(len(token)-1))
        english.update(s.lower() for s in re.findall(r'[A-Za-z][A-Za-z0-9_-]*', text))
        results.append({'id': item['id'], 'cjk_chars': han_count, 'sentence_count': len(lengths),
                        'average_sentence_chars': round(sum(lengths)/max(1, len(lengths)), 2),
                        'short_sentence_share': round(sum(n <= 15 for n in lengths)/max(1, len(lengths)), 3),
                        'long_sentence_share': round(sum(n >= 50 for n in lengths)/max(1, len(lengths)), 3),
                        'paragraph_count': len(paragraphs), 'dash_count': text.count('——'),
                        'parenthesis_count': text.count('（')+text.count('('),
                        'english_tokens': len(re.findall(r'[A-Za-z][A-Za-z0-9_-]*', text))})
    value = {'scope': 'descriptive-language-statistics', 'articles': results,
             'frequent_han_bigrams': han_pairs.most_common(40), 'frequent_english_tokens': english.most_common(40),
             'limitation': '句子按标点近似切分；汉字双字组合不是中文分词或理解结果。不能把这些计数当成作者偏好或文风质量结论。'}
    save(study / 'language-stats.json', value)
    return value


def input_hashes(study):
    study = Path(study).resolve()
    profile = read(study / 'style.json')
    names = ['study.json', 'style.json', 'articles.json', 'article-metadata.json', 'language-stats.json', 'style-sample.md']
    names += ['dna/' + name for name in DOCS[profile['language']]]
    result = {name: sha(study / name) for name in names}
    config = read(study / 'study.json')
    for record in read(study / 'articles.json', []):
        if record.get('status') == 'read_complete':
            result['corpus:' + record['id']] = sha(learning.body_path(study, Path(config['workspace']), record['full_text_file']))
    return result


def check(study):
    study = Path(study).resolve()
    reading = learning.audit(study)
    config, profile = read(study / 'study.json'), read(study / 'style.json', {})
    issues = []
    if config.get('mode') != 'writing-style' or not profile:
        raise ValueError('explicit writing-style study and style.json are required')
    validate_id(profile['id'])
    if not reading['reading_complete'] or reading['errors']:
        issues.append('complete the requested unique full-text reading and correct its ledger')
    if reading['valid_read_complete'] < 20:
        issues.append('at least 20 unique complete articles are required for an active style; keep smaller studies provisional')
    records = {item['id']: item for item in read(study / 'articles.json', []) if item.get('status') == 'read_complete'}
    metadata = read(study / 'article-metadata.json', [])
    seen, annotated = set(), []
    if not isinstance(metadata, list):
        issues.append('article-metadata.json must be an array')
        metadata = []
    for item in metadata:
        ident = item.get('id') if isinstance(item, dict) else None
        if ident in seen or ident not in records:
            issues.append('duplicate or unknown metadata article id')
            continue
        seen.add(ident)
        origin = records[ident]
        if any(item.get(key) != origin.get(key) for key in ('title', 'author')):
            issues.append('metadata title/author must match the actually-read article')
            continue
        if item.get('date') != origin.get('published_at') or item.get('date_kind') != origin.get('date_kind'):
            issues.append('metadata date must preserve the real date or recorded uncertainty')
            continue
        if (all(item.get(key) for key in META_FIELDS) and isinstance(item['topic_tags'], list)
                and isinstance(item['source_types'], list) and type(item['word_count']) is int and item['word_count'] > 0):
            annotated.append(item)
    coverage = len(annotated)/max(1, len(records))
    if coverage < .8:
        issues.append('at least 80% of read articles need complete genre/topic/hook/structure/material metadata')
    for filename in DOCS.get(profile.get('language'), ()):
        path = study / 'dna' / filename
        text = path.read_text(encoding='utf-8-sig') if path.is_file() else ''
        if len(text.strip()) < 120 or re.search(r'待填写|\[待补\]|\[占位\]|\bTODO\b', text):
            issues.append('unfinished DNA document: ' + filename)
        if filename == 'Writing-DNA.md' and len(text) > 4000:
            issues.append('keep Writing-DNA.md within 4000 characters; detailed evidence belongs in the other documents')
    if profile.get('language') not in DOCS or profile.get('visual_scope') != 'image-purpose-only':
        issues.append('unsupported language or visual scope; preserve the existing layouts and fonts')
    sample = study / 'style-sample.md'
    if not sample.is_file() or len(sample.read_text(encoding='utf-8-sig').strip()) < 300:
        issues.append('write an original sample on a new topic before registration')
    review = read(study / 'style-review.json', {})
    if not review.get('reviewed_by') or not review.get('originality_note') or not review.get('scope_notes'):
        issues.append('record the host editorial review, originality and applicability limits')
    scores = review.get('scores', {})
    if any(type(scores.get(key)) not in (int, float) or not 7 <= scores[key] <= 10 for key in SCORES):
        issues.append('all five editorial sample scores must reach 7/10; these are host judgments, not benchmark results')
    observations = review.get('observations', [])
    if not isinstance(observations, list):
        observations = []
    dimensions = set()
    for finding in observations:
        if not isinstance(finding, dict):
            issues.append('style observations must be objects')
            continue
        evidence = finding.get('evidence_ids', [])
        if (finding.get('dimension') not in DIMENSIONS or not finding.get('rule') or not finding.get('applicability')
                or not finding.get('exceptions') or not isinstance(evidence, list)
                or len(set(evidence)) < 2 or not set(evidence) <= set(records)):
            issues.append('each style rule needs a dimension, scope, limits and at least two read article ids')
        else:
            dimensions.add(finding['dimension'])
    if dimensions != DIMENSIONS or sum(x.get('dimension') == 'cognition' for x in observations if isinstance(x, dict)) < 3:
        issues.append('review all six content layers, including at least three specific cognitive principles')
    genres = {item['article_type'] for item in annotated}
    if set(review.get('genre_scope', [])) != genres:
        issues.append('genre scope must match the actual annotated corpus; do not invent three genres for a narrow corpus')
    try:
        if review.get('input_hashes') != input_hashes(study):
            issues.append('review is missing or stale; bind it to the current corpus, five documents and sample')
    except (OSError, KeyError):
        issues.append('review inputs are incomplete')
    result = {'scope': 'style-registration-consistency', 'passed': not issues,
              'style_id': profile['id'], 'full_articles': reading['valid_read_complete'],
              'metadata_coverage': round(coverage, 3), 'genres': sorted(genres), 'errors': issues,
              'limitation': '脚本验证记录与版本；全文理解、原创性、规则有效性和文风相似度由宿主实际审阅，不保证传播效果。'}
    save(study / 'style-check.json', result)
    return result


def checked_version(workspace, ident, version, expected_hash=None):
    validate_id(ident)
    if not re.fullmatch(r'[a-f0-9]{20}', str(version)):
        raise ValueError('invalid style version')
    root = inside(library(workspace), ident + '/versions/' + version)
    manifest_path = root / 'manifest.json'
    if expected_hash and sha(manifest_path) != expected_hash:
        raise ValueError('style manifest changed; restore or relearn the profile')
    manifest = read(manifest_path)
    if (not manifest or manifest.get('id') != ident or manifest.get('version') != version
            or manifest.get('language') not in DOCS or not manifest.get('files')):
        raise ValueError('style version is missing or invalid')
    for filename, digest in manifest['files'].items():
        if sha(inside(root, filename)) != digest:
            raise ValueError('style file changed: ' + filename)
    return root, manifest


def catalog(workspace):
    available, unavailable = builtins(), []
    index = read(library(workspace) / 'index.json', {'styles': {}})
    for ident, item in index.get('styles', {}).items():
        if not item.get('active', True):
            continue
        try:
            root, manifest = checked_version(workspace, ident, item['version'], item['manifest_sha256'])
            available[ident] = {'id': ident, 'name': item['name'], 'kind': 'distilled', 'available': True,
                                'version': item['version'], 'path': str(root), 'manifest_sha256': item['manifest_sha256'],
                                'genre_scope': manifest['genre_scope'], 'full_articles': len(manifest['corpus'])}
        except (ValueError, OSError, KeyError, TypeError) as exc:
            unavailable.append({'id': ident, 'name': item.get('name', ident), 'reason': str(exc)})
    return {'writing_styles': available, 'unavailable': unavailable}


def resolve(workspace, ident, version=None, manifest_hash=None):
    if ident in builtins():
        return builtins()[ident]
    if version:
        root, manifest = checked_version(workspace, ident, version, manifest_hash)
        return {'id': ident, 'name': manifest['name'], 'kind': 'distilled', 'version': version,
                'manifest_sha256': sha(root / 'manifest.json'), 'path': str(root)}
    item = catalog(workspace)['writing_styles'].get(ident)
    if not item:
        raise ValueError('unknown or unavailable writing style; list the current workspace style library')
    return item


def register(study):
    study = Path(study).resolve()
    report = check(study)
    if not report['passed']:
        raise ValueError('; '.join(report['errors']))
    config, profile = read(study / 'study.json'), read(study / 'style.json')
    if config.get('approval_policy', 'review_first') != 'explicit_delegation':
        approval = read(study / 'style-approval.json', {})
        if (approval.get('origin') != 'user' or not str(approval.get('instruction', '')).strip()
                or approval.get('input_hashes') != input_hashes(study)):
            raise ValueError('review-first study needs the actual current user approval before registration')
    workspace = Path(config['workspace'])
    version = hashlib.sha256(json.dumps({'inputs': input_hashes(study), 'review': sha(study/'style-review.json')},
                                       sort_keys=True).encode()).hexdigest()[:20]
    dest = inside(library(workspace), profile['id'] + '/versions/' + version)
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        # Publish only a complete version; interrupted copying cannot create a
        # half-registered option. Temporary cleanup stays inside the style root.
        with tempfile.TemporaryDirectory(prefix='.pending-', dir=dest.parent) as temporary:
            staging = Path(temporary).resolve()
            if not staging.is_relative_to(library(workspace).resolve()):
                raise ValueError('invalid style staging directory')
            for name in DOCS[profile['language']]:
                shutil.copyfile(study / 'dna' / name, staging / name)
            for name in ('article-metadata.json', 'style-review.json', 'style-sample.md', 'style-check.json'):
                shutil.copyfile(study / name, staging / name)
            metadata = {x['id']: x for x in read(study / 'article-metadata.json')}
            corpus = []
            for number, item in enumerate(read(study / 'articles.json')):
                if item.get('status') != 'read_complete':
                    continue
                target = staging / 'corpus' / f'{number:04d}.md'
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(learning.body_path(study, workspace, item['full_text_file']), target)
                corpus.append({**item, 'full_text_file': target.relative_to(staging).as_posix(),
                               'metadata': metadata.get(item['id'], {})})
            files = {p.relative_to(staging).as_posix(): sha(p) for p in staging.rglob('*') if p.is_file()}
            save(staging / 'manifest.json', {**profile, 'version': version, 'corpus': corpus, 'files': files,
                                           'genre_scope': report['genres'], 'registered_at': learning.now()})
            os.rename(staging, dest)
    checked_version(workspace, profile['id'], version)
    index_path = library(workspace) / 'index.json'
    index = read(index_path, {'schema_version': 1, 'styles': {}})
    if any(x.get('name') == profile['name'] and k != profile['id'] for k, x in {**builtins(), **index['styles']}.items()):
        raise ValueError('style display name is already used; choose a distinct name')
    index['styles'][profile['id']] = {'name': profile['name'], 'version': version,
                                     'manifest_sha256': sha(dest / 'manifest.json'), 'active': True}
    save(index_path, index)
    receipt = {'status': 'registered', 'id': profile['id'], 'name': profile['name'], 'version': version,
               'path': str(dest), 'next': 'this style is now an option in intake.py questions --workspace WORKSPACE'}
    save(study / 'style-registration.json', receipt)
    return receipt


def prepare(run, article_type=None, tags=None):
    run = Path(run).resolve()
    from intake import ready
    ready(run)
    brief = read(run / 'brief.json')
    ident = brief.get('writing_style', 'khazix')
    selected = resolve(brief['workspace'], ident, brief.get('writing_style_version'), brief.get('writing_style_manifest_sha256'))
    if selected['kind'] == 'builtin':
        return {'status': 'builtin', 'style_id': ident, 'next': 'read khazix-writer or the bundled editorial fallback'}
    root, manifest = checked_version(brief['workspace'], ident, selected['version'], selected['manifest_sha256'])
    intent = read(run / 'reader-intent.json', {})
    genre = article_type or intent.get('article_type')
    tags = tags if tags is not None else intent.get('topic_tags', [])
    if not genre or not isinstance(tags, list):
        raise ValueError('prepare needs the actual article genre and topic tags')
    def rank(record):
        metadata = record.get('metadata', {})
        return (metadata.get('article_type') == genre,
                len(set(metadata.get('topic_tags', [])) & set(tags)), str(record.get('published_at') or ''), record['id'])
    closest = sorted(manifest['corpus'], key=rank, reverse=True)[:5]
    out = run / 'style-context'
    paths, sample_records = [], []
    for name in DOCS[manifest['language']]:
        target = out / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / name, target)
        paths.append(target.relative_to(run).as_posix())
    for number, record in enumerate(closest):
        target = out / f'sample-{number+1}.md'
        shutil.copyfile(inside(root, record['full_text_file']), target)
        rel = target.relative_to(run).as_posix()
        paths.append(rel)
        sample_records.append({'id': record['id'], 'title': record['title'], 'path': rel, 'metadata': record['metadata']})
    snapshot = {'schema_version': 1, 'style_id': ident, 'name': selected['name'], 'version': selected['version'],
                'manifest_sha256': selected['manifest_sha256'], 'article_type': genre, 'topic_tags': tags,
                'documents': paths[:5], 'samples': sample_records,
                'files': {path: sha(inside(run, path)) for path in paths}, 'prepared_at': learning.now(),
                'limitation': '文件准备不等于已读；宿主须完整阅读五份文档及五篇样本后记录校准。'}
    save(run / 'style-context.json', snapshot)
    return {**snapshot, 'status': 'awaiting_host_read', 'next': 'read all files, then record style-calibration.json before writing'}


def context_ready(run, require_body=False):
    run = Path(run).resolve()
    brief = read(run / 'brief.json', {})
    if brief.get('writing_style', 'khazix') in builtins():
        return {'status': 'builtin'}
    context = read(run / 'style-context.json', {})
    selected = resolve(brief['workspace'], brief['writing_style'], brief.get('writing_style_version'),
                       brief.get('writing_style_manifest_sha256'))
    if (context.get('style_id') != selected['id'] or context.get('version') != selected['version']
            or context.get('manifest_sha256') != selected['manifest_sha256'] or len(context.get('documents', [])) != 5
            or len(context.get('samples', [])) != 5):
        raise ValueError('writing style context missing or stale; prepare the selected version')
    expected = set(context['documents']) | {x['path'] for x in context['samples']}
    if set(context.get('files', {})) != expected or any(sha(inside(run, path)) != digest for path, digest in context['files'].items()):
        raise ValueError('style context files changed; reread and recalibrate')
    calibration = read(run / 'style-calibration.json', {})
    if (calibration.get('context_sha256') != sha(run / 'style-context.json') or calibration.get('read_complete') is not True
            or not calibration.get('reviewed_by') or not calibration.get('common_features')
            or not calibration.get('genre_adaptation') or not calibration.get('avoid_copying')):
        raise ValueError('host must read all five documents and five samples and record concrete style calibration')
    if require_body:
        review = read(run / 'style-writing-review.json', {})
        if (review.get('body_sha256') != sha(run / 'body.md') or review.get('context_sha256') != sha(run / 'style-context.json')
                or not review.get('reviewed_by') or not review.get('style_application')
                or not review.get('originality_check') or not review.get('cleanup_check')):
            raise ValueError('review style use and originality against the current body and selected context')
    return {'status': 'style_ready', 'id': selected['id'], 'version': selected['version']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    s = commands.add_parser('seed'); s.add_argument('--study', required=True, type=Path); s.add_argument('--id', required=True); s.add_argument('--name', required=True); s.add_argument('--language', choices=DOCS, default='zh')
    for name in ('stats', 'check', 'inputs', 'register'):
        p = commands.add_parser(name); p.add_argument('--study', required=True, type=Path)
    p = commands.add_parser('list'); p.add_argument('--workspace', required=True, type=Path)
    p = commands.add_parser('prepare'); p.add_argument('--run', required=True, type=Path); p.add_argument('--article-type'); p.add_argument('--tags', nargs='*')
    p = commands.add_parser('ready'); p.add_argument('--run', required=True, type=Path); p.add_argument('--body', action='store_true')
    args = parser.parse_args()
    try:
        if args.command == 'seed': result = seed(args.study, args.id, args.name, args.language)
        elif args.command == 'stats': result = language_stats(args.study)
        elif args.command == 'check': result = check(args.study)
        elif args.command == 'inputs': result = input_hashes(args.study)
        elif args.command == 'register': result = register(args.study)
        elif args.command == 'list': result = catalog(args.workspace)
        elif args.command == 'prepare': result = prepare(args.run, args.article_type, args.tags)
        else: result = context_ready(args.run, args.body)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2 if result.get('passed') is False else 0
    except (ValueError, OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(json.dumps({'error': str(exc)}, ensure_ascii=False)); return 1


if __name__ == '__main__':
    raise SystemExit(main())
