"""Bind topic-specific editorial acceptance to actual current passages."""
import argparse
import json
from pathlib import Path
import workflow as w

RUBRICS = {
    'tutorial': ('starting_point', 'steps_and_inputs', 'success_signal', 'errors_and_recovery'),
    'comparison': ('same_task_or_explicit_difference', 'visible_outputs', 'cost_and_conditions', 'choice_and_limits'),
    'news': ('what_changed', 'access_and_use', 'benefit_and_cost', 'analysis_and_uncertainty'),
    'analysis': ('clear_question', 'concrete_case', 'alternative_explanation', 'changed_reader_judgment'),
    'narrative': ('specific_scene', 'human_stakes', 'different_perspectives', 'meaning_without_fake_experience')}


def template(run, kind):
    return {'schema_version': 1, 'article_type': kind, 'body_sha256': w.file_hash(Path(run) / 'body.md'),
            'reader': '', 'reader_outcome': '', 'checks': {key: {'status': 'pending', 'body_quote': '', 'reason': ''} for key in RUBRICS[kind]},
            'review_method': 'editorial_readthrough', 'reader_tested': False}


def errors(run):
    run = Path(run)
    review = w.read(run / 'reader-value.json', {})
    body = (run / 'body.md').read_text(encoding='utf8') if (run / 'body.md').is_file() else ''
    issues = []
    if not body or review.get('body_sha256') != w.file_hash(run / 'body.md'):
        issues.append('Reader-value review missing or stale against current body')
    kind = review.get('article_type')
    if kind not in RUBRICS:
        return issues + ['Choose the actual article type; do not apply one checklist to every topic']
    if len(review.get('reader', '').strip()) < 4 or len(review.get('reader_outcome', '').strip()) < 12:
        issues.append('Specify audience and concrete reader outcome')
    for key in RUBRICS[kind]:
        check = review.get('checks', {}).get(key, {})
        if check.get('status') != 'pass' or len(check.get('reason', '').strip()) < 12 or len(check.get('body_quote', '').strip()) < 8 or check.get('body_quote', '') not in body:
            issues.append('Current passage and editorial reasoning required: ' + key)
    if review.get('reader_tested') is True:
        evidence = review.get('reader_test_evidence', '')
        if not evidence or not w.within(run, evidence).is_file():
            issues.append('Do not claim reader testing without actual reader feedback')
    return issues


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=('init', 'check'))
    p.add_argument('--run', type=Path, required=True)
    p.add_argument('--type', choices=tuple(RUBRICS))
    a = p.parse_args()
    if a.command == 'init':
        if not a.type:
            p.error('--type required')
        if (a.run / 'reader-value.json').exists():
            p.error('Existing review retained; update it against actual changes')
        w.save(a.run / 'reader-value.json', template(a.run, a.type))
        result = {'status': 'pending_editorial_review'}
    else:
        issues = errors(a.run)
        result = {'passed': not issues, 'errors': issues, 'scope': 'current-passages-and-review-records',
                  'limits': 'Does not algorithmically prove quality, truth or reader satisfaction.'}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(2 if result.get('passed') is False else 0)
