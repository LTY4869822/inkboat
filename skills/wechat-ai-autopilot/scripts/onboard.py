"""Read-only capability inventory and opt-in local preferences. Never logs secrets."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import workflow as w


def runtime_probe(runtime=None):
    runtime = runtime or {}
    node = os.getenv('NODE_EXE') or runtime.get('node_executable') or shutil.which('node')
    module = os.getenv('PLAYWRIGHT_MODULE_PATH') or runtime.get('playwright_module_path')
    browser = os.getenv('WECHAT_BROWSER_EXECUTABLE') or runtime.get('browser_executable')
    result = {'node': 'missing', 'playwright': 'missing', 'pngjs': 'missing', 'browser': 'unknown'}
    if not node:
        return result
    code = r'''const p=require('path');let result={node:process.version};
for(const name of ['playwright','pngjs']){try{const loc=process.argv[1]?p.join(p.dirname(process.argv[1]),name):name;const pkg=require(p.join(loc,'package.json'));result[name]=pkg.version;
if(name==='playwright'){const fs=require('fs');result.bundled_browser=fs.existsSync(require(loc).chromium.executablePath());}}catch{result[name]='missing';}}
console.log(JSON.stringify(result));'''
    try:
        process = subprocess.run([node, '-e', code, module or ''], capture_output=True,
                                 text=True, encoding='utf8', timeout=10)
        if process.returncode == 0:
            result.update(json.loads(process.stdout))
    except (OSError, ValueError, subprocess.TimeoutExpired):
        result['node'] = 'probe_failed'
    chrome = []
    if os.name == 'nt':
        chrome = [Path(os.environ.get(key, '')) / 'Google/Chrome/Application/chrome.exe'
                  for key in ('PROGRAMFILES', 'PROGRAMFILES(X86)', 'LOCALAPPDATA') if os.environ.get(key)]
    if browser and Path(browser).is_file():
        result['browser'] = 'executable_present_not_launched'
    elif result.get('bundled_browser') or any(p.is_file() for p in chrome) or shutil.which('google-chrome') or Path('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome').is_file():
        result['browser'] = 'executable_present_not_launched'
    result['node_supported'] = result['node'].startswith('v') and int(result['node'].split('.')[0][1:]) >= 20
    return result


def doctor(workspace, capabilities=None, probe=True):
    workspace = Path(workspace).resolve()
    profile = w.read(workspace / '.wechat-ai/profile.json', {})
    runtime = w.read(workspace / '.wechat-ai/runtime.json', {})
    skills = w.skill_paths(workspace, profile)
    capabilities = capabilities or {}
    tools = capabilities.get('tools', [])
    if not isinstance(tools, list) or any(not isinstance(x, str) for x in tools):
        raise ValueError('tools must list actual tool names, never credential values')
    declared = bool(capabilities.get('observed_at'))
    native = declared and any('imagegen' in x or 'image_gen' in x for x in tools)
    search = declared and any('web' in x or 'search' in x for x in tools)
    image = 'declared_available_not_called' if native else 'unknown'
    if declared and not native:
        image = profile.get('image_generation', {}).get('mode', 'ask_user')
    renderer = skills.get('zhouxing-paiban-wx')
    renderer_ready = bool(renderer and (Path(renderer) / 'scripts/build_preview.py').is_file())
    checks = {'python': sys.version.split()[0], 'python_supported': sys.version_info >= (3, 10),
              'renderer': 'present_not_rendered' if renderer_ready else 'missing',
              'writing_style': 'installed_khazix' if skills.get('khazix-writer') else 'explicit_simplified_fallback',
              'search': 'declared_available_not_called' if search else 'unknown',
              'image_generation': image, 'pillow': 'present' if importlib.util.find_spec('PIL') else 'optional_missing',
              'runtime': runtime_probe(runtime) if probe else {'status': 'not_probed'}}
    baseline = w.read(w.ROOT / 'assets/tested-dependencies.json', {}).get('zhouxing', {}).get('files', {})
    checks['renderer_baseline'] = ('matches_observed_files' if renderer_ready and baseline and
                                   all(w.file_hash(Path(renderer) / name) == sha for name, sha in baseline.items())
                                   else 'different_or_unknown_requires_smoke_test')
    account = w.read(workspace / '.wechat-ai/account.json', {})
    selectors = w.read(workspace / '.wechat-ai/browser-selectors.json', {})
    connected = w.read(workspace / '.wechat-ai/browser-connection.json', {})
    browser_config = bool(selectors.get('account_id') and connected.get('status') == 'login_observed')
    credentials = bool(os.getenv('WECHAT_APP_ID') and os.getenv('WECHAT_APP_SECRET'))
    checks['wechat'] = {'account_bound': bool(account.get('account_id')), 'api_credentials_present': credentials,
                        'browser_calibrated': browser_config, 'live_login': 'not_probed',
                        'api_permissions': 'not_probed'}
    nitter = w.read(workspace / '.wechat-tools/x-nitter.json', {})
    checks['x'] = {'public_link_fetch': 'available_not_probed', 'nitter_configured': bool(nitter.get('instances')),
                   'original_chinese_screenshot': 'requires_accessible_original_page_not_guaranteed_without_login'}
    actions = []
    if not renderer_ready:
        actions.append({'id': 'renderer', 'blocks': ['layout', 'workshop'],
                        'action': 'Install zhouxing-paiban-wx using the host skill installer; research and drafting can continue.'})
    if renderer_ready and checks['renderer_baseline'] != 'matches_observed_files':
        actions.append({'id': 'renderer_compatibility', 'blocks': [],
                        'action': 'Dependency differs from observed hashes; render ten themes and save/reopen a local workshop before claiming compatibility.'})
    if not skills.get('khazix-writer'):
        actions.append({'id': 'full_writing_style', 'blocks': ['full_khazix_style'],
                        'action': 'For the original Khazix style install khazix-writer; explain the simplified fallback and obtain acceptance before presenting it as the selected style.'})
    if not declared:
        actions.append({'id': 'host_tools', 'blocks': [], 'action': 'Agent records tools actually exposed now; Python cannot discover host image/search tools.'})
    elif not native and image not in ('configured', 'declined'):
        actions.append({'id': 'image_choice', 'blocks': ['ai_images'], 'action': 'Ask once whether to configure image generation; if yes ask provider/model, otherwise save opt-out.'})
    runtime_ready = (checks['runtime'].get('node_supported') is True and
                     checks['runtime'].get('playwright') not in (None, 'missing') and
                     checks['runtime'].get('pngjs') not in (None, 'missing') and
                     checks['runtime'].get('browser') == 'executable_present_not_launched')
    if not runtime_ready:
        actions.append({'id': 'browser_runtime', 'blocks': ['draft_browser', 'pixel_replay'],
                        'action': 'Reuse host runtime, or install assets/browser-runtime/package.json in a workspace runtime folder and launch a browser smoke test.'})
    if not browser_config and not credentials:
        actions.append({'id': 'wechat_optional', 'blocks': ['draft'], 'action': 'Article preview works without WeChat. For draft upload, scan into the dedicated profile and calibrate the actual account.'})
    return {'schema_version': 1, 'status': 'local_ready' if renderer_ready else 'research_only',
            'checks': checks, 'next_actions': actions, 'network_attempted': False,
            'limits': ['Presence is not successful generation, login, API permission or complete end-to-end verification.',
                       'X and Nitter are optional research paths; do not block unrelated article work.']}


def setup(workspace, output_mode=None, screenshot_mode=None, image_choice=None, decision=None, runtime=None):
    root = Path(workspace) / '.wechat-ai'
    if runtime:
        allowed = {'node_executable', 'playwright_module_path', 'browser_executable'}
        if set(runtime) - allowed or any(not isinstance(v, str) or not Path(v).exists() for v in runtime.values()):
            raise ValueError('Runtime accepts only existing local executable/module paths')
    profile = w.read(root / 'profile.json', {})
    if output_mode:
        if output_mode not in ('local', 'draft_after_layout_selection'):
            raise ValueError('invalid output mode')
        profile['output_mode'] = output_mode
    if screenshot_mode:
        if screenshot_mode not in ('contextual', 'screen-frame', 'focused'):
            raise ValueError('invalid screenshot preference')
        profile['screenshot_preference'] = screenshot_mode
    if image_choice:
        if image_choice != 'declined' or not decision or not decision.strip():
            raise ValueError('Opt-out needs the actual user decision; configuration needs a real generation test.')
        profile['image_generation'] = {'mode': 'declined', 'user_decision': decision}
    profile['release_contract'] = 'reader-value-v1'
    w.save(root / 'profile.json', profile)
    if runtime:
        w.save(root / 'runtime.json', runtime)
    return {'status': 'preferences_saved', 'grants_upload_authorization': False, 'credentials_saved': False}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=('doctor', 'setup'))
    p.add_argument('--workspace', type=Path, default=Path.cwd())
    p.add_argument('--capabilities', type=Path)
    p.add_argument('--output-mode', choices=('local', 'draft_after_layout_selection'))
    p.add_argument('--screenshot-mode', choices=('contextual', 'screen-frame', 'focused'))
    p.add_argument('--image-choice', choices=('declined',))
    p.add_argument('--decision')
    p.add_argument('--runtime', type=Path)
    p.add_argument('--out', type=Path)
    a = p.parse_args()
    result = doctor(a.workspace, w.read(a.capabilities, {}) if a.capabilities else None) if a.command == 'doctor' else setup(
        a.workspace, a.output_mode, a.screenshot_mode, a.image_choice, a.decision, w.read(a.runtime) if a.runtime else None)
    if a.out:
        w.save(a.out, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
