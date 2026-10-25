# SPDX-License-Identifier: GPL-3.0-only
"""Geometric evidence and feedback-compatible hypotheses for planar faces."""
from dataclasses import dataclass
from math import hypot
from time import monotonic

from .contours import compare_contours
from .matching import _angle, _near
from .region_geometry import region_geometry_match
from .regions import similar_regions


@dataclass(frozen=True)
class IntentOrder:
    groups: tuple
    explanations: tuple
    hypothesis: str
    ambiguous: bool


def geometric_order(snapshot, examples, exclusions, tolerance, scalar_items):
    """Return semantic groups, or None when trimmed planar data is unavailable.

    Only explicit seeds support hypotheses. A one-hop wall of a shape analog
    is labelled indirect; it never becomes an example or starts propagation.
    """
    seeds = tuple(snapshot.by_key[k] for k in examples)
    if not seeds or not all(d.kind == 'face' and d.geometry == 'plane' and d.contours for d in seeds):
        return None
    started, comparisons, cache = monotonic(), 0, {}

    def same(a, b):
        nonlocal comparisons
        if a.key == b.key:
            return True
        key = tuple(sorted((a.key, b.key)))
        if key in cache:
            return cache[key]
        if monotonic() - started > 1.5 or comparisons >= 20000:
            raise ValueError('Shape analysis exceeded its budget. Refine the examples.')
        comparisons += 1
        result = False
        if (a.contours and b.contours and a.geometry == b.geometry
                and _near(a.measure, b.measure, tolerance.relative, tolerance.area)
                and _near(a.perimeter, b.perimeter, tolerance.relative, tolerance.length)):
            comparison = compare_contours(a.contours, b.contours, tolerance)
            if not comparison.complete:
                raise ValueError('Contour comparison is incomplete. Refine the examples.')
            result = comparison.matched
        cache[key] = result
        return result

    pool = snapshot.entities
    seed_keys, negatives = set(examples), set(exclusions)
    shape_sets = {s.key: {d.key for d in pool if same(s, d)} for s in seeds}
    shapes = set.intersection(*(shape_sets[s.key] for s in seeds))
    neighbours = {d.key: set() for d in pool}
    for a, b in snapshot.wall_pairs:
        neighbours[a].add(b)
        neighbours[b].add(a)

    # A wall-pair example teaches a two-face motif. Match BOTH endpoint
    # shapes and normal separation instead of erasing differing dimensions.
    wall_family = set()
    if len(seeds) == 2 and seeds[1].key in neighbours[seeds[0].key]:
        a, b = seeds

        def thickness(x, y):
            if x.position is None or y.position is None or not x.normal:
                return None
            norm = hypot(*x.normal)
            if not norm or not x.contours or not y.contours:
                return None
            # Plane geometry origins are arbitrary and can lie far outside
            # the trim. Use local trimmed points for near-parallel patches.
            return abs(sum((v-u)*n/norm for u, v, n in
                           zip(x.contours[0][0], y.contours[0][0], x.normal)))

        reference = thickness(a, b)
        for x, y in snapshot.wall_pairs:
            p, q = snapshot.by_key[x], snapshot.by_key[y]
            if ((same(a, p) and same(b, q)) or (same(a, q) and same(b, p))):
                gap = thickness(p, q)
                if reference is not None and gap is not None and _near(reference, gap, tolerance.relative, tolerance.length):
                    for target in ((p, q), (q, p)):
                        proof = region_geometry_match((a, b), target, tolerance)
                        if not proof.complete:
                            raise ValueError('Wall-pair shape analysis is incomplete.')
                        if proof.matched:
                            wall_family.update((x, y))
                            break

    repeated = set()
    if 1 < len(seeds) <= 12:
        # A connected set of explicit examples can describe a repeated node.
        # Nonconnected examples remain independent feedback, not a new motif.
        reachable, todo = {examples[0]}, [examples[0]]
        while todo:
            for key in snapshot.adjacency[todo.pop()]:
                if key in seed_keys and key not in reachable:
                    reachable.add(key)
                    todo.append(key)
        if reachable == seed_keys:
            search = similar_regions(snapshot, examples, compare_geometry=True, tolerance=tolerance)
            if not search.complete:
                raise ValueError('Repeated-region analysis is incomplete. Use fewer examples.')
            # Exclude rejects a whole motif, rather than leaving its fragments
            # behind and pretending that the repeated node still matches.
            repeated = {key for region in search.regions if not set(region) & negatives for key in region}

    hypotheses = []
    from .plane_order import plane_class
    shape_negatives = negatives & shapes
    coplanar_shapes = {k for k in shapes if plane_class(snapshot.by_key[k], seeds, tolerance) == 'coplanar'}
    plane_separates = (bool(coplanar_shapes - seed_keys - negatives)
                       and all(plane_class(snapshot.by_key[k], seeds, tolerance) in ('parallel', 'other')
                               for k in shape_negatives))
    if seed_keys <= shapes and (not shape_negatives or plane_separates):
        hypotheses.append(('shape', shapes))
    if seed_keys <= wall_family and not negatives & wall_family:
        hypotheses.append(('wall_sides', wall_family))
    if seed_keys <= repeated and repeated - seed_keys:
        hypotheses.append(('repeated_region', repeated))
    # Explicit feedback may favour a broad invariant over congruent shape.
    # Every accepted set must explain ALL seeds and separate ALL negatives.
    for field, label in (('normal', 'parallel_planes'), ('measure', 'same_area')):
        def matches(a, b):
            if field == 'normal':
                return a.normal is not None and b.normal is not None and _angle(a.normal, b.normal, axial=True) <= tolerance.angle
            return _near(a.measure, b.measure, tolerance.relative, tolerance.area)
        members = {d.key for d in pool if all(matches(s, d) for s in seeds)}
        if seed_keys <= members and not negatives & members:
            hypotheses.append((label, members))

    hypothesis, preferred = hypotheses[0] if hypotheses else ('unresolved', set())
    groups, labels, used = [], [], seed_keys | negatives

    def add(keys, label):
        keys = tuple(sorted(set(keys) - used))
        if keys:
            groups.append(keys)
            labels.append(label)
            used.update(keys)

    add(preferred, hypothesis)
    if hypothesis == 'shape':
        add({k for s in examples for k in neighbours[s]}, 'direct_wall')
        add({k for s in shapes - seed_keys - negatives for k in neighbours[s]}, 'analog_wall')
    # Coarse, fixed geometric-distance bands avoid a separate PgUp for every
    # tiny floating-point variation. Equal evidence always shares a group.
    for ceiling in (.02, .10, .25, .50, 1.0):
        add({row.key for row in scalar_items if row.distance <= ceiling}, 'approximate')
    if monotonic() - started > 1.5:
        raise ValueError('Geometric intention analysis exceeded its time budget.')
    return IntentOrder(tuple(groups), tuple(labels), hypothesis, not hypotheses)
