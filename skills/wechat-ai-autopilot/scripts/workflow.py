#!/usr/bin/env python3
"""Portable artifact coordinator. Agent performs semantic work and native imagegen."""
import argparse
import base64
import datetime as dt
import hashlib
import html
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from aihot_client import AIhotError, fetch_json

ROOT = Path(__file__).resolve().parents[1]
UTC8 = dt.timezone(dt.timedelta(hours=8))
REVIEW_KEYS = ("facts", "voice", "type_value", "title_alignment", "image_fidelity",
               "cover_safe_zone", "mobile")
WEIGHTS = [25, 15, 15, 15, 10, 10, 5, 5]


def now():
    return dt.datetime.now(UTC8).isoformat(timespec="seconds")


def read(path, default=None):
    return json.loads(Path(path).read_text(encoding="utf-8-sig")) if Path(path).is_file() else default


def save(path, data):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    temp = p.with_name(p.name + ".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temp, p)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def file_hash(path):
    return digest(Path(path).read_bytes()) if Path(path).is_file() else None


def within(run, path):
    run = Path(run).resolve()
    p = Path(path)
    p = (run / p).resolve() if not p.is_absolute() else p.resolve()
    if not p.is_relative_to(run):
        raise ValueError("artifact path must remain inside run")
    return p


def date(value):
    if not value:
        return None
    try:
        result = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        return result.replace(tzinfo=UTC8) if result.tzinfo is None else result
    except (ValueError, TypeError):
        return None


def skill_paths(workspace, profile=None):
    home = Path.home()
    candidates = [Path(workspace) / ".agents" / "skills", Path(workspace) / ".codex" / "skills",
                  Path(os.environ.get("CODEX_HOME", home / ".codex")) / "skills",
                  home / ".agents" / "skills", home / ".claude" / "skills"]
    found = {}
    for name in ("aihot", "khazix-writer", "baokuan-title-generator", "zhouxing-paiban-wx"):
        explicit = (profile or {}).get("skills", {}).get(name)
        paths = ([Path(explicit).expanduser()] if explicit else []) + [p / name for p in candidates]
        found[name] = next((str(p.resolve()) for p in paths if (p / "SKILL.md").is_file()), None)
    return found


def preferences(workspace=".", profile_path=None):
    catalog = read(ROOT / "assets" / "preferences.json")
    from style_library import catalog as style_catalog
    learned = style_catalog(workspace)
    catalog['writing_styles'] = learned['writing_styles']
    catalog['unavailable_writing_styles'] = learned['unavailable']
    path = skill_paths(workspace, read(profile_path, {}) if profile_path else {})["zhouxing-paiban-wx"]
    catalog["theme_availability"] = {
        key: bool(path and any(candidate.is_file() for candidate in (
            ROOT / 'assets' / 'layout-themes' / (key + '.json'),
            Path(path) / 'assets' / 'style-library' / (key + '.json'),
            Path(path) / 'assets' / 'learned-style-library' / (key + '.json'))))
        for key in catalog['themes']}
    catalog["counting_basis"] = "正文汉字，不含代码、图片文字/图注、来源编号及附录；英文不折算成汉字"
    return catalog


def length_choice(profile, kind, preset=None, chars=None):
    catalog = read(ROOT / "assets" / "preferences.json")
    chosen = preset or profile.get("length_preset", "standard")
    if chars is not None:
        bounds, chosen = list(chars), "custom"
    elif preset:
        bounds = catalog["lengths"][preset]["range"]
    elif profile.get("length", {}).get(kind):
        bounds, chosen = profile["length"][kind], "custom"
    else:
        bounds = catalog["lengths"][chosen]["range"]
    if (len(bounds) != 2 or any(type(v) is not int for v in bounds) or
            not 300 <= bounds[0] <= bounds[1] <= 20000):
        raise ValueError("length requires ordered integer bounds between 300 and 20000")
    return chosen, list(bounds)


def validate_preference(theme, visual_style):
    catalog = read(ROOT / "assets" / "preferences.json")
    if theme != "auto" and theme not in catalog["themes"]:
        raise ValueError("unknown Zhouxing theme; use preferences to list existing options")
    if visual_style not in catalog["visual_styles"]:
        raise ValueError("unknown visual style")


def font_choice(value='theme', custom=''):
    fonts = read(ROOT / 'assets' / 'preferences.json')['fonts']
    if value == 'custom':
        if not re.fullmatch(r'[\w \-\u4e00-\u9fff]{1,80}', custom.strip()):
            raise ValueError('custom font must be a font name, not CSS or a URL')
        name = custom.strip()
        return {'value': 'autopilot-custom', 'label': name,
                'stack': '"' + name + '","PingFang SC","Microsoft YaHei",sans-serif',
                'note': '仅在读者设备已安装此字体时使用；否则回退，不上传字体文件'}
    if value not in fonts:
        raise ValueError('unknown font; use a catalog ID or custom font name')
    item = fonts[value]
    return {'value': value, 'label': item['name'], 'stack': item['stack'], 'note': item['note']}


def presentation(brief):
    # Existing runs keep their original contract; init writes the new defaults.
    value = brief.get("presentation", {"citations": "inline", "image_captions": "labeled"})
    if (not isinstance(value, dict) or value.get("citations") not in ("internal", "inline") or
            value.get("image_captions") not in ("none", "labeled")):
        raise ValueError("invalid article presentation")
    return value


def presentation_errors(body, policy):
    errors = []
    if policy["citations"] == "internal" and (re.search(r"\[S\d+\]", body) or
            re.search(r"(?m)^#{1,6}\s+(?:来源|参考文献|参考资料)\s*$", body)):
        errors.append("public article includes citations/source appendix despite internal evidence policy")
    if policy["image_captions"] == "none" and re.search(
            r"!\[[^\]]*\]\([^)]+\)[ \t]*\n(?:[ \t]*\n)?[ \t]*\*?(?:图注[：:]|AI[ \t]*生成)", body):
        errors.append("public article includes an image provenance caption despite caption-free policy")
    return errors


def evidence_ids(body, claims, policy):
    if policy["citations"] == "internal":
        return {source_id for claim in claims for source_id in claim.get("source_ids", [])}
    return set(re.findall(r"\[(S\d+)\]", body))


def init(workspace, kind, topic, profile_path=None, preset=None, chars=None, theme=None, visual_style=None):
    profile = read(ROOT / "assets" / "profile.example.json")
    personal = read(Path(workspace) / ".wechat-ai/profile.json", {})
    if isinstance(personal, dict):
        profile.update(personal)
    if profile_path:
        profile.update(read(profile_path))
    chosen, bounds = length_choice(profile, kind, preset, chars)
    theme = theme or profile.get("theme", "auto")
    visual_style = visual_style or profile.get("visual_style", "cinematic-editorial")
    validate_preference(theme, visual_style)
    policy = profile.get("presentation", {"citations": "internal", "image_captions": "none"})
    presentation({"presentation": policy})
    run = Path(workspace).resolve() / "wechat-ai-runs" / (dt.datetime.now(UTC8).strftime("%Y%m%d-%H%M%S") + "-" + kind)
    run.mkdir(parents=True, exist_ok=False)
    (run / "assets").mkdir()
    save(run / "brief.json", {"schema_version": 3, "created_at": now(), "workspace": str(Path(workspace).resolve()),
         "reader_value_policy": profile.get("release_contract"),
         "type": kind, "topic": topic, "audience": profile["audience"], "author": profile.get("author", ""),
         "min_chars": bounds[0], "max_chars": bounds[1], "body_images": profile["body_images"],
         "theme": theme, "length_preset": chosen, "counting_basis": "prose-cjk-v2", "visual_style": visual_style,
         "font": profile.get('font', 'system'), "custom_font": profile.get('custom_font', ''), "writing_style": profile.get("writing_style", "khazix"),
         "visual_policy": {"mode": "mixed", "min_screenshots": 1, "selection": "content-driven-v2", "body_ai": "when_available"},
         "editorial_policy": "research-depth-v1",
         "humanizer_policy": "humanizer-style-preserving-v1",
         "tone_policy": "dual-tone-style-preserving-v1",
         "tutorial_policy": "step-screenshots-v1", "illustration_policy": "content-fit-v1",
         "motion_policy": "article-motion-v1", "studio_policy": "saved-final-v1",
         "practical_mode": "verified", "presentation": policy, "profile": profile})
    return {"run": str(run), "next": "record missing pre-writing answers with intake.py; own topic skips hotspot selection"}


def configure(run, preset=None, chars=None, theme=None, visual_style=None, citations=None, image_captions=None, font=None, custom_font=None):
    run = Path(run)
    brief = read(run / "brief.json")
    if preset or chars is not None:
        chosen, bounds = length_choice(brief.get("profile", {}), brief["type"], preset, chars)
        brief.update(length_preset=chosen, min_chars=bounds[0], max_chars=bounds[1], counting_basis="prose-cjk-v2")
    if theme is not None:
        brief["theme"] = theme
    if visual_style is not None:
        brief["visual_style"] = visual_style
    if font is not None or custom_font is not None:
        selected_font = font or brief.get('font', 'theme')
        selected_custom = custom_font if custom_font is not None else brief.get('custom_font', '')
        font_choice(selected_font, selected_custom)
        brief.update(font=selected_font, custom_font=selected_custom)
    validate_preference(brief.get("theme", "auto"), brief.get("visual_style", "editorial"))
    if citations is not None or image_captions is not None:
        policy = dict(presentation(brief))
        if citations is not None:
            policy["citations"] = citations
        if image_captions is not None:
            policy["image_captions"] = image_captions
        presentation({"presentation": policy})
        brief["presentation"] = policy
    save(run / "brief.json", brief)
    return {"preferences": {key: brief.get(key) for key in ("theme", "font", "custom_font", "visual_style", "length_preset", "min_chars", "max_chars", "presentation")},
            "next": "review changed settings; rebuild layout/export if theme changed, revise body if length changed, replan images if visual style changed"}


def recommend_layout(run, theme, reason):
    run = Path(run)
    brief = read(run / "brief.json")
    validate_preference(theme, brief.get("visual_style", "editorial"))
    if theme == "auto" or len(reason.strip()) < 12 or not (run / "body.md").is_file():
        raise ValueError("recommendation needs an existing body, concrete theme and content-specific reason")
    record = {"recommended_theme": theme, "reason": reason.strip(), "body_sha256": file_hash(run / "body.md"),
              "created_at": now()}
    save(run / "layout-choice.json", record)
    return {**record, "effective_theme": theme if brief.get("theme") == "auto" else brief["theme"],
            "user_override": brief.get("theme") != "auto"}


def effective_theme(run, brief):
    recommendation = read(Path(run) / "layout-choice.json", {})
    if brief.get("schema_version", 1) >= 2:
        if recommendation.get("body_sha256") != file_hash(Path(run) / "body.md"):
            raise ValueError("layout recommendation missing/stale; recommend against current article")
        validate_preference(recommendation.get("recommended_theme"), brief.get("visual_style", "editorial"))
    selected = brief.get("theme", "auto")
    return recommendation["recommended_theme"] if selected == "auto" else selected


def prose_cjk(body):
    text = re.sub(r"(?ms)^\s*(`{3,}|~{3,})[^\n]*\n.*?^\s*\1\s*$", "", body)
    caption = r"(?:图注[：:]|AI[ \t]*生成(?:的)?(?:概念)?示意|图[0-9一二三四五六七八九十]+[：:、．.])"
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)[ \t]*\n(?:[ \t]*\n)?[ \t]*\*?" + caption + r"[^\n]*", "", text)
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", text)
    text = re.sub(r"\[S\d+\]", "", text)
    return len(re.findall(r"[\u4e00-\u9fff]", text))


def fetch(url, cache_dir, opener=None, sleeper=time.sleep, trace=None):
    return fetch_json(url, cache_dir, opener=opener, sleeper=sleeper, trace=trace)


def diagnose_aihot(run, opener=None):
    run = Path(run)
    trace = {}
    try:
        value = fetch('https://aihot.virxact.com/api/v1/hot-topics', run / '.cache', opener=opener, trace=trace)
        result = {'status': 'ok', 'anonymous': True, 'count': len(value['items']), **trace}
    except (AIhotError, ValueError) as exc:
        result = {'status': 'failed', 'anonymous': True, **trace,
                  'error': exc.detail if isinstance(exc, AIhotError) else {'code': 'invalid_response', 'message': str(exc)}}
    save(run / 'aihot-diagnostic.json', result)
    return result


def discover(run, query=None, opener=None):
    run = Path(run)
    brief = read(run / "brief.json")
    query = query or brief["topic"]
    params = {"mode": "selected", "window": "7d", "limit": 10}
    if query.lower().strip() not in ("ai", "人工智能"):
        if not 2 <= len(query) <= 200:
            raise ValueError("AIhot q must contain 2—200 characters")
        params["q"] = query
    result = {"provider": "aihot", "fetched_at": now(), "responses": [], "errors": [], "error_details": [], "requests": []}
    endpoints = ["https://aihot.virxact.com/api/v1/hot-topics",
                 "https://aihot.virxact.com/api/v1/items?" + urllib.parse.urlencode(params)]
    for url in endpoints:
        trace = {}
        result['requests'].append(trace)
        try:
            body = fetch(url, run / ".cache", opener=opener, trace=trace)
            result["responses"].append({"url": url, "data": body})
            if "/items?" in url and "q" in params and not body.get("items"):
                params["mode"] = "all"
                fallback_url = "https://aihot.virxact.com/api/v1/items?" + urllib.parse.urlencode(params)
                trace = {}
                result['requests'].append(trace)
                result["responses"].append({"url": fallback_url, "not_selected": True,
                                            "data": fetch(fallback_url, run / ".cache", opener=opener, trace=trace)})
        except (RuntimeError, ValueError) as exc:
            result["errors"].append(str(exc))
            detail = exc.detail if isinstance(exc, AIhotError) else {'code': 'invalid_response', 'message': str(exc), 'url': url}
            result['error_details'].append(detail)
            # A refused transport affects both endpoints on this same host.
            if detail['code'] in ('transport_connection_refused', 'transport_dns_failure', 'transport_tls_failure', 'http_rate_limited', 'local_filesystem_error'):
                break
    save(run / "discovery.json", result)
    return {"provider": "aihot", "counts": [len(x["data"].get("items", [])) for x in result["responses"]],
            "errors": result["errors"], "error_details": result['error_details'],
            "next": result['error_details'][0].get('action', 'host-search') if result['error_details'] else "open originals; build topic/sources/claims"}


def screenshot_errors(run, image, sources, body=None):
    """Check traceability of host-captured pixels; visual review remains required."""
    errors = []
    record = image.get('provenance', {})
    source_ids = record.get('source_ids', [])
    matched = [x for x in sources if x.get('id') in source_ids]
    if (not source_ids or len(matched) != len(set(source_ids)) or
            any(not x.get('verified') or x.get('kind') == 'lead' for x in matched)):
        errors.append('screenshot needs verified source records')
    url = record.get('page_url') or ''
    kind = record.get('kind')
    user_image = kind == 'tutorial-step' and record.get('tutorial_origin') == 'user'
    parsed = urllib.parse.urlsplit(url)
    sensitive = {'token', 'access_token', 'secret', 'ticket', 'key', 'api_key', 'auth', 'code', 'signature'}
    invalid_url = (parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password or
                   sensitive & {key.lower() for key, _ in urllib.parse.parse_qsl(parsed.query)})
    if invalid_url and not (user_image and not url):
        errors.append('screenshot URL must be an observed page without credentials')
    if kind in ('announcement', 'public-case'):
        if not any(x.get('kind') == 'primary' and urllib.parse.urldefrag(x.get('url', ''))[0]
                   == urllib.parse.urldefrag(url)[0] for x in matched):
            errors.append('announcement/public-case screenshot must match a verified primary page')
        if kind == 'public-case' and (not record.get('platform') or not record.get('author') or
                                      not record.get('post_time') or not record.get('evidence_scope')):
            errors.append('public case screenshot needs platform, author, post time and evidence scope')
    elif kind == 'tutorial-step':
        if record.get('capture_method') not in ('source-image-crop', 'source-image-annotation') or len(record.get('usage_basis', '')) < 12:
            errors.append('imported tutorial screenshot needs original image provenance and usage basis')
        if user_image:
            if record.get('supplied_by') != 'user' or not any(
                    x.get('read_record', {}).get('access') == 'human_supplied' for x in matched):
                errors.append('user tutorial screenshot needs an actual human-supplied source')
        elif record.get('tutorial_origin') == 'external':
            if not any(x.get('kind') == 'primary' and urllib.parse.urldefrag(x.get('url', ''))[0]
                       == urllib.parse.urldefrag(url)[0] for x in matched):
                errors.append('external tutorial screenshot must match its verified original author page')
            if any(not record.get(k) for k in ('platform', 'author', 'post_time', 'evidence_scope')):
                errors.append('external tutorial screenshot needs author, platform, time and scope')
        else:
            errors.append('tutorial screenshot must distinguish external and user-provided origins')
    elif kind != 'operation' or not any(x.get('kind') == 'experiment' for x in matched):
        errors.append('operation screenshot needs an actual experiment record')
    if (not date(record.get('captured_at')) or not record.get('page_title') or
            len(record.get('observed_text', '').strip()) < 8 or not record.get('review_note')):
        errors.append('screenshot capture observation incomplete')
    if record.get('capture_sha256') != image.get('sha256'):
        errors.append('screenshot pixels differ from capture record')
    viewport, clip = record.get('viewport', {}), record.get('clip', {})
    method = record.get('capture_method')
    annotated_full = method in ('browser-annotation', 'source-image-annotation')
    original_partial = (method == 'source-image-crop' and record.get('already_partial') is True and
                        len(record.get('partial_note', '')) >= 12)
    width = height = None
    try:
        vw, vh = viewport['width'], viewport['height']
        x, y, width, height = (clip[k] for k in ('x', 'y', 'width', 'height'))
        values = (vw, vh, x, y, width, height)
        if (any(type(v) not in (int, float) for v in values) or min(vw, vh, width, height) <= 0 or
                min(x, y) < 0 or x + width > vw or y + height > vh or
                (width * height >= vw * vh * .85 and not original_partial and not annotated_full)):
            raise ValueError('crop')
    except (KeyError, TypeError, ValueError):
        errors.append('screenshot needs a useful partial viewport crop')
    method = record.get('capture_method')
    if method == 'pdf-render-crop':
        try:
            pdf = within(Path(run).resolve(), record['pdf_file'])
            if (pdf.suffix.lower() != '.pdf' or not pdf.is_file() or
                    not pdf.read_bytes().startswith(b'%PDF-') or
                    file_hash(pdf) != record.get('pdf_sha256') or
                    type(record.get('page_number')) is not int or record['page_number'] < 1 or
                    type(record.get('render_scale')) not in (int, float) or record['render_scale'] <= 0):
                raise ValueError('PDF capture')
            points = record['page_size_points']
            scale = record['render_scale']
            if (abs(viewport['width'] - points['width'] * scale) > 1 or
                    abs(viewport['height'] - points['height'] * scale) > 1):
                raise ValueError('PDF render dimensions')
        except (KeyError, TypeError, ValueError, OSError):
            errors.append('PDF crop needs its original file, hash, page and consistent render dimensions')
    elif method == 'browser-pixel-crop':
        try:
            original = within(Path(run).resolve(), record['original_capture_file'])
            if (not original.is_file() or file_hash(original) != record.get('original_capture_sha256') or
                    record.get('pixel_operation') != 'crop_only' or
                    record.get('output_pixel_size') != {'width': width, 'height': height}):
                raise ValueError('original browser crop')
        except (KeyError, TypeError, ValueError, OSError):
            errors.append('browser pixel crop needs the unchanged original capture, hash, crop-only operation and output dimensions')
    elif method == 'source-image-crop':
        try:
            original = within(Path(run).resolve(), record['original_image_file'])
            if (kind != 'tutorial-step' or not original.is_file() or
                    file_hash(original) != record.get('original_image_sha256') or
                    record.get('pixel_operation') != 'crop_only' or
                    record.get('output_pixel_size') != {'width': width, 'height': height}):
                raise ValueError('original tutorial image')
        except (KeyError, TypeError, ValueError, OSError):
            errors.append('imported tutorial image needs unchanged original file/hash and crop dimensions')
    elif method in ('browser-annotation', 'source-image-annotation'):
        from screenshot_annotations import annotation_errors
        errors.extend(annotation_errors(run, image))
    elif method != 'browser-clip':
        errors.append('screenshot must contain original browser or PDF pixels, not generated')
    anchor = record.get('insert_after', '')
    if len(anchor.strip()) < 8:
        errors.append('screenshot insertion needs a concrete article passage')
    elif body is not None:
        occurrence = re.search(r'!\[[^\]]*\]\(' + re.escape(image['path']) + r'\)', body)
        if anchor not in body or not occurrence or body.find(anchor) >= occurrence.start():
            errors.append('screenshot insertion passage is missing or after its image')
    return errors


def mixed_image_errors(run, brief, images, body_refs, sources, body):
    policy = brief.get('visual_policy')
    if policy is None:
        return []  # Do not invalidate previously approved runs on upgrade.
    if (not isinstance(policy, dict) or policy.get('mode') != 'mixed' or policy.get('min_screenshots') != 1 or
            policy.get('selection') not in (None, 'content-driven-v1', 'content-driven-v2') or
            set(policy) - {'mode', 'min_screenshots', 'selection', 'body_ai'} or
            (policy.get('selection') == 'content-driven-v2' and policy.get('body_ai') != 'when_available')):
        return ['invalid mixed illustration policy']
    screenshots = [x for x in images if x.get('role') == 'body' and
                   x.get('backend') == 'screenshot' and x.get('path') in body_refs]
    errors = [] if screenshots else ['mixed illustrations need at least one inserted real screenshot']
    for image in screenshots:
        errors.extend(x + ': ' + image['path'] for x in screenshot_errors(run, image, sources, body))
    from visual_policy import generation_errors
    errors.extend(generation_errors(policy, read(Path(run) / 'images-plan.json', {}), images, body_refs))
    return errors


def image_plan_errors(run, brief, body, refs, final_review=True):
    """Require explicit editorial value for new content-driven runs, not a quota."""
    policy = brief.get('visual_policy')
    if not isinstance(policy, dict) or policy.get('selection') not in ('content-driven-v1', 'content-driven-v2'):
        return []
    plan = read(Path(run) / 'images-plan.json', {})
    errors = []
    from tutorial_visuals import content_fit_errors
    errors.extend(content_fit_errors(brief, plan, body, final_review=final_review))
    if plan.get('body_sha256') != file_hash(Path(run) / 'body.md'):
        errors.append('content-driven illustration plan is stale')
    coverage = plan.get('coverage', [])
    if not coverage:
        errors.append('illustration plan needs passage-by-passage coverage decisions')
    sections = set(re.findall(r'(?m)^## (.+)$', body))
    if not sections <= {x.get('section') for x in coverage}:
        errors.append('illustration coverage must consider every article section')
    for item in coverage:
        paths = item.get('asset_paths', [])
        anchor = item.get('anchor', '')
        if (len(anchor) < 8 or anchor not in body or len(item.get('reason', '')) < 12 or
                item.get('need') not in ('screenshot', 'generated', 'text-only') or
                not isinstance(paths, list) or not set(paths) <= set(refs) or
                (item.get('need') == 'text-only' and paths) or
                (item.get('need') != 'text-only' and not paths)):
            errors.append('illustration coverage missing a current passage or useful decision')
            break
    planned = {x.get('path'): x for x in plan.get('assets', []) if x.get('role') == 'body'}
    if set(planned) != set(refs):
        errors.append('inserted illustrations differ from the content-driven plan')
    covered = {p for c in coverage for p in c.get('asset_paths', [])}
    if not set(refs) <= covered:
        errors.append('inserted illustration has no coverage decision')
    for path in refs:
        value = planned.get(path, {}).get('value_check', {})
        if (value.get('evidence_kind') not in ('feature', 'data', 'case', 'operation', 'concept') or
                any(len(value.get(key, '').strip()) < 8 for key in
                    ('question', 'reader_gain', 'why_this_medium', 'removal_cost'))):
            errors.append('illustration needs concrete reader value; identity-only screenshots do not count: ' + path)
    for item in coverage:
        expected = ('screenshot',) if item.get('need') == 'screenshot' else ('native', 'configured')
        if item.get('need') != 'text-only' and any(planned.get(p, {}).get('backend') not in expected
                                                 for p in item.get('asset_paths', [])):
            errors.append('illustration medium differs from the passage decision')
    return errors


def explicit_image_minimum(brief):
    value = brief.get('body_images', 'auto')
    if value in ('auto', None):
        return 0  # Mixed evidence and content-plan checks remain in force.
    if type(value) is not int or value < 0:
        raise ValueError('body_images must be auto or a nonnegative explicit minimum')
    return value


def register_image(run, path, role, prompt, backend, checked=False, note="", model=None, provenance=None):
    run = Path(run).resolve()
    p = within(run, path)
    if not p.is_file() or p.suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp"):
        raise ValueError("image must be an existing raster file in run")
    items = read(run / "images.json", [])
    rel = p.relative_to(run).as_posix()
    entry = {"path": rel, "role": role, "backend": backend, "source": "AI-generated" if backend in ("native", "configured") else backend,
             "actual_model": model, "prompt": prompt, "sha256": file_hash(p), "visually_checked": checked,
             "check_note": note, "registered_at": now()}
    if backend == 'screenshot':
        entry['provenance'] = read(within(run, provenance), {}) if provenance else {}
        errors = screenshot_errors(run, entry, read(run / 'sources.json', []))
        if errors:
            raise ValueError('; '.join(errors))
        entry['actual_model'] = None
    elif backend in ('native', 'configured') and provenance:
        entry['generation_record'] = read(within(run, provenance), {})
    if backend == 'configured' and (not model or not provenance):
        raise ValueError('configured generation requires actual model and successful generation record')
    items = [x for x in items if x["path"] != rel]
    items.append(entry)
    save(run / "images.json", items)
    return entry


def check_images(run):
    """Fail before layout/export when required visual evidence is missing."""
    run = Path(run).resolve()
    brief = read(run / 'brief.json', {})
    body = (run / 'body.md').read_text(encoding='utf-8')
    refs = re.findall(r'!\[[^\]]*\]\(([^)]+)\)', body)
    images = read(run / 'images.json', [])
    by_path = {x['path']: x for x in images}
    errors = mixed_image_errors(run, brief, images, refs, read(run / 'sources.json', []), body)
    errors.extend(image_plan_errors(run, brief, body, refs, final_review=False))
    from tutorial_visuals import tutorial_errors
    errors.extend(tutorial_errors(run, brief, body, images, refs))
    if len(refs) < explicit_image_minimum(brief):
        errors.append('body image count below plan')
    for ref in refs:
        image = by_path.get(ref, {})
        if (image.get('role') != 'body' or not image.get('visually_checked') or not image.get('check_note') or
                image.get('sha256') != file_hash(within(run, ref))):
            errors.append('body image missing, changed or unchecked: ' + ref)
    if errors:
        raise ValueError('; '.join(errors))
    return {'status': 'images_ready', 'body_images': len(refs), 'mixed_policy': brief.get('visual_policy')}


def assemble(run):
    run = Path(run)
    if read(run / 'brief.json', {}).get('schema_version', 1) >= 3:
        from intake import ready
        ready(run)
    from style_library import context_ready
    context_ready(run, require_body=True)
    topic = read(run / "topic.json", {})
    body = (run / "body.md").read_text(encoding="utf-8")
    policy = presentation(read(run / "brief.json", {}))
    violations = presentation_errors(body, policy)
    if violations:
        raise ValueError("; ".join(violations))
    if re.search(r"(?m)^# ", body):
        raise ValueError("body.md must not include a first-level title")
    titles = read(run / "titles.json", {})
    title = topic.get("working_title")
    if titles:
        if titles.get("body_sha256") != file_hash(run / "body.md"):
            raise ValueError("titles are stale; regenerate against current body")
        selected = next((x for x in titles.get("candidates", []) if x.get("id") == titles.get("selected")), None)
        if not selected or selected.get("risk") == "high":
            raise ValueError("selected title missing or high risk")
        title = selected["title"]
    if not title or "\n" in title or "\r" in title:
        raise ValueError("missing or invalid title")
    sources = read(run / "sources.json", [])
    used = set(re.findall(r"\[(S\d+)\]", body))
    refs = []
    for s in sources:
        if s["id"] in used:
            safe_title = str(s["title"]).replace("[", "（").replace("]", "）").replace("\n", " ")
            refs.append(f"[{s['id']}] [{safe_title}]({s['url']}) · {s.get('published_at') or '原文日期未明确'}")
    text = f"# {title}\n\n{body.strip()}\n"
    if policy["citations"] == "inline":
        text += "\n---\n\n## 来源\n\n" + "\n\n".join(refs) + "\n"
    (run / "article.md").write_text(text, encoding="utf-8")
    save(run / "article-meta.json", {"title": title, "digest": titles.get("digest", ""),
                                     "body_sha256": file_hash(run / "body.md"), "sources_sha256": file_hash(run / "sources.json"),
                                     "presentation": policy})
    return {"title": title, "final_title": bool(titles), "article_sha256": file_hash(run / "article.md")}


def build_layout(run, brief, theme, output):
    path = skill_paths(brief["workspace"], brief.get("profile"))["zhouxing-paiban-wx"]
    if not path:
        raise ValueError("zhouxing-paiban-wx missing; install repository skill directory first")
    proc = subprocess.run([sys.executable, str(ROOT / 'scripts' / 'zhouxing_adapter.py'), '--zhouxing', path,
                           "--article", str(run / "article.md"), "--theme", theme,
                           "--output", str(output)], capture_output=True, text=True, encoding="utf-8")
    if proc.returncode:
        raise ValueError("Zhouxing build failed: " + proc.stderr[-1800:])
    summary = json.loads(proc.stdout)
    # Keep Zhouxing's exact formatter; expose the button's own output for hosts
    # whose session clipboard does not observe navigator.clipboard.write.
    preview = output
    document = preview.read_text(encoding='utf-8')
    # Set ordinary prose to black in every theme before computed-style export.
    # Headings, strong/em, links, quotes, code and decorative labels retain ink.
    color_hook = 'themeStyle.textContent=css;'
    if document.count(color_hook) != 1:
        raise ValueError('Zhouxing color contract changed; inspect template before adapting')
    body_ink = '.note-to-mp{color:#000000!important}.note-to-mp>p,.note-to-mp>ul,.note-to-mp>ol,.note-to-mp li,.note-to-mp li p,.note-to-mp td{color:#000000!important}'
    document = document.replace(color_hook, 'css+=' + json.dumps('\n'+body_ink) + ';' + color_hook, 1)
    hook = 'htmlContent=stripClipboardMetadata(clone).outerHTML;try'
    if document.count(hook) != 1:
        raise ValueError('Zhouxing export contract changed; inspect new template before adapting')
    document = document.replace(hook, 'htmlContent=stripClipboardMetadata(clone).outerHTML;document.getElementById("autopilotExport").value=htmlContent;try', 1)
    # Preserve the responsive intent instead of exporting desktop auto margins
    # as pixel offsets. This also applies to Zhouxing's legacy-copy fallback.
    sizing_hook = 'flattenListsForClipboard(clone);return clone'
    if document.count(sizing_hook) != 1:
        raise ValueError('Zhouxing sizing contract changed; inspect template before adapting')
    document = document.replace(sizing_hook, "flattenListsForClipboard(clone);clone.style.marginLeft='auto';clone.style.marginRight='auto';clone.style.maxWidth=getComputedStyle(article).maxWidth;return clone", 1)
    panel = '<details style="max-width:760px;margin:24px;padding:16px;background:white"><summary>本地导出结果（复制按钮生成）</summary><p>剪贴板未更新时，从此只读区域读取周行按钮实际生成的 HTML；不会包含设置栏。</p><textarea id="autopilotExport" aria-label="周行按钮导出HTML" readonly style="width:100%;height:180px"></textarea></details>'
    document = document.replace('</body>', panel + '</body>', 1)
    selected_font = font_choice(brief.get('font', 'theme'), brief.get('custom_font', ''))
    if selected_font['value'] != 'theme':
        marker = 'fontChoices.forEach(choice=>addOption(fontSelect,choice.value,choice.label));'
        reset = "fontSelect.value=preset?preset.font:'theme';"
        if document.count(marker) != 1 or document.count(reset) != 1:
            raise ValueError('Zhouxing font contract changed; inspect template before adapting')
        data = json.dumps(selected_font, ensure_ascii=False).replace('<', '\\u003c')
        document = document.replace(marker, 'const autopilotFont=' + data + ';const fontIndex=fontChoices.findIndex(x=>x.value===autopilotFont.value);if(fontIndex>=0)fontChoices[fontIndex]=autopilotFont;else fontChoices.push(autopilotFont);' + marker, 1)
        document = document.replace(reset, 'fontSelect.value=preset?preset.font:autopilotFont.value;', 1)
    # A reading mode for the comparison gallery; styles still come from Zhouxing.
    document = document.replace('</head>', '<style>html[data-autopilot-reading] body{min-width:0!important;width:100%!important;background:#fff!important}html[data-autopilot-reading] .app-header,html[data-autopilot-reading] .toolbar,html[data-autopilot-reading] .ambient-flow,html[data-autopilot-reading] details{display:none!important}html[data-autopilot-reading] .workspace{padding:0!important;margin:0!important}html[data-autopilot-reading] .paper-shell{width:100%!important;padding:0!important;border:0!important;border-radius:0!important;box-shadow:none!important;overflow:visible!important}html[data-autopilot-reading] body:before{display:none!important}</style></head>', 1)
    document = document.replace('</body>', '<script>if(new URLSearchParams(location.search).get("reading")==="1"){document.documentElement.dataset.autopilotReading="true";document.getElementById("article").contentEditable="false";}</script></body>', 1)
    if brief.get('motion_policy') == 'article-motion-v1':
        from motion import install
        document = install(run, brief, output, document)
    preview.write_text(document, encoding='utf-8')
    summary['export_adapter'] = 'button-dom-observer'
    summary['selected_theme'] = theme
    summary['selected_font'] = selected_font
    summary['theme_source'] = 'host-zhouxing-plus-bundled-confirmed-originals'
    summary['responsive_copy_margins'] = True
    summary['body_text_color'] = '#000000'
    return summary


def layout(run):
    run = Path(run).resolve()
    if (run/'studio-final.json').is_file():
        from studio_state import selection_current
        selection_current(run)
        return {'preserved':True,'backend':'studio-saved-final','preview':str(run/'preview.html'),'studio_revision':read(run/'studio-final.json')['revision']}
    brief = read(run / 'brief.json')
    summary = build_layout(run, brief, effective_theme(run, brief), run / 'preview.html')
    save(run / "layout.json", {**summary, "article_sha256": file_hash(run / "article.md"),
                                "preview_sha256": file_hash(run / "preview.html"), "brief_sha256": file_hash(run / "brief.json"),
                                "recommendation_sha256": file_hash(run / "layout-choice.json"), "created_at": now()})
    return summary


def layout_previews(run):
    run = Path(run).resolve()
    brief = read(run / 'brief.json')
    if brief.get('schema_version', 1) >= 3:
        from intake import ready
        ready(run)
    recommended = effective_theme(run, {**brief, 'theme': 'auto'})
    catalog = read(ROOT / 'assets' / 'preferences.json')
    folder = run / 'layouts'
    folder.mkdir(exist_ok=True)
    variants, cards = [], []
    article_sha = file_hash(run / 'article.md')
    for theme, info in catalog['themes'].items():
        output = folder / (theme + '.html')
        result = build_layout(run, brief, theme, output)
        if result.get('warnings'):
            raise ValueError('comparison preview warnings: ' + str(result['warnings']))
        variants.append({'theme': theme, 'name': info['name'], 'preview': output.relative_to(run).as_posix(),
                         'preview_sha256': file_hash(output), 'article_sha256': article_sha})
        label = info['name'] + (' · 推荐' if theme == recommended else '') + (' · 当前采用' if theme == brief.get('theme') else '')
        cards.append('<section class="card"><h2>' + html.escape(label) + '</h2><p>' + html.escape(info['use']) + '</p><iframe loading="lazy" title="' + html.escape(info['name']) + '全文预览" src="layouts/' + theme + '.html?reading=1"></iframe><a href="layouts/' + theme + '.html" target="_blank">打开完整设置与全文</a><button data-theme="' + theme + '">选用' + html.escape(info['name']) + '</button></section>')
    manifest = {'schema_version': 2, 'theme_ids': list(catalog['themes']), 'article_sha256': article_sha, 'body_sha256': file_hash(run / 'body.md'),
                'asset_hashes': {item['path']: file_hash(within(run, item['path'])) for item in read(run / 'images.json', [])},
                'font': font_choice(brief.get('font', 'theme'), brief.get('custom_font', '')),
                'recommended_theme': recommended, 'selected_theme': brief.get('theme', 'auto'), 'variants': variants, 'created_at': now()}
    save(run / 'layout-variants.json', manifest)
    data = json.dumps(manifest, ensure_ascii=False).replace('<', '\\u003c')
    page = '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>' + str(len(variants)) + '套公众号排版对比</title><style>body{margin:0;background:#f4f7f5;color:#203b31;font:16px/1.6 system-ui,sans-serif}main{max-width:1320px;margin:auto;padding:28px}h1{font-size:30px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(300px,100%),1fr));gap:22px}.card{background:white;padding:18px;border:1px solid #d5e2da;border-radius:14px}.card h2{margin:0;font-size:20px}.card p{font-size:14px;color:#60756a}iframe{display:block;width:100%;height:620px;border:1px solid #e2e9e5;margin:16px 0}a{color:#176c4a}button{display:block;padding:12px 20px;margin-top:12px;border:0;background:#176c4a;color:white;border-radius:8px;cursor:pointer}textarea{display:none;width:100%;min-height:110px}#choicePanel{background:#e5efe8;padding:20px;margin:24px 0}@media(max-width:640px){main{padding:16px}}</style><main><h1>同一篇文章，' + str(len(variants)) + '套排版</h1><p>每套都是周行真实渲染，保留本次图片与字体选择；未指定字体的旧稿沿用各主题字体。卡片里可滚动阅读全文。选定后如需改稿，先告诉助手；没有修改时存入已连接公众号的草稿箱。</p><div id="choicePanel"><p id="choiceStatus">尚未选择排版。选择后将显示可发送给助手的确认文字。</p><textarea id="layoutChoice" readonly aria-label="排版选择记录"></textarea><p id="choicePrompt"></p></div><div class="grid">' + ''.join(cards) + '</div></main><script type="application/json" id="variants">' + data + '</script><script>const m=JSON.parse(document.getElementById("variants").textContent);document.querySelectorAll("button[data-theme]").forEach(b=>b.addEventListener("click",()=>{const v=m.variants.find(x=>x.theme===b.dataset.theme);const c={theme:v.theme,article_sha256:m.article_sha256,preview_sha256:v.preview_sha256,font:m.font};document.getElementById("layoutChoice").style.display="block";document.getElementById("layoutChoice").value=JSON.stringify(c,null,2);document.getElementById("choiceStatus").textContent="已选择："+v.name;document.getElementById("choicePrompt").textContent="发给助手：我选择"+v.name+"，没有其他修改，存入公众号草稿箱。";}));</script></html>'
    (run / 'layout-gallery.html').write_text(page, encoding='utf-8')
    result={'gallery': str(run / 'layout-gallery.html'), 'variants': len(variants), 'font': manifest['font'], 'recommended': recommended}
    if brief.get('studio_policy')=='saved-final-v1':
        from studio import prepare as prepare_studio
        result['studio']=prepare_studio(run)['studio']
        result['next']='启动studio.py serve --run RUN，打开实际URL供预览；确认后采用保存版本'
    return result


class ContentParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.texts, self.images, self.links, self.unsafe = [], [], [], []
        self.svg_images, self.all_images = [], []
        self.fonts = []
        self.font_stack = []
        self.hidden = []
        self.code_blocks = []
        self.pre_depth = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        declarations = dict(x.split(':', 1) for x in attrs.get('style', '').split(';') if ':' in x)
        inherited_font = self.font_stack[-1][1] if self.font_stack else ''
        font = next((v.strip() for k, v in declarations.items() if k.strip().lower() == 'font-family'), inherited_font)
        if font.lower() in ('inherit', 'unset'):
            font = inherited_font
        if tag in ('p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
            # Rich-text editors may remove redundant declarations. Validate the
            # effective inline inheritance instead of requiring duplication.
            self.fonts.append(font)
        if tag in ("script", "iframe", "object", "embed", "style", "button", "input", "select"):
            self.unsafe.append(tag)
        if any(k.startswith("on") for k in attrs):
            self.unsafe.append("event-handler")
        for key in ("href", "src"):
            if attrs.get(key, "").lower().strip().startswith("javascript:"):
                self.unsafe.append("javascript-url")
        inherited = bool(self.hidden and self.hidden[-1][1])
        hide = inherited or attrs.get("aria-hidden") == "true"
        if tag not in ("img", "br", "hr", "input", "meta", "link", "source", "wbr"):
            self.hidden.append((tag, hide))
            self.font_stack.append((tag, font))
        if tag == "img":
            self.images.append(attrs.get("src", ""))
            self.all_images.append(attrs.get('src',''))
        if tag == 'image':
            src=attrs.get('xlink:href',attrs.get('href',''))
            self.svg_images.append(src)
            self.all_images.append(src)
        if tag == "a":
            self.links.append(attrs.get("href", ""))
        if tag == 'pre':
            self.pre_depth += 1
            self.code_blocks.append('')
        if tag == 'br' and self.pre_depth and not hide:
            # WeChat ProseMirror serializes visible code newlines as <br>.
            # Preserve them so missing line breaks and indentation still fail.
            self.code_blocks[-1] += '\n'

    def handle_endtag(self, tag):
        if tag == 'pre':
            self.pre_depth = max(0, self.pre_depth - 1)
        for i in range(len(self.hidden) - 1, -1, -1):
            if self.hidden[i][0] == tag:
                del self.hidden[i:]
                break
        for i in range(len(self.font_stack) - 1, -1, -1):
            if self.font_stack[i][0] == tag:
                del self.font_stack[i:]
                break

    def handle_data(self, value):
        if not self.hidden or not self.hidden[-1][1]:
            self.texts.append(value)
            if self.pre_depth:
                self.code_blocks[-1] += value


def plain_md(text):
    if re.search(r'```[^\n]*\n.*?```', text, re.S):
        parts = re.split(r'(```[^\n]*\n.*?```)', text, flags=re.S)
        return ''.join(re.sub(r'\s+', '', re.sub(r'^```[^\n]*\n|```$', '', part))
                       if part.startswith('```') else plain_md(part) for part in parts)
    code_block = text.lstrip().startswith('```')
    text = re.sub(r"(?m)^```[^\n]*\n?", "", text)
    text = re.sub(r"!\[[^\]]*\]\([^\n]+?\)", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^\n]+?\)", r"\1", text)
    text = re.sub(r"(?m)^\s*#{1,6}\s+|^\s*>\s?|^\s*[-*+]\s+|^\s*\d+\.\s+|^\s*---+\s*$", "", text)
    text = re.sub(r"(?m)^\s*\|?\s*:?-{3,}.*$", "", text)
    if not code_block:
        text = re.sub(r'(?<!\\)\*{1,2}(?=\S)(.+?)(?<=\S)\*{1,2}', r'\1', text)
    text = text.replace("```", "").replace("`", "").replace("|", "")
    return re.sub(r"\s+", "", html.unescape(text))


def html_check(run, content, source_md=None, font_override=None):
    parser = ContentParser()
    parser.feed(content)
    errors = []
    if parser.unsafe:
        errors.append("export includes unsafe/control elements: " + ",".join(set(parser.unsafe)))
    if "style=" not in content:
        errors.append("export missing inline styles")
    brief = read(Path(run) / 'brief.json', {})
    if font_override is not None:
        brief = {**brief, 'font': 'custom' if font_override=='autopilot-custom' else font_override}
    if brief.get('schema_version', 1) >= 3 and brief.get('font') != 'theme':
        selected_font = font_choice(brief.get('font', 'system'), brief.get('custom_font', ''))['stack']
        normalize_font = lambda value: re.sub(r'[\s\"\']', '', value.replace('!important', '')).lower()
        if not parser.fonts or any(normalize_font(value) != normalize_font(selected_font) for value in parser.fonts):
            errors.append('exported paragraph/heading font differs from user choice')
    md = source_md if source_md is not None else (Path(run) / "article.md").read_text(encoding="utf-8")
    # Exact visible sequence ignores aria-hidden decorations and Markdown syntax,
    # but rejects additions and reordered text as well as dropped paragraphs.
    text = re.sub(r"\s+", "", "".join(parser.texts))
    if plain_md(md) != text:
        errors.append('export dropped/changed content: visible sequence differs (added, removed, or reordered text)')
    original_code = re.findall(r'(?m)^```[^\n]*\n(.*?)^```', md, re.S)
    normalize_code = lambda value: value.replace('\r\n', '\n').strip('\n\r')
    if [normalize_code(x) for x in original_code] != [normalize_code(x) for x in parser.code_blocks]:
        errors.append('export changed code blocks or indentation')
    refs = re.findall(r"!\[[^\]]*\]\(([^)]+)\)", md)
    if len(refs) != len(parser.images):
        errors.append("export image count differs from source")
    for ref, src in zip(refs, parser.images):
        try:
            p = within(run, ref)
            if not src.startswith("data:image/") or digest(base64.b64decode(src.split(",", 1)[1])) != file_hash(p):
                errors.append("export image differs from local source: " + ref)
        except (ValueError, IndexError):
            errors.append("invalid image: " + ref)
    for link in re.findall(r"(?<!!)\[[^\]]+\]\((https?://[^)]+)\)", md):
        if link not in parser.links:
            errors.append("export dropped source link")
    if '<svg' in content.lower():
        from motion import check_html
        errors.extend(check_html(run, content).errors)
    return errors


def accept_html(run, path, backend='zhouxing-browser-clipboard'):
    run = Path(run)
    manifest = read(run / "layout.json", {})
    if manifest.get("article_sha256") != file_hash(run / "article.md"):
        raise ValueError("layout stale; rebuild final preview before export")
    content = Path(path).read_text(encoding="utf-8")
    errors = html_check(run, content)
    if errors:
        raise ValueError("; ".join(errors))
    (run / "article.html").write_text(content, encoding="utf-8")
    shell = '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>手机文章预览</title><body style="margin:0;background:#fff"><main style="max-width:677px;margin:auto">' + content + '</main></body></html>'
    (run / "mobile-preview.html").write_text(shell, encoding="utf-8")
    (run / "paste-test.html").write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>富文本粘贴验收</title><h1>富文本粘贴验收</h1><p>点击下方区域，粘贴刚复制的排版。此页不连接公众号。</p><div id="paste" contenteditable="true" aria-label="富文本测试区" style="min-height:500px;border:1px solid #aaa;max-width:677px;margin:auto"></div></html>', encoding="utf-8")
    shutil.copyfile(ROOT / 'assets/rich-import-test.html', run / 'rich-import-test.html')
    save(run / "export.json", {"article_sha256": file_hash(run / "article.md"), "html_sha256": file_hash(run / "article.html"), "backend": backend, "created_at": now()})
    return {"exported": True, "html_bytes": len(content.encode()), "wechat_paste": "not_tested"}


def fingerprint(run):
    run = Path(run)
    names = ["brief.json", "topic.json", "sources.json", "claims.json", "body.md", "images.json",
             "experiments.json", "titles.json", "article.md", "article.html", "layout.json", "export.json",
             "preview.html", "mobile-preview.html", "paste-test.html", "rich-import-test.html", "roundtrip.html", "article-meta.json"]
    if read(run / "brief.json", {}).get("schema_version", 1) >= 2:
        names += ["layout-choice.json", "outline.json", "images-plan.json", "visual-review.json"]
    if read(run / 'brief.json', {}).get('schema_version', 1) >= 3:
        names += ['intake.json', 'topic-candidates.json', 'layout-variants.json', 'layout-selection.json']
    if read(run / "brief.json", {}).get("reader_value_policy") == "reader-value-v1":
        names += ["reader-value.json", "screenshot-ledger.json"]
    if read(run / 'brief.json', {}).get('editorial_policy') == 'research-depth-v1':
        names += ['research-plan.json', 'research-log.json', 'cases.json', 'depth-review.json']
    if read(run / 'brief.json', {}).get('tutorial_policy') == 'step-screenshots-v1':
        names += ['reader-intent.json', 'tutorial-plan.json']
    if read(run / 'brief.json', {}).get('writing_style', 'khazix') != 'khazix':
        names += ['style-context.json', 'style-calibration.json', 'style-writing-review.json']
        names += list(read(run / 'style-context.json', {}).get('files', {}))
    if read(run/'brief.json',{}).get('humanizer_policy')=='humanizer-style-preserving-v1':
        names += ['writing-draft.md','humanizer-context.json','humanizer-review.json']
    if read(run/'brief.json',{}).get('tone_policy')=='dual-tone-style-preserving-v1':
        names += ['humanizer-output.md','lieflat-context.json','lieflat-review.json']
    if read(run / 'brief.json', {}).get('motion_policy') == 'article-motion-v1':
        names += ['motion-plan.json','studio-final.json','studio/latest.json','studio-assets/motion-designs.js','studio-assets/bridge.js']
        names += [x['path'] for x in read(run/'studio-final.json',{}).get('motion_assets',[])]
    hashes = {name: file_hash(run / name) for name in names}
    for image in read(run / "images.json", []):
        hashes[image["path"]] = file_hash(within(run, image["path"]))
    if read(run / 'brief.json', {}).get('editorial_policy') == 'research-depth-v1':
        for source in read(run / 'sources.json', []):
            path = source.get('read_record', {}).get('artifact_path')
            if path:
                hashes['reading:' + path] = file_hash(within(run, path))
    return {"fingerprint": digest(json.dumps(hashes, sort_keys=True).encode()), "body_sha256": hashes["body.md"], "hashes": hashes}


def audit(run):
    run = Path(run)
    errors, warnings = [], []
    brief = read(run / "brief.json", {})
    from style_library import context_ready
    try:
        context_ready(run, require_body=True)
    except (ValueError, OSError, KeyError) as exc:
        errors.append(str(exc))
    topic = read(run / "topic.json", {})
    body = (run / "body.md").read_text(encoding="utf-8") if (run / "body.md").exists() else ""
    from humanize import errors as humanizer_errors
    errors.extend(humanizer_errors(run))
    source_items = read(run / "sources.json", [])
    sources = {x["id"]: x for x in source_items}
    if len(sources) != len(source_items):
        errors.append("duplicate source ids")
    policy = presentation(brief)
    claims = read(run / "claims.json", [])
    errors.extend(presentation_errors(body, policy))
    if brief.get('editorial_policy') == 'research-depth-v1':
        from research import research_errors, title_errors, depth_errors
        for validator in (research_errors, title_errors, depth_errors):
            extra_errors, extra_warnings = validator(run)
            errors.extend(extra_errors)
            warnings.extend(extra_warnings)
    if brief.get('schema_version', 1) >= 3:
        from intake import ready, selection_current
        try:
            ready(run)
            selection_current(run)
        except ValueError as exc:
            errors.append(str(exc))
        intake = read(run / 'intake.json', {})
        if intake.get('status') != 'ready_to_write' or intake.get('topic') != brief.get('topic'):
            errors.append('writing intake missing or incomplete')
        if intake.get('writing_style') != brief.get('writing_style') or intake.get('font') != brief.get('font') or intake.get('custom_font', '') != brief.get('custom_font', ''):
            errors.append('writing style/font differs from user intake')
        if brief.get('length_preset') == 'auto' and not read(run / 'outline.json', {}).get('length_reason'):
            errors.append('free length needs a content-specific outline length_reason')
    used = evidence_ids(body, claims, policy)
    if not used or not used <= set(sources):
        errors.append("missing/unknown evidence references")
    verified = [sources[x] for x in used & set(sources) if sources[x].get("verified") and sources[x].get("kind") != "lead"]
    if len(verified) < 2 or not any(s.get("kind") == "primary" for s in verified):
        errors.append("need at least 2 verified sources, including primary evidence")
    if any(not s.get("verification_note") or not s.get("retrieved_at") for s in verified):
        errors.append("source verification trace incomplete")
    if brief.get("type") == "news":
        groups = {s.get("independence_group") for s in verified if s.get("independence_group")}
        if len(groups) < 2:
            errors.append("news requires 2 independent information origins")
        timestamp = date(brief.get("created_at"))
        fresh = [s for s in verified if s.get("kind") == "primary" and date(s.get("published_at")) and timestamp and dt.timedelta(0) <= timestamp - date(s["published_at"]) <= dt.timedelta(days=7)]
        if not fresh:
            errors.append("news lacks a verified original published in the last 7 days")
    if not claims or any(c.get("status") != "verified" or not c.get("source_ids") or
                         not set(c["source_ids"]) <= set(sources) or
                         any(not sources[x].get("verified") or sources[x].get("kind") == "lead" for x in c["source_ids"])
                         for c in claims):
        errors.append("claims ledger incomplete or cites unverified leads")
    if policy["citations"] == "internal" and any(
            not c.get("locator") or len(c.get("body_quote", "")) < 8 or c["body_quote"] not in body
            for c in claims):
        errors.append("internal claims need current body passages and locators")
    if not topic.get("angle") or not topic.get("reader_benefit"):
        errors.append("topic lacks angle/reader benefit")
    chars = prose_cjk(body) if brief.get("counting_basis") == "prose-cjk-v2" else len(re.findall(r"[\u4e00-\u9fff]", body))
    if not brief.get("min_chars", 0) <= chars <= brief.get("max_chars", 0):
        errors.append(f"body CJK count {chars} outside requested range")
    if re.search(r"TODO|\[待补\]|\[占位\]|作者[：:]\s*卡兹克|wzglyay@", body, re.I):
        errors.append("placeholder or copied author identity")
    if brief.get("type") == "practical":
        mode = brief.get("practical_mode")
        experiments = read(run / "experiments.json", [])
        if mode == "verified":
            if not experiments or any(not x.get("actions") or not x.get("observations") or not x.get("limitations") or
                                      not within(run, x.get("output_path", "")).is_file() for x in experiments):
                errors.append("verified practical article requires actual experiment records")
        elif mode == "documented":
            if "未实测" not in body or re.search(r"亲测|实测了|我用了\d", body):
                errors.append("documented tutorial must disclose 未实测 and avoid experience claims")
        else:
            errors.append("unknown practical mode")
    titles = read(run / "titles.json", {})
    candidates = titles.get("candidates", [])
    selected = next((x for x in candidates if x.get("id") == titles.get("selected")), {})
    fixed = titles.get('user_fixed', {})
    title_minimum = 1 if (fixed.get('origin') == 'user' and len(fixed.get('instruction', '')) >= 8 and
                         fixed.get('title') == selected.get('title') and brief.get('editorial_policy') == 'research-depth-v1') else 6
    if titles.get("body_sha256") != file_hash(run / "body.md") or len(candidates) < title_minimum:
        errors.append("titles missing or stale; need 6 candidates bound to body")
    for candidate in candidates:
        scores = candidate.get("scores", [])
        if len(scores) != 8 or any(not isinstance(v, (int, float)) or not 0 <= v <= cap for v, cap in zip(scores, WEIGHTS)) or not candidate.get("evidence"):
            errors.append("invalid title scoring/evidence")
            break
    if not selected or selected.get("risk") == "high" or not titles.get("digest"):
        errors.append("selected title/digest missing or high risk")
    meta = read(run / "article-meta.json", {})
    if meta.get("title") != selected.get("title") or meta.get("body_sha256") != file_hash(run / "body.md") or meta.get("sources_sha256") != file_hash(run / "sources.json"):
        errors.append("article metadata stale")
    if "presentation" in brief and meta.get("presentation") != policy:
        errors.append("article presentation changed; assemble/export again")
    images = read(run / "images.json", [])
    if not any(x.get("role") == "cover" for x in images):
        errors.append("cover missing")
    body_refs = re.findall(r"!\[[^\]]*\]\(([^)]+)\)", body)
    if len(body_refs) < explicit_image_minimum(brief):
        errors.append("body image count below plan")
    registered = {x["path"]: x for x in images}
    errors.extend(image_plan_errors(run, brief, body, body_refs))
    errors.extend(mixed_image_errors(run, brief, images, body_refs, source_items, body))
    from tutorial_visuals import tutorial_errors
    errors.extend(tutorial_errors(run, brief, body, images, body_refs))
    for ref in body_refs:
        if ref not in registered or registered[ref].get("role") != "body":
            errors.append("unregistered body image: " + ref)
    for image in images:
        if image.get("sha256") != file_hash(within(run, image["path"])) or not image.get("visually_checked") or not image.get("check_note"):
            errors.append("image changed or unchecked: " + image["path"])
    layout_info = read(run / "layout.json", {})
    export_info = read(run / "export.json", {})
    if brief.get("schema_version", 1) >= 2:
        if layout_info.get("brief_sha256") != file_hash(run / "brief.json") or layout_info.get("recommendation_sha256") != file_hash(run / "layout-choice.json"):
            errors.append("layout preferences or recommendation changed; rebuild and export")
        try:
            if layout_info.get("selected_theme") != effective_theme(run, brief):
                errors.append("exported layout differs from selected theme")
        except (ValueError, KeyError) as exc:
            errors.append(str(exc))
        outline = read(run / "outline.json", {})
        sections = outline.get("sections", [])
        if not sections or not outline.get("reader_promise") or any(not s.get("purpose") or type(s.get("target_chars")) is not int or s["target_chars"] <= 0 for s in sections):
            errors.append("missing meaningful outline with section length budgets")
        elif not brief["min_chars"] <= sum(s["target_chars"] for s in sections) <= brief["max_chars"]:
            errors.append("outline budget outside selected length")
        plan = read(run / "images-plan.json", {})
        if plan.get("body_sha256") != file_hash(run / "body.md") or not plan.get("art_direction") or not plan.get("assets"):
            errors.append("image art direction missing/stale")
        visual = read(run / "visual-review.json", {})
        for image in images:
            item = visual.get("images", {}).get(image["path"], {})
            if item.get("sha256") != image.get("sha256") or item.get("status") != "pass" or not item.get("checks"):
                errors.append("visual design review missing/stale: " + image["path"])
    if layout_info.get("article_sha256") != file_hash(run / "article.md") or layout_info.get("preview_sha256") != file_hash(run / "preview.html") or not (run / "preview.html").is_file() or layout_info.get("warnings"):
        errors.append("layout missing/stale or parsing warnings unresolved")
    if export_info.get("article_sha256") != file_hash(run / "article.md") or export_info.get("html_sha256") != file_hash(run / "article.html") or not (run / "article.html").is_file():
        errors.append("HTML export missing or stale")
    elif (run / "article.html").is_file():
        errors.extend(html_check(run, (run / "article.html").read_text(encoding="utf-8")))
    for name in ("mobile-preview.html", "paste-test.html"):
        if not (run / name).is_file() or not (run / name).read_text(encoding="utf-8").lower().startswith("<!doctype html>"):
            errors.append("missing/invalid delivery page: " + name)
    current = fingerprint(run)
    review = read(run / "review.json", {})
    if review.get("fingerprint") != current["fingerprint"]:
        errors.append("semantic/visual review missing or stale")
    review_keys = REVIEW_KEYS + (("length_depth", "layout_fit", "visual_design") if brief.get("schema_version", 1) >= 2 else ())
    for key in review_keys:
        item = review.get("checks", {}).get(key, {})
        if item.get("status") != "pass" or len(item.get("reason", "")) < 8:
            errors.append("review incomplete: " + key)
    methods = {key: review.get('checks', {}).get(key, {}) for key in ('rich_paste', 'rich_import')}
    if not any(item.get('status') == 'pass' and len(item.get('reason', '')) >= 8 for item in methods.values()):
        errors.append('rich text round-trip unverified: need actual paste OR HTML import in isolated editor')
    if methods['rich_import'].get('status') == 'pass':
        if not (run / 'roundtrip.html').is_file():
            errors.append('HTML import review missing actual editor roundtrip.html')
        else:
            errors.extend(html_check(run, (run / 'roundtrip.html').read_text(encoding='utf-8')))
    if methods['rich_paste'].get('status') != 'pass':
        warnings.append('Browser clipboard rich paste not verified; local HTML import is a separate test')
    if brief.get('motion_policy') == 'article-motion-v1':
        from motion import validate as validate_motion
        try:
            plan=read(run/'motion-plan.json',{})
            validate_motion(run,plan)
            if not plan['enabled'] and read(run/'layout-selection.json',{}).get('selection_backend')!='studio-saved-final':
                errors.append('Static final requires the user choice saved from preview')
        except (ValueError,KeyError) as exc:
            errors.append(str(exc))
        item=review.get('checks',{}).get('motion_design',{})
        if item.get('status')!='pass' or len(item.get('reason',''))<8:
            errors.append('Motion placement, readability and static alternative need actual review')
    if review.get("wechat_paste") != "pass":
        warnings.append("WeChat editor paste not verified")
    for phrase in ("说白了", "本质上", "换句话说", "这意味着", "综上所述"):
        if phrase in body:
            warnings.append("voice phrase to review: " + phrase)
    for paragraph in body.split("\n\n"):
        if len(re.findall(r"[\u4e00-\u9fff]", paragraph)) > 110 and not paragraph.startswith(("|", "```")):
            warnings.append("long mobile paragraph")
            break
    if brief.get("reader_value_policy") == "reader-value-v1":
        from reader_value import errors as reader_errors
        errors.extend(reader_errors(run))
        if (run / "screenshot-ledger.json").is_file():
            from screenshot_plan import check as capture_check
            errors.extend(capture_check(run, read(run / "screenshot-ledger.json", []))["errors"])
    report = {"schema_version": 1, "passed": not errors, "scope": "local-editorial-package", "fingerprint": current["fingerprint"],
              "checked_at": now(), "body_cjk_chars": chars, "errors": errors, "warnings": warnings,
              "rich_paste": methods['rich_paste'].get('status', 'not_tested'), "rich_import": methods['rich_import'].get('status', 'not_tested'),
              "wechat_paste": review.get("wechat_paste", "not_tested"), "review_sha256": file_hash(run / "review.json")}
    save(run / "quality.json", report)
    return report


def status(run):
    run = Path(run)
    brief = read(run / 'brief.json', {})
    saved=read(run/'studio/latest.json',{})
    if saved:
        from studio_state import selection_current as studio_selection_current
        try:studio_selection_current(run)
        except ValueError as exc:
            return {'complete':False,'next':'studio-save-and-user-confirmation','studio_revision':saved['revision'],'reason':str(exc)}
    current = fingerprint(run)
    quality = read(run / "quality.json", {})
    stages = [("discovery", "discovery.json"), ("evidence", "claims.json"), ("writing", "body.md"),
              ("images", "images.json"), ("layout", "layout.json"), ("titles", "titles.json"),
              ("export", "export.json"), ("review", "review.json")]
    if brief.get('schema_version', 1) >= 3:
        from intake import ready, selection_current, account_path
        try:
            intake = ready(run)
        except ValueError as exc:
            return {'complete': False, 'next': 'pre-writing-questions', 'reason': str(exc)}
        if intake.get('topic_mode') == 'own':
            stages = [item for item in stages if item[0] != 'discovery']
        if (run / 'article.md').is_file() and (run / 'titles.json').is_file():
            try:
                selection_current(run)
            except ValueError as exc:
                if brief.get('studio_policy')=='saved-final-v1':
                    return {'complete':False,'next':'studio-save-and-user-confirmation','studio_revision':read(run/'studio/latest.json',{}).get('revision'),'reason':str(exc)}
                return {'complete': False, 'next': 'layout-selection' if (run / 'layout-variants.json').is_file() else 'layout-previews', 'reason': str(exc)}
    missing = [stage for stage, file in stages if not (run / file).is_file()]
    stale = quality.get("fingerprint") != current["fingerprint"] or quality.get("review_sha256") != file_hash(run / "review.json")
    complete = quality.get("passed") and not stale and not missing
    discovery = read(run / "discovery.json", {})
    discover_errors = discovery.get("errors", [])
    no_leads = not discovery.get("candidates") and not any(x.get("data", {}).get("items") for x in discovery.get("responses", []))
    if no_leads and not (run / "sources.json").is_file() and discovery:
        return {"complete": False, "stale_audit": stale, "missing": missing, "next": "discovery-retry-or-import",
                "errors": discover_errors or ["no candidate topics returned"]}
    next_step = "complete" if complete else (missing[0] if missing else "audit/repair")
    if complete and brief.get('schema_version', 1) >= 3 and brief.get('profile', {}).get('output_mode') != 'local':
        receipt = read(run / 'draft-receipt.json', {})
        if receipt.get('status') != 'saved_verified' or receipt.get('fingerprint') != current['fingerprint']:
            next_step = 'push-draft' if account_path(brief['workspace']).is_file() else 'first-account-connection'
    return {"complete": bool(complete), "stale_audit": stale, "missing": missing,
            "next": next_step, "errors": quality.get("errors", []),
            "pending_verifications": [name for name in ('rich_paste', 'wechat_paste') if quality.get(name) != 'pass']}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("doctor", "init", "preferences"):
        s = sub.add_parser(name)
        s.add_argument("--workspace", default=".")
        s.add_argument("--profile")
        if name == "init":
            s.add_argument("--type", choices=("news", "practical"), default="news")
            s.add_argument("--topic", default="AI")
            s.add_argument("--length", choices=("light", "standard", "deep", "auto"))
            s.add_argument("--chars", nargs=2, type=int, metavar=("MIN", "MAX"))
            s.add_argument("--theme")
            s.add_argument("--visual-style", choices=("cinematic-editorial", "editorial", "product-photo", "clear-diagram"))
    for name in ("discover", "diagnose-aihot", "assemble", "layout", "layout-previews", "accept-html", "fingerprint", "audit", "status", "register-image", "check-images", "configure", "recommend-layout"):
        s = sub.add_parser(name)
        s.add_argument("--run", required=True, type=Path)
        if name == "discover":
            s.add_argument("--query")
        if name == "configure":
            s.add_argument("--length", choices=("light", "standard", "deep", "auto"))
            s.add_argument("--chars", nargs=2, type=int, metavar=("MIN", "MAX"))
            s.add_argument("--theme")
            s.add_argument("--visual-style", choices=("cinematic-editorial", "editorial", "product-photo", "clear-diagram"))
            s.add_argument("--citations", choices=("internal", "inline"))
            s.add_argument("--image-captions", choices=("none", "labeled"))
            s.add_argument('--font', choices=('system', 'kai', 'song', 'yahei', 'pingfang', 'theme', 'custom'))
            s.add_argument('--custom-font')
        if name == "recommend-layout":
            s.add_argument("--theme", required=True)
            s.add_argument("--reason", required=True)
        if name == "accept-html":
            s.add_argument("--file", required=True, type=Path)
            s.add_argument("--backend", choices=('zhouxing-browser-clipboard', 'zhouxing-button-dom'), default='zhouxing-browser-clipboard')
        if name == "register-image":
            s.add_argument("--file", required=True, type=Path)
            s.add_argument("--role", required=True, choices=("cover", "body"))
            s.add_argument("--prompt", required=True)
            s.add_argument("--backend", choices=("native", "configured", "user-supplied", "screenshot"), default="native")
            s.add_argument("--checked", action="store_true")
            s.add_argument("--note", default="")
            s.add_argument("--actual-model")
            s.add_argument("--provenance", type=Path, help="Browser capture or actual successful generation JSON")
    a = p.parse_args()
    try:
        if a.cmd == "doctor":
            from onboard import doctor
            result = doctor(a.workspace)
        elif a.cmd == "init":
            result = init(a.workspace, a.type, a.topic, a.profile, a.length, a.chars, a.theme, a.visual_style)
        elif a.cmd == "preferences":
            result = preferences(a.workspace, a.profile)
        elif a.cmd == "configure":
            result = configure(a.run, a.length, a.chars, a.theme, a.visual_style, a.citations, a.image_captions, a.font, a.custom_font)
        elif a.cmd == "recommend-layout":
            result = recommend_layout(a.run, a.theme, a.reason)
        elif a.cmd == "register-image":
            result = register_image(a.run, a.file, a.role, a.prompt, a.backend, a.checked, a.note, a.actual_model, a.provenance)
        elif a.cmd == "discover":
            result = discover(a.run, a.query)
        elif a.cmd == "accept-html":
            result = accept_html(a.run, a.file, a.backend)
        else:
            stage = "layout" if a.cmd in ("layout", "layout-previews", "assemble", "accept-html") else "preflight"
            from operations import measure
            with measure(a.run, stage):
                result = globals()[a.cmd.replace("-", "_")](a.run)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2 if (a.cmd == "audit" and not result["passed"]) or (a.cmd == "discover" and result["errors"]) or (a.cmd == 'diagnose-aihot' and result['status'] != 'ok') else 0
    except (ValueError, KeyError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
