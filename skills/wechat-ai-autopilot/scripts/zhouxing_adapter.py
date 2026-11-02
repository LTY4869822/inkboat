"""Load confirmed original themes into Zhouxing's actual renderer in memory.

The third-party renderer, parser, components and template remain on the host.
This adapter does not install or modify files in the dependency's directory.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


def merge_themes(inherited, validate):
    folder = ROOT / 'assets' / 'layout-themes'
    confirmation = json.loads((folder / 'confirmation.json').read_text(encoding='utf-8'))
    bundled = []
    for item in confirmation['themes']:
        path = folder / (item['id'] + '.json')
        theme = json.loads(path.read_text(encoding='utf-8'))
        if theme.get('id') != item['id']:
            raise ValueError('confirmed theme ID differs from its file: ' + path.name)
        errors = validate(theme, path, learned=True)
        if errors:
            raise ValueError('invalid confirmed theme: ' + path.name + ': ' + '; '.join(errors))
        bundled.append(theme)
    own_ids = {theme['id'] for theme in bundled}
    if len(own_ids) != len(bundled):
        raise ValueError('duplicate confirmed theme ID')
    # The package's confirmed definitions supersede same-ID host copies only
    # in this generated page. Other host themes and their defaults survive.
    combined = [theme for theme in inherited if theme['id'] not in own_ids]
    used_orders = {theme['order'] for theme in combined}
    previous_order = 99
    for theme in sorted(bundled, key=lambda t: t['order']):
        theme['order'] = max(theme['order'], previous_order + 1)
        while theme['order'] in used_orders:
            theme['order'] += 1
        previous_order = theme['order']
        used_orders.add(theme['order'])
        combined.append(theme)
    if sum(bool(theme.get('default')) for theme in combined) != 1:
        raise ValueError('combined Zhouxing themes need exactly one default')
    return sorted(combined, key=lambda t: t['order'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--zhouxing', required=True, type=Path)
    args, renderer_args = parser.parse_known_args()
    dependency = args.zhouxing.expanduser().resolve()
    script = dependency / 'scripts' / 'build_preview.py'
    if not script.is_file():
        raise ValueError('Zhouxing renderer missing: ' + str(script))
    # Import the host implementation without writing caches into its install.
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(script.parent))
    spec = importlib.util.spec_from_file_location('autopilot_zhouxing_renderer', script)
    renderer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(renderer)
    original_loader = renderer.load_themes
    renderer.load_themes = lambda: merge_themes(original_loader(), renderer.validate_theme)
    sys.argv = [str(script), *renderer_args]
    return renderer.main()


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, OSError, KeyError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
