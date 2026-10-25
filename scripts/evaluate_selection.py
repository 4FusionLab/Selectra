# SPDX-License-Identifier: GPL-3.0-only
"""Compare the hand-labelled synthetic corpus with a frozen baseline."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
ROOT = Path(__file__).resolve().parents[1]

from evaluation.baseline_c5ac432 import rank as baseline
from evaluation.corpus import tasks, holdout_tasks
from evaluation.metrics import evaluate
from Selectra.ranking import rank


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--json', type=Path, help='Write inspectable complete results')
    parser.add_argument('--repeats', type=int, default=5)
    args = parser.parse_args()
    if args.repeats <= 0:
        parser.error('--repeats must be positive')
    corpus = tasks()
    result = {'corpus': 'synthetic-v1', 'baseline_commit': 'c5ac432',
              'scope': 'Python only; no CAD read/display timing',
              'python': platform.python_version(),
              'source_sha256': {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                                for pattern in ('Selectra/*.py', 'evaluation/*.py')
                                for path in sorted(ROOT.glob(pattern))},
              'baseline': evaluate(corpus, baseline, args.repeats),
              'current': evaluate(corpus, rank, args.repeats),
              'holdout': {'baseline': evaluate(tuple(holdout_tasks()), baseline, args.repeats),
                          'current': evaluate(tuple(holdout_tasks()), rank, args.repeats)}}
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print('Synthetic corpus; precision/recall exclude explicit examples.')
    for name in ('baseline', 'current'):
        print(name+': '+json.dumps(result[name]['summary'], ensure_ascii=False))
    print('task | baseline exact/reachable/steps | current exact/reachable/steps')
    for old, new in zip(result['baseline']['rows'], result['current']['rows']):
        def brief(row):
            return '{}/{}/{}'.format(int(row['first_exact']), int(row['target_reachable']), row['range_steps'])
        print('{} | {} | {}'.format(new['task'], brief(old), brief(new)))
    print('Adversarial holdout, not included in the development-corpus totals:')
    for name in ('baseline', 'current'):
        print(name+': '+json.dumps(result['holdout'][name]['summary'], ensure_ascii=False))
    for old, new in zip(result['holdout']['baseline']['rows'], result['holdout']['current']['rows']):
        print('{} | {} | {}'.format(new['task'], brief(old), brief(new)))
    return result


if __name__ == '__main__':
    main()
