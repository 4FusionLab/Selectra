# SPDX-License-Identifier: GPL-3.0-only
"""Bounded congruence of complete planar polygonal trims, without live CAD.

The outer loop is first. All holes share its rigid transform; holes cannot
slide independently. Reflection and either loop winding are allowed. Points
are cm. Collinear subdivisions are removed, including STEP edge splits.

This checks polygonal boundaries, not the underlying analytic curves. Different
non-collinear tessellations may conservatively fail; callers must not describe
that failure as proof of a different analytic surface. Missing/nonplanar data
and exhausted work budgets have ``complete=False`` and never match.
"""
from dataclasses import dataclass
from math import hypot, isfinite

from .matching import Tolerance


@dataclass(frozen=True)
class ContourComparison:
    matched: bool
    complete: bool
    states: int


class _BudgetExceeded(Exception):
    pass


class _Budget:
    def __init__(self, limit):
        self.limit, self.states = limit, 0

    def step(self):
        if self.states >= self.limit:
            raise _BudgetExceeded
        self.states += 1


def _sub(a, b):
    return tuple(x - y for x, y in zip(a, b))


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def _cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])


def _unit(a):
    length = hypot(*a)
    if not isfinite(length) or not length:
        raise ValueError('Contour has no finite planar frame.')
    return tuple(x / length for x in a)


def normalize_contours(contours, *, max_points=512):
    """Copy finite loops to tuples; reject incomplete/oversized input.

    Repeated closing/consecutive points are accepted and removed. No external
    objects or iterators are retained. Topology must describe a complete trim.
    """
    if type(max_points) is not int or max_points < 3:
        raise ValueError('max_points must be an integer of at least three.')
    if not contours:
        raise ValueError('A complete outer boundary is required.')
    loops, count = [], 0
    for loop in contours:
        points = []
        for point in loop:
            count += 1
            if count > max_points:
                raise ValueError('Contour exceeds the point budget.')
            point = tuple(point)
            if len(point) != 3 or any(not isfinite(x) for x in point):
                raise ValueError('Contour points need three finite coordinates.')
            if not points or point != points[-1]:
                points.append(point)
        if len(points) > 1 and points[0] == points[-1]:
            points.pop()
        if len(points) < 3:
            raise ValueError('A closed polygon needs at least three points.')
        loops.append(tuple(points))
    if not loops:
        raise ValueError('A complete outer boundary is required.')
    return tuple(loops)


def _extent(loops):
    # Half the outer perimeter is a rigid-transform/loop-order invariant
    # upper bound on diameter, unlike a world-axis bounding box.
    outer = loops[0]
    return sum(hypot(*_sub(a, b)) for a, b in zip(outer, outer[1:]+outer[:1])) / 2


def _simplify(loop, epsilon, work):
    # Preserve corners, including reversals. Only remove a vertex lying on
    # the segment joining its neighbours, never a general short feature.
    points = list(loop)
    changed = True
    while changed and len(points) > 3:
        changed = False
        for i, point in enumerate(points):
            work.step()
            a, b = points[i-1], points[(i+1) % len(points)]
            segment, delta = _sub(b, a), _sub(point, a)
            size2 = _dot(segment, segment)
            if not size2:
                continue
            fraction = _dot(delta, segment) / size2
            distance = hypot(*(delta[j] - fraction * segment[j] for j in range(3)))
            if 0 <= fraction <= 1 and distance <= epsilon:
                del points[i]
                changed = True
                break
    return tuple(points)


def _frame(loops, epsilon, work):
    outer = loops[0]
    origin = outer[0]
    far = max(range(1, len(outer)), key=lambda i: hypot(*_sub(outer[i], origin)))
    x = _unit(_sub(outer[far], origin))
    transverse = [_cross(x, _sub(point, origin)) for point in outer]
    normal = max(transverse, key=lambda v: hypot(*v))
    if hypot(*normal) <= epsilon:
        raise ValueError('Contour has no nondegenerate planar boundary.')
    normal = _unit(normal)
    y = _cross(normal, x)
    projected = []
    for loop in loops:
        row = []
        for point in loop:
            work.step()
            delta = _sub(point, origin)
            if any(not isfinite(v) for v in delta) or abs(_dot(delta, normal)) > epsilon:
                raise ValueError('Only coplanar complete trims are supported.')
            projected_point = (_dot(delta, x), _dot(delta, y))
            if any(not isfinite(v) for v in projected_point):
                raise ValueError('Contour projection must remain finite.')
            row.append(projected_point)
        projected.append(tuple(row))
    return tuple(projected), far


def _intersects(a, b, c, d, epsilon):
    def cross(p, q, r):
        return (q[0]-p[0])*(r[1]-p[1]) - (q[1]-p[1])*(r[0]-p[0])

    if any(max(a[i], b[i])+epsilon < min(c[i], d[i]) or
           max(c[i], d[i])+epsilon < min(a[i], b[i]) for i in (0, 1)):
        return False
    ab_c, ab_d = cross(a, b, c), cross(a, b, d)
    cd_a, cd_b = cross(c, d, a), cross(c, d, b)
    # The bounding test handles collinear disjoint segments. Only numerical
    # tolerance belongs here; a geometric match tolerance must not erase a
    # valid narrow channel or make an invalid contour valid.
    return ab_c * ab_d <= 0 and cd_a * cd_b <= 0


def _inside(point, loop):
    inside = False
    x, y = point
    for a, b in zip(loop, loop[1:]+loop[:1]):
        if (a[1] > y) != (b[1] > y):
            crossing = a[0] + (y-a[1]) * (b[0]-a[0]) / (b[1]-a[1])
            if x < crossing:
                inside = not inside
    return inside


def _validate_planar_loops(loops, extent, work):
    epsilon = max(1e-12, extent*1e-12)
    for loop in loops:
        signed_area = sum(a[0]*b[1]-a[1]*b[0] for a, b in zip(loop, loop[1:]+loop[:1]))
        if abs(signed_area) <= epsilon*extent:
            raise ValueError('Contour has no finite enclosed area.')
        for i, a in enumerate(loop):
            b = loop[(i+1) % len(loop)]
            for j in range(i+1, len(loop)):
                if j == i+1 or (i == 0 and j == len(loop)-1):
                    continue
                work.step()
                if _intersects(a, b, loop[j], loop[(j+1) % len(loop)], epsilon):
                    raise ValueError('Self-intersecting contours are incomplete trims.')
    for i, a in enumerate(loops):
        for b in loops[i+1:]:
            for a0, a1 in zip(a, a[1:]+a[:1]):
                for b0, b1 in zip(b, b[1:]+b[:1]):
                    work.step()
                    if _intersects(a0, a1, b0, b1, epsilon):
                        raise ValueError('Trim loops cannot cross or touch.')
    for i, hole in enumerate(loops[1:], 1):
        if not _inside(hole[0], loops[0]):
            raise ValueError('Hole must lie inside the outer trim.')
        if any(_inside(hole[0], other) or _inside(other[0], hole)
               for other in loops[1:i]):
            raise ValueError('Holes cannot overlap or contain each other.')


def _loop_matches(a, b, epsilon, work):
    if len(a) != len(b):
        return False
    for shift in range(len(b)):
        for winding in (1, -1):
            for i, point in enumerate(a):
                work.step()
                target = b[(shift + winding * i) % len(b)]
                if hypot(point[0]-target[0], point[1]-target[1]) > epsilon:
                    break
            else:
                return True
    return False


def _holes_match(source, target, epsilon, work):
    # Bipartite matching avoids a greedy, hole-order-dependent assignment
    # when tolerance makes more than one target compatible with a hole.
    options = []
    for a in source:
        options.append([j for j, b in enumerate(target) if _loop_matches(a, b, epsilon, work)])
    assigned = {}

    def augment(i, seen):
        for j in options[i]:
            work.step()
            if j in seen:
                continue
            seen.add(j)
            if j not in assigned or augment(assigned[j], seen):
                assigned[j] = i
                return True
        return False

    return all(augment(i, set()) for i in range(len(source)))


def compare_contours(a, b, tolerance=None, *, max_states=200000, max_points=512):
    """Compare complete planar polygonal trims under one rigid isometry.

    Limits are deterministic. ``complete`` distinguishes a proven mismatch
    from absent/unsupported data or a budget hit. Length tolerance is absolute
    or relative to half the outer perimeter, whichever is larger. Collinear
    simplification uses only absolute/numerical tolerance, not relative size.
    """
    if type(max_states) is not int or max_states <= 0:
        raise ValueError('max_states must be a positive integer.')
    work = _Budget(max_states)
    t = tolerance or Tolerance()
    try:
        a = normalize_contours(a, max_points=max_points)
        b = normalize_contours(b, max_points=max_points)
        extent = max(_extent(a), _extent(b))
        if not isfinite(extent) or extent <= 0:
            raise ValueError('Contour needs finite positive extent.')
        epsilon = max(t.length, t.relative * extent, 1e-12)
        if not isfinite(epsilon):
            raise ValueError('Contour tolerance must remain finite.')
        collinear = max(t.length, extent * 1e-12)
        a = tuple(_simplify(loop, collinear, work) for loop in a)
        b = tuple(_simplify(loop, collinear, work) for loop in b)
        source, far = _frame(a, epsilon, work)
        target, _ = _frame(b, epsilon, work)
        _validate_planar_loops(source, extent, work)
        _validate_planar_loops(target, extent, work)
        if len(source) != len(target) or len(source[0]) != len(target[0]):
            return ContourComparison(False, True, work.states)
        if sorted(map(len, source[1:])) != sorted(map(len, target[1:])):
            return ContourComparison(False, True, work.states)
        span = source[0][far][0]
        count = len(target[0])
        for shift in range(count):
            for winding in (1, -1):
                work.step()
                origin = target[0][shift]
                tip = target[0][(shift + winding * far) % count]
                delta = (tip[0]-origin[0], tip[1]-origin[1])
                length = hypot(*delta)
                if abs(length-span) > epsilon or not length:
                    continue
                x = (delta[0]/length, delta[1]/length)
                for mirror in (1, -1):
                    y = (-x[1]*mirror, x[0]*mirror)

                    def transform(loop):
                        return tuple((origin[0]+p[0]*x[0]+p[1]*y[0],
                                      origin[1]+p[0]*x[1]+p[1]*y[1]) for p in loop)

                    outer = transform(source[0])
                    for i, point in enumerate(outer):
                        work.step()
                        q = target[0][(shift+winding*i) % count]
                        if hypot(point[0]-q[0], point[1]-q[1]) > epsilon:
                            break
                    else:
                        holes = tuple(transform(loop) for loop in source[1:])
                        if _holes_match(holes, target[1:], epsilon, work):
                            return ContourComparison(True, True, work.states)
        return ContourComparison(False, True, work.states)
    except (_BudgetExceeded, ValueError, TypeError, OverflowError):
        return ContourComparison(False, False, work.states)


def contours_match(a, b, tolerance=None, *, max_states=200000, max_points=512):
    """Conservative boolean convenience wrapper; incomplete never matches."""
    return compare_contours(a, b, tolerance, max_states=max_states,
                            max_points=max_points).matched
