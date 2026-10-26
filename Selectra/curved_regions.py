# SPDX-License-Identifier: GPL-3.0-only
"""Bounded topology and sampled-surface matching of curved face groups.

All faces share one rigid/reflected transform. Mesh nodes and triangle centres
are checked in both directions, with oriented normals. This is sampled surface
evidence at a tolerance, not a proof of exact analytic BRep congruence.
"""
from dataclasses import dataclass, replace
from itertools import permutations
from math import hypot
from time import monotonic

from .matching import _near, Tolerance
from .contours import _sub, _dot, _cross, _unit
from .plane_order import plane_class


class Budget:
    def __init__(self, limit=2000000, seconds=2.0):
        self.states, self.limit, self.until = 0, limit, monotonic()+seconds

    def step(self):
        self.states += 1
        if self.states > self.limit or (self.states % 1024 == 0 and monotonic() > self.until):
            raise ValueError('Curved-group analysis exceeded its budget. No partial group was applied.')


def compatible(a, b, t):
    if a.kind != 'face' or b.kind != 'face' or a.geometry != b.geometry:
        return False
    if not _near(a.measure, b.measure, t.relative, t.area):
        return False
    for field in ('perimeter', 'radius'):
        x, y = getattr(a, field), getattr(b, field)
        if x is not None or y is not None:
            if x is None or y is None or not _near(x, y, t.relative, t.length):
                return False
    return a.loops == b.loops


def components(snapshot, keys):
    remaining, result = set(keys), []
    while remaining:
        first = min(remaining)
        seen, todo = {first}, [first]
        while todo:
            for key in snapshot.adjacency[todo.pop()]:
                if key in remaining and key not in seen:
                    seen.add(key)
                    todo.append(key)
        remaining -= seen
        result.append(tuple(sorted(seen)))
    return tuple(result)


def _closest(p, a, b, c):
    ab, ac, ap = _sub(b, a), _sub(c, a), _sub(p, a)
    xx, xy, yy = _dot(ab, ab), _dot(ab, ac), _dot(ac, ac)
    det = xx*yy-xy*xy
    if det > 1e-30:
        u = (_dot(ap, ab)*yy-_dot(ap, ac)*xy)/det
        v = (_dot(ap, ac)*xx-_dot(ap, ab)*xy)/det
        if u >= 0 and v >= 0 and u+v <= 1:
            q = tuple(a[i]+u*ab[i]+v*ac[i] for i in range(3))
            return hypot(*_sub(p, q)), (1-u-v, u, v)
    best = (float('inf'), None)
    for i, j in ((0, 1), (1, 2), (2, 0)):
        vertices = (a, b, c)
        x, delta = vertices[i], _sub(vertices[j], vertices[i])
        length = _dot(delta, delta)
        u = min(1, max(0, _dot(_sub(p, x), delta)/length)) if length else 0
        distance = hypot(*(p[k]-x[k]-u*delta[k] for k in range(3)))
        if distance < best[0]:
            bary = [0., 0., 0.]
            bary[i], bary[j] = 1-u, u
            best = distance, tuple(bary)
    return best


class MeshIndex:
    def __init__(self, patch):
        _, self.points, self.triangles, self.normals = patch
        boxes = {i: tuple((min(self.points[v][k] for v in tri), max(self.points[v][k] for v in tri))
                           for k in range(3)) for i, tri in enumerate(self.triangles)}
        def build(ids):
            box = tuple((min(boxes[i][k][0] for i in ids), max(boxes[i][k][1] for i in ids)) for k in range(3))
            if len(ids) <= 8:
                return box, ids, ()
            axis = max(range(3), key=lambda k: box[k][1]-box[k][0])
            ids = sorted(ids, key=lambda i: sum(boxes[i][axis]))
            middle = len(ids)//2
            return box, (), (build(ids[:middle]), build(ids[middle:]))
        self.tree = build(tuple(range(len(self.triangles))))

    def contains(self, point, normal, epsilon, work):
        todo = [self.tree]
        normal_length = hypot(*normal)
        if not normal_length:
            return False
        while todo:
            work.step()
            box, ids, children = todo.pop()
            if any(point[k] < box[k][0]-epsilon or point[k] > box[k][1]+epsilon for k in range(3)):
                continue
            todo.extend(children)
            for index in ids:
                work.step()
                tri = self.triangles[index]
                distance, bary = _closest(point, *(self.points[i] for i in tri))
                if distance <= epsilon:
                    n = tuple(sum(bary[j]*self.normals[tri[j]][k] for j in range(3)) for k in range(3))
                    if _dot(normal, n) >= .95*normal_length*hypot(*n) and any(n):
                        return True
        return False


def _samples(patch):
    _, points, triangles, normals = patch
    yield from zip(points, normals)
    for tri in triangles:
        yield (tuple(sum(points[i][k] for i in tri)/3 for k in range(3)),
               tuple(sum(normals[i][k] for i in tri)/3 for k in range(3)))


def _basis(a, b, c):
    x = _unit(_sub(b, a))
    z = _unit(_cross(x, _sub(c, a)))
    return x, _cross(z, x), z


def matches(source, target, t, work, indexes):
    if any(not d.patch or len(d.patch[0]) < 3 for d in source+target):
        raise ValueError('Curved group needs complete surface meshes and BRep landmarks.')
    anchor = max(range(len(source)), key=lambda i: source[i].measure)
    vertices = source[anchor].patch[0]
    a = min(vertices)
    b = max(vertices, key=lambda p: hypot(*_sub(p, a)))
    c = max(vertices, key=lambda p: hypot(*_cross(_sub(b, a), _sub(p, a))))
    if hypot(*_cross(_sub(b, a), _sub(c, a))) < 1e-12:
        raise ValueError('Curved group has no stable landmark frame.')
    basis = _basis(a, b, c)
    extent = max(hypot(*_sub(p, q)) for p in vertices for q in vertices)
    epsilon = max(t.length, t.relative*extent, 1e-8)
    lengths = tuple(hypot(*_sub(p, q)) for p, q in ((a, b), (a, c), (b, c)))
    for x, y, z in permutations(target[anchor].patch[0], 3):
        work.step()
        if any(abs(hypot(*_sub(p, q))-size) > epsilon for p, q, size in
               ((x, y, lengths[0]), (x, z, lengths[1]), (y, z, lengths[2]))):
            continue
        if hypot(*_cross(_sub(y, x), _sub(z, x))) < 1e-12:
            continue
        other = _basis(x, y, z)
        for mirror in (1, -1):
            axes = (other[0], other[1], tuple(mirror*v for v in other[2]))
            def vector(v):
                return tuple(sum(_dot(v, basis[j])*axes[j][i] for j in range(3)) for i in range(3))
            def point(p):
                return tuple(u+v for u, v in zip(x, vector(_sub(p, a))))
            def inverse_vector(v):
                return tuple(sum(_dot(v, axes[j])*basis[j][i] for j in range(3)) for i in range(3))
            def inverse_point(p):
                return tuple(u+v for u, v in zip(a, inverse_vector(_sub(p, x))))
            # Test all mapped faces' true BRep vertices before the mesh work.
            if any(any(not any(hypot(*_sub(point(p), q)) <= epsilon for q in d.patch[0]) for p in s.patch[0])
                   or any(not any(hypot(*_sub(inverse_point(q), p)) <= epsilon for p in s.patch[0]) for q in d.patch[0])
                   for s, d in zip(source, target)):
                continue
            good = True
            for s, d in zip(source, target):
                for face in (s, d):
                    if face.key not in indexes:
                        indexes[face.key] = MeshIndex(face.patch)
                if (not all(indexes[d.key].contains(point(p), vector(n), epsilon, work) for p, n in _samples(s.patch))
                        or not all(indexes[s.key].contains(inverse_point(p), inverse_vector(n), epsilon, work)
                                   for p, n in _samples(d.patch))):
                    good = False
                    break
            if good:
                return True
    return False


def _plane(snapshot, region):
    # Extruded slot sides have a cylindrical axis. The slab's middle plane
    # identifies its opening level; one region is kept atomic when ranked.
    anchor = next((snapshot.by_key[k] for k in region if snapshot.by_key[k].geometry == 'cylinder'
                   and snapshot.by_key[k].direction), None)
    if anchor is None:
        return None
    axis = _unit(anchor.direction)
    vertices = tuple(p for k in region for p in snapshot.by_key[k].patch[0])
    offsets = tuple(_dot(p, axis) for p in vertices)
    low, high = min(offsets), max(offsets)
    if high-low <= 1e-8 or any(min(abs(v-low), abs(v-high)) > max(1e-6, (high-low)*1e-4) for v in offsets):
        return None
    middle = (low+high)/2
    return replace(anchor, planes=((axis, tuple(middle*n for n in axis)),))


@dataclass(frozen=True)
class CurvedOrder:
    groups: tuple
    explanations: tuple
    plane_groups: tuple
    ambiguous: bool = False
    hypothesis: str = 'curved_regions'
    automatic_level: int = 1


def curved_order(snapshot, examples, exclusions, tolerance, scalar_items):
    seeds = tuple(snapshot.by_key[k] for k in examples)
    if not any(d.kind == 'face' and d.geometry != 'plane' for d in seeds):
        return None
    patterns = components(snapshot, examples)
    if not patterns or any(len(p) < 2 for p in patterns):
        return None
    if any(len(p) > 12 for p in patterns):
        raise ValueError('Curved group exceeds 12 faces. Use a smaller example.')
    t, work, indexes, found = tolerance or Tolerance(), Budget(), {}, set()
    for pattern in patterns:
        options = {}
        for key in pattern:
            candidates = []
            for d in snapshot.entities:
                work.step()
                if compatible(snapshot.by_key[key], d, t):
                    candidates.append(d.key)
            options[key] = tuple(candidates)
        if any(not snapshot.by_key[k].patch for optionset in options.values() for k in optionset):
            raise ValueError('Curved-group meshes are unavailable. Restart Select Similar with these examples.')
        order = sorted(pattern, key=lambda k: (len(options[k]), k))
        mapping, used = {}, set()
        def search(depth):
            work.step()
            if depth == len(order):
                region = tuple(sorted(used))
                if region in found or set(region) & set(exclusions):
                    return
                source = tuple(snapshot.by_key[k] for k in pattern)
                target = tuple(snapshot.by_key[mapping[k]] for k in pattern)
                if matches(source, target, t, work, indexes):
                    found.add(region)
                    if len(found) > 1000:
                        raise ValueError('Too many matching curved groups. Narrow the scope.')
                return
            key = order[depth]
            for target in options[key]:
                if target in used or any((other in snapshot.adjacency[key]) != (mapped in snapshot.adjacency[target])
                                         for other, mapped in mapping.items()):
                    continue
                mapping[key] = target
                used.add(target)
                search(depth+1)
                used.remove(target)
                del mapping[key]
        search(0)
    planes = tuple(p for pattern in patterns if (p := _plane(snapshot, pattern)) is not None)
    buckets = {name: set() for name in ('coplanar', 'parallel', 'other', 'unknown')}
    for region in sorted(found):
        plane = _plane(snapshot, region)
        name = plane_class(plane, planes, t) if plane is not None else 'unknown'
        buckets[name].update(set(region)-set(examples)-set(exclusions))
    groups, labels = [], []
    for name, keys in buckets.items():
        if keys:
            groups.append(tuple(sorted(keys)))
            labels.append(name)
    used = set(examples) | set(exclusions) | set().union(*buckets.values())
    exact_count = len(groups)
    for ceiling in (.02, .10, .25, .50, 1.0):
        keys = tuple(sorted(r.key for r in scalar_items if r.key not in used and r.distance <= ceiling))
        if keys:
            groups.append(keys)
            labels.append('unknown')
            used.update(keys)
    return CurvedOrder(tuple(groups), ('curved_regions',)*exact_count+('approximate',)*(len(groups)-exact_count), tuple(labels), automatic_level=1 if exact_count else 0)
