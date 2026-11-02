"""Validate a distributable file set; exclude personal state by construction."""
import argparse
import hashlib
import json
from pathlib import Path
import re

TOP_FILES = {'SKILL.md', 'LICENSE', 'VERSION', 'CHANGELOG.md', 'THIRD_PARTY_NOTICES.md'}
TOP_DIRS = {'agents', 'assets', 'references', 'scripts', 'tests'}
SKIP = {'__pycache__', '.cache', '.git', 'node_modules', '.venv'}
PRIVATE = {'.wechat-ai', '.wechat-tools', 'browser-profile', 'runs', 'wechat-ai-runs'}


def files(root):
    root = Path(root).resolve()
    result = []
    for file in sorted(root.rglob('*')):
        rel = file.relative_to(root)
        if any(part in SKIP for part in rel.parts) or file.suffix in ('.pyc', '.tmp'):
            continue
        if file.is_symlink() or not file.resolve().is_relative_to(root):
            raise ValueError('Symlink or external path not distributable: ' + rel.as_posix())
        if not file.is_file():
            continue
        if rel.as_posix() == 'distribution-manifest.json':
            continue
        if any(part in PRIVATE for part in rel.parts) or file.name == '.env' or re.match(r'(?i)(cookies|session|account|credentials)\.(json|txt)$', file.name):
            raise ValueError('Personal state found inside skill: ' + rel.as_posix())
        if rel.parts[0] not in TOP_DIRS and rel.as_posix() not in TOP_FILES:
            raise ValueError('Unexpected top-level file: ' + rel.as_posix())
        if file.suffix in ('.md', '.py', '.cjs', '.js', '.json', '.yaml', '.txt'):
            text = file.read_text(encoding='utf8', errors='replace')
            if re.search(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|ghp_[A-Za-z0-9]{36}(?![A-Za-z0-9])', text):
                raise ValueError('Credential-like content requires review: ' + rel.as_posix())
        result.append(file)
    return result


def check(root):
    root = Path(root).resolve()
    problems = []
    for name in TOP_FILES:
        if not (root / name).is_file():
            problems.append('Missing release file: ' + name)
    if (root / 'VERSION').is_file() and not re.fullmatch(r'\d+\.\d+\.\d+(?:-[a-z0-9.]+)?', (root / 'VERSION').read_text().strip()):
        problems.append('Invalid version')
    for vendor in ('humanizer', 'writing-dna-skill', 'x-tweet-fetcher', 'agent-reach', 'lieflat-less-ai-tone'):
        if not (root / 'references/vendor' / vendor / 'LICENSE').is_file():
            problems.append('Missing vendor license: ' + vendor)
    try:
        selected = files(root)
    except ValueError as error:
        problems.append(str(error))
        selected = []
    broken = []
    for file in selected:
        if file.suffix != '.md' or 'vendor' in file.relative_to(root).parts:
            continue
        prose = re.sub(r'`[^`]*`', '', file.read_text(encoding='utf8'))
        for target in re.findall(r'\]\(([^)]+)\)', prose):
            target = target.split('#', 1)[0]
            if not target or re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:', target) or target.startswith(('/', '<', 'PATH', 'RUN')):
                continue
            resolved = (file.parent / target).resolve()
            if not resolved.exists():
                broken.append(file.relative_to(root).as_posix() + ': ' + target)
    problems.extend('Broken local reference: ' + x for x in broken)
    manifest = {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in selected}
    if (root / 'distribution-manifest.json').is_file():
        try:
            shipped = json.loads((root / 'distribution-manifest.json').read_text(encoding='utf8'))
            if shipped.get('files') != manifest:
                problems.append('Installed files differ from distribution manifest')
        except (ValueError, OSError):
            problems.append('Invalid distribution manifest')
    return {'passed': not problems, 'errors': problems, 'file_count': len(selected),
            'manifest': manifest,
            'limits': 'File-set and obvious credential checks; not a comprehensive security or license audit.'}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    p.add_argument('--out', type=Path)
    a = p.parse_args()
    result = check(a.root)
    if a.out:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf8')
    print(json.dumps({k: v for k, v in result.items() if k != 'manifest'}, ensure_ascii=False))
    raise SystemExit(0 if result['passed'] else 2)
