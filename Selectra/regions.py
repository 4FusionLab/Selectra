# SPDX-License-Identifier: GPL-3.0-only
"""Bounded exact induced-subgraph matching for connected same-body regions.

This verifies adjacency, not just counts or degree signatures. A budget-hit
result is explicitly incomplete and cannot be converted to a selection.
Extraction of real BRep region graphs still needs native Fusion acceptance.
"""
from dataclasses import dataclass

from .matching import Tolerance, _near


@dataclass(frozen=True)
class RegionSearch:
    regions: tuple
    complete: bool
    states: int

    def selection_keys(self):
        if not self.complete:
            raise RuntimeError('Region search reached its budget; no complete selection is available.')
        return tuple(sorted({key for region in self.regions for key in region}))


def similar_regions(snapshot, pattern, *, compare_geometry=False, tolerance=None,
                    max_states=50000, max_results=1000, max_pattern=12):
    pattern = snapshot.require_keys(pattern)
    if not pattern:
        return RegionSearch((), True, 0)
    if type(max_states) is not int or max_states <= 0 or type(max_results) is not int or max_results <= 0:
        raise ValueError('Search limits must be positive integers.')
    if len(pattern) > max_pattern:
        raise ValueError('Region exceeds the supported pattern size.')
    pattern_set, reachable, todo = set(pattern), {pattern[0]}, [pattern[0]]
    while todo:
        key = todo.pop()
        for other in snapshot.adjacency[key]:
            if other in pattern_set and other not in reachable:
                reachable.add(other)
                todo.append(other)
    if reachable != pattern_set:
        raise ValueError('A region pattern must be connected.')
    neighbours = {k: set(snapshot.adjacency[k]) for k in snapshot.by_key}
    degree = {k: len(neighbours[k] & pattern_set) for k in pattern}
    t = tolerance or Tolerance()

    def compatible(a, b):
        if not compare_geometry:
            return True
        a, b = snapshot.by_key[a], snapshot.by_key[b]
        absolute = t.length if a.kind == 'edge' else t.area
        if a.geometry != b.geometry or not _near(a.measure, b.measure, t.relative, absolute):
            return False
        for field in ('radius', 'perimeter'):
            x, y = getattr(a, field), getattr(b, field)
            if x is not None or y is not None:
                if not _near(x, y, t.relative, t.length):
                    return False
        return True

    # Build candidates inside the same state budget. Preparation must not do
    # an unbounded O(pattern * body) pass before the search budget starts.
    states, complete, options = 0, True, {}
    for key in pattern:
        options[key] = []
        for target in snapshot.by_key:
            if states >= max_states:
                return RegionSearch((), False, states)
            states += 1
            if len(neighbours[target]) >= degree[key] and compatible(key, target):
                options[key].append(target)
    order = sorted(pattern, key=lambda k: (len(options[k]), -degree[k], k))
    mapping, used, matches = {}, set(), set()

    def search(depth):
        nonlocal states, complete
        if depth == len(order):
            region = tuple(sorted(used))
            if region not in matches and len(matches) >= max_results:
                complete = False
                return
            matches.add(region)
            return
        key = order[depth]
        for target in options[key]:
            if not complete:
                return
            if states >= max_states:
                complete = False
                return
            states += 1
            if target in used:
                continue
            if any((other in neighbours[key]) != (mapped in neighbours[target])
                   for other, mapped in mapping.items()):
                continue
            mapping[key] = target
            used.add(target)
            search(depth + 1)
            used.remove(target)
            del mapping[key]

    search(0)
    return RegionSearch(tuple(sorted(matches)), complete, states)
