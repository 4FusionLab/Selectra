# SPDX-License-Identifier: GPL-3.0-only
"""Find annular face strips from exact edge and vertex incidence."""
from collections import Counter, defaultdict
from time import monotonic
from .patch_boundaries import closed_boundary_loops


def find_face_strips(faces, edges, examples, *, max_states=100000, deadline=None):
    """Return (face keys, boundary perimeter, width ratio) for simple strips.

    A strip has a chordless cycle of faces and exactly two complete simple
    boundary loops. Width is estimated from the shared cross edges; it is a
    ranking heuristic, not a claim of constant thickness.
    """
    examples = set(examples)
    if not examples or not examples <= faces.keys():
        return ()
    neighbors = defaultdict(set)
    for edge in edges.values():
        owners = tuple(f for f in edge['faces'] if f in faces)
        if len(owners) == 2 and owners[0] != owners[1]:
            a, b = owners
            neighbors[a].add(b); neighbors[b].add(a)
    seed = min(examples)
    stack = [(seed,)]
    seen = 0
    results = {}
    while stack:
        path = stack.pop()
        seen += 1
        if seen > max_states or (deadline is not None and monotonic() > deadline):
            raise ValueError('Face-strip analysis exceeded its topology budget. No partial chain was applied.')
        for nxt in sorted(neighbors[path[-1]], reverse=True):
            if nxt == seed:
                if len(path) < 3 or not examples <= set(path):
                    continue
                keys = tuple(sorted(path))
                if keys in results:
                    continue
                counts = Counter(e for f in path for e in faces[f])
                if any(n > 2 for n in counts.values()):
                    continue
                boundary = {e for e, n in counts.items() if n == 1}
                if any(e not in edges or edges[e]['vertices'] is None for e in boundary):
                    continue
                loops = closed_boundary_loops(tuple(faces[f] for f in path),
                                               {e: edges[e]['vertices'] for e in boundary})
                if len(loops) != 2 or set().union(*map(set, loops)) != boundary:
                    continue
                internal = [e for e, n in counts.items() if n == 2]
                if (len(internal) != len(path) or
                        any(len(set(edges[e]['faces']) & set(path)) != 2 for e in internal)):
                    continue
                lengths = [sum(edges[e]['length'] for e in loop) for loop in loops]
                if min(lengths) <= 0:
                    continue
                width = sum(edges[e]['length'] for e in internal) / len(internal)
                results[keys] = (keys, min(lengths), width / min(lengths))
            elif nxt not in path:
                # Chords imply a branch rather than a simple strip.
                if len(path) > 2 and seed in neighbors[path[-1]]:
                    continue
                if any(nxt in neighbors[p] for p in path[1:-1]):
                    continue
                stack.append(path + (nxt,))
    return tuple(sorted(results.values(), key=lambda r: (r[2], r[1], r[0])))
