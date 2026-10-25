# SPDX-License-Identifier: GPL-3.0-only
"""Selection operations on bounded, same-body adjacency snapshots."""
from collections import deque
import heapq
from math import isfinite

from .matching import _angle


def grow(snapshot, selected):
    keys = set(snapshot.require_keys(selected))
    return tuple(sorted(keys | {n for key in keys for n in snapshot.adjacency[key]}))


def shrink(snapshot, selected, *, protected=()):
    keys = set(snapshot.require_keys(selected))
    protected = set(snapshot.require_keys(protected))
    if not protected <= keys:
        raise ValueError('Protected examples must be selected.')
    # Only the selected/unselected frontier is removed. Mesh boundary rules
    # require explicit boundary data and are not inferred from graph degree.
    return tuple(sorted(protected | {k for k in keys if set(snapshot.adjacency[k]) <= keys}))


def linked(snapshot, selected, *, can_cross=None):
    keys = set(snapshot.require_keys(selected))
    todo = deque(sorted(keys))
    while todo:
        key = todo.popleft()
        for neighbour in snapshot.adjacency[key]:
            if neighbour not in keys and (can_cross is None or can_cross(key, neighbour)):
                keys.add(neighbour)
                todo.append(neighbour)
    return tuple(sorted(keys))


def linked_flat(snapshot, selected, angle):
    if not isfinite(angle) or not 0 <= angle <= 3.141592653589793:
        raise ValueError('Angle must be in [0, pi].')
    selected = snapshot.require_keys(selected)
    if any(snapshot.by_key[k].kind != 'face' or snapshot.by_key[k].geometry != 'plane' for k in selected):
        raise ValueError('Linked flat selection needs planar face examples.')

    def cross(a, b):
        a, b = snapshot.by_key[a], snapshot.by_key[b]
        return a.geometry == b.geometry == 'plane' and _angle(a.normal, b.normal) <= angle

    # Local neighbour threshold intentionally matches Blender-style flood
    # semantics: a long chain may drift away from the seed's original normal.
    return linked(snapshot, selected, can_cross=cross)


def shortest_path(snapshot, start, end, *, weights=None):
    """One deterministic minimum-hop / positive-weight path; empty if disconnected.

    weights maps undirected links to explicit costs, never distance guesses
    from tempId or an arbitrary curve parameterization.
    """
    snapshot.require_keys((start, end))
    costs = {}
    if weights is not None:
        for edge, cost in weights.items():
            key = tuple(sorted(edge))
            if key not in snapshot.links or not isfinite(cost) or cost <= 0:
                raise ValueError('Path costs must be positive finite values on valid links.')
            costs[key] = cost
        if set(costs) != set(snapshot.links):
            raise ValueError('Weighted paths require a cost for every link.')
    distance, previous = {start: 0}, {}
    queue = [(0, start)]
    while queue:
        cost, key = heapq.heappop(queue)
        if cost != distance.get(key):
            continue
        if key == end:
            path = [key]
            while key in previous:
                key = previous[key]
                path.append(key)
            return tuple(reversed(path))
        for neighbour in snapshot.adjacency[key]:
            candidate = cost + (costs[tuple(sorted((key, neighbour)))] if weights is not None else 1)
            if candidate < distance.get(neighbour, float('inf')):
                distance[neighbour] = candidate
                previous[neighbour] = key
                heapq.heappush(queue, (candidate, neighbour))
    return ()
