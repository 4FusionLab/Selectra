# SPDX-License-Identifier: GPL-3.0-only
"""Closed BRep-loop candidates and reversible topology range, without adsk."""
from collections import deque
from dataclasses import dataclass
from math import isfinite
from .ranking import Ranking
from .selection import Feedback
from .matching import Tolerance
from .plane_order import support_planes, classify_planes


@dataclass(frozen=True)
class ClosedChain:
    keys: tuple
    perimeter: float
    inner: bool = False
    planes: tuple = ()

    def __post_init__(self):
        object.__setattr__(self, 'keys', tuple(sorted(set(self.keys))))
        planes=tuple((tuple(n),tuple(p)) for n,p in self.planes)
        if any(len(v)!=3 or not all(isfinite(x) for x in v) for plane in planes for v in plane) or any(not any(n) for n,_ in planes):
            raise ValueError('Contour planes need finite points and nonzero normals.')
        object.__setattr__(self,'planes',planes)
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
        reference = ()
        t = Tolerance()
        if examples and self.snapshot.by_key[examples[0]].kind == 'edge':
            seed_planes = tuple(support_planes(self.snapshot.by_key[k]) for k in examples)
            if all(seed_planes):
                reference = tuple(plane for plane in seed_planes[0]
                                  if all(classify_planes((plane,),other,t)=='coplanar' for other in seed_planes[1:]))
        if not reference:
            anchors = tuple(c for c in self.chains if c.planes and set(examples) <= set(c.keys))
            if anchors:
                reference = min(anchors,key=lambda c:(not c.inner,c.perimeter,c.keys,c.planes)).planes
        classes = ('coplanar','parallel','other','unknown')
        # Duplicate cap boundaries can describe the same wall ring. Preserve
        # its strongest (inner/smallest) explanation, never repeat the ring.
        candidates = {}
        for chain in self.chains if through_all else ():
            hops_by_seed = [min((distances[k] for k in chain.keys if k in distances), default=None) for distances in per_example]
            if any(h is None for h in hops_by_seed):
                continue
            hops = max(hops_by_seed)
            relation = classes.index(classify_planes(chain.planes,reference,t)) if reference else 3
            score = relation, hops, not chain.inner, chain.perimeter
            if chain.keys not in candidates or score < candidates[chain.keys]:
                candidates[chain.keys] = score
        ordered = sorted(candidates, key=lambda keys: (candidates[keys], keys))
        if ordered:
            first_score=min(candidates[k] for k in ordered if set(examples)<=set(k))
            primary=[k for k in ordered if candidates[k]==first_score]
            ordered=primary+[k for k in ordered if candidates[k]!=first_score]
        tiers, scores, planes, used = [], [], [], set(examples)
        for keys in ordered:
            score = candidates[keys]
            new = set(keys)-used
            # Keep the first contour even when it is one closed circular edge
            # or a single cylindrical face already supplied as the example.
            if not new and tiers:
                continue
            if scores and score[:-1] == scores[-1][:-1] and abs(score[-1]-scores[-1][-1]) <= 1e-8*max(1,score[-1]):
                tiers[-1] = tuple(sorted(set(tiers[-1]) | new))
            else:
                tiers.append(tuple(sorted(new)))
                scores.append(score)
                planes.append(classes[score[0]])
            used.update(keys)
        self.ranking = Ranking((), tuple(tiers), (), not bool(tiers), automatic_level=1 if tiers else 0,
                               explanations=tuple('closed_chain' for _ in tiers), hypothesis='closed_chain',
                               plane_groups=tuple(planes) if reference else ())
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
