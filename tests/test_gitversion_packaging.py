# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
"""GitVersion is embedded into Selectra ZIP while the source manifest remains intact."""
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from scripts.build import build

ROOT = Path(__file__).resolve().parents[1]


class GitVersionPackageTests(unittest.TestCase):
    def test_embed_numeric_version(self):
        source = ROOT / 'Selectra/Selectra.manifest'
        original = source.read_bytes()
        with tempfile.TemporaryDirectory() as temp:
            archive, checksum = build(output=temp, version_override='9.8.7')
            self.assertTrue(checksum.exists())
            self.assertEqual(archive.name, 'Selectra-9.8.7.zip')
            with zipfile.ZipFile(archive) as zipped:
                self.assertEqual(json.loads(zipped.read('Selectra/Selectra.manifest'))['version'], '9.8.7')
        self.assertEqual(source.read_bytes(), original)
