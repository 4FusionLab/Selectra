# SPDX-License-Identifier: GPL-3.0-only
"""Explicit Blender-style criteria; the automatic workflow does not require them.

Multiple examples use union semantics here, unlike shared-intent inference.
Thresholds are CAD tolerances (relative plus absolute), not Blender UI units.
"""
from math import isfinite

from .matching import Tolerance, _angle, _near

SCALARS = {'length': ('edge', 'measure', 'length'),
           'area': ('face', 'measure', 'area'),
           'perimeter': ('face', 'perimeter', 'length'),
           'radius': (None, 'radius', 'length'),
           'sides': ('face', 'sides', None),
           'adjacent_faces': ('edge', 'adjacent_faces', None),
           'face_angle': ('edge', 'face_angle', 'angle')}
CRITERIA = tuple(SCALARS) + ('direction', 'normal', 'geometry')


def select_similar(seeds, candidates, criterion, comparison='equal', tolerance=None):
    """Select matches to any example, always retaining the original examples."""
    if criterion not in CRITERIA:
        raise ValueError('Unsupported criterion: ' + criterion)
    if comparison not in ('equal', 'greater', 'less'):
        raise ValueError('Comparison must be equal, greater or less.')
    if criterion not in SCALARS and comparison != 'equal':
        raise ValueError('Ordering is only available for numerical criteria.')
    t = tolerance or Tolerance()
    seeds, candidates = tuple(seeds), tuple(candidates)
    if not seeds:
        return ()
    all_items = seeds + candidates
    if len({d.scope_key for d in all_items}) > 1:
        raise ValueError('Selection cannot cross body snapshots.')
    if len({d.kind for d in seeds}) != 1:
        raise ValueError('Examples must have one entity kind.')
    if any(d.kind not in ('edge', 'face') or not isfinite(d.measure) or d.measure <= 0 for d in seeds):
        raise ValueError('Examples need a supported kind and positive finite size.')
    known = {}
    for d in all_items:
        if d.key in known and known[d.key] != d:
            raise ValueError('Conflicting descriptor: ' + d.key)
        known[d.key] = d

    def matches(a, b):
        if a.kind != b.kind or b.measure <= 0 or not isfinite(b.measure):
            return False
        if criterion in SCALARS:
            kind, field, unit = SCALARS[criterion]
            if kind and a.kind != kind:
                return False
            x, y = getattr(a, field), getattr(b, field)
            if x is None or y is None or not isfinite(x) or not isfinite(y) or x < 0 or y < 0:
                return False
            absolute = getattr(t, unit) if unit else 0
            relative = t.relative if unit in ('length', 'area') else 0
            slack = max(absolute, relative * max(abs(x), abs(y)))
            if comparison == 'greater':
                return y >= x - slack
            if comparison == 'less':
                return y <= x + slack
            return _near(x, y, relative, absolute)
        if criterion == 'geometry':
            return a.geometry == b.geometry
        if criterion == 'direction':
            return _angle(a.direction, b.direction, axial=True) <= t.angle
        return (a.geometry == b.geometry == 'plane'
                and _angle(a.normal, b.normal) <= t.angle)

    selected = {s.key for s in seeds}
    selected.update(d.key for d in known.values() if any(matches(s, d) for s in seeds))
    return tuple(sorted(selected))
