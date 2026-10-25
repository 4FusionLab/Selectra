# SPDX-License-Identifier: GPL-3.0-only
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from scripts.build import ROOT, build, source_files


class PackagingTests(unittest.TestCase):
    def test_portable_source_archive_and_checksum(self):
        with tempfile.TemporaryDirectory() as temporary:
            archive, checksum = build(output=temporary)
            with zipfile.ZipFile(archive) as zipped:
                names = zipped.namelist()
                self.assertIn('Selectra/Selectra.py', names)
                self.assertIn('Selectra/Selectra.manifest', names)
                self.assertIn('LICENSE', names)
                self.assertIn('docs/INSTALLATION.md', names)
                self.assertIn('tests/test_matching.py', names)
                self.assertEqual(names, sorted(names))
                self.assertTrue(all(not n.startswith('/') and '..' not in Path(n).parts for n in names))
                self.assertFalse(any('.git/' in n or '__pycache__' in n or n.endswith('.pyc') for n in names))
                manifest = json.loads(zipped.read('Selectra/Selectra.manifest'))
                self.assertIn(manifest['version'], archive.name)
            digest = hashlib.sha256(archive.read_bytes()).hexdigest()
            self.assertEqual(checksum.read_text(encoding='ascii'), digest + '  ' + archive.name + '\n')

    def test_repeated_build_is_byte_identical(self):
        with tempfile.TemporaryDirectory() as temporary:
            one, _ = build(output=Path(temporary) / 'one')
            two, _ = build(output=Path(temporary) / 'two')
            self.assertEqual(one.read_bytes(), two.read_bytes())

    def test_allowlist_excludes_credentials_and_cache_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name in ('Selectra/credentials.json', 'Selectra/__pycache__/cached.pyc',
                         '.env', 'private.key', 'dist/previous.zip'):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('must not ship', encoding='utf-8')
            actual = {p.relative_to(root).as_posix() for p in source_files(root) if p.is_file()}
            self.assertEqual(actual, set())


if __name__ == '__main__':
    unittest.main()
