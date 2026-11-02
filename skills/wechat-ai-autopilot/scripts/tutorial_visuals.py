"""Check tutorial coverage and editorial decisions; no image quota or style whitelist."""
import re
from pathlib import Path
import workflow as w


def meaningful(value, minimum=8):
    return isinstance(value, str) and len(value.strip()) >= minimum


def tutorial_errors(run, brief, body, images, refs):
    run = Path(run)
    intent = w.read(run / 'reader-intent.json', {})
    path = run / 'tutorial-plan.json'
    enabled = brief.get('tutorial_policy') == 'step-screenshots-v1'
    declared = intent.get('article_type') in ('tutorial', '教程') or bool(intent.get('tutorial_sections'))
    if not path.is_file() and not (enabled and declared):
        return []
    plan = w.read(path, {})
    errors = []
    if plan.get('body_sha256') != w.file_hash(run / 'body.md'):
        errors.append('tutorial plan missing or stale against current body')
    if any(not meaningful(plan.get(k)) for k in ('task_context', 'starting_point', 'success_definition')):
        errors.append('tutorial needs verified context, beginner starting point and success definition')
    steps = plan.get('steps', [])
    if not isinstance(steps, list) or not steps:
        return errors + ['tutorial needs actual step-by-step instructions and screenshots']
    ids = [s.get('id') for s in steps]
    if any(not sid for sid in ids) or len(set(ids)) != len(ids):
        errors.append('tutorial step IDs missing or duplicated')
    by_path = {im.get('path'): im for im in images}
    for step in steps:
        sid = step.get('id', '?')
        if not step.get('title') or any(not meaningful(step.get(k)) for k in
                ('before', 'action', 'input_hint', 'expected_result', 'attention')):
            errors.append(f'{sid}: tutorial needs location, action, input, result and precautions')
        quote = step.get('body_quote', '')
        if not meaningful(quote) or quote not in body:
            errors.append(f'{sid}: tutorial step is absent from current article')
        status = step.get('status')
        if status != 'ready':
            missing = next((m for m in plan.get('missing_images', []) if m.get('step_id') == sid), {})
            errors.append(f"{sid}: tutorial screenshot pending ({status}): {missing.get('need', 'specific required screenshot not recorded')}")
            if any(not meaningful(missing.get(k)) for k in ('need', 'reason', 'help_action')) or not missing.get('tried'):
                errors.append(f'{sid}: report the exact missing picture, attempts and required user help')
        paths = step.get('image_paths', [])
        if not isinstance(paths, list) or not paths:
            errors.append(f'{sid}: each tutorial step needs an inserted real screenshot')
            continue
        for ref in paths:
            im = by_path.get(ref, {})
            if im.get('role') != 'body' or im.get('backend') != 'screenshot' or ref not in refs:
                errors.append(f'{sid}: concept, cover or unused image cannot replace step screenshot: {ref}')
            found = re.search(r'!\[[^\]]*\]\(' + re.escape(ref) + r'\)', body)
            if found and quote in body and body.find(quote) >= found.start():
                errors.append(f'{sid}: screenshot is before the step it should illustrate')
    if plan.get('missing_images'):
        errors.append('tutorial has unresolved missing pictures; do not claim complete or push draft')
    return errors


def content_fit_errors(brief, plan, body, final_review=True):
    if brief.get('illustration_policy') != 'content-fit-v1':
        return []
    errors = []
    for asset in plan.get('assets', []):
        if asset.get('role') == 'body' and asset.get('backend') in ('native', 'configured'):
            choice = asset.get('style_decision', {})
            if not meaningful(choice.get('style'), 2) or not meaningful(choice.get('reason'), 12):
                errors.append('body AI image needs a content-specific style decision: ' + asset.get('path', '?'))
    density = plan.get('density_review', {})
    quote = density.get('body_quote', '')
    allowed = ('pass',) if final_review else ('planned', 'pass')
    if (density.get('status') not in allowed or not meaningful(quote) or quote not in body or
            any(not meaningful(density.get(k), 12) for k in ('excess_check', 'gap_check'))):
        errors.append('illustration density needs current-body excess and gap review, not a fixed image count')
    return errors
