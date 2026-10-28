# SPDX-License-Identifier: GPL-3.0-only
"""Closed BRep-loop candidates and reversible topology range, without adsk."""
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
    supplemental: bool = False
    strip_ratio: float = None

    def __post_init__(self):
        object.__setattr__(self, 'keys', tuple(sorted(set(self.keys))))
        planes=tuple((tuple(n),tuple(p)) for n,p in self.planes)
        if any(len(v)!=3 or not all(isfinite(x) for x in v) for plane in planes for v in plane) or any(not any(n) for n,_ in planes):
            raise ValueError('Contour planes need finite points and nonzero normals.')
        object.__setattr__(self,'planes',planes)
        if not self.keys or not isfinite(self.perimeter) or self.perimeter <= 0:
            raise ValueError('A closed chain needs entities and a finite positive perimeter.')
        if self.strip_ratio is not None and (not isfinite(self.strip_ratio) or self.strip_ratio < 0):
            raise ValueError('Strip ratio must be finite and nonnegative.')


class ChainSelection:
    def __init__(self, snapshot, chains, examples):
        self.snapshot, self.chains = snapshot, tuple(chains)
        for chain in self.chains:
            snapshot.require_keys(chain.keys)
        self.feedback = Feedback()
        self.replace_examples(examples)

    def replace_examples(self, examples):
        examples = self.snapshot.require_keys(examples)
        example_keys = set(examples)
        eligible = tuple(chain for chain in self.chains if example_keys and example_keys <= set(chain.keys))
        reference = ()
        t = Tolerance()
        if examples and self.snapshot.by_key[examples[0]].kind == 'edge':
            seed_planes = tuple(support_planes(self.snapshot.by_key[k]) for k in examples)
            if all(seed_planes):
                reference = tuple(plane for plane in seed_planes[0]
                                  if all(classify_planes((plane,),other,t)=='coplanar' for other in seed_planes[1:]))
        if not reference:
            anchors = tuple(c for c in eligible if c.planes)
            if anchors:
                reference = min(anchors,key=lambda c:(not c.inner,c.perimeter,c.keys,c.planes)).planes
        classes = ('coplanar','parallel','other','unknown')
        # Duplicate cap boundaries can describe the same wall ring. Preserve
        # its strongest (inner/smallest) explanation, never repeat the ring.
        candidates = {}
        for chain in eligible:
            relation = classes.index(classify_planes(chain.planes,reference,t)) if reference else 3
            strip = chain.strip_ratio
            priority = 0 if strip is not None and strip < .1 else (2 if strip is not None else 1)
            score = priority, strip if strip is not None else 0, relation, chain.supplemental, not chain.inner, chain.perimeter
            if chain.keys not in candidates or score < candidates[chain.keys]:
                candidates[chain.keys] = score
        ordered = sorted(candidates, key=lambda keys: (candidates[keys], keys))
        # Each choice is a complete independent contour. Equal scores do
        # not merge alternatives, and previously seen entities do not hide
        # another valid loop assembled from the same edge set.
        tiers = tuple(ordered)
        planes = tuple(classes[candidates[keys][2]] for keys in ordered)
        self.ranking = Ranking((), tuple(tiers), (), not bool(tiers), automatic_level=1 if tiers else 0,
                               explanations=tuple('closed_chain' for _ in tiers), hypothesis='closed_chain',
                               plane_groups=tuple(planes) if reference else ())
        self.feedback = Feedback(examples=examples)

    @property
    def level(self):
        return self.ranking.automatic_level if self.feedback.level is None else self.feedback.level

    @property
    def result(self):
        return self.ranking.tiers[self.level-1] if self.level else self.feedback.examples

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
