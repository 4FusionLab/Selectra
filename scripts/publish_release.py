# SPDX-License-Identifier: GPL-3.0-only
"""Publish a stable GitHub Release using identical packages built by the CI matrix."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import urllib.error
import urllib.parse
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PLATFORMS = ('Linux', 'macOS', 'Windows')


def validated_assets(artifacts, version):
    """Require every platform, exact checksum, matching manifest and identical ZIPs."""
    filename = 'Selectra-' + version + '.zip'
    packages = []
    for platform in PLATFORMS:
        folder = Path(artifacts) / ('Selectra-package-' + platform)
        archive, checksum = folder / filename, folder / (filename + '.sha256')
        data = archive.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if checksum.read_text(encoding='ascii') != digest + '  ' + filename + '\n':
            raise ValueError('Invalid checksum for ' + platform)
        with zipfile.ZipFile(archive) as zipped:
            if json.loads(zipped.read('Selectra/Selectra.manifest'))['version'] != version:
                raise ValueError('Package manifest does not match release version.')
            if any(name.startswith('/') or '..' in Path(name).parts for name in zipped.namelist()):
                raise ValueError('Invalid package entry.')
            zipped.getinfo('Selectra/Selectra.py')
            zipped.getinfo('LICENSE')
        packages.append((archive, checksum, digest))
    if len({digest for _, _, digest in packages}) != 1:
        raise ValueError('CI packages differ across operating systems.')
    return packages[0][:2]


def release_version(tag, manifest):
    version = manifest['version']
    if not re.fullmatch(r'\d+\.\d+\.\d+', version) or tag != 'v' + version:
        raise ValueError('Release tag must exactly match manifest version.')
    return version


def main(artifacts):
    if os.environ.get('GITHUB_ACTIONS') != 'true' or os.environ.get('GITHUB_REF_TYPE') != 'tag':
        raise ValueError('Release publication must run in a GitHub Actions tag workflow.')
    version = release_version(os.environ['GITHUB_REF_NAME'], json.loads(
        (ROOT / 'Selectra/Selectra.manifest').read_text(encoding='utf-8')))
    assets = validated_assets(artifacts, version)
    repository = os.environ['GITHUB_REPOSITORY']
    if repository != '4FusionLab/Selectra':
        raise ValueError('Unexpected release repository.')
    base = 'https://api.github.com/repos/' + repository
    token = os.environ['GITHUB_TOKEN']

    def request(url, method='GET', payload=None, content_type='application/json'):
        data = json.dumps(payload).encode() if payload is not None and content_type == 'application/json' else payload
        req = urllib.request.Request(url, data=data, method=method, headers={
            'Authorization': 'Bearer ' + token, 'Accept': 'application/vnd.github+json',
            'Content-Type': content_type, 'X-GitHub-Api-Version': '2022-11-28',
            'User-Agent': 'Selectra-release-CI'})
        with urllib.request.urlopen(req, timeout=120) as response:
            return json.load(response)

    tag = 'v' + version
    try:
        release = request(base + '/releases/tags/' + tag)
    except urllib.error.HTTPError as error:
        if error.code != 404:
            raise
        notes = (ROOT / 'docs/releases' / (version + '.md')).read_text(encoding='utf-8')
        notes += '\n\nBuilt and published by [GitHub Actions](https://github.com/' + repository
        notes += '/actions/runs/' + os.environ['GITHUB_RUN_ID'] + '). Commit: `' + os.environ['GITHUB_SHA'] + '`.\n'
        release = request(base + '/releases', 'POST', dict(tag_name=tag,
            target_commitish=os.environ['GITHUB_SHA'], name='Selectra ' + version + ' — Stable',
            body=notes, draft=True, prerelease=False))
    existing = {asset['name']: asset for asset in release['assets']}
    for path in assets:
        digest = 'sha256:' + hashlib.sha256(path.read_bytes()).hexdigest()
        if path.name in existing:
            if existing[path.name].get('digest') != digest:
                raise ValueError('An existing release asset differs: ' + path.name)
            continue
        if not release['draft']:
            raise ValueError('Refusing to change the assets of a published release.')
        upload = release['upload_url'].split('{', 1)[0] + '?' + urllib.parse.urlencode({'name': path.name})
        asset = request(upload, 'POST', path.read_bytes(),
                        'application/zip' if path.suffix == '.zip' else 'text/plain')
        if asset.get('digest') != digest:
            raise ValueError('Uploaded asset digest does not match CI package.')
    if release['draft']:
        release = request(base + '/releases/' + str(release['id']), 'PATCH',
                          dict(draft=False, prerelease=False, make_latest='true'))
    final = request(base + '/releases/latest')
    if final['tag_name'] != tag or final['draft'] or final['prerelease']:
        raise ValueError('Published release is not the expected latest Stable.')
    print(final['html_url'])
    for asset in final['assets']:
        print(asset['name'], asset.get('digest'), asset['browser_download_url'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--artifacts', type=Path, required=True)
    main(parser.parse_args().artifacts)
