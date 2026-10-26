# SPDX-License-Identifier: GPL-3.0-only
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
from scripts.publish_release import PLATFORMS, release_version, validated_assets


class ReleaseTests(unittest.TestCase):
    def package(self, root, platform, version='1.0.0', extra=''):
        folder=Path(root)/('Selectra-package-'+platform);folder.mkdir(exist_ok=True)
        archive=folder/'Selectra-1.0.0.zip'
        with zipfile.ZipFile(archive,'w') as zipped:
            for name,data in [('Selectra/Selectra.manifest',json.dumps({'version':version})),
                              ('Selectra/Selectra.py','source'+extra),('LICENSE','GPL-3.0-only')]:
                zipped.writestr(zipfile.ZipInfo(name,(2026,1,1,0,0,0)),data)
        archive.with_suffix('.zip.sha256').write_text(hashlib.sha256(archive.read_bytes()).hexdigest()+'  '+archive.name+'\n',encoding='ascii')
        return archive

    def test_all_platforms_must_produce_identical_checked_packages(self):
        with tempfile.TemporaryDirectory() as root:
            for platform in PLATFORMS:self.package(root,platform)
            assets=validated_assets(root,'1.0.0')
            self.assertEqual(assets[0].name,'Selectra-1.0.0.zip')
            self.package(root,'Windows',extra='different')
            with self.assertRaises(ValueError):validated_assets(root,'1.0.0')

    def test_missing_platform_or_bad_checksum_blocks_publication(self):
        with tempfile.TemporaryDirectory() as root:
            for platform in PLATFORMS[:2]:self.package(root,platform)
            with self.assertRaises(FileNotFoundError):validated_assets(root,'1.0.0')
            archive=self.package(root,'Windows')
            archive.with_suffix('.zip.sha256').write_text('incorrect',encoding='ascii')
            with self.assertRaises(ValueError):validated_assets(root,'1.0.0')

    def test_version_mismatch_blocks_publication(self):
        with self.assertRaises(ValueError):release_version('v1.0.1',{'version':'1.0.0'})
        self.assertEqual(release_version('v1.0.0',{'version':'1.0.0'}),'1.0.0')
        with tempfile.TemporaryDirectory() as root:
            for platform in PLATFORMS:self.package(root,platform,version='0.0.1')
            with self.assertRaises(ValueError):validated_assets(root,'1.0.0')
