"""Validate conditional body generation without treating a cover as a body illustration."""


def generation_errors(policy, plan, images, refs):
    if not isinstance(policy, dict) or policy.get('selection') != 'content-driven-v2':
        return []
    choice = plan.get('generation', {})
    if not isinstance(choice, dict):
        return ['image generation capability decision is missing']
    available = choice.get('builtin_available')
    mode = choice.get('mode')
    if type(available) is not bool or len(choice.get('capability_evidence', '')) < 12:
        return ['host must record actual built-in image tool availability']
    if available and (mode != 'builtin' or not choice.get('tool')):
        return ['available built-in image generation must be used']
    if not available:
        if mode not in ('configured', 'declined'):
            return ['image setup decision pending: ask whether to configure, then ask provider and model']
        if len(choice.get('user_decision', '')) < 4:
            return ['image setup or opt-out requires an actual user answer']
        if mode == 'configured' and (not choice.get('provider') or not choice.get('model') or
                                     not choice.get('tool') or choice.get('setup_status') != 'verified'):
            return ['configured image provider/model needs a verified working connection']
    generated = [x for x in images if x.get('role') == 'body' and x.get('path') in refs and
                 x.get('backend') in ('native', 'configured')]
    if mode == 'declined':
        return ['AI illustration contradicts the user opt-out'] if generated else []
    errors = []
    for image in generated:
        record = image.get('generation_record', {})
        expected = 'native' if mode == 'builtin' else 'configured'
        if (image.get('backend') != expected or record.get('status') != 'success' or
                record.get('output_sha256') != image.get('sha256') or
                record.get('tool') != choice.get('tool') or not record.get('generated_at')):
            errors.append('body AI illustration needs the actual successful generation record: ' + image['path'])
        if mode == 'configured' and (record.get('provider') != choice.get('provider') or
                                     record.get('model') != choice.get('model') or
                                     image.get('actual_model') != choice.get('model')):
            errors.append('configured image provider/model does not match the chosen setup')
    if not generated:
        exception = choice.get('no_gain_exception', {})
        anchors = exception.get('anchors', [])
        considered = {c.get('anchor') for c in plan.get('coverage', [])}
        if (exception.get('status') != 'editor-reviewed' or len(exception.get('reason', '')) < 25 or
                not isinstance(anchors, list) or not anchors or not set(anchors) <= considered or
                any(c.get('need') == 'generated' for c in plan.get('coverage', []))):
            errors.append('body needs useful AI generation; a generated cover does not satisfy it')
    return errors
