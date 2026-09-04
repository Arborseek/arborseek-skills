"""Build reproducible ZIPs without overwriting different existing artifacts."""
import argparse
import hashlib
import io
import json
import zipfile
from pathlib import Path

from check import CATALOG, NAMES, ROOT, metadata, skill_files, validate


def content(source):
    return source if isinstance(source, bytes) else source.read_bytes()


def archive(path, entries):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_DEFLATED) as output:
        for relative, source in sorted(entries.items()):
            info = zipfile.ZipInfo(relative, date_time=(2026, 9, 4, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            output.writestr(info, content(source))
    data = buffer.getvalue()
    with zipfile.ZipFile(io.BytesIO(data)) as result:
        if result.testzip() is not None or set(result.namelist()) != set(entries):
            raise ValueError('Archive verification failed')
        for relative, source in entries.items():
            if result.read(relative) != content(source):
                raise ValueError('Content mismatch: ' + relative)
    if path.exists():
        if path.is_symlink() or path.read_bytes() != data:
            raise FileExistsError('Different file already exists: ' + str(path))
    else:
        with path.open('xb') as stream:
            stream.write(data)
    print(hashlib.sha256(data).hexdigest() + '  ' + path.name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'dist')
    args = parser.parse_args()
    version = validate()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    suite = {}
    paper_names = {'tianshu-tanjie-paper-search', 'tianshu-tanjie-arxiv',
                   'tianshu-tanjie-paper-reading', 'paper-wechat-article'}
    paper_suite, paper_workbuddy = {}, {}
    for name in NAMES:
        root = ROOT / 'skills' / name
        skill_version = metadata(root)['version']
        entries = {str(Path(name) / p.relative_to(root)).replace('\\', '/'): p
                   for p in skill_files(root)}
        archive(args.output_dir / (name + '-' + skill_version + '.zip'), entries)
        direct = {str(p.relative_to(root)).replace('\\', '/'): p for p in skill_files(root)}
        item = next(item for item in CATALOG['skills'] if item['name'] == name)
        text = (root / 'SKILL.md').read_text(encoding='utf-8')
        end = text.index('\n---\n', 4)
        fields = {'name': name, 'display_name': item['display_name'],
                  'description': metadata(root)['description'], 'version': skill_version,
                  'author': 'Arborseek', 'category': item['category']}
        header = '\n'.join(key + ': ' + json.dumps(value, ensure_ascii=False)
                           for key, value in fields.items())
        direct['SKILL.md'] = ('---\n' + header + '\nuser-invocable: true\n---\n'
                              + text[end + 5:]).encode('utf-8')
        archive(args.output_dir / (name + '-' + skill_version + '-workbuddy.zip'), direct)
        if name in paper_names:
            paper_suite.update(entries)
            paper_workbuddy[item['display_name'] + '-' + skill_version + '-WorkBuddy.zip'] = args.output_dir / (name + '-' + skill_version + '-workbuddy.zip')
        suite.update({'skills/' + relative: source for relative, source in entries.items()})
    for relative in ('README.md', 'CHANGELOG.md', 'catalog.json', 'docs/installation.md',
                     'scripts/check.py', 'scripts/package.py', 'tests/test_paper_pipeline.py', 'docs/paper-workflow.md'):
        suite[relative] = ROOT / relative
    archive(args.output_dir / ('arborseek-skills-' + version + '.zip'), suite)
    for entries in (paper_suite, paper_workbuddy):
        entries['使用说明.md'] = ROOT / 'docs/paper-workflow.md'
    archive(args.output_dir / ('论文四技能-通用-' + version + '.zip'), paper_suite)
    archive(args.output_dir / ('论文四技能-WorkBuddy-' + version + '.zip'), paper_workbuddy)


if __name__ == '__main__':
    main()
