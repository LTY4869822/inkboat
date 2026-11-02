"""Prepare and verify WeChat draft transfers. Browser actions belong to the host.

This module never logs in, stores credentials, sends requests, or publishes.
Images are mapped to actual WeChat URLs. Four verified SVG card variants receive
ID-free replay transport; approved text, CSS and immutable studio files stay intact.
"""
import argparse
import base64
import html
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

import workflow as w


def current(run):
    quality = w.read(run / 'quality.json', {})
    fp = w.fingerprint(run)['fingerprint']
    if not quality.get('passed') or quality.get('fingerprint') != fp:
        raise ValueError('Local quality failed or is stale; export, review and audit first')
    if quality.get('review_sha256') != w.file_hash(run / 'review.json'):
        raise ValueError('Local review changed; audit first')
    return fp


def image_url(url):
    parts = urlsplit(url)
    if parts.scheme != 'https' or parts.hostname != 'mmbiz.qpic.cn' or parts.username or parts.password:
        raise ValueError('Use the image URL actually returned by the WeChat upload UI')
    if any(k in parts.query.lower() for k in ('access_token', 'token=', 'secret', 'ticket')):
        raise ValueError('Do not store authentication information in image URLs')
    return url


def image_identity(url):
    """WeChat switches /0 originals to /640 display renditions after saving."""
    parts = urlsplit(image_url(url))
    return parts.hostname + parts.path.rsplit('/', 1)[0]


def prepare(run, account, authorization=None, account_id=None):
    run = Path(run).resolve()
    if w.read(run / 'brief.json', {}).get('schema_version', 1) >= 3:
        from intake import ready, selection_current
        ready(run)
        selection_current(run)
    if authorization is None:
        from intake import draft_authorization
        authorization = draft_authorization(run, account, account_id)
    if not account.strip() or not authorization.strip():
        raise ValueError('Need the observed account name and the actual user authorization')
    fp = current(run)
    meta = w.read(run / 'article-meta.json', {})
    content = (run / 'article.html').read_text(encoding='utf-8')
    errors = w.html_check(run, content)
    if errors:
        raise ValueError('; '.join(errors))
    images = w.read(run / 'images.json', [])
    cover = [x for x in images if x['role'] == 'cover']
    if len(cover) != 1:
        raise ValueError('Exactly one approved cover is required')
    receipt = w.read(run / 'draft-receipt.json', {})
    journal = w.read(run / 'browser-publish-journal.json', {})
    if receipt.get('account') and receipt['account'] != account:
        raise ValueError('Existing draft belongs to a different account; select a separate run')
    result = dict(schema_version=1, status='prepared', account=account,
                  authorization=authorization, account_id=account_id, fingerprint=fp,
                  html_sha256=w.file_hash(run / 'article.html'), title=meta['title'],
                  digest=meta.get('digest', ''), cover=cover[0]['path'],
                  cover_sha256=w.file_hash(w.within(run, cover[0]['path'])),
                  images=[{'path': x['path'], 'sha256': x['sha256']} for x in images if x['role'] == 'body'],
                  existing_draft_id=receipt.get('draft_id') or journal.get('draft_id'), created_at=w.now())
    from motion import check_html
    svg=check_html(run,content)
    final=w.read(run/'studio-final.json',{})
    extras=final.get('motion_assets',[])
    known={x['sha256'] for x in result['images']}
    result['images'] += [x for x in extras if x['sha256'] not in known]
    if svg.images and not extras:
        raise ValueError('SVG image originals missing; save/adopt the actual studio version first')
    parsed=w.ContentParser();parsed.feed(content)
    result.update(studio_revision=final.get('revision'),motion_enabled=bool(svg.animations),image_occurrences=len(parsed.all_images))
    w.save(run / 'draft-transfer.json', result)
    return result


def locked(run):
    manifest = w.read(run / 'draft-transfer.json', {})
    if (Path(run)/'studio-final.json').is_file():
        from studio_state import selection_current
        selection_current(run)
    if not manifest.get('authorization') or manifest.get('fingerprint') != current(run):
        raise ValueError('Transfer approval is absent or stale; apply the latest user instruction to the current final')
    if manifest.get('html_sha256') != w.file_hash(run / 'article.html'):
        raise ValueError('Approved HTML changed')
    if manifest.get('transport_html_sha256') and manifest['transport_html_sha256'] != w.file_hash(Path(run)/'wechat-transfer.html'):
        raise ValueError('Verified transport HTML changed')
    if manifest.get('motion_transport_sha256') and manifest['motion_transport_sha256'] != w.file_hash(Path(run)/'wechat-motion-transport.json'):
        raise ValueError('Motion transport record changed')
    return manifest


def transfer(run, mapping):
    manifest = locked(run)
    mapped = {x['sha256']: image_url(x['url']) for x in mapping}
    if len(mapped) != len(mapping):
        raise ValueError('Duplicate image mappings')
    approved = {x['sha256'] for x in manifest['images']}
    if set(mapped) != approved:
        raise ValueError('Uploaded image map must match all approved body images')
    for item in manifest['images']:
        if w.file_hash(w.within(run, item['path'])) != item['sha256']:
            raise ValueError('Approved image changed')
    source = (run / 'article.html').read_text(encoding='utf-8')
    seen = []
    def replace(match):
        payload = html.unescape(match.group(3))
        if not payload.startswith('data:image/'):
            raise ValueError('Expected an embedded approved source image')
        sha = w.digest(base64.b64decode(payload.split(',', 1)[1], validate=True))
        if sha not in mapped:
            raise ValueError('Embedded image was not uploaded')
        seen.append(sha)
        return match.group(1) + match.group(2) + html.escape(mapped[sha], quote=True) + match.group(2)
    result = re.sub(r'''(<(?:img\b[^>]*\bsrc|image\b[^>]*\b(?:xlink:href|href))\s*=\s*)(["'])(.*?)(?:\2)''', replace, source, flags=re.I | re.S)
    if len(seen) != manifest.get('image_occurrences',len(manifest['images'])) or set(seen) != approved:
        raise ValueError('Image count differs from approved final')
    from motion_transport import adapt, VERSION
    image_mapped = result
    result, cards = adapt(image_mapped)
    (run / 'wechat-transfer-before-compat.html').write_text(image_mapped, encoding='utf-8')
    (run / 'wechat-transfer.html').write_text(result, encoding='utf-8')
    transport = {'schema_version': 1, 'adapter_version': VERSION,
                 'approved_html_sha256': manifest['html_sha256'],
                 'image_mapped_html_sha256': w.file_hash(run/'wechat-transfer-before-compat.html'),
                 'transport_html_sha256': w.file_hash(run/'wechat-transfer.html'),
                 'converted_cards': sum(x['converted'] for x in cards), 'cards': cards,
                 'limits': ['Only quote, three-node steps, comparison and conclusion single-play variants tested in actual WeChat reader; other variants need reader verification'],
                 'created_at': w.now()}
    w.save(run/'wechat-motion-transport.json', transport)
    manifest.update(transport_html_sha256=transport['transport_html_sha256'],
                    motion_transport_sha256=w.file_hash(run/'wechat-motion-transport.json'),
                    motion_reader_gate=bool(cards), motion_card_count=len(cards))
    w.save(run/'draft-transfer.json', manifest)
    w.save(run / 'wechat-images.json', mapping)
    return {'status': 'ready_to_paste', 'chars': len(result), 'images': len(seen),
            'html_sha256': w.file_hash(run / 'wechat-transfer.html')}


class Styles(HTMLParser):
    def __init__(self):
        super().__init__()
        self.styles = []
    def handle_starttag(self, tag, attrs):
        style = dict(attrs).get('style', '')
        if style:
            # Exported computed CSS has simple declarations; reject changed values,
            # while accepting insignificant spaces around semicolons and colons.
            declarations = {}
            for item in style.split(';'):
                if ':' in item:
                    key, value = item.split(':', 1)
                    declarations[key.strip().lower()] = re.sub(r'\s+', ' ', value.strip())
            self.styles.append(declarations)


def compare(source, remote):
    a, b = w.ContentParser(), w.ContentParser()
    a.feed(source)
    b.feed(remote)
    normalize = lambda p: re.sub(r'\s+', '', ''.join(p.texts))
    sa, sb = Styles(), Styles()
    sa.feed(source)
    sb.feed(remote)
    ai = [image_identity(x) for x in a.all_images if x]
    bi = [image_identity(x) for x in b.all_images if x]
    from motion import check_html
    ma,mb=check_html(Path('.'),source),check_html(Path('.'),remote)
    signature=lambda p:[(tag,{k:v for k,v in attrs.items() if k in ('attributename','type','values','keytimes','dur','repeatcount','fill','begin','restart')}) for tag,attrs in p.animations]
    return {'text_sequence': normalize(a) == normalize(b),
            'code_blocks': [x.replace('\r\n', '\n').strip('\r\n') for x in a.code_blocks]
            == [x.replace('\r\n', '\n').strip('\r\n') for x in b.code_blocks],
            'inline_styles': bool(sa.styles) and sa.styles == sb.styles,
            'image_order': ai == bi, 'image_count': len(ai),
            'styled_nodes': len(sa.styles), 'links': a.links == b.links,
            'safe_content': not b.unsafe and not mb.errors,
            'motion_structure': ma.svg==mb.svg and signature(ma)==signature(mb)}


def verify(run, account, draft_id, observed_path, remote_path, proof_path, save_observation):
    manifest = locked(run)
    if account != manifest['account'] or not draft_id or not save_observation.strip():
        raise ValueError('Need the same observed account, actual draft ID and save result')
    proof = w.within(run, proof_path)
    if not proof.is_file() or proof.stat().st_size == 0:
        raise ValueError('Need a screenshot of the actual saved/reopened draft')
    observed = w.read(w.within(run, observed_path), {})
    checks = compare((run / 'wechat-transfer.html').read_text(encoding='utf-8'),
                     w.within(run, remote_path).read_text(encoding='utf-8'))
    checks.update(title=observed.get('title') == manifest['title'],
                  digest=observed.get('digest') == manifest['digest'],
                  images_loaded=len(observed.get('images', [])) == checks['image_count']
                  and all(x.get('complete') and x.get('w', 0) > 1 and str(x.get('src','')).startswith('https://mmbiz.qpic.cn/') for x in observed.get('images', [])),
                  cover_present=bool(observed.get('cover')))
    if manifest.get('motion_enabled'):
        checks['motion_observed']=observed.get('motion',{}).get('status')=='pass' and len(observed.get('motion',{}).get('note',''))>=8
    if manifest.get('motion_enabled') and manifest.get('motion_reader_gate'):
        reader=observed.get('motion',{}).get('reader',{})
        tests=reader.get('cards',[])
        checks['motion_reader_replay']=(reader.get('status')=='pass'
            and reader.get('auto_finished_before_click') is True
            and len(tests)==manifest.get('motion_card_count', 0)
            and bool(tests) and all(t.get('background_replay') is True and t.get('second_replay') is True for t in tests))
    passed = all(v for k, v in checks.items() if k not in ('image_count', 'styled_nodes'))
    receipt = {'schema_version': 1, 'status': 'saved_verified' if passed else 'saved_needs_review',
               'account': account, 'draft_id': draft_id, 'published': False,
               'fingerprint': manifest['fingerprint'], 'checks': checks,
               'save_observation': save_observation, 'proof': proof_path,
               'remote_html_sha256': w.file_hash(w.within(run, remote_path)),
               'verified_at': w.now(),
               'limits': ['HTML normalization and WeChat image rendition compression are accepted; not byte-identical',
                          'Desktop editor/local mobile preview checked; actual phone dark mode still needs user preview']}
    w.save(run / 'draft-receipt.json', receipt)
    return receipt


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    for command in ('prepare', 'transfer', 'verify'):
        s = sub.add_parser(command)
        s.add_argument('--run', required=True, type=Path)
        if command == 'prepare':
            s.add_argument('--account', required=True)
            s.add_argument('--authorization')
            s.add_argument('--account-id', help='Observed public original ID; required for remembered-account automatic draft')
        elif command == 'transfer':
            s.add_argument('--image-map', required=True, type=Path)
        else:
            s.add_argument('--account', required=True)
            s.add_argument('--draft-id', required=True)
            s.add_argument('--observed', default='wechat-observed.json')
            s.add_argument('--remote', default='wechat-reopened.html')
            s.add_argument('--proof', default='wechat-draft-proof.png')
            s.add_argument('--save-observation', required=True)
    args = p.parse_args()
    try:
        if args.command == 'prepare':
            result = prepare(args.run, args.account, args.authorization, args.account_id)
        elif args.command == 'transfer':
            result = transfer(args.run, w.read(args.image_map, []))
        else:
            result = verify(args.run, args.account, args.draft_id, args.observed,
                            args.remote, args.proof, args.save_observation)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2 if result.get('status') == 'saved_needs_review' else 0
    except (ValueError, KeyError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({'error': str(exc)}, ensure_ascii=False))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
