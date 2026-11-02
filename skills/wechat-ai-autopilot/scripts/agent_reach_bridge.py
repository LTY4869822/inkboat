"""Project-local Agent Reach runtime and bounded, read-only upstream calls."""
import argparse
import datetime
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parents[1]

def paths(workspace):
    ws=Path(workspace).resolve(); venv=ws/'.wechat-tools/search-venv'
    return {'workspace':ws,'venv':venv,
        'python':venv/('Scripts/python.exe' if os.name=='nt' else 'bin/python'),
        'bin':venv/('Scripts' if os.name=='nt' else 'bin'),
        'node_dir':ws/'.wechat-tools/agent-reach-node',
        'mcporter':ws/'.wechat-tools/agent-reach-node/node_modules/mcporter/dist/cli.js',
        'config':ws/'.wechat-tools/agent-reach-node/mcporter.json'}

def execute(arguments, workspace, timeout=45, proxy=None):
    p=paths(workspace); env=os.environ.copy()
    env['PYTHONIOENCODING']='utf-8'
    env['PATH']=str(p['bin'])+os.pathsep+str(p['node_dir']/'node_modules/.bin')+os.pathsep+env.get('PATH','')
    if proxy:
        env['HTTP_PROXY']=proxy; env['HTTPS_PROXY']=proxy
    try:
        result=subprocess.run([str(x) for x in arguments],cwd=p['workspace'],env=env,
            capture_output=True,text=True,encoding='utf8',errors='replace',timeout=timeout)
        try: payload=json.loads(result.stdout)
        except json.JSONDecodeError: payload={'text':result.stdout}
        return {'observed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
                'returncode':result.returncode,'payload':payload,
                'stderr':result.stderr[:1500],
                'scope':'Actual read-only invocation; results remain leads until read and verified'}
    except subprocess.TimeoutExpired:
        return {'returncode':1,'error':'timeout','limit_seconds':timeout,
                'action':'Stop this backend attempt and use host search/browser; do not repeat automatically'}

def setup(workspace):
    p=paths(workspace)
    pin=json.loads((ROOT/'references/vendor/agent-reach/provenance.json').read_text(encoding='utf8'))
    if not p['python'].is_file():
        p['venv'].parent.mkdir(parents=True,exist_ok=True)
        subprocess.run([sys.executable,'-m','venv',str(p['venv'])],check=True)
    url='https://github.com/Panniantong/Agent-Reach/archive/'+pin['commit']+'.zip'
    uv=shutil.which('uv')
    command=[uv,'--cache-dir',str(p['workspace']/'.wechat-tools/uv-cache'),'pip','install','--python',str(p['python']),url] if uv else [str(p['python']),'-m','pip','install',url]
    subprocess.run(command,cwd=p['workspace'],check=True)
    npm=shutil.which('npm.cmd' if os.name=='nt' else 'npm')
    node=shutil.which('node')
    if not npm or not node: raise ValueError('Node/npm missing; Agent Reach installed but Exa requires a host Node runtime')
    # npm.cmd cannot be started with shell=False on Windows. Invoke npm's actual
    # JavaScript entrypoint with Node; never build a shell command from input.
    npm_script=Path(npm).parent/'node_modules/npm/bin/npm-cli.js'
    command=[node,str(npm_script)] if os.name=='nt' else [npm]
    subprocess.run(command+['install','--prefix',str(p['node_dir']),'--save-exact','mcporter@'+pin['mcporter_version']],check=True,cwd=p['workspace'])
    configure(workspace)
    return {'installed':True,'pinned_commit':pin['commit'],'scope':'Isolated runtime; no system install or credential import'}

def configure(workspace,proxy=None):
    p=paths(workspace)
    p['config'].parent.mkdir(parents=True,exist_ok=True)
    if not p['config'].exists():
        # Dedicated explicit config prevents importing editor/account secrets.
        p['config'].write_text(json.dumps({'mcpServers':{'exa':{'baseUrl':'https://mcp.exa.ai/mcp'}}},indent=2),encoding='utf8')
    if proxy:
        parsed=urlsplit(proxy)
        if parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError('Supply a trusted HTTP proxy without credentials in the URL')
        (p['workspace']/'.wechat-tools/agent-reach-network.json').write_text(json.dumps({'exa_proxy':proxy,'scope':'Public Exa queries only; explicitly authorized by user'},indent=2),encoding='utf8')

def run(command,workspace,query=None,url=None,limit=5):
    p=paths(workspace)
    if not p['python'].is_file(): raise ValueError('Search runtime missing; run setup after installation authorization')
    if command=='doctor':
        result=execute([p['python'],'-m','agent_reach.cli','doctor','--json'],workspace,timeout=60)
        result['scope']='Upstream capability/configuration snapshot; unprobed channels are not marked connected'
        return result
    if command=='read':
        if not url: raise ValueError('--url required')
        # Use upstream's audited URL normalization, response-size cap and
        # challenge detection. No browser profile, account cookies or login.
        code='import json,sys; from agent_reach.channels.web import WebChannel; text=WebChannel().read(sys.argv[1]); print(json.dumps({"text":text},ensure_ascii=False))'
        return execute([p['python'],'-c',code,url],workspace)
    if command=='search':
        if not query or not query.strip(): raise ValueError('--query required')
        if not p['mcporter'].is_file(): raise ValueError('Exa runtime missing; install pinned mcporter locally')
        if not p['config'].is_file(): raise ValueError('Dedicated Exa config missing; run configure')
        node=shutil.which('node')
        if not node: raise ValueError('Node runtime unavailable')
        args=json.dumps({'query':query,'numResults':min(10,max(1,limit))},ensure_ascii=False)
        network=p['workspace']/'.wechat-tools/agent-reach-network.json'
        proxy=json.loads(network.read_text(encoding='utf8')).get('exa_proxy') if network.is_file() else None
        command=[node]+(['--use-env-proxy'] if proxy else [])+[p['mcporter'],'--config',p['config'],'call','exa.web_search_exa','--args',args,'--timeout','35000']
        result=execute(command,workspace,proxy=proxy)
        payload=result.get('payload',{})
        if isinstance(payload,dict) and payload.get('isError'):result['returncode']=1
        status={'observed_at':result.get('observed_at'),'returncode':result['returncode'],'backend':'Exa via mcporter','proxy_authorized':bool(proxy),
                'scope':'Actual query transport; returned items still need original-source reading'}
        (p['workspace']/'.wechat-tools/agent-reach-exa-status.json').write_text(json.dumps(status,indent=2),encoding='utf8')
        return result
    raise ValueError('Unknown read-only command')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('setup','configure','doctor','search','read'))
    parser.add_argument('--workspace',type=Path,default=Path('.'))
    parser.add_argument('--query'); parser.add_argument('--url'); parser.add_argument('--limit',type=int,default=5)
    parser.add_argument('--proxy',help='Only with configure, after explicit user authorization; no credential-bearing URL')
    parser.add_argument('--output',type=Path)
    a=parser.parse_args()
    try:
        if a.command=='setup': value=setup(a.workspace)
        elif a.command=='configure': configure(a.workspace,a.proxy); value={'configured':True,'account_credentials':False,'exa_proxy':bool(a.proxy)}
        else: value=run(a.command,a.workspace,a.query,a.url,a.limit)
        if a.output:
            a.output.parent.mkdir(parents=True,exist_ok=True)
            a.output.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf8')
        print(json.dumps(value,ensure_ascii=False,indent=2))
        return int(value.get('returncode',0)!=0)
    except (OSError,ValueError,subprocess.CalledProcessError) as exc:
        print(json.dumps({'error':str(exc)},ensure_ascii=False)); return 1

if __name__=='__main__':raise SystemExit(main())
