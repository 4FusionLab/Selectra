# SPDX-License-Identifier: GPL-3.0-only
"""Inspect complete rankings without depending on native UI or wall extraction."""
from statistics import median
from time import perf_counter

from .corpus import transformed


def selected(task, ranking, level=None):
    level = ranking.automatic_level if level is None else level
    result = set(task.examples)
    for tier in ranking.tiers[:level]:
        result.update(tier)
    return tuple(sorted(result-set(task.exclusions)))


def measure(task, ranker, repeats=5):
    elapsed = []
    for _ in range(repeats):
        started = perf_counter()
        ranking = ranker(task.snapshot, task.examples, task.exclusions)
        elapsed.append((perf_counter()-started)*1000)
    first = set(selected(task, ranking))
    target, seeds = set(task.target), set(task.examples)
    first_target = set(task.checkpoints[0]) if task.checkpoints else target
    # Measuring additional entities avoids giving free precision for known seeds.
    predicted, wanted = first-seeds, first_target-seeds
    true = len(predicted & wanted)
    precision = true/len(predicted) if predicted else (1.0 if not wanted else 0.0)
    recall = true/len(wanted) if wanted else 1.0
    ranges = [set(selected(task, ranking, i)) for i in range(len(ranking.tiers)+1)]
    hits = [abs(i-ranking.automatic_level) for i, keys in enumerate(ranges) if keys == target]
    checkpoints = [any(set(checkpoint) == keys for keys in ranges) for checkpoint in task.checkpoints]
    variants = [transformed(task), transformed(task, mirror=True)]
    signature = tuple(frozenset(tier) for tier in ranking.tiers)
    def same_order(other):
        return (tuple(frozenset(tier) for tier in other.tiers) == signature
                and other.automatic_level == ranking.automatic_level
                and other.ambiguous == ranking.ambiguous)
    invariant = all(same_order(ranker(v.snapshot, v.examples, v.exclusions)) for v in variants)
    renamed = {key: 'id-%04d' % i for i, key in enumerate(reversed(sorted(task.snapshot.by_key)))}
    # Rename keys independently of geometry to catch tempId-based tie splitting.
    from dataclasses import replace
    snap = replace(task.snapshot,
                   entities=tuple(replace(d, key=renamed[d.key]) for d in task.snapshot.entities),
                   links=tuple((renamed[a], renamed[b]) for a, b in task.snapshot.links),
                   wall_pairs=tuple((renamed[a], renamed[b]) for a, b in task.snapshot.wall_pairs))
    reverse = {v: k for k, v in renamed.items()}
    reranked = ranker(snap, tuple(renamed[k] for k in task.examples),
                      tuple(renamed[k] for k in task.exclusions))
    invariant = (invariant and tuple(frozenset(reverse[k] for k in tier)
                                    for tier in reranked.tiers) == signature
                 and reranked.automatic_level == ranking.automatic_level
                 and reranked.ambiguous == ranking.ambiguous)
    return {'task': task.key, 'description': task.description,
            'first_exact': first == first_target, 'precision_additional': precision,
            'recall_additional': recall, 'target_reachable': bool(hits),
            'range_steps': min(hits) if hits else None,
            'feedback_actions': task.feedback_actions,
            'checkpoints_reachable': checkpoints, 'invariant': invariant,
            'analysis_ms_median': median(elapsed), 'first': sorted(first),
            'first_target': sorted(first_target), 'target': sorted(target),
            'tiers': [list(tier) for tier in ranking.tiers]}


def evaluate(tasks, ranker, repeats=5):
    rows = [measure(task, ranker, repeats) for task in tasks]
    n = len(rows)
    return {'summary': {'tasks': n,
            'first_exact': sum(row['first_exact'] for row in rows),
            'precision_additional_macro': sum(row['precision_additional'] for row in rows)/n,
            'recall_additional_macro': sum(row['recall_additional'] for row in rows)/n,
            'reachable': sum(row['target_reachable'] for row in rows),
            'invariant': sum(row['invariant'] for row in rows),
            'analysis_ms_total_median_sum': sum(row['analysis_ms_median'] for row in rows)},
            'rows': rows}
