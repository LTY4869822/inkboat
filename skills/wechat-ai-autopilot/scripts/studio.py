"""Portable local article studio. Saving is local; only Agent confirmation adopts a final."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import socket
import sys
import threading
import uuid
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit,parse_qs,unquote
sys.dont_write_bytecode=True
import workflow as w
import motion
import studio_state as state
LOCK=threading.Lock()

class StudioServer(ThreadingHTTPServer):
    allow_reuse_address=False
    def server_bind(self):
        if hasattr(socket,'SO_EXCLUSIVEADDRUSE'):
            self.socket.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1)
        return super().server_bind()

def workspace(run):return Path(w.read(Path(run)/'brief.json')['workspace']).resolve()
def personal_folder(run):return workspace(run)/'.wechat-ai/layout-library'
def library(run):
    folder=personal_folder(run);folder.mkdir(parents=True,exist_ok=True)
    return [w.read(p) for p in sorted(folder.glob('*.json'))]

def build_working(run,markdown):
    run=Path(run).resolve();work=run/'studio/work';work.mkdir(parents=True,exist_ok=True)
    for ref in re.findall(r'!\[[^\]]*\]\(([^)]+)\)',markdown):
        image=w.within(run,ref)
        if not image.is_file() or image.suffix.lower() not in ('.png','.jpg','.jpeg','.gif','.webp','.svg'):
            raise ValueError('配图必须是本稿已有的图片；新增图片请先交由Agent放入文章素材')
    (work/'article.md').write_text(markdown,encoding='utf8')
    if (run/'assets').is_dir():shutil.copytree(run/'assets',work/'assets',dirs_exist_ok=True)
    brief={**w.read(run/'brief.json'),'motion_policy':motion.POLICY}
    original=w.read(run/'motion-plan.json',{})
    if original and w.file_hash(work/'article.md')==w.file_hash(run/'article.md'):
        motion.validate(run,original);w.save(work/'motion-plan.json',original)
    else:motion.plan(work,force=True)
    summary=w.build_layout(work,brief,w.effective_theme(run,brief),run/'studio/site/rendered.html')
    if summary.get('warnings'):raise ValueError('正文存在排版警告：'+str(summary['warnings']))
    return summary

def prepare(run):
    run=Path(run).resolve();site=run/'studio/site';site.mkdir(parents=True,exist_ok=True)
    source=w.ROOT/'assets/studio'
    for name in ('index.html','studio.css','studio.js','motion-designs.js','motion-lab.html','motion-lab.css','motion-lab.js','paste-test.html'):
        shutil.copy2(source/name,site/name)
    shutil.copytree(source/'backgrounds',site/'backgrounds',dirs_exist_ok=True)
    previous=state.latest(run);source_hash=w.file_hash(run/'article.md')
    working=(run/'article.md').read_text(encoding='utf8')
    if previous and (previous.get('source_hash')==source_hash or previous.get('markdown_sha256')==source_hash):working=(state.paths(run,previous['revision'])/'article.md').read_text(encoding='utf8')
    unsaved=w.read(run/'studio/dirty.json',{})
    if unsaved.get('dirty') and unsaved.get('revision')==previous.get('revision',0) and unsaved.get('source_hash')==source_hash:
        working=unsaved.get('markdown',working)
    build_working(run,working)
    shutil.copy2(w.ROOT/'assets/preferences.json',site/'catalog.json')
    result={'schema_version':2,'run':str(run),'source_hash':source_hash,'markdown':working,'revision':previous.get('revision',0),'saved':previous or None,'recommended_theme':w.effective_theme(run,w.read(run/'brief.json')),'title':w.read(run/'article-meta.json',{}).get('title','当前文章'),'motion_library_count':len(motion.KINDS),'created_at':w.now()}
    w.save(run/'studio/session.json',result)
    return {'prepared':True,'studio':str(site/'index.html'),'revision':result['revision'],'motion_library_count':len(motion.KINDS)}

def validate_theme_definition(run,theme):
    dep=w.skill_paths(workspace(run),w.read(Path(run)/'brief.json').get('profile'))['zhouxing-paiban-wx']
    if not dep:raise ValueError('周行依赖缺失')
    spec=importlib.util.spec_from_file_location('studio_theme_validator',Path(dep)/'scripts/validate_theme.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    theme={**theme,'id':theme.get('id','personal-theme'),'order':200,'default':False}
    problems=module.validate_theme(theme,Path(theme['id']+'.json'),learned=True)
    if problems or re.search(r'<|url\s*\(|@media|position\s*:\s*fixed',theme.get('css',''),re.I):raise ValueError('; '.join(problems) or '不支持的主题CSS')
    return theme

def validate_design(run,payload):
    snapshot=payload.get('snapshot',{})
    theme=validate_theme_definition(run,{**payload.get('theme',{}),'id':'personal-'+uuid.uuid4().hex})
    name=theme.get('name','').strip()
    if not 1<=len(name)<=24 or any(x['theme']['name']==name for x in library(run)):raise ValueError('名称需1—24字，且不能与已有模板重名')
    # Templates store visual choices, never this article's quotes or images.
    saved={k:snapshot.get(k) for k in ('schema_version','baseThemeId','accent','font','typeOverrides','styleSelections','spacingOverrides')}
    saved['themeOverride']=theme
    saved['motion_preset']={'enabled':snapshot.get('motion',{}).get('enabled',True),'kinds':[i['kind'] for i in snapshot.get('motion',{}).get('items',[])]}
    return {'schema_version':2,'theme':theme,'snapshot':saved,'saved_at':w.now()}

class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*args,**kwargs):super().__init__(*args,directory=str(args[2].run),**kwargs)
    def log_message(self,*args):pass
    def reply(self,status,data):
        data=json.dumps(data,ensure_ascii=False).encode();self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
    def allowed(self):return self.headers.get('Host')==f'127.0.0.1:{self.server.server_port}'
    def translate_path(self,path):
        path=unquote(urlsplit(path).path).lstrip('/') or 'studio/site/index.html'
        target=(self.server.run/path).resolve()
        safe=target.is_relative_to(self.server.run) and (path.startswith(('studio/site/','studio/work/studio-assets/','studio-assets/','assets/','layouts/')) or path in ('preview.html','layout-gallery.html','mobile-preview.html'))
        return str(target if safe else self.server.run/'studio/site/not-found')
    def do_GET(self):
        if not self.allowed():return self.reply(403,{'error':'仅限本机预览'})
        path=urlsplit(self.path).path;run=self.server.run
        if path=='/':
            self.send_response(302);self.send_header('Location','/studio/site/index.html');self.send_header('Cache-Control','no-store');self.send_header('Content-Length','0');self.end_headers();return
        if path=='/api/session':
            session=w.read(run/'studio/session.json');last=state.latest(run);unsaved=w.read(run/'studio/dirty.json',{})
            current=not last or session['source_hash'] in (last.get('source_hash'),last.get('markdown_sha256'))
            active=current and unsaved.get('dirty') and unsaved.get('revision')==last.get('revision',0) and unsaved.get('source_hash')==session['source_hash']
            saved_markdown=(state.paths(run,last['revision'])/'article.md').read_text(encoding='utf8') if last and current else session['markdown']
            return self.reply(200,{**session,'markdown':unsaved.get('markdown',saved_markdown) if active else saved_markdown,'unsaved':unsaved if active else None,'revision':last.get('revision',0),'saved':last if current else None,'source_changed':not current})
        if path=='/api/library':return self.reply(200,{'designs':library(run)})
        if path=='/api/history':return self.reply(200,{'revisions':[{'revision':r['revision'],'saved_at':r['saved_at'],'content_changed':r['content_changed']} for p in sorted((run/'studio/revisions').glob('*/record.json')) if (r:=w.read(p))]})
        if path=='/api/version':
            try:
                n=int(parse_qs(urlsplit(self.path).query)['revision'][0]);folder=state.paths(run,n);record=w.read(folder/'record.json')
                if not record:raise ValueError('版本不存在')
                return self.reply(200,{'record':record,'markdown':(folder/'article.md').read_text(encoding='utf8')})
            except (ValueError,KeyError):return self.reply(400,{'error':'版本不存在'})
        if path=='/api/info':return self.reply(200,{'version':'article-studio-v2','motion_count':len(motion.KINDS),'pid':os.getpid()})
        return super().do_GET()
    def do_POST(self):
        origin=f'http://127.0.0.1:{self.server.server_port}';run=self.server.run
        if not self.allowed() or self.headers.get('Origin')!=origin or self.headers.get('Content-Type','').split(';')[0]!='application/json':return self.reply(403,{'error':'需要本机同源操作'})
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<=32_000_000:raise ValueError('保存内容为空或过大')
            payload=json.loads(self.rfile.read(length))
            with LOCK:
                if self.path=='/api/save':return self.reply(200,state.save_version(run,payload))
                if self.path=='/api/dirty':w.save(run/'studio/dirty.json',{'dirty':bool(payload.get('dirty')),'revision':payload.get('revision'),'source_hash':payload.get('source_hash'),'snapshot':payload.get('snapshot'),'markdown':payload.get('markdown'),'updated_at':w.now()});return self.reply(200,{'recorded':True})
                if self.path=='/api/render':
                    markdown=payload.get('markdown','')
                    if not isinstance(markdown,str) or not markdown.strip() or len(markdown)>200000:raise ValueError('正文为空或过长')
                    result=build_working(run,markdown);return self.reply(200,{'rendered':True,'warnings':result.get('warnings',[])})
                if self.path=='/api/designs':
                    item=validate_design(run,payload);w.save(personal_folder(run)/(item['theme']['id']+'.json'),item);return self.reply(200,{'design':item})
                return self.reply(404,{'error':'未知操作'})
        except (ValueError,KeyError,TypeError) as exc:return self.reply(409 if '窗口' in str(exc) or 'Agent已' in str(exc) else 400,{'error':str(exc)})
        except Exception as exc:return self.reply(500,{'error':'保存失败：'+str(exc)[:180]})

def serve(run,port):
    run=Path(run).resolve()
    server=StudioServer(('127.0.0.1',port),Handler);server.run=run
    try:prepare(run)
    except Exception:
        server.server_close();raise
    url=f'http://127.0.0.1:{server.server_port}/studio/site/index.html'
    w.save(run/'studio/server.json',{'url':url,'port':server.server_port,'pid':os.getpid(),'skill_root':str(w.ROOT),'started_at':w.now()})
    print(json.dumps({'url':url,'motion_gallery':url.replace('index.html','motion-lab.html'),'run':str(run)},ensure_ascii=False),flush=True);server.serve_forever()

def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    for name in ('prepare','serve','status','adopt'):
        p=sub.add_parser(name);p.add_argument('--run',required=True,type=Path)
        if name=='serve':p.add_argument('--port',type=int,default=0)
        if name=='adopt':p.add_argument('--revision',required=True,type=int);p.add_argument('--decision',required=True)
    args=parser.parse_args()
    if args.command=='prepare':result=prepare(args.run)
    elif args.command=='serve':return serve(args.run,args.port)
    elif args.command=='adopt':result=state.adopt(args.run,args.revision,args.decision)
    else:
        last=state.latest(args.run)
        result={'saved':{k:last.get(k) for k in ('revision','saved_at','content_changed','html_sha256')},'unsaved_changes':w.read(args.run/'studio/dirty.json',{}).get('dirty',False),'server':w.read(args.run/'studio/server.json',{}),'next':'等待用户确认保存版本，然后adopt；保存按钮不授予草稿权限'}
    print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':
    try:main()
    except (ValueError,OSError) as exc:print(json.dumps({'error':str(exc)},ensure_ascii=False),file=sys.stderr);raise SystemExit(1)
