# SPDX-License-Identifier: GPL-3.0-only
"""Continuous, deterministic similarity ranking for every entity of one body.

Distance is a geometric ranking score, not a probability. Examples teach
which properties are invariant. Exclusions remain ranked but are blocked.
"""
from dataclasses import dataclass
from itertools import combinations
from math import isclose, isfinite, pi

from .matching import Tolerance, _angle


@dataclass(frozen=True)
class RankedEntity:
    key: str
    distance: float
    blocked: bool = False
    example: bool = False


@dataclass(frozen=True)
class Ranking:
    items: tuple
    tiers: tuple
    features: tuple
    ambiguous: bool
    distances: tuple = ()
    automatic_level: int = 0
    explanations: tuple = ()
    hypothesis: str = ''


FEATURES = (('geometry', .8), ('measure', 1.2), ('radius', 1.6),
            ('direction', 1.0), ('normal', 1.0), ('perimeter', .7),
            ('sides', .25), ('loops', .25), ('adjacent_faces', .25), ('face_angle', .5))


def _value(d, field):
    value = getattr(d, field)
    if field == 'normal' and d.geometry != 'plane':
        return None
    if field in ('normal', 'direction'):
        return value if value and any(value) else None
    return value


def _difference(a, b, field, tolerance, deadband=True, *, axial_normal=False):
    x, y = _value(a, field), _value(b, field)
    if x is None or y is None:
        return 1.0
    if field == 'geometry':
        return float(x != y)
    if field in ('direction', 'normal'):
        axial = field == 'direction' or (field == 'normal' and axial_normal)
        maximum = pi / 2 if axial else pi
        angle = _angle(x, y, axial=axial)
        threshold = tolerance.angle if deadband else 0
        return min(1.0, max(0.0, angle - threshold) / max(1e-12, maximum - threshold))
    if not isfinite(x) or not isfinite(y):
        return 1.0
    if field == 'face_angle':
        threshold = tolerance.angle if deadband else 0
        return min(1.0, max(0.0, abs(x-y)-threshold)/pi)
    if field in ('sides', 'loops', 'adjacent_faces'):
        return abs(x-y) / max(1, abs(x), abs(y))
    absolute = tolerance.area if field == 'measure' and a.kind == 'face' else tolerance.length
    scale = max(abs(x), abs(y), absolute, 1e-300)
    threshold = max(absolute, tolerance.relative * scale) if deadband else 0
    return min(1.0, max(0.0, abs(x-y)-threshold) / scale)


def rank(snapshot, examples, exclusions=(), tolerance=None, *, criterion='auto'):
    allowed = {'auto', 'geometry', 'measure', 'radius', 'direction', 'normal', 'perimeter'}
    if criterion not in allowed:
        raise ValueError('Unsupported ranking criterion.')
    examples, exclusions = snapshot.require_keys(examples), snapshot.require_keys(exclusions)
    if set(examples) & set(exclusions):
        raise ValueError('Examples and exclusions must be disjoint.')
    if not examples:
        return Ranking(tuple(RankedEntity(d.key, 1.0, d.key in exclusions) for d in snapshot.entities), (), (), True)
    t = tolerance or Tolerance()
    def difference(a, b, field):
        # Automatic similarity treats a plane's orientation as an axis.
        # Signed facing is available through the explicit Normal criterion.
        return _difference(a, b, field, t, axial_normal=criterion == 'auto')

    seeds = tuple(snapshot.by_key[k] for k in examples)
    negatives = tuple(snapshot.by_key[k] for k in exclusions)
    features = []
    for field, base in FEATURES:
        if criterion != 'auto' and field != criterion:
            continue
        if any(_value(d, field) is None for d in seeds):
            continue
        # A varying property is not what these examples have in common.
        if criterion == 'auto' and any(difference(a, b, field) > 1e-12 for a, b in combinations(seeds, 2)):
            continue
        separation = (sum(min(difference(s, n, field) for s in seeds) for n in negatives)
                      / len(negatives) if negatives else 0)
        if criterion == 'auto' and field == 'normal':
            # Identical shape/size across a rotated part should outrank a
            # differently sized parallel face; orientation is a refinement.
            base *= .2
        features.append((field, base * (1 + 3 * separation)))
    # If no invariant distinguishes the examples, preserve deterministic
    # ordering but do not pretend that arbitrary key order means similarity.
    informative = [f for f in features if f[0] not in ('geometry', 'sides', 'loops', 'adjacent_faces')]
    total = sum(weight for _, weight in features)
    rows = []
    for d in snapshot.entities:
        aggregate = max if criterion == 'auto' else min
        distance = (sum(weight * aggregate(difference(s, d, field) for s in seeds)
                        for field, weight in features) / total if total else 0)
        rows.append(RankedEntity(d.key, 0.0 if d.key in examples else distance,
                                 d.key in exclusions, d.key in examples))
    rows.sort(key=lambda item: (item.distance, not item.example, item.key))
    tiers, distances, bands = [], [], []
    for item in rows:
        if item.example or item.blocked:
            continue
        band = next(i for i, ceiling in enumerate((0, .005, .02, .05, .10, .20, .35, .60, 1.0))
                    if item.distance <= ceiling + 1e-9)
        # Curves use stable distance bands rather than dozens of numerical
        # steps for one size family. Exact matches remain a separate tier.
        same_tier = (band == bands[-1] if snapshot.entities[0].kind == 'edge' and bands
                     else bool(distances) and isclose(item.distance, distances[-1], abs_tol=1e-9, rel_tol=1e-9))
        if not same_tier:
            tiers.append([])
            distances.append(item.distance)
            bands.append(band)
        tiers[-1].append(item.key)
    identical_exclusion = any(item.blocked and item.distance <= 1e-12 for item in rows)
    # Open on the first nonempty group beyond the examples. A fixed score
    # threshold could otherwise leave an apparently inactive seed-only view.
    automatic_level = 1 if informative and distances and not identical_exclusion else 0
    if criterion == 'auto':
        from .intentions import geometric_order
        order = geometric_order(snapshot, examples, exclusions, t, rows)
        if order is not None:
            group_distance = {key: index / max(1, len(order.groups))
                              for index, group in enumerate(order.groups) for key in group}
            rows = [RankedEntity(r.key, 0.0 if r.example else group_distance.get(r.key, r.distance),
                                 r.blocked, r.example) for r in rows]
            rows.sort(key=lambda r: (r.distance, not r.example, r.key))
            return Ranking(tuple(rows), order.groups, tuple(field for field, _ in features),
                           order.ambiguous, tuple(i / max(1, len(order.groups)) for i in range(len(order.groups))),
                           0 if order.ambiguous or not order.groups else 1,
                           order.explanations, order.hypothesis)
        if all(s.kind == 'face' and s.geometry == 'plane' for s in seeds) and any(not s.contours for s in seeds):
            return Ranking(tuple(rows), tuple(tuple(tier) for tier in tiers),
                           tuple(field for field, _ in features), True, tuple(distances), 0,
                           tuple('approximate' for _ in tiers), 'unverified_shape')
    return Ranking(tuple(rows), tuple(tuple(tier) for tier in tiers),
                   tuple(field for field, _ in features), not informative or identical_exclusion,
                   tuple(distances), automatic_level)
