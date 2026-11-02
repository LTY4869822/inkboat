"""Check public repository boundaries and local Markdown references (not a full security audit)."""
import json,re,sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DIRS={'skills','docs','examples','scripts','.github'}
FILES={'README.md','LICENSE','.gitignore','.gitattributes','CONTRIBUTING.md','SECURITY.md','CHANGELOG.md'}
SKIP={'.git','node_modules','__pycache__','.venv','dist','artifacts'}
PRIVATE={'.wechat-ai','.wechat-tools','browser-profile','wechat-ai-runs','wechat-tutorial-writer'}
PATTERNS={
 'private-key':r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
 'github-token':r'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{50,})',
 'personal-account-id':r'\bgh_[a-z0-9]{12}\b',
 'personal-windows-path':r'[A-Za-z]:[/\\]Users[/\\][^\s\n"<>]+',
 'wechat-session-link':r'mp\.weixin\.qq\.com/[^\s"<>]*[?&](?:token|tempkey)=',
}

def check():
    errors=[];checked=0
    for p in ROOT.rglob('*'):
        rel=p.relative_to(ROOT)
        if rel.parts[0].startswith('.inkboat-demo') or any(s in SKIP for s in rel.parts):continue
        if p.is_symlink():errors.append(f'{rel}: symlink not allowed');continue
        if not p.is_file():continue
        checked+=1
        if any(s in PRIVATE for s in rel.parts) or p.name in ('.env','cookies.json','credentials.json','session.json','account.json'):
            errors.append(f'{rel}: private runtime file')
        if rel.parts[0] not in DIRS and rel.as_posix() not in FILES:errors.append(f'{rel}: unexpected public file')
        if p.suffix.lower() not in ('.md','.py','.js','.cjs','.json','.yml','.yaml','.txt'):continue
        text=p.read_text(encoding='utf-8',errors='replace')
        for name,pattern in PATTERNS.items():
            if re.search(pattern,text):errors.append(f'{rel}: {name}')
        if p.suffix=='.md' and 'vendor' not in rel.parts:
            prose=re.sub(r'`[^`]*`','',text)
            for dest in re.findall(r'\]\(([^)]+)\)',prose):
                dest=dest.split('#',1)[0]
                if not dest or re.match(r'^[A-Za-z][A-Za-z0-9+.-]*:',dest) or dest.startswith(('/','<','PATH','RUN')):continue
                target=(p.parent/dest).resolve()
                if not target.is_relative_to(ROOT) or not target.exists():errors.append(f'{rel}: broken/local-outside reference {dest}')
    return {'passed':not errors,'checked_files':checked,'errors':errors,'limits':'File boundaries, selected credential patterns and local links only; not a complete security/license audit.'}
if __name__=='__main__':
    result=check();print(json.dumps(result,ensure_ascii=False,indent=2));sys.exit(0 if result['passed'] else 1)
