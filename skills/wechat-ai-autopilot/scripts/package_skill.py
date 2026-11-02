"""Package distributable skill, excluding runtime data/caches."""
import argparse
from pathlib import Path
import zipfile
import json
from release_check import check, files

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("--output", required=True, type=Path)
args = parser.parse_args()
if args.output.resolve().is_relative_to(root):
    parser.error('Output must be outside the installed skill directory')
report = check(root)
if not report['passed']:
    parser.error('; '.join(report['errors']))
args.output.parent.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(args.output, "w", zipfile.ZIP_DEFLATED) as archive:
    for path in files(root):
        archive.write(path, (Path(root.name) / path.relative_to(root)).as_posix())
    archive.writestr(root.name + '/distribution-manifest.json', json.dumps(
        {'version': (root/'VERSION').read_text().strip(), 'files': report['manifest']}, ensure_ascii=False, indent=2))
with zipfile.ZipFile(args.output) as archive:
    if archive.testzip() is not None:
        raise ValueError('ZIP integrity failed')
print(args.output.resolve())
