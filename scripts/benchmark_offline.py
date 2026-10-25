# SPDX-License-Identifier: GPL-3.0-only
"""Measure numeric matching only; never imports or contacts Fusion."""
import argparse
from dataclasses import replace
import json
from pathlib import Path
import platform
import statistics
import sys
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from Selectra.matching import Descriptor, infer
from Selectra.snapshot import BodySnapshot
from Selectra.selection import SelectionSession
from Selectra.ranking import rank


def run(sizes=(100, 1000, 10000), repeats=5):
    rows = []
    for count in sizes:
        seed = Descriptor('seed', 'edge', 'line', 1, direction=(1, 0, 0), scope_key='benchmark-body')
        pool = tuple(replace(seed, key=str(i), measure=1 + i % 5,
                             direction=(1, 0, 0) if i % 3 else (0, 1, 0)) for i in range(count))
        timings, signatures, rank_timings, step_timings = [], [], [], []
        snapshot = BodySnapshot(seed.scope_key, "r1", (seed,) + pool)
        for _ in range(repeats):
            start = perf_counter()
            result = infer((seed,), pool)
            timings.append((perf_counter() - start) * 1000)
            signatures.append(tuple((p.intent, p.keys) for p in result.proposals))
            start = perf_counter()
            ranking = rank(snapshot, (seed.key,))
            rank_timings.append((perf_counter()-start)*1000)
            session = SelectionSession(snapshot, (seed.key,))
            start = perf_counter()
            session.adjust_similarity(1)
            session.adjust_similarity(-1)
            step_timings.append((perf_counter()-start)*1000)
        assert all(s == signatures[0] for s in signatures), 'Nondeterministic matching.'
        rows.append({'candidates': count, 'median_ms': round(statistics.median(timings), 3),
                     'min_ms': round(min(timings), 3), 'max_ms': round(max(timings), 3),
                     'proposals': len(result.proposals),
                     'ranking_median_ms': round(statistics.median(rank_timings), 3),
                     'pg_pair_median_ms': round(statistics.median(step_timings), 3),
                     'ranked_entities': len(ranking.items)})
    return {'scope': 'synthetic numeric descriptors only; no CAD/API/highlighting',
            'python': platform.python_version(), 'platform': platform.platform(),
            'repeats': repeats, 'results': rows}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repeats', type=int, default=5)
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error('repeats must be positive')
    print(json.dumps(run(repeats=args.repeats), indent=2))
