"""Offline validation: python3 scripts/check.py (Python 3.9+, standard library)."""
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = json.loads((ROOT / 'catalog.json').read_text(encoding='utf-8'))
NAMES = tuple(item['name'] for item in CATALOG['skills'])
DISPLAY_NAMES = tuple(item['display_name'] for item in CATALOG['skills'])


def skill_files(root):
    return sorted(p for p in root.rglob('*') if p.is_file()
                  and '__pycache__' not in p.parts and p.suffix != '.pyc'
                  and p.name != '.DS_Store')


def metadata(root):
    text = (root / 'SKILL.md').read_text(encoding='utf-8')
    front = re.match(r'\A---\n(.*?)\n---\n', text, re.S)
    if not front:
        raise ValueError('Missing frontmatter: ' + str(root))
    fields = front[1]
    name = re.search(r'^name: ([-a-z0-9]+)$', fields, re.M)
    desc = re.search(r'^description: (.+)$', fields, re.M)
    version = re.search(r'^  version: "(\d+\.\d+\.\d+)"$', fields, re.M)
    if not name or not desc or not version or name[1] != root.name:
        raise ValueError('Invalid skill identity: ' + str(root))
    if len(name[1]) > 64 or not 1 <= len(desc[1]) <= 60:
        raise ValueError('Name or description length: ' + str(root))
    return {'name': name[1], 'description': desc[1], 'version': version[1]}


def validate():
    if len(set(NAMES)) != len(NAMES):
        raise ValueError('Duplicate catalog entry')
    actual = {p.name for p in (ROOT / 'skills').iterdir() if p.is_dir()}
    if actual != set(NAMES):
        raise ValueError('Skill directories and catalog differ')
    for name, display in zip(NAMES, DISPLAY_NAMES):
        root = ROOT / 'skills' / name
        metadata(root)
        interface = (root / 'agents/openai.yaml').read_text(encoding='utf-8')
        if 'display_name: "' + display + '"' not in interface:
            raise ValueError('Unexpected display name: ' + name)
        for required in ('SOURCES.md',):
            if not (root / required).is_file():
                raise ValueError('Missing: ' + required)
        for file in skill_files(root):
            if file.is_symlink():
                raise ValueError('Skill files must be self-contained: ' + str(file))
            if file.suffix != '.md':
                continue
            for link in re.findall(r'\]\(([^)]+)\)', file.read_text(encoding='utf-8')):
                if '://' in link or link.startswith('#'):
                    continue
                resolved = (file.parent / link.split('#')[0]).resolve()
                if root.resolve() not in resolved.parents or not resolved.is_file():
                    raise ValueError('Broken or external local reference: ' + str(file) + ' -> ' + link)
    if not re.fullmatch(r'\d+\.\d+\.\d+', CATALOG['bundle_version']):
        raise ValueError('Invalid collection version')
    return CATALOG['bundle_version']


def main():
    print('Validating collection ' + validate(), flush=True)
    for item in CATALOG['skills']:
        if 'tests' not in item:
            continue
        name = item['name']
        subprocess.run([sys.executable, '-X', 'utf8', '-m', 'unittest', 'discover',
                        '-s', str(ROOT / 'skills' / name / item['tests']), '-p', 'test_*.py'], check=True)
    with tempfile.TemporaryDirectory(prefix='paper skills 中文 ') as tmp:
        base = Path(tmp)
        cwd = base / 'unrelated working directory'
        cwd.mkdir()
        for name in NAMES:
            shutil.copytree(ROOT / 'skills' / name, base / name,
                            ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '.DS_Store'))
        result = subprocess.run([sys.executable, '-X', 'utf8',
                                 str(base / NAMES[0] / 'scripts/search.py'),
                                 '--keywords', '图神经网络 测试', '--dry-run'],
                                cwd=cwd, capture_output=True, encoding='utf-8', check=True)
        payload = json.loads(result.stdout)
        if payload['network_requested'] is not False or '图神经网络 测试' not in payload['query']:
            raise ValueError('Dry-run output mismatch')
        subprocess.run([sys.executable, '-X', 'utf8', str(base / NAMES[1] / 'scripts/arxiv.py'),
                        '--help'], cwd=cwd, capture_output=True, check=True)
        if list(cwd.iterdir()):
            raise ValueError('Offline startup wrote unexpected files')
    print('PASS: offline tests, skill structure, local references, and relocated startup.')
    print('Not tested here: network, native client import, model behavior, images, browser UI, PDF/OCR.')


if __name__ == '__main__':
    main()
