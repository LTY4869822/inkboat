"""Draft-only official API transport and route preflight. No desktop control.

Credentials are read from environment; never saved or printed. Browser numeric
appmsgid and API media_id are intentionally different namespaces.
"""
import argparse
import base64
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import mimetypes
import os
from pathlib import Path
import re
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

import draft_bridge as bridge
import workflow as w

API = 'https://api.weixin.qq.com'
# Project guard, not a claim about all current account/API limits.
HTML_GUARD = 20000


class ApiError(RuntimeError):
    def __init__(self, code):
        self.code = code
        super().__init__('WeChat API error code ' + str(code))


class UncertainWrite(RuntimeError):
    pass


def credentials():
    return (os.getenv('WECHAT_APP_ID') or os.getenv('WECHAT_APPID'),
            os.getenv('WECHAT_APP_SECRET') or os.getenv('WECHAT_APPSECRET'))


def motion_gate(source):
    """Only the four actually observed variants are stable publication presets."""
    from motion_transport import adapt
    # A full local preview can contain JS template strings with <svg> examples;
    # they are not rendered article cards. Publishing HTML is separately checked.
    source=re.sub(r'<(?:script|style)\b[^>]*>[\s\S]*?</(?:script|style)>','',source,flags=re.I)
    transformed, cards = adapt(source)
    errors = []
    for raw in re.findall(r'<svg\b[\s\S]*?</svg>', transformed):
        if not re.search(r'<animate(?:Transform)?\b', raw):
            continue
        if 'url(#' in raw or re.search(r'\w+\.(?:click|touchstart|begin|end)', raw):
            errors.append('SVG references an ID that WeChat may remove')
        if re.search(r'(?:href|xlink:href)=["\']#', raw):
            errors.append('SVG animation target depends on an ID')
        label = re.search(r'aria-label=["\']([^"\']*)', raw)
        name = label.group(1).split('：')[-1] if label else ''
        if name not in ('引文显影', '步骤接力', '双栏对照', '结论收束'):
            errors.append('Motion preset is experimental; it needs its own reader test')
        if re.search(r'repeatCount=["\'](?!1["\'])', raw):
            errors.append('Loop variant has not been verified on WeChat')
        for begin in re.findall(r'\bbegin=["\']([^"\']*)', raw):
            if 'click' not in begin or 'touchstart' not in begin:
                errors.append('Missing replay event after autoplay ends')
    return {'status': 'pass' if not errors else 'blocked',
            'cards': len(cards), 'errors': sorted(set(errors)),
            'scope': 'Static preflight; actual saved reader playback is still required'}


def plan(run, html_guard=HTML_GUARD, workspace=None):
    run = Path(run).resolve()
    manifest = bridge.locked(run)
    original = (run/'article.html').read_text(encoding='utf8')
    transport = (run/'wechat-transfer.html')
    source = transport.read_text(encoding='utf8') if transport.is_file() else original
    # Estimate after embedding is replaced by a normal remote URL.
    estimate = len(re.sub(r'data:image/[^"\'\s]+', 'https://mmbiz.qpic.cn/'+'x'*180, source))
    app, secret = credentials()
    blockers = []
    if not app or not secret:
        blockers.append('api_credentials_missing')
    else:
        workspace=Path(workspace or w.read(run/'brief.json',{}).get('workspace') or run.parent)
        binding=w.read(workspace/'.wechat-ai/api-account.json',{})
        if (binding.get('account_key')!=hashlib.sha256(app.encode()).hexdigest()
                or binding.get('account_id')!=manifest.get('account_id')):
            blockers.append('api_account_not_bound')
    for item in manifest.get('images',[]):
        asset=w.within(run,item['path'])
        if asset.suffix.lower() not in ('.png','.jpg','.jpeg') or asset.stat().st_size>1024*1024:
            blockers.append('body_asset_exceeds_project_api_format_or_size_guard')
            break
    if manifest.get('motion_enabled') or re.search(r'<animate(?:Transform)?\b', source):
        blockers.append('native_svg_motion_requires_browser_reader')
    if estimate > html_guard:
        blockers.append('html_exceeds_project_api_guard')
    receipt = w.read(run/'draft-receipt.json', {})
    api_receipt = w.read(run/'api-draft-receipt.json', {})
    if (receipt.get('draft_id') or manifest.get('existing_draft_id')) and not api_receipt.get('media_id'):
        blockers.append('existing_web_draft_has_no_api_media_id')
    gate = motion_gate(source)
    return {'schema_version': 1, 'status': 'ready' if gate['status']=='pass' else 'blocked',
            'route': 'official_api' if not blockers else 'browser_dom',
            'api_blockers': blockers, 'api_credentials_present': bool(app and secret),
            'html_chars_after_image_mapping_estimate': estimate,
            'api_html_guard': html_guard, 'motion': gate,
            'fingerprint': manifest['fingerprint'],
            'existing_web_draft': bool(receipt.get('draft_id') or manifest.get('existing_draft_id')),
            'scope': 'API permission/IP and browser login require live checks; GUI is not the default fallback'}


class Client:
    def __init__(self, app_id, secret, timeout=20):
        if not app_id or not secret:
            raise ValueError('Set WECHAT_APP_ID and WECHAT_APP_SECRET locally')
        self.app_id, self.secret, self.timeout = app_id, secret, timeout
        self._token, self._expires = None, 0
        self._lock = threading.Lock()

    def raw(self, route, data=None, content_type='application/json', authenticated=True):
        if route not in ('/cgi-bin/token', '/cgi-bin/draft/count', '/cgi-bin/draft/add',
                         '/cgi-bin/draft/update', '/cgi-bin/draft/get', '/cgi-bin/draft/batchget',
                         '/cgi-bin/media/uploadimg', '/cgi-bin/material/add_material'):
            raise ValueError('Only documented draft/material endpoints are allowed')
        params = {}
        if authenticated:
            params['access_token'] = self.token()
        else:
            params = {'grant_type':'client_credential', 'appid':self.app_id, 'secret':self.secret}
        if route.endswith('/add_material'):
            params['type'] = 'image'
        body = json.dumps(data, ensure_ascii=False).encode('utf8') if isinstance(data, dict) else data
        request = urllib.request.Request(API+route+'?'+urllib.parse.urlencode(params),
                                        data=body, headers={'Content-Type':content_type})
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                result = json.load(response)
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as error:
            # Exception strings often contain a URL/token: never forward them.
            raise ConnectionError('WeChat request failed; no authentication data logged') from None
        if result.get('errcode', 0):
            raise ApiError(result['errcode'])
        return result

    def token(self):
        with self._lock:
            if self._token and self._expires > time.monotonic():
                return self._token
            result = self.raw('/cgi-bin/token', authenticated=False)
            if not result.get('access_token'):
                raise ValueError('WeChat returned no access token')
            self._token = result['access_token']
            self._expires = time.monotonic() + max(0, result.get('expires_in',7200)-120)
            return self._token

    def upload(self, filename, cover=False):
        filename = Path(filename)
        mime = mimetypes.guess_type(filename.name)[0]
        if mime not in ('image/png','image/jpeg'):
            raise ValueError('API image route currently accepts approved PNG/JPEG only; no GIF flattening')
        boundary = 'wechat-'+uuid.uuid4().hex
        # No filename from untrusted Markdown is interpolated into headers.
        ext = '.png' if mime=='image/png' else '.jpg'
        body = (f'--{boundary}\r\nContent-Disposition: form-data; name="media"; filename="asset{ext}"\r\n'
                f'Content-Type: {mime}\r\n\r\n').encode()+filename.read_bytes()+f'\r\n--{boundary}--\r\n'.encode()
        return self.raw('/cgi-bin/material/add_material' if cover else '/cgi-bin/media/uploadimg',
                        body, 'multipart/form-data; boundary='+boundary)


def _save(path, data):
    path = Path(path)
    temp = path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8')
    temp.replace(path)


def publish_api(run, workspace, client=None, html_guard=HTML_GUARD):
    run=Path(run).resolve(); lock=run/'api-publish.lock'
    try:
        fd=os.open(lock,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    except FileExistsError:
        raise ValueError('Another upload or a crashed process holds the run lock; inspect journal before clearing') from None
    try:
        with os.fdopen(fd,'w',encoding='utf8') as stream:
            json.dump({'pid':os.getpid(),'created_at':w.now()},stream)
        return _publish_api(run,workspace,client,html_guard)
    finally:
        lock.unlink(missing_ok=True)


def _publish_api(run, workspace, client=None, html_guard=HTML_GUARD):
    run, workspace = Path(run).resolve(), Path(workspace).resolve()
    selection = plan(run, html_guard, workspace)
    if selection['status']!='ready' or selection['route']!='official_api':
        raise ValueError('API preflight blocked: '+', '.join(selection['api_blockers']+selection['motion']['errors']))
    manifest = bridge.locked(run)
    client = client or Client(*credentials())
    journal_path = run/'api-publish-journal.json'
    journal = w.read(journal_path,{})
    account_key = hashlib.sha256(client.app_id.encode()).hexdigest()
    binding=w.read(workspace/'.wechat-ai/api-account.json',{})
    if binding.get('account_key')!=account_key or binding.get('account_id')!=manifest.get('account_id') or not manifest.get('account_id'):
        raise ValueError('Bind the observed AppID to the approved public account ID before API upload')
    if journal.get('account_key') and journal['account_key'] != account_key:
        raise ValueError('Journal belongs to another API account')
    if journal.get('status')=='write_in_flight':
        raise UncertainWrite('Previous write outcome is unknown. Use recover; never create again blindly')
    # Live read-only connectivity check before uploading. Does not prove add permission.
    client.raw('/cgi-bin/draft/count')
    prior = w.read(run/'api-draft-receipt.json',{})
    media_id = prior.get('media_id') or journal.get('media_id')
    if prior.get('account_key') and prior['account_key']!=account_key:
        raise ValueError('API receipt belongs to another account')
    if journal.get('status') in ('written','readback_pass') and journal.get('fingerprint')==manifest['fingerprint']:
        return readback(run, client, journal['media_id'], manifest, account_key)
    cache_path = workspace/'.wechat-ai'/('api-assets-'+account_key+'.json')
    cache_path.parent.mkdir(parents=True,exist_ok=True)
    cache = w.read(cache_path,{})
    asset_lock = threading.Lock()
    def asset(item, cover=False):
        filename=w.within(run,item['path'])
        if w.file_hash(filename)!=item['sha256']:
            raise ValueError('Approved image changed')
        key=('cover:' if cover else 'body:')+item['sha256']
        if key in cache:
            if not cover: bridge.image_url(cache[key]['url'])
            return cache[key]
        result=client.upload(filename,cover)
        if cover and not result.get('media_id'): raise ValueError('No cover media ID returned')
        if not cover: bridge.image_url(result.get('url',''))
        # Only public asset identifiers, never token/cookie.
        keep={k:result[k] for k in ('url','media_id') if k in result}
        with asset_lock:
            cache[key]=keep
            _save(cache_path,cache)
        return keep
    started=time.monotonic()
    unique={x['sha256']:x for x in manifest['images']}
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures={sha:pool.submit(asset,item) for sha,item in unique.items()}
        cover_future=pool.submit(asset,{'path':manifest['cover'],'sha256':manifest['cover_sha256']},True)
        mapping=[{'sha256':sha,'url':future.result()['url']} for sha,future in futures.items()]
        cover=cover_future.result()
    bridge.transfer(run,mapping)
    content=(run/'wechat-transfer.html').read_text(encoding='utf8')
    if len(content)>html_guard: raise ValueError('Actual mapped HTML exceeds project API guard; use browser')
    meta=w.read(run/'article-meta.json',{})
    article={'title':manifest['title'],'digest':manifest['digest'],'content':content,'thumb_media_id':cover['media_id']}
    if meta.get('author'): article['author']=meta['author']
    # No comment/original/publication switches are changed implicitly.
    bridge.locked(run)
    journal={'schema_version':1,'status':'write_in_flight','account_key':account_key,
             'fingerprint':manifest['fingerprint'],'media_id':media_id,
             'html_sha256':w.file_hash(run/'wechat-transfer.html'), 'started_at':w.now(),
             'cover_media_id':cover['media_id']}
    _save(journal_path,journal)
    try:
        if media_id:
            client.raw('/cgi-bin/draft/update',{'media_id':media_id,'index':0,'articles':article})
        else:
            result=client.raw('/cgi-bin/draft/add',{'articles':[article]})
            media_id=result.get('media_id')
            if not media_id: raise ConnectionError('No draft identifier returned')
    except ApiError as error:
        journal.update(status='write_rejected',error_code=error.code)
        _save(journal_path,journal)
        raise
    except ConnectionError:
        raise UncertainWrite('Write response lost. Journal retained; recover before any repeat') from None
    journal.update(status='written',media_id=media_id,elapsed_seconds=round(time.monotonic()-started,3))
    _save(journal_path,journal)
    return readback(run,client,media_id,manifest,account_key)


def readback(run, client, media_id, manifest, account_key):
    result=client.raw('/cgi-bin/draft/get',{'media_id':media_id})
    articles=result.get('news_item',[])
    if len(articles)!=1: raise ValueError('Unexpected draft article count; no overwrite')
    article=articles[0]
    source=(run/'wechat-transfer.html').read_text(encoding='utf8')
    checks=bridge.compare(source,article.get('content',''))
    checks.update(title=article.get('title')==manifest['title'],digest=article.get('digest','')==manifest['digest'])
    journal=w.read(run/'api-publish-journal.json',{})
    checks['cover_identity']=article.get('thumb_media_id')==journal.get('cover_media_id')
    passed=all(v for k,v in checks.items() if k not in ('image_count','styled_nodes'))
    (run/'api-reopened.html').write_text(article.get('content',''),encoding='utf8')
    receipt={'status':'saved_needs_review','api_readback_status':'pass' if passed else 'fail',
             'account_key':account_key,'account':manifest['account'],'media_id':media_id,
             'fingerprint':manifest['fingerprint'],'checks':checks,'published':False,'verified_at':w.now(),
             'limits':['API readback is not a rendered reader check; crop, loaded images and reader still need verification']}
    _save(run/'api-draft-receipt.json',receipt)
    journal.update(status='readback_pass' if passed else 'readback_fail',media_id=media_id)
    _save(run/'api-publish-journal.json',journal)
    return receipt


def recover(run, client):
    """Read-only reconciliation. Unique exact match only; never creates drafts."""
    run=Path(run).resolve(); manifest=bridge.locked(run)
    journal=w.read(run/'api-publish-journal.json',{})
    account_key=hashlib.sha256(client.app_id.encode()).hexdigest()
    if journal.get('account_key')!=account_key: raise ValueError('Recovery account mismatch')
    if journal.get('media_id'):
        return readback(run,client,journal['media_id'],manifest,account_key)
    if journal.get('status')!='write_in_flight': raise ValueError('No ambiguous write to recover')
    if journal.get('html_sha256')!=w.file_hash(run/'wechat-transfer.html'): raise ValueError('Recovery content changed')
    matches=[]; source=(run/'wechat-transfer.html').read_text(encoding='utf8')
    # Bounded recent scan; missing result requires manual inspection, not retry add.
    for offset in (0,20,40):
        result=client.raw('/cgi-bin/draft/batchget',{'offset':offset,'count':20,'no_content':0})
        for item in result.get('item',[]):
            articles=item.get('content',{}).get('news_item',[])
            if len(articles)!=1: continue
            article=articles[0]
            if article.get('title')!=manifest['title'] or article.get('digest','')!=manifest['digest']: continue
            if article.get('thumb_media_id')!=journal.get('cover_media_id'): continue
            checks=bridge.compare(source,article.get('content',''))
            if all(v for k,v in checks.items() if k not in ('image_count','styled_nodes')):
                matches.append(item['media_id'])
        if len(result.get('item',[]))<20: break
    matches=list(set(matches))
    if len(matches)!=1: raise UncertainWrite('Recovery found zero or multiple matches; inspect existing drafts, do not create')
    journal.update(status='written',media_id=matches[0]);_save(run/'api-publish-journal.json',journal)
    return readback(run,client,matches[0],manifest,account_key)


def deliver(run, workspace):
    from operations import measure
    with measure(run, "draft_transport"):
        return _deliver(run, workspace)


def _deliver(run, workspace):
    """One draft-only entry point; ambiguous writes never trigger cross-route retry."""
    selected=plan(run,workspace=workspace)
    if selected['status']!='ready':raise ValueError('Motion preflight blocked; fix/review before upload')
    if selected['route']=='official_api':
        try:
            return publish_api(run,workspace)
        except ApiError as error:
            journal=w.read(Path(run)/'api-publish-journal.json',{})
            if error.code not in (40164,48001) or journal.get('status')=='write_in_flight':raise
            api_existing=w.read(Path(run)/'api-draft-receipt.json',{}).get('media_id')
            web_existing=w.read(Path(run)/'draft-receipt.json',{}).get('draft_id')
            if api_existing and not web_existing:
                raise ValueError('Existing API draft needs its actual web draft identity before browser fallback') from None
            # Explicit IP/permission refusal, not a lost response. No new API
            # draft exists from this attempt. UI must still verify same account.
    browser=Path(__file__).with_name('browser_draft.cjs')
    try:
        process=subprocess.run([os.getenv('NODE_EXE','node'),str(browser),'push',
                                '--workspace',str(Path(workspace).resolve()),'--run',str(Path(run).resolve())],
                               capture_output=True,text=True,encoding='utf8',timeout=240,
                               env={**os.environ,'PYTHON_EXE':os.sys.executable,'PYTHONIOENCODING':'utf-8'})
    except subprocess.TimeoutExpired:
        raise UncertainWrite('Browser deadline exceeded. Inspect stage/journal and same draft before repeating') from None
    # Worker emits a small JSON result; never forwards raw trace/URL/stderr.
    lines=[x for x in process.stdout.splitlines() if x.strip()]
    try:result=json.loads(lines[-1]) if lines else json.loads(process.stderr.splitlines()[-1])
    except (ValueError,IndexError):raise ValueError('Browser failed; inspect local state without printing session data') from None
    if process.returncode:raise ValueError(result.get('error','Browser connection/calibration required'))
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('plan','doctor','push','deliver','recover','bind-api','motion-check'))
    parser.add_argument('--run',type=Path)
    parser.add_argument('--workspace',type=Path,default=Path.cwd())
    parser.add_argument('--account-id',help='Public gh_ID observed together with this AppID in the account settings')
    parser.add_argument('--html',type=Path,help='Unapproved local preview HTML for read-only motion preflight')
    args=parser.parse_args()
    try:
        if args.command=='motion-check':
            if not args.html: parser.error('--html is required')
            result=motion_gate(args.html.read_text(encoding='utf8'))
        elif args.command=='bind-api':
            app,secret=credentials()
            if not app or not secret or not args.account_id or not re.fullmatch(r'gh_[A-Za-z0-9_]+',args.account_id):
                raise ValueError('Need locally configured credentials and the actually observed public gh_ID')
            target=args.workspace/'.wechat-ai/api-account.json';target.parent.mkdir(parents=True,exist_ok=True)
            _save(target,{'account_key':hashlib.sha256(app.encode()).hexdigest(),'account_id':args.account_id,'observed_at':w.now()})
            result={'status':'bound','account_id':args.account_id,'scope':'Requires actual UI observation; bind-api is not an identity discovery tool'}
        elif args.command=='doctor':
            app,secret=credentials()
            if not app or not secret:
                result={'status':'not_configured','missing':['WECHAT_APP_ID','WECHAT_APP_SECRET'],'network_attempted':False}
            else:
                Client(app,secret).raw('/cgi-bin/draft/count')
                result={'status':'read_probe_pass','scope':'Token/IP and draft/count passed; add permission not yet proven'}
        else:
            if not args.run: parser.error('--run is required')
            if args.command=='plan': result=plan(args.run,workspace=args.workspace)
            elif args.command=='deliver': result=deliver(args.run,args.workspace)
            elif args.command=='push': result=publish_api(args.run,args.workspace)
            else: result=recover(args.run,Client(*credentials()))
        print(json.dumps(result,ensure_ascii=False,indent=2))
    except (ValueError,ApiError,UncertainWrite,ConnectionError) as error:
        print(json.dumps({'status':'blocked','error':str(error)},ensure_ascii=False));raise SystemExit(1)


if __name__=='__main__': main()
