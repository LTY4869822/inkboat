"""Portable discovery, X material capability checks and public Bilibili metadata."""
import argparse, datetime, importlib.metadata, json, os, pathlib, shutil, subprocess, sys

def locate(name, workspace):
    folder = pathlib.Path(workspace)/'.wechat-tools/search-venv'
    candidates = [folder/'Scripts'/(name+'.exe'), folder/'bin'/name]
    if name in ('opencli',):
        candidates += [pathlib.Path(workspace)/'.wechat-tools/agent-reach-node/node_modules/.bin'/(name+'.cmd' if sys.platform=='win32' else name)]
    return next((str(p.resolve()) for p in candidates if p.is_file()), shutil.which(name))

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=['doctor','bilibili-search','bilibili-video'])
    p.add_argument('--workspace', default='.')
    p.add_argument('--keyword');p.add_argument('--bvid');p.add_argument('--limit',type=int,default=5)
    p.add_argument('--output'); a=p.parse_args()
    now=datetime.datetime.now(datetime.timezone.utc).isoformat()
    if a.command=='doctor':
        from x_fetch import doctor as x_doctor
        try:x_info=x_doctor(a.workspace)
        except ValueError:x_info={'installed':True,'configuration':'invalid; review XTF_NITTER without exposing credentials'}
        result={'observed_at':now,'platform':sys.platform,'commands':{n:locate(n,a.workspace) for n in ['bili','opencli','agent-reach','yt-dlp']},'x_tweet_fetcher':x_info,'note':'Executable availability is not connectivity. Windows detection uses shutil.which, not sh. Known X tweet URLs use bundled x_fetch.py; X search needs configured Nitter or host search/browser. Douyin/XHS require a separately verified backend.'}
    else:
        executable=locate('bili',a.workspace)
        if not executable: p.error('bilibili-cli missing; install official PyPI bilibili-cli into a workspace venv first')
        # Only these two audited public commands are exposed. No login, subtitle, comments,
        # user history or write flags; bilibili-cli 0.6.2 sends credential=None for both.
        if a.command=='bilibili-search':
            if not a.keyword:p.error('--keyword required')
            args=['search',a.keyword,'--type','video','--max',str(min(20,max(1,a.limit))),'--json']
        else:
            import re
            if not a.bvid or not re.fullmatch(r'BV[0-9A-Za-z]{10}',a.bvid):p.error('valid --bvid required')
            args=['video',a.bvid,'--json']
        child_env=os.environ.copy();child_env['PYTHONIOENCODING']='utf-8'
        try:
            command=[executable,*args]
            if a.command=='bilibili-video':
                # CLI normalizes away pubdate. Public SDK metadata preserves it.
                interpreter=pathlib.Path(executable).parent/('python.exe' if sys.platform=='win32' else 'python')
                child_code='import asyncio,json,sys; from bili_cli import client; d=asyncio.run(client.get_video_info(sys.argv[1], credential=None)); keys=("bvid","title","pubdate","desc","duration","owner","stat","pages","copyright"); print(json.dumps({"ok":True,"data":{k:d.get(k) for k in keys}},ensure_ascii=False))'
                if not interpreter.is_file():p.error('metadata needs the venv Python next to bili')
                command=[str(interpreter),'-c',child_code,a.bvid]
            proc=subprocess.run(command,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=45,env=child_env)
            try: payload=json.loads(proc.stdout)
            except json.JSONDecodeError: payload={'ok':False,'error':{'code':'invalid_json','message':proc.stderr[:1200] or proc.stdout[:1200]}}
            execution={'method':'cli','arguments':args} if a.command=='bilibili-search' else {'method':'public_sdk','call':'bili_cli.client.get_video_info','bvid':a.bvid,'credential':None}
            result={'observed_at':now,'backend':'bilibili-cli','execution':execution,'returncode':proc.returncode,'result':payload,'scope':'Public video metadata/search only; no browser cookies read; no video/transcript comprehension asserted.'}
        except subprocess.TimeoutExpired:
            result={'observed_at':now,'backend':'bilibili-cli','result':{'ok':False,'error':{'code':'timeout','message':'45-second bounded query expired; switch to host search/browser, do not loop.'}}}
    if a.output:
        out=pathlib.Path(a.output);out.parent.mkdir(parents=True,exist_ok=True)
        out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))
    if a.command!='doctor' and not result['result'].get('ok'):sys.exit(1)

if __name__=='__main__':main()
