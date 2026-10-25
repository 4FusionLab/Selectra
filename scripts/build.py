# SPDX-License-Identifier: GPL-3.0-only
"""Build a deterministic prototype source ZIP using an explicit file allowlist."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def source_files(root):
    files = {root / name for name in ('.gitignore', '.gitattributes', '.editorconfig', 'LICENSE', 'selectra.png')}
    files.update(root.glob('*.md'))
    patterns = {'Selectra': ('*.py', '*.manifest'), 'scripts': ('*.py',),
                'tests': ('*.py',), 'evaluation': ('*.py', '*.json'), 'docs': ('*.md',), '.github': ('*.yml', '*.md')}
    for directory, globs in patterns.items():
        for pattern in globs:
            files.update((root / directory).rglob(pattern))
    return sorted((p for p in files if not {'__pycache__', '.vscode', '.venv', '.git'} & set(p.parts)),
                  key=lambda p: p.relative_to(root).as_posix())


def build(root=ROOT, output=None):
    root = Path(root).resolve()
    manifest = json.loads((root / 'Selectra/Selectra.manifest').read_text(encoding='utf-8'))
    version = manifest['version']
    if not re.fullmatch(r'\d+\.\d+\.\d+', version):
        raise ValueError('Manifest version must be X.Y.Z.')
    output = Path(output) if output is not None else root / 'dist'
    output.mkdir(parents=True, exist_ok=True)
    archive = output / ('Selectra-' + version + '-prototype.zip')
    files = source_files(root)
    for path in files:
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise ValueError('Package source must be a regular file inside the repository: ' + str(path))
    # Stored entries avoid platform-specific zlib differences. Text, timestamps
    # and permissions are normalized so the same source yields the same bytes.
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_STORED) as zipped:
        for path in files:
            info = zipfile.ZipInfo(path.relative_to(root).as_posix(), (2026, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            content = path.read_bytes()
            if path.suffix != '.png':
                content = content.replace(b'\r\n', b'\n')
            zipped.writestr(info, content)
    checksum = archive.with_suffix('.zip.sha256')
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    checksum.write_text(digest + '  ' + archive.name + '\n', encoding='ascii')
    return archive, checksum


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, help='Output directory (default: dist)')
    args = parser.parse_args()
    for result in build(output=args.output):
        print(result)
