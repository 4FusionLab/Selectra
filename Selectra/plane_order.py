# SPDX-License-Identifier: GPL-3.0-only
"""Refine equal geometric families by actual support planes, never screen depth."""
from math import hypot

from .matching import _angle


def support_planes(descriptor):
    if descriptor.planes:
        return descriptor.planes
    if descriptor.normal is not None and descriptor.position is not None and any(descriptor.normal):
        return ((descriptor.normal, descriptor.position),)
    return ()


def plane_class(descriptor, examples, tolerance):
    candidates = support_planes(descriptor)
    seeds = tuple(plane for example in examples for plane in support_planes(example))
    if not candidates or not seeds:
        return 'unknown'
    parallel = False
    for normal, point in candidates:
        for seed_normal, seed_point in seeds:
            # Plane identity is stricter than the optional broad angular
            # similarity tolerance. A tilted intersecting plane is not equal.
            if _angle(normal, seed_normal, axial=True) > 1e-7:
                continue
            parallel = True
            scale = max(map(abs, seed_normal))
            scaled = tuple(n/scale for n in seed_normal)
            length = hypot(*scaled)
            offset = abs(sum((a-b)*(n/length) for a, b, n in zip(point, seed_point, scaled)))
            if offset <= max(tolerance.length, 1e-8):
                return 'coplanar'
    return 'parallel' if parallel else 'other'


def split_plane_groups(snapshot, tiers, examples, tolerance):
    seeds = tuple(snapshot.by_key[key] for key in examples)
    if not any(support_planes(seed) for seed in seeds):
        return None
    groups, classes, origins = [], [], []
    for index, tier in enumerate(tiers):
        buckets = {name: [] for name in ('coplanar', 'parallel', 'other', 'unknown')}
        for key in tier:
            buckets[plane_class(snapshot.by_key[key], seeds, tolerance)].append(key)
        for name, bucket in buckets.items():
            if bucket:
                groups.append(tuple(sorted(bucket)))
                classes.append(name)
                origins.append(index)
    return tuple(groups), tuple(classes), tuple(origins)
