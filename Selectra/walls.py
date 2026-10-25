# SPDX-License-Identifier: GPL-3.0-only
"""Bounded planar wall evidence, independent of Fusion and live BRep objects.

Normals must point OUT of the solid. Trimmed overlap is computed from a planar
segment arrangement, not bounding boxes or centroids. Material evidence remains
discrete: successful probes do not prove that the entire intervening volume is
solid, and this module never claims such a proof.
"""
from dataclasses import dataclass
from math import cos, hypot, isfinite, sqrt

from .matching import Tolerance


def _sub(a, b):
    return tuple(x - y for x, y in zip(a, b))


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def _cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])


def _unit(a):
    scale = max(map(abs, a))
    if not scale:
        return None
    scaled = tuple(x/scale for x in a)
    length = hypot(*scaled)
    return tuple(x / length for x in scaled)


def _point(value):
    value = tuple(value)
    if len(value) != 3 or any(not isfinite(x) for x in value):
        raise ValueError('Planar wall coordinates need three finite components.')
    return value


@dataclass(frozen=True)
class PlanarPatch:
    key: str
    normal: tuple
    position: tuple
    contours: tuple  # Outer loop first; remaining loops are holes.

    def __post_init__(self):
        normal = _unit(_point(self.normal))
        if not self.key or normal is None:
            raise ValueError('A planar patch needs a key and a nonzero outward normal.')
        contours = tuple(tuple(_point(p) for p in loop) for loop in self.contours)
        object.__setattr__(self, 'normal', normal)
        object.__setattr__(self, 'position', _point(self.position))
        object.__setattr__(self, 'contours', contours)


@dataclass(frozen=True)
class WallProbe:
    keys: tuple
    points: tuple = ()
    thickness: float = 0.0  # Maximum local separation of sampled traces, cm.
    overlap_area: float = 0.0  # Projected trimmed overlap, cm².
    complete: bool = False  # Entire bounded overlap computation completed.
    reason: str = ''
    trace_count: int = 0


@dataclass(frozen=True)
class WallRelation:
    keys: tuple
    thickness: float
    overlap_area: float
    probe_count: int
    evidence: str = 'sampled_material'


def _segments(loops):
    return tuple((loop[i], loop[(i+1) % len(loop)])
                 for loop in loops for i in range(len(loop)))


def _cross2(a, b):
    return a[0]*b[1] - a[1]*b[0]


def _intersection_x(a, b, c, d):
    ab, cd, ac = _sub(b, a), _sub(d, c), _sub(c, a)
    denominator = _cross2(ab, cd)
    if abs(denominator) <= 1e-14 * max(hypot(*ab)*hypot(*cd), 1e-300):
        return None
    t, u = _cross2(ac, cd)/denominator, _cross2(ac, ab)/denominator
    return a[0] + t*ab[0] if 0 < t < 1 and 0 < u < 1 else None


def _loop_intervals(loop, x):
    crossings = []
    for a, b in _segments((loop,)):
        if min(a[0], b[0]) < x < max(a[0], b[0]):
            crossings.append(a[1] + (b[1]-a[1])*(x-a[0])/(b[0]-a[0]))
    crossings.sort()
    return tuple(zip(crossings[::2], crossings[1::2]))


def _subtract(intervals, holes):
    for low, high in holes:
        remaining = []
        for start, end in intervals:
            if high <= start or low >= end:
                remaining.append((start, end))
            else:
                if start < low:
                    remaining.append((start, low))
                if high < end:
                    remaining.append((high, end))
        intervals = remaining
    return intervals


def _trim_intervals(loops, x):
    intervals = list(_loop_intervals(loops[0], x))
    for hole in loops[1:]:
        intervals = _subtract(intervals, _loop_intervals(hole, x))
    return intervals


def _trimmed_area(loops):
    def area(loop):
        return abs(sum(_cross2(a, b) for a, b in _segments((loop,)))) / 2
    return area(loops[0]) - sum(area(loop) for loop in loops[1:])


def wall_probe_points(a, b, tolerance=None, *, max_thickness=None,
                      max_probes=256, max_segments=1024):
    """Return interior material probes for overlapping, opposing planar patches.

    ``max_probes`` bounds traces; each trace has five points at 5, 25, 50, 75
    and 95 percent of local thickness. If there are more overlap cells, the
    operation fails closed. ``complete`` describes the geometric computation,
    never material coverage. Missing contours and budget failures fail closed.
    ``max_thickness`` is an optional caller-defined locality limit. By default
    thickness is at most 0.25*sqrt(smaller trimmed projected face area). At
    least half of the smaller face must overlap. These scale-invariant rules
    are a conservative wall hypothesis policy, not a universal wall definition.
    Arrangement work is capped at one million segment/scan operations and
    4096 distinct scan events, in addition to the public segment/trace budgets.
    """
    if type(max_probes) is not int or max_probes <= 0:
        raise ValueError('max_probes must be a positive integer.')
    if type(max_segments) is not int or max_segments < 6:
        raise ValueError('max_segments must be an integer of at least six.')
    if max_thickness is not None and (not isfinite(max_thickness) or max_thickness <= 0):
        raise ValueError('max_thickness must be positive and finite.')
    t = tolerance or Tolerance()
    keys = tuple(sorted((a.key, b.key)))

    def reject(reason, *, incomplete=False):
        return WallProbe(keys, complete=not incomplete, reason=reason)

    if a.key == b.key:
        return reject('same_patch')
    if _dot(a.normal, b.normal) > -cos(min(t.angle, 1.5707963267948966)):
        return reject('normals_not_opposed')
    if (not a.contours or not b.contours
            or any(len(loop) < 3 for loop in a.contours + b.contours)):
        return reject('missing_contours', incomplete=True)
    count = sum(map(len, a.contours + b.contours))
    for patch in (a, b):
        if any(abs(_dot(_sub(p, patch.position), patch.normal)) > t.length
               for loop in patch.contours for p in loop):
            return reject('nonplanar_contour', incomplete=True)
    # A local frame anchored to the longest projected outer edge is independent
    # of camera and world translation; ties affect probe placement, not overlap.
    edges = tuple(_sub(a.contours[0][(i+1) % len(a.contours[0])], p)
                  for i, p in enumerate(a.contours[0]))
    tangent = max(edges, key=lambda v: hypot(*v))
    tangent = _sub(tangent, tuple(_dot(tangent, a.normal)*n for n in a.normal))
    u = _unit(tangent)
    if u is None:
        return reject('degenerate_contour', incomplete=True)
    v = _cross(a.normal, u)

    def project(p):
        delta = _sub(p, a.position)
        return _dot(delta, u), _dot(delta, v)

    projected_a = tuple(tuple(project(p) for p in loop) for loop in a.contours)
    projected_b = tuple(tuple(project(p) for p in loop) for loop in b.contours)
    smaller_area = min(_trimmed_area(projected_a), _trimmed_area(projected_b))
    if smaller_area <= t.area:
        return reject('degenerate_contour', incomplete=True)
    thickness_limit = max_thickness if max_thickness is not None else .25*sqrt(smaller_area)
    # Outward normals must point away from the slab. Facing into a cavity has
    # the opposite sign and is rejected even before the material query.
    if any(_dot(_sub(p, a.position), a.normal) >= -t.length
           for loop in b.contours for p in loop):
        return reject('not_behind_outward_normal')
    # Establish a negative without constructing the O(n²) segment arrangement:
    # if every point of B is farther away than the permitted thickness, so is
    # every point of its projection overlap. This is conservative for tilted
    # planes: only the minimum gap can reject the pair at this stage.
    if min(-_dot(_sub(p, a.position), a.normal)
           for loop in b.contours for p in loop) > thickness_limit:
        return reject('thickness_limit')
    if count > max_segments:
        return reject('segment_budget', incomplete=True)
    segments = _segments(projected_a + projected_b)
    xs = {p[0] for segment in segments for p in segment}
    work = 0
    for i, (p, q) in enumerate(segments):
        for r, s in segments[i+1:]:
            work += 1
            if work > 1000000:
                return reject('arrangement_budget', incomplete=True)
            x = _intersection_x(p, q, r, s)
            if x is not None:
                xs.add(x)
                if len(xs) > 4096:
                    return reject('arrangement_budget', incomplete=True)
    xs = sorted(xs)
    area, cells = 0.0, []
    for left, right in zip(xs, xs[1:]):
        if right-left <= t.length:
            continue
        work += count
        if work > 1000000:
            return reject('arrangement_budget', incomplete=True)
        x = (left+right)/2
        for start, end in _trim_intervals(projected_a, x):
            for low, high in _trim_intervals(projected_b, x):
                bottom, top = max(start, low), min(end, high)
                if top-bottom <= t.length:
                    continue
                cell_area = (right-left)*(top-bottom)
                area += cell_area
                cells.append((x, (bottom+top)/2))
    if area <= t.area or not cells:
        return reject('no_trimmed_overlap')
    if area + t.area < .5*smaller_area:
        return reject('insufficient_trimmed_overlap')
    if len(cells) > max_probes:
        return reject('trace_budget', incomplete=True)
    points, thickness = [], 0.0
    denominator = _dot(b.normal, a.normal)
    for x, y in cells:
        start = tuple(o+x*du+y*dv for o, du, dv in zip(a.position, u, v))
        offset = _dot(b.normal, _sub(b.position, start))/denominator
        if offset >= -t.length:
            return reject('not_behind_outward_normal')
        thickness = max(thickness, -offset)
        if -offset > thickness_limit:
            return reject('thickness_limit')
        for fraction in (.05, .25, .5, .75, .95):
            points.append(tuple(p+fraction*offset*n for p, n in zip(start, a.normal)))
    return WallProbe(keys, tuple(points), thickness, area, True,
                     'sampled_material_required', len(cells))


def confirm_wall(probe, material):
    """Accept only complete geometry and explicit inside results at EVERY probe.

    The caller must obtain these bools from the same body/revision that owns
    the patches. ``None``, boundary/unknown classifications, integer enum values
    and missing/extra observations are rejected, rather than coerced to True.
    """
    material = tuple(material)
    if (not probe.complete or not probe.points
            or len(material) != len(probe.points)
            or any(value is not True for value in material)):
        return None
    return WallRelation(probe.keys, probe.thickness, probe.overlap_area,
                        len(probe.points))
