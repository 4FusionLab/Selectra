# SPDX-License-Identifier: GPL-3.0-only
"""Offline research: conservative union of adjacent planar polygonal fragments.

No native API objects are retained. Every group keeps all original face keys;
rejected components remain explicit. This is not enabled in native selection.
"""
from dataclasses import dataclass
from math import acos, hypot, isfinite

from .matching import Tolerance


@dataclass(frozen=True)
class SurfaceGroup:
    source_keys: tuple
    contours: tuple
    normal: tuple
    position: tuple


@dataclass(frozen=True)
class RejectedSurface:
    source_keys: tuple
    reason: str


@dataclass(frozen=True)
class SurfaceGrouping:
    groups: tuple
    complete: bool
    rejected: tuple
    states: int

    def selection_keys(self):
        if not self.complete:
            raise ValueError('Surface grouping is incomplete; no full selection is available.')
        return tuple(sorted(key for group in self.groups for key in group.source_keys))


class _BudgetHit(Exception):
    pass


class _Invalid(Exception):
    pass


class _Work:
    def __init__(self, maximum):
        self.maximum, self.states = maximum, 0

    def step(self):
        if self.states >= self.maximum:
            raise _BudgetHit
        self.states += 1


def _sub(a, b):
    return tuple(x-y for x, y in zip(a, b))


def _dot(a, b):
    return sum(x*y for x, y in zip(a, b))


def _cross(a, b):
    return a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]


def _unit(v):
    length = hypot(*v)
    if not isfinite(length) or not length:
        raise _Invalid('missing or invalid planar normal')
    return tuple(x/length for x in v)


def _area(loop):
    return sum(a[0]*b[1]-b[0]*a[1] for a, b in zip(loop, loop[1:]+loop[:1]))/2


def _on(point, a, b, epsilon):
    delta, span = _sub(point, a), _sub(b, a)
    size2 = _dot(span, span)
    if not size2:
        return hypot(*delta) <= epsilon
    ratio = _dot(delta, span)/size2
    return (0 <= ratio <= 1 and
            hypot(*(delta[i]-ratio*span[i] for i in range(2))) <= epsilon)


def _location(point, ring, epsilon, work):
    inside = False
    for a, b in zip(ring, ring[1:]+ring[:1]):
        work.step()
        if _on(point, a, b, epsilon):
            return 0
        if (a[1] > point[1]) != (b[1] > point[1]):
            at = a[0]+(point[1]-a[1])*(b[0]-a[0])/(b[1]-a[1])
            if point[0] < at:
                inside = not inside
    return 1 if inside else -1


def _material_location(point, loops, epsilon, work):
    outer = _location(point, loops[0], epsilon, work)
    if outer != 1:
        return outer
    for hole in loops[1:]:
        status = _location(point, hole, epsilon, work)
        if status == 0:
            return 0
        if status == 1:
            return -1
    return 1


def _proper_cross(a, b, c, d, epsilon):
    def signed(p, q, r):
        return (q[0]-p[0])*(r[1]-p[1])-(q[1]-p[1])*(r[0]-p[0])
    x, y = signed(a, b, c), signed(a, b, d)
    u, v = signed(c, d, a), signed(c, d, b)
    first = epsilon*hypot(*_sub(b, a))
    second = epsilon*hypot(*_sub(d, c))
    return ((x > first and y < -first or y > first and x < -first)
            and (u > second and v < -second or v > second and u < -second))


def _touch(a, b, c, d, epsilon):
    return (_proper_cross(a, b, c, d, epsilon) or _on(a, c, d, epsilon)
            or _on(b, c, d, epsilon) or _on(c, a, b, epsilon) or _on(d, a, b, epsilon))


def _validate(loops, epsilon, work):
    for ring in loops:
        if len(ring) < 3 or abs(_area(ring)) <= epsilon*epsilon:
            raise _Invalid('degenerate trim loop')
        for i, a in enumerate(ring):
            b = ring[(i+1) % len(ring)]
            if hypot(*_sub(a, b)) <= epsilon:
                raise _Invalid('trim edge shorter than topology tolerance')
            for j in range(i+1, len(ring)):
                if j == i+1 or i == 0 and j == len(ring)-1:
                    continue
                work.step()
                if _touch(a, b, ring[j], ring[(j+1) % len(ring)], epsilon):
                    raise _Invalid('self-intersecting trim')
    for i, a in enumerate(loops):
        for b in loops[i+1:]:
            for a0, a1 in zip(a, a[1:]+a[:1]):
                for b0, b1 in zip(b, b[1:]+b[:1]):
                    work.step()
                    if _touch(a0, a1, b0, b1, epsilon):
                        raise _Invalid('trim loops touch or cross')
    for i, hole in enumerate(loops[1:], 1):
        if _location(hole[0], loops[0], epsilon, work) != 1:
            raise _Invalid('hole lies outside outer trim')
        if any(_location(hole[0], old, epsilon, work) == 1
               or _location(old[0], hole, epsilon, work) == 1 for old in loops[1:i]):
            raise _Invalid('nested or overlapping holes')


def _frame(descriptor):
    if descriptor.kind != 'face' or descriptor.geometry != 'plane' or not descriptor.contours:
        raise _Invalid('complete planar face contours required')
    if descriptor.normal is None:
        raise _Invalid('planar normal required')
    normal = _unit(descriptor.normal)
    # Sign is immaterial to the support plane, but deterministic in one frame.
    if next((x for x in normal if abs(x) > 1e-12), 1) < 0:
        normal = tuple(-x for x in normal)
    axis = min(((1, 0, 0), (0, 1, 0), (0, 0, 1)), key=lambda v: abs(_dot(v, normal)))
    u = _unit(_cross(axis, normal))
    return descriptor.contours[0][0], u, _cross(normal, u), normal


def _merge(snapshot, keys, epsilon, work, max_points):
    origin, u, v, normal = _frame(snapshot.by_key[keys[0]])
    projected, total = {}, 0
    for key in keys:
        descriptor = snapshot.by_key[key]
        _frame(descriptor)  # Reject unsupported fragments even in singleton groups.
        loops = []
        for raw in descriptor.contours:
            points = []
            for point in raw:
                work.step()
                total += 1
                if total > max_points:
                    raise _Invalid('component point budget exceeded')
                delta = _sub(point, origin)
                if abs(_dot(delta, normal)) > epsilon:
                    raise _Invalid('fragment vertices do not share one support plane')
                p = (_dot(delta, u), _dot(delta, v))
                if not points or hypot(*_sub(p, points[-1])) > epsilon:
                    points.append(p)
            if len(points) > 1 and hypot(*_sub(points[0], points[-1])) <= epsilon:
                points.pop()
            loops.append(tuple(points))
        loops = tuple(loops)
        _validate(loops, epsilon, work)
        projected[key] = tuple(ring if (_area(ring) > 0) == (i == 0) else tuple(reversed(ring))
                               for i, ring in enumerate(loops))

    # Overlap is rejected, rather than repaired by a general polygon union.
    for i, key in enumerate(keys):
        a = projected[key]
        for other in keys[i+1:]:
            b = projected[other]
            for loop_a in a:
                for p, q in zip(loop_a, loop_a[1:]+loop_a[:1]):
                    midpoint = tuple((x+y)/2 for x, y in zip(p, q))
                    if _material_location(midpoint, b, epsilon, work) == 1:
                        raise _Invalid('fragment interiors overlap')
                    for loop_b in b:
                        for r, s in zip(loop_b, loop_b[1:]+loop_b[:1]):
                            work.step()
                            if _proper_cross(p, q, r, s, epsilon):
                                raise _Invalid('fragment boundaries cross')
            for loop_b in b:
                for p, q in zip(loop_b, loop_b[1:]+loop_b[:1]):
                    midpoint = tuple((x+y)/2 for x, y in zip(p, q))
                    if _material_location(midpoint, a, epsilon, work) == 1:
                        raise _Invalid('fragment interiors overlap')

    points = sorted({p for loops in projected.values() for ring in loops for p in ring})
    # Topological welding is absolute; the 1% similarity tolerance cannot close
    # real slits. Ambiguous transitive near-point clusters are refused.
    parent = list(range(len(points)))
    def root(i):
        while parent[i] != i:
            i = parent[i]
        return i
    for i, p in enumerate(points):
        for j in range(i):
            work.step()
            if hypot(*_sub(p, points[j])) <= epsilon:
                parent[root(i)] = root(j)
    clusters = {}
    for i, p in enumerate(points):
        clusters.setdefault(root(i), []).append(p)
    welded = {}
    for cluster in clusters.values():
        for i, p in enumerate(cluster):
            for q in cluster[:i]:
                work.step()
                if hypot(*_sub(p, q)) > epsilon:
                    raise _Invalid('ambiguous tolerance welding')
        representative = tuple(sum(p[i] for p in cluster)/len(cluster) for i in range(2))
        for p in cluster:
            welded[p] = representative
    vertices = tuple(sorted(set(welded.values())))
    atomic = {}
    for key, loops in projected.items():
        for ring in loops:
            for raw_a, raw_b in zip(ring, ring[1:]+ring[:1]):
                a, b = welded[raw_a], welded[raw_b]
                span = _sub(b, a)
                size2 = _dot(span, span)
                if not size2:
                    raise _Invalid('welding collapsed a trim edge')
                splits = []
                for p in vertices:
                    work.step()
                    if _on(p, a, b, epsilon):
                        splits.append((_dot(_sub(p, a), span)/size2, p))
                splits.sort()
                for (_, p), (_, q) in zip(splits, splits[1:]):
                    if p != q:
                        atomic.setdefault(tuple(sorted((p, q))), []).append((key, p, q))

    shared, boundary = {key: set() for key in keys}, []
    allowed_links = {tuple(sorted(link)) for link in snapshot.links}
    for owners in atomic.values():
        work.step()
        if len(owners) == 1:
            boundary.append(owners[0][1:])
        elif len(owners) == 2:
            (a, p, q), (b, r, s) = owners
            if a == b or p != s or q != r:
                raise _Invalid('overlapping or inconsistently oriented fragment boundaries')
            if tuple(sorted((a, b))) not in allowed_links:
                raise _Invalid('shared boundary has no source adjacency link')
            shared[a].add(b)
            shared[b].add(a)
        else:
            raise _Invalid('more than two fragments own one boundary segment')
    reachable, todo = {keys[0]}, [keys[0]]
    while todo:
        for key in shared[todo.pop()]:
            work.step()
            if key not in reachable:
                reachable.add(key)
                todo.append(key)
    if reachable != set(keys):
        raise _Invalid('source adjacency is not confirmed by a shared boundary segment')

    following, incoming = {}, {}
    for a, b in boundary:
        work.step()
        if a in following or b in incoming:
            raise _Invalid('boundary branches or touches itself')
        following[a], incoming[b] = b, a
    if set(following) != set(incoming) or not following:
        raise _Invalid('boundary is open or empty')
    loops, unseen = [], set(following)
    while unseen:
        first, ring = min(unseen), []
        point = first
        while point in unseen:
            work.step()
            unseen.remove(point)
            ring.append(point)
            point = following[point]
        if point != first:
            raise _Invalid('boundary traversal joins another loop')
        loops.append(tuple(ring))
    outer = [ring for ring in loops if _area(ring) > 0]
    if len(outer) != 1:
        raise _Invalid('union has multiple outer boundaries')
    holes = sorted((ring for ring in loops if _area(ring) < 0), key=lambda ring: min(ring))
    loops = (outer[0],)+tuple(holes)
    _validate(loops, epsilon, work)
    expected = sum(_area(ring) for rows in projected.values() for ring in rows)
    actual = sum(_area(ring) for ring in loops)
    perimeter = sum(hypot(*_sub(a, b)) for rows in projected.values() for ring in rows
                    for a, b in zip(ring, ring[1:]+ring[:1]))
    if abs(actual-expected) > max(epsilon*perimeter*2, epsilon*epsilon):
        raise _Invalid('union area does not preserve fragment material')
    def world(p):
        return tuple(origin[i]+p[0]*u[i]+p[1]*v[i] for i in range(3))
    return SurfaceGroup(tuple(keys), tuple(tuple(world(p) for p in ring) for ring in loops),
                        normal, origin)


def surface_groups(snapshot, tolerance=None, *, max_states=500000, max_fragments=64, max_points=2048):
    """Group linked coplanar fragments, preserving all original BRep face keys.

    Complete means every input face is accounted for by a validated group.
    Unsupported/rejected components and budget exhaustion make it incomplete;
    callers may inspect evidence but cannot obtain a full selection from it.
    """
    for value, name, minimum in ((max_states, 'max_states', 1), (max_fragments, 'max_fragments', 1),
                                 (max_points, 'max_points', 3)):
        if type(value) is not int or value < minimum:
            raise ValueError(name+' must be an integer >= '+str(minimum))
    if any(d.kind != 'face' for d in snapshot.entities):
        raise ValueError('Logical surfaces require a face snapshot.')
    t, work = tolerance or Tolerance(), _Work(max_states)
    epsilon = max(t.length, 1e-10)
    groups, rejected, remaining = [], [], set(snapshot.by_key)
    neighbours = {key: set() for key in remaining}
    frames = {}
    try:
        for descriptor in snapshot.entities:
            work.step()
            try:
                frames[descriptor.key] = _frame(descriptor)
            except _Invalid as error:
                rejected.append(RejectedSurface((descriptor.key,), str(error)))
                remaining.remove(descriptor.key)
        for a, b in snapshot.links:
            work.step()
            if a not in remaining or b not in remaining:
                continue
            pa, _, _, na = frames[a]
            pb, _, _, nb = frames[b]
            angle = acos(max(-1, min(1, abs(_dot(na, nb)))))
            if angle <= t.angle and abs(_dot(_sub(pb, pa), na)) <= epsilon:
                neighbours[a].add(b)
                neighbours[b].add(a)
        while remaining:
            first = min(remaining)
            component, todo = {first}, [first]
            while todo:
                work.step()
                for key in neighbours[todo.pop()]:
                    if key not in component:
                        component.add(key)
                        todo.append(key)
            keys = tuple(sorted(component))
            if len(keys) > max_fragments:
                rejected.append(RejectedSurface(keys, 'component fragment budget exceeded'))
            else:
                try:
                    groups.append(_merge(snapshot, keys, epsilon, work, max_points))
                except _Invalid as error:
                    rejected.append(RejectedSurface(keys, str(error)))
            remaining.difference_update(component)
    except _BudgetHit:
        if remaining:
            rejected.append(RejectedSurface(tuple(sorted(remaining)), 'work budget exceeded'))
    return SurfaceGrouping(tuple(groups), not rejected, tuple(rejected), work.states)
