"""Build reproducible ZIPs without overwriting different existing artifacts."""
import argparse
import hashlib
import io
import zipfile
from pathlib import Path

from check import NAMES, ROOT, skill_files, validate


def archive(path, entries):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_DEFLATED) as output:
        for relative, source in sorted(entries.items()):
            info = zipfile.ZipInfo(relative, date_time=(2026, 9, 4, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            output.writestr(info, source.read_bytes())
    data = buffer.getvalue()
    with zipfile.ZipFile(io.BytesIO(data)) as result:
        if result.testzip() is not None or set(result.namelist()) != set(entries):
            raise ValueError('Archive verification failed')
        for relative, source in entries.items():
            if result.read(relative) != source.read_bytes():
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
    for name in NAMES:
        root = ROOT / 'skills' / name
        entries = {str(Path(name) / p.relative_to(root)).replace('\\', '/'): p
                   for p in skill_files(root)}
        archive(args.output_dir / (name + '-' + version + '.zip'), entries)
        suite.update({'skills/' + relative: source for relative, source in entries.items()})
    for relative in ('README.md', 'CHANGELOG.md', 'docs/installation.md',
                     'scripts/check.py', 'scripts/package.py'):
        suite[relative] = ROOT / relative
    archive(args.output_dir / ('arborseek-paper-skills-' + version + '.zip'), suite)


if __name__ == '__main__':
    main()
