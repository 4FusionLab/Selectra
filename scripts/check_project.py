# SPDX-License-Identifier: GPL-3.0-only
"""Validate public metadata, Python license headers and local Markdown links."""
import json
from pathlib import Path
import re
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]


def check(root=ROOT):
    manifest = json.loads((root / 'Selectra/Selectra.manifest').read_text(encoding='utf-8'))
    assert manifest['type'] == 'addin'
    assert manifest['autodeskProduct'] == 'Fusion360'
    assert re.fullmatch(r'\d+\.\d+\.\d+', manifest['version'])
    UUID(manifest['id'])
    assert manifest['runOnStartup'] is False, 'Startup must remain an explicit user choice.'
    required = ('README.md', 'LICENSE', 'CONTRIBUTING.md', 'CODE_OF_CONDUCT.md',
                'SECURITY.md', 'CHANGELOG.md', 'AGENTS.md', 'PLAN.md',
                'docs/INSTALLATION.md', 'docs/PUBLISHING.md', 'docs/VALIDATION.md',
                '.github/workflows/ci.yml', '.github/dependabot.yml',
                '.github/ISSUE_TEMPLATE/bug_report.yml',
                '.github/ISSUE_TEMPLATE/feature_request.yml',
                '.github/ISSUE_TEMPLATE/config.yml', '.github/PULL_REQUEST_TEMPLATE.md')
    for name in required:
        assert (root / name).is_file(), 'Missing: ' + name
    assert 'GNU GENERAL PUBLIC LICENSE' in (root / 'LICENSE').read_text(encoding='utf-8')
    for directory in ('Selectra', 'scripts', 'tests', 'evaluation'):
        for path in (root / directory).rglob('*.py'):
            assert path.read_text(encoding='utf-8').startswith(
                '# SPDX-License-Identifier: GPL-3.0-only\n'), str(path)
    documents = [p for p in root.rglob('*.md') if '.git' not in p.parts and 'dist' not in p.parts]
    for path in documents:
        text = path.read_text(encoding='utf-8')
        for target in re.findall(r'\]\(([^)]+)\)', text):
            if '://' in target or target.startswith('#'):
                continue
            target = target.split('#', 1)[0]
            assert not target.startswith('/'), 'Local absolute link in ' + str(path)
            assert (path.parent / target).exists(), (str(path), target)
        assert '/Users/' not in text, 'Private workstation path in ' + str(path)
    return len(documents)


if __name__ == '__main__':
    print('Project metadata, SPDX headers and links OK ({} documents).'.format(check()))
