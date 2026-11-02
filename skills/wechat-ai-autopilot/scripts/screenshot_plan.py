"""Scenario-aware capture decisions and explicit missing-image handoff."""
import argparse
import json
from pathlib import Path
import workflow as w


def choose(kind, preference='contextual', chinese=False):
    if kind not in ('tutorial', 'x-post', 'chart', 'video-result', 'announcement'):
        raise ValueError('unknown screenshot scenario')
    extent = 'complete-post' if kind == 'x-post' else 'complete-chart-with-conditions' if kind == 'chart' else 'screen-with-operation-frame' if kind == 'tutorial' or preference == 'screen-frame' else 'result-with-context'
    return {'kind': kind, 'extent': extent, 'chinese_translation': 'platform-native-required' if chinese and kind == 'x-post' else 'nearby-chinese-explanation',
            'attempt_limit': 2, 'preserve_original_pixels': True,
            'if_unavailable': 'seek_accessible_original_or_report_specific_missing_image'}


def check(run, records):
    issues = []
    for record in records:
        ident = record.get('id', 'unknown')
        if record.get('status') != 'captured':
            if not all(record.get(k) for k in ('need', 'reason', 'tried', 'help_action')):
                issues.append(ident + ': missing image needs a precise handoff')
            else:
                issues.append(ident + ': capture pending; do not call package complete')
            continue
        original = w.within(run, record.get('original_file', ''))
        if not original.is_file() or w.file_hash(original) != record.get('original_sha256'):
            issues.append(ident + ': original pixels missing or changed')
        if record.get('kind') == 'x-post':
            required = ('author', 'all_body', 'media', 'absolute_date', 'metrics')
            if not all(record.get('visible', {}).get(k) is True for k in required):
                issues.append(ident + ': full post must preserve author, complete body, attachments, date and metrics')
            if record.get('chinese_required') and record.get('translation') not in ('platform-native', 'original-chinese'):
                issues.append(ident + ': English interface or translated card is not native Chinese post capture')
            if record.get('capture_method') == 'scroll-stitch':
                assembly = w.read(w.within(run, record.get('assembly_file', '')), {})
                fragments = assembly.get('fragments', [])
                if len(fragments) < 2 or not assembly.get('seams_reviewed') or not assembly.get('media_kept_in_single_fragment'):
                    issues.append(ident + ': long-post stitching needs seam and moving-media review')
                for item in fragments:
                    if not item.get('sha256') or w.file_hash(w.within(run, item.get('path', ''))) != item.get('sha256'):
                        issues.append(ident + ': stitch fragment missing or changed')
    return {'passed': not issues, 'errors': issues,
            'limits': 'Checks recorded completeness and pixel provenance; actual viewing remains required.'}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=('choose', 'check'))
    p.add_argument('--kind')
    p.add_argument('--preference', default='contextual')
    p.add_argument('--chinese', action='store_true')
    p.add_argument('--run', type=Path)
    p.add_argument('--records', type=Path)
    a = p.parse_args()
    result = choose(a.kind, a.preference, a.chinese) if a.command == 'choose' else check(a.run, w.read(a.records, []))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(2 if result.get('passed') is False else 0)
