# SPDX-License-Identifier: GPL-3.0-only
"""One bounded 3D isometry for a mapped region of planar trimmed faces.

Topology provides the face correspondence. Geometry then verifies all loops
under a single transform, including relative positions and orientations. This
is a polygonal proof at the supplied tolerance, not an analytic-surface proof.
"""
from math import hypot, isfinite

from .matching import Tolerance, _angle
from .contours import (ContourComparison, normalize_contours, _Budget,
                       _BudgetExceeded, _simplify, _frame, _validate_planar_loops,
                       _extent, _sub, _cross, _dot, _unit)


def _basis(outer):
    origin = outer[0]
    far = max(range(1, len(outer)), key=lambda i: hypot(*_sub(outer[i], origin)))
    x = _unit(_sub(outer[far], origin))
    z = _unit(max((_cross(x, _sub(p, origin)) for p in outer), key=lambda v: hypot(*v)))
    return origin, x, _cross(z, x), z, far


def _fixed_loop_match(a, b, epsilon, work):
    if len(a) != len(b):
        return False
    for shift in range(len(b)):
        for winding in (1, -1):
            for i, p in enumerate(a):
                work.step()
                q = b[(shift+winding*i) % len(b)]
                if hypot(*_sub(p, q)) > epsilon:
                    break
            else:
                return True
    return False


def _fixed_trim_match(a, b, epsilon, work):
    if len(a) != len(b) or not _fixed_loop_match(a[0], b[0], epsilon, work):
        return False
    options = [[j for j, target in enumerate(b[1:])
                if _fixed_loop_match(source, target, epsilon, work)] for source in a[1:]]
    assigned = {}

    def augment(i, visited):
        for j in options[i]:
            work.step()
            if j in visited:
                continue
            visited.add(j)
            if j not in assigned or augment(assigned[j], visited):
                assigned[j] = i
                return True
        return False

    return all(augment(i, set()) for i in range(len(options)))


def region_geometry_match(source, target, tolerance=None, *, max_states=50000, max_points=512):
    """Prove a mapped planar-face region with one rigid/reflected transform.

    Descriptor sequences have corresponding positions from graph matching.
    Missing contours, unsupported surfaces and invalid data are incomplete;
    budget-hit results are also incomplete. No scale change is permitted.
    Total input points across each region are bounded by ``max_points``.
    """
    if type(max_states) is not int or max_states <= 0:
        raise ValueError('max_states must be a positive integer.')
    work = _Budget(max_states)
    t = tolerance or Tolerance()
    try:
        source, target = tuple(source), tuple(target)
        if not source or len(source) != len(target):
            return ContourComparison(False, True, work.states)
        if any(d.kind != 'face' or d.geometry != 'plane' or not d.contours
               for d in source+target):
            return ContourComparison(False, False, work.states)
        a = tuple(normalize_contours(d.contours, max_points=max_points) for d in source)
        b = tuple(normalize_contours(d.contours, max_points=max_points) for d in target)
        if any(sum(len(loop) for face in region for loop in face) > max_points for region in (a, b)):
            return ContourComparison(False, False, work.states)
        extent = max(_extent(face) for face in a+b)
        if not isfinite(extent) or extent <= 0:
            raise ValueError('Region needs finite face extent.')
        epsilon = max(t.length, t.relative * extent, 1e-12)
        collinear = max(t.length, extent*1e-12)
        if not isfinite(epsilon):
            raise ValueError('Region tolerance must be finite.')
        a = tuple(tuple(_simplify(loop, collinear, work) for loop in face) for face in a)
        b = tuple(tuple(_simplify(loop, collinear, work) for loop in face) for face in b)
        for face in a+b:
            projection, _ = _frame(face, epsilon, work)
            _validate_planar_loops(projection, extent, work)
        if any(len(x) != len(y) or len(x[0]) != len(y[0]) or
               sorted(map(len, x[1:])) != sorted(map(len, y[1:])) for x, y in zip(a, b)):
            return ContourComparison(False, True, work.states)
        origin, sx, sy, sz, far = _basis(a[0][0])
        _, _, _, normal, _ = _basis(b[0][0])
        coordinates = tuple(tuple(tuple((_dot(_sub(p, origin), sx),
                                         _dot(_sub(p, origin), sy),
                                         _dot(_sub(p, origin), sz)) for p in loop)
                                  for loop in face) for face in a)
        span = hypot(*_sub(a[0][0][far], origin))
        outer = b[0][0]
        for shift, destination in enumerate(outer):
            for winding in (1, -1):
                work.step()
                tip = outer[(shift+winding*far) % len(outer)]
                delta = _sub(tip, destination)
                length = hypot(*delta)
                if not length or abs(length-span) > epsilon:
                    continue
                tx = _unit(delta)
                base_y = _cross(normal, tx)
                for inplane_sign in (1, -1):
                    ty = tuple(inplane_sign*v for v in base_y)
                    base_z = _cross(tx, ty)
                    for normal_sign in (1, -1):
                        tz = tuple(normal_sign*v for v in base_z)

                        def transform(face):
                            return tuple(tuple(tuple(destination[i]+p[0]*tx[i]+p[1]*ty[i]+p[2]*tz[i]
                                                     for i in range(3)) for p in loop) for loop in face)

                        for index, (face, candidate) in enumerate(zip(coordinates, b)):
                            if not _fixed_trim_match(transform(face), candidate, epsilon, work):
                                break
                            # Outward BRep normals transform as ordinary
                            # vectors under a spatial reflection. Checking
                            # them jointly prevents independently flipped
                            # facings from passing as one repeated feature.
                            sn, tn = source[index].normal, target[index].normal
                            if sn is not None and tn is not None:
                                work.step()
                                local = (_dot(sn, sx), _dot(sn, sy), _dot(sn, sz))
                                transformed = tuple(local[0]*tx[i]+local[1]*ty[i]+local[2]*tz[i]
                                                    for i in range(3))
                                if _angle(transformed, tn) > t.angle:
                                    break
                        else:
                            return ContourComparison(True, True, work.states)
        return ContourComparison(False, True, work.states)
    except (_BudgetExceeded, ValueError, TypeError, OverflowError):
        return ContourComparison(False, False, work.states)
