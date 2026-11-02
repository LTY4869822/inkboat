"""Bind host-performed Humanizer editing to the selected voice and current prose.

This helper does not call a model or infer authorship. It protects executable and
linked material, and validates the actual agent's recorded editorial review.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

POLICY = 'humanizer-style-preserving-v1'
ROOT = Path(__file__).resolve().parents[1]
CHECKS = ('facts_preserved', 'voice_preserved', 'reader_fit', 'naturalness')

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def load(path, default=None):
    return json.loads(Path(path).read_text(encoding='utf8')) if Path(path).exists() else default

def save(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf8')

def prose_sha(text):
    # Image registration follows prose review. New standalone image lines do
    # not change its prose; captions, existing images and all links stay checked.
    text=re.sub(r'(?m)^!\[[^\]]*\]\([^\n]*?\)\s*$', '', text)
    text=re.sub(r'\n{3,}', '\n\n', text).strip()
    return hashlib.sha256(text.encode('utf8')).hexdigest()

def protected(text):
    fences = re.findall(r'(?ms)^(`{3,}|~{3,})[^\n]*\n.*?^\1[^\n]*(?:\n|$)', text)
    # Include complete fence bytes, not merely the fence delimiter.
    blocks = [m.group(0).replace('\r\n','\n') for m in re.finditer(r'(?ms)^(`{3,}|~{3,})[^\n]*\n.*?^\1[^\n]*(?:\n|$)', text)]
    prose = re.sub(r'(?ms)^(`{3,}|~{3,})[^\n]*\n.*?^\1[^\n]*(?:\n|$)', '', text)
    return {'code_blocks': blocks,
            'inline_code': re.findall(r'(`+)([^`\n]*?)\1', prose),
            'image_tokens': re.findall(r'!\[[^\]]*\]\([^\n]*?\)', prose),
            'link_targets': re.findall(r'\]\(([^\n]*?)\)', prose),
            'plain_urls': re.findall(r'https?://[^\s\u4e00-\u9fff<>）)\]`，。；]+', prose)}

def prepare(run):
    run = Path(run)
    body = run/'body.md'
    if not body.is_file(): raise ValueError('Write the style draft before Humanizer review')
    backup = run/'writing-draft.md'
    if backup.exists():
        context = load(run/'humanizer-context.json', {})
        if context.get('source_draft_sha256') != sha(backup):
            raise ValueError('Original writing draft changed; keep the original review trace')
        return context
    backup.write_bytes(body.read_bytes())
    brief = load(run/'brief.json', {})
    vendor = ROOT/'references/vendor/humanizer'
    provenance = load(vendor/'provenance.json', {})
    if sha(vendor/'SKILL.md') != provenance.get('files',{}).get('SKILL.md'):
        raise ValueError('Vendored Humanizer differs from the pinned source')
    context = {'policy': POLICY, 'source_draft_sha256': sha(backup),
               'writing_style': brief.get('writing_style','khazix'),
               'style_context_sha256': sha(run/'style-context.json') if (run/'style-context.json').is_file() else None,
               'upstream_commit': provenance.get('commit'),
               'upstream_skill_sha256': sha(vendor/'SKILL.md'),
               'mode': 'embedded', 'scope': 'Editorial revision, not AI authorship detection'}
    save(run/'humanizer-context.json', context)
    return context

def errors(run, required=None, include_second=True):
    run=Path(run); brief=load(run/'brief.json',{})
    if required is None: required=brief.get('humanizer_policy')==POLICY
    if not required: return []
    result=[]; context=load(run/'humanizer-context.json',{})
    review=load(run/'humanizer-review.json',{})
    source=run/'writing-draft.md'; body=run/'body.md'
    # The second editor receives the actual first editor's saved output. Its
    # changes must not invalidate or silently rewrite the first review trace.
    if brief.get('tone_policy') == 'dual-tone-style-preserving-v1' and (run/'humanizer-output.md').is_file():
        body=run/'humanizer-output.md'
    if not source.is_file() or not body.is_file(): return ['Humanizer original draft or current body missing']
    if context.get('policy')!=POLICY or context.get('source_draft_sha256')!=sha(source):
        result.append('Humanizer original draft/context is stale')
    if context.get('writing_style')!=brief.get('writing_style','khazix'):
        result.append('Humanizer context differs from the selected voice')
    style_hash=sha(run/'style-context.json') if (run/'style-context.json').is_file() else None
    if context.get('style_context_sha256')!=style_hash: result.append('Humanizer voice inputs changed')
    vendor=ROOT/'references/vendor/humanizer'
    if context.get('upstream_skill_sha256')!=sha(vendor/'SKILL.md'): result.append('Humanizer source changed')
    before=source.read_text(encoding='utf8'); after=body.read_text(encoding='utf8')
    original=protected(before); revised=protected(after)
    # New image placements may be added by the subsequent illustration stage.
    # Every pre-existing image must remain, in order, with its alt and target.
    remaining=iter(revised['image_tokens'])
    if not all(any(candidate==token for candidate in remaining) for token in original['image_tokens']):
        result.append('Humanizer changed protected image_tokens')
    for key in ('code_blocks','inline_code','plain_urls'):
        if revised[key]!=original[key]: result.append('Humanizer changed protected '+key)
    links=lambda t: protected(re.sub(r'!\[[^\]]*\]\([^\n]*?\)', '', t))['link_targets']
    if links(after)!=links(before): result.append('Humanizer changed protected link_targets')
    if review.get('status')!='pass' or review.get('prose_sha256')!=prose_sha(after) or review.get('source_draft_sha256')!=sha(source):
        result.append('Humanizer review absent, failed, or not bound to current body')
    if review.get('writing_style')!=context.get('writing_style'): result.append('Humanizer review voice differs')
    for name in CHECKS:
        item=review.get('checks',{}).get(name,{})
        if item.get('status')!='pass' or len(item.get('reason','').strip())<12:
            result.append('Humanizer semantic review missing: '+name)
    findings=review.get('findings')
    if not isinstance(findings,list): result.append('Humanizer needs actual findings, or an empty list with no-change reason')
    elif not findings and len(review.get('no_change_reason',''))<12:
        result.append('Explain an actual no-change review; do not invent findings')
    else:
        for item in findings:
            if not isinstance(item,dict) or item.get('before','') not in before or not item.get('before'):
                result.append('Humanizer finding is not in the original draft'); continue
            if item.get('after') and item['after'] not in after: result.append('Humanizer finding not in current body')
            if not item.get('pattern') or len(item.get('reason',''))<8: result.append('Explain each actual Humanizer edit')
    intent=load(run/'reader-intent.json',{})
    if intent.get('article_type')=='tutorial' or intent.get('tutorial_sections'):
        check=review.get('checks',{}).get('tutorial_handholding',{})
        if check.get('status')!='pass' or len(check.get('reason',''))<12:
            result.append('Tutorial Humanizer review needs concrete handholding assessment')
    if include_second and brief.get('tone_policy') == 'dual-tone-style-preserving-v1':
        from lieflat_review import errors as second_errors
        result.extend(second_errors(run))
    return result

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('prepare','check','hash'))
    parser.add_argument('--run',required=True,type=Path)
    args=parser.parse_args()
    try:
        if args.command=='prepare': result=prepare(args.run); code=0
        elif args.command=='hash':
            result={'body_sha256':sha(args.run/'body.md'),'prose_sha256':prose_sha((args.run/'body.md').read_text(encoding='utf8'))}; code=0
        else:
            problems=errors(args.run,required=True); code=1 if problems else 0
            result={'passed':not problems,'errors':problems,'scope':'Recorded editorial review and protected material; no model detector'}
        print(json.dumps(result,ensure_ascii=False,indent=2)); return code
    except (ValueError,OSError,KeyError) as exc:
        print(json.dumps({'error':str(exc)},ensure_ascii=False)); return 1

if __name__=='__main__': raise SystemExit(main())
