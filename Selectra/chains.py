# SPDX-License-Identifier: GPL-3.0-only
"""Closed BRep-loop candidates and reversible topology range, without adsk."""
from collections import deque
from dataclasses import dataclass
from math import isfinite
from .ranking import Ranking
from .selection import Feedback


@dataclass(frozen=True)
class ClosedChain:
    keys: tuple
    perimeter: float
    inner: bool = False

    def __post_init__(self):
        object.__setattr__(self, 'keys', tuple(sorted(set(self.keys))))
        if not self.keys or not isfinite(self.perimeter) or self.perimeter <= 0:
            raise ValueError('A closed chain needs entities and a finite positive perimeter.')


class ChainSelection:
    def __init__(self, snapshot, chains, examples):
        self.snapshot, self.chains = snapshot, tuple(chains)
        for chain in self.chains:
            snapshot.require_keys(chain.keys)
        self.feedback = Feedback()
        self.replace_examples(examples)

    def replace_examples(self, examples):
        examples = self.snapshot.require_keys(examples)
        per_example = []
        for seed in examples:
            distances, todo = {seed: 0}, deque((seed,))
            while todo:
                key = todo.popleft()
                for other in self.snapshot.adjacency[key]:
                    if other not in distances:
                        distances[other] = distances[key]+1
                        todo.append(other)
            per_example.append(distances)
        through_all = bool(examples) and any(set(examples) <= set(chain.keys) for chain in self.chains)
        # Duplicate cap boundaries can describe the same wall ring. Preserve
        # its strongest (inner/smallest) explanation, never repeat the ring.
        candidates = {}
        for chain in self.chains if through_all else ():
            hops_by_seed = [min((distances[k] for k in chain.keys if k in distances), default=None) for distances in per_example]
            if any(h is None for h in hops_by_seed):
                continue
            hops = max(hops_by_seed)
            score = hops, not chain.inner, chain.perimeter
            if chain.keys not in candidates or score < candidates[chain.keys]:
                candidates[chain.keys] = score
        ordered = sorted(candidates, key=lambda keys: (candidates[keys], keys))
        tiers, scores, used = [], [], set(examples)
        for keys in ordered:
            score = candidates[keys]
            new = set(keys)-used
            # Keep the first contour even when it is one closed circular edge
            # or a single cylindrical face already supplied as the example.
            if not new and tiers:
                continue
            if scores and score[:2] == scores[-1][:2] and abs(score[2]-scores[-1][2]) <= 1e-8*max(1,score[2]):
                tiers[-1] = tuple(sorted(set(tiers[-1]) | new))
            else:
                tiers.append(tuple(sorted(new)))
                scores.append(score)
            used.update(keys)
        self.ranking = Ranking((), tuple(tiers), (), not bool(tiers), automatic_level=1 if tiers else 0,
                               explanations=tuple('closed_chain' for _ in tiers), hypothesis='closed_chain')
        self.feedback = Feedback(examples=examples)

    @property
    def level(self):
        return self.ranking.automatic_level if self.feedback.level is None else self.feedback.level

    @property
    def result(self):
        return tuple(sorted(set(self.feedback.examples).union(*(set(t) for t in self.ranking.tiers[:self.level]))))

    @property
    def boundary_group(self):
        return self.ranking.tiers[self.level-1] if self.level else ()

    @property
    def can_apply(self):
        return bool(self.ranking.tiers and self.level)

    def set_level(self, level):
        from dataclasses import replace
        if type(level) is not int or not 0 <= level <= len(self.ranking.tiers):
            raise ValueError('Chain range is outside the available closed contours.')
        self.feedback = replace(self.feedback, level=level)

    def adjust_similarity(self, steps):
        self.set_level(max(0, min(len(self.ranking.tiers), self.level+steps)))
