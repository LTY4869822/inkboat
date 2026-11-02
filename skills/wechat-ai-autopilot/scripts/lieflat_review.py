"""Validate an actual, style-preserving second editorial pass; no AI detector."""
import argparse
import re
from pathlib import Path
from humanize import ROOT, load, save, sha, prose_sha, protected

POLICY = 'dual-tone-style-preserving-v1'
CHECKS = ('facts_preserved', 'voice_preserved', 'whitelist_only', 'structure_preserved')
VENDOR = ROOT/'references/vendor/lieflat-less-ai-tone'

def prose(text):
    text = re.sub(r'(?m)^!\[[^\]]*\]\([^\n]*?\)\s*$', '', text)
    return re.sub(r'\n{3,}', '\n\n', text).strip()

def structure(text):
    # Rules may change sentence syntax, but never reorder/merge paragraphs or
    # move headings, lists, tables and code. Image placement is a later stage.
    paragraphs = prose(text).split('\n\n')
    return [ ('heading', len(re.match(r'^#+', p)[0])) if p.startswith('#')
             else ('code',) if p.startswith(('```','~~~'))
             else ('table', len(p.splitlines())) if p.startswith('|')
             else ('list', len(p.splitlines())) if re.match(r'^(?:[-*+] |\d+[.)] )',p)
             else ('quote',) if p.startswith('>') else ('prose',)
             for p in paragraphs ]

def prepare(run):
    from humanize import errors as first_errors
    run=Path(run)
    brief=load(run/'brief.json',{})
    if brief.get('tone_policy')!=POLICY:
        raise ValueError('Enable tone_policy only for this new/unconfirmed writing run')
    problems=first_errors(run, required=True, include_second=False)
    if problems: raise ValueError('Finish the actual Humanizer pass first: '+'; '.join(problems))
    intermediate=run/'humanizer-output.md'
    if not intermediate.is_file(): intermediate.write_bytes((run/'body.md').read_bytes())
    provenance=load(VENDOR/'provenance.json',{})
    if sha(VENDOR/'SKILL.md')!=provenance.get('files',{}).get('SKILL.md'):
        raise ValueError('Second editor source differs from the pinned version')
    context={'policy':POLICY, 'input_sha256':sha(intermediate),
        'first_review_sha256':sha(run/'humanizer-review.json'),
        'writing_style':brief.get('writing_style','khazix'),
        'upstream_commit':provenance.get('commit'),
        'upstream_skill_sha256':sha(VENDOR/'SKILL.md'),
        'scope':'Whitelist language edits to Humanizer output; no authorship inference'}
    existing=load(run/'lieflat-context.json')
    if existing and existing!=context:
        raise ValueError('Second pass inputs changed; preserve the previous trace and explicitly rebuild its review')
    save(run/'lieflat-context.json',context)
    return context

def errors(run):
    run=Path(run); result=[]
    context=load(run/'lieflat-context.json',{})
    review=load(run/'lieflat-review.json',{})
    intermediate=run/'humanizer-output.md'; body=run/'body.md'
    if not intermediate.is_file() or not body.is_file(): return ['Second editorial pass input/current body missing']
    if (context.get('policy')!=POLICY or context.get('input_sha256')!=sha(intermediate)
        or context.get('first_review_sha256')!=sha(run/'humanizer-review.json')
        or context.get('upstream_skill_sha256')!=sha(VENDOR/'SKILL.md')):
        result.append('Second editorial pass context is stale')
    if context.get('writing_style')!=load(run/'brief.json',{}).get('writing_style','khazix'):
        result.append('Second editorial pass selected voice changed')
    before=intermediate.read_text(encoding='utf8'); after=body.read_text(encoding='utf8')
    if (review.get('status')!='pass' or review.get('input_sha256')!=sha(intermediate)
        or review.get('prose_sha256')!=prose_sha(after)
        or review.get('writing_style')!=context.get('writing_style')):
        result.append('Second editorial review missing, failed or not bound to current prose')
    for name in CHECKS:
        item=review.get('checks',{}).get(name,{})
        if item.get('status')!='pass' or len(item.get('reason','').strip())<12:
            result.append('Second editorial semantic review missing: '+name)
    findings=review.get('findings')
    reconstructed=prose(before)
    if not isinstance(findings,list): result.append('Second pass needs actual findings')
    else:
        if not findings and len(review.get('no_change_reason','').strip())<12:
            result.append('Explain why the actual second review needed no changes')
        for item in findings:
            if not isinstance(item,dict) or type(item.get('rule')) is not int or not 1<=item['rule']<=11:
                result.append('Second edit must identify upstream whitelist rule 1–11'); continue
            old=item.get('before'); new=item.get('after')
            if not old or not isinstance(new,str) or old not in reconstructed:
                result.append('Second finding does not match its actual input'); continue
            if len(item.get('reason',''))<8: result.append('Explain each second edit trigger')
            reconstructed=reconstructed.replace(old,new,1)
        if reconstructed!=prose(after):
            result.append('Second pass changed text outside its recorded whitelist edits')
    if structure(before)!=structure(after): result.append('Second pass changed paragraph or document structure')
    old=protected(before); new=protected(after)
    remaining=iter(new['image_tokens'])
    if not all(any(candidate==token for candidate in remaining) for token in old['image_tokens']):
        result.append('Second pass changed a protected image')
    for key in ('code_blocks','inline_code','plain_urls'):
        if old[key]!=new[key]: result.append('Second pass changed protected '+key)
    links=lambda t: protected(re.sub(r'!\[[^\]]*\]\([^\n]*?\)', '',t))['link_targets']
    if links(before)!=links(after): result.append('Second pass changed protected links')
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=('prepare','check')); p.add_argument('--run',type=Path,required=True)
    a=p.parse_args()
    try:
        if a.command=='prepare': value=prepare(a.run); code=0
        else:
            problems=errors(a.run); code=bool(problems)
            value={'passed':not problems,'errors':problems,'scope':'Recorded second editorial pass, not an AI detector'}
        import json
        print(json.dumps(value,ensure_ascii=False,indent=2)); return code
    except (ValueError,OSError,KeyError) as exc:
        import json
        print(json.dumps({'error':str(exc)},ensure_ascii=False)); return 1

if __name__=='__main__': raise SystemExit(main())
