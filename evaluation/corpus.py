# SPDX-License-Identifier: GPL-3.0-only
"""Hand-labelled synthetic tasks; no user CAD geometry or native API objects.

Labels express a task, not the current algorithm's output. In particular the
wall task requires three successive useful groups even if scalars disagree.
"""
from dataclasses import dataclass, replace
from math import hypot

from Selectra.matching import Descriptor
from Selectra.snapshot import BodySnapshot


@dataclass(frozen=True)
class Task:
    key: str
    description: str
    snapshot: BodySnapshot
    examples: tuple
    target: tuple
    exclusions: tuple = ()
    checkpoints: tuple = ()
    feedback_actions: int = 0


def loop(points, z=0):
    return tuple((x, y, z) for x, y in points)


def shifted(contours, dx=0, dy=0, dz=0):
    return tuple(tuple((x+dx, y+dy, z+dz) for x, y, z in ring) for ring in contours)


def face(key, contours, normal=(0, 0, 1)):
    # These fixtures lie in XY. Independent area/perimeter labels preserve
    # holes and avoid setting scalar features merely to help the recognizer.
    areas = [abs(sum(a[0]*b[1]-b[0]*a[1] for a, b in
                     zip(ring, ring[1:]+ring[:1])))/2 for ring in contours]
    perimeter = sum(hypot(*(a[i]-b[i] for i in range(3)))
                    for ring in contours for a, b in zip(ring, ring[1:]+ring[:1]))
    return Descriptor(key, 'face', 'plane', areas[0]-sum(areas[1:]),
                      perimeter=perimeter, normal=normal,
                      sides=sum(map(len, contours)), loops=len(contours),
                      scope_key='corpus-body', position=contours[0][0], contours=contours)


def edge(key, length=1, direction=(1, 0, 0)):
    return Descriptor(key, 'edge', 'line', length, direction=direction,
                      scope_key='corpus-body')


def body(*entities, wall_pairs=()):
    return BodySnapshot('corpus-body', 'synthetic-r1', entities, wall_pairs=wall_pairs)


def tasks():
    rows = []
    edges = body(edge('seed'), edge('twin'), edge('turned', direction=(0, 1, 0)),
                 edge('long', 2), edge('long-twin', 2))
    rows.append(Task('edge-closest', 'Same length and axis, with distracting rotated/long edges',
                     edges, ('seed',), ('seed', 'twin')))
    rows.append(Task('edge-length-feedback', 'Second example changes intended family to same axis',
                     edges, ('seed', 'long'), ('seed', 'long', 'long-twin', 'twin'),
                     feedback_actions=1))
    rows.append(Task('edge-exclude', 'Negative example rejects longer edges', edges,
                     ('seed',), ('seed', 'twin'), ('long',), feedback_actions=1))
    rows.append(Task('contradictory-feedback', 'Identical edge is excluded: honest seed-only result',
                     edges, ('seed',), ('seed',), ('twin',), feedback_actions=1))

    # U and T pentomino boundaries: both area 5, perimeter 12, eight corners.
    u = (loop(((0, 0), (3, 0), (3, 2), (2, 2), (2, 1), (1, 1), (1, 2), (0, 2))),)
    t = (loop(((0, 0), (3, 0), (3, 1), (2, 1), (2, 3), (1, 3), (1, 1), (0, 1))),)
    shape_body = body(face('seed', u), face('twin', shifted(u, dx=5)), face('false-shape', t))
    rows.append(Task('equal-area-perimeter', 'Equal scalar signatures do not prove same boundary',
                     shape_body, ('seed',), ('seed', 'twin')))
    rows.append(Task('shape-negative-feedback', 'Exclude another shape despite identical scalar signature',
                     shape_body, ('seed',), ('seed', 'twin'), ('false-shape',), feedback_actions=1))
    rotated = tuple(tuple((-y+8, x+2, z) for x, y, z in ring) for ring in u)
    reflected = tuple(tuple((-x-8, y+2, z) for x, y, z in ring) for ring in u)
    rows.append(Task('rotated-mirrored-shape', 'Congruence accepts rigid transforms and reflection',
                     body(face('seed', u), face('rotated', rotated), face('mirror', reflected),
                          face('false-shape', t)), ('seed',), ('seed', 'rotated', 'mirror')))

    outer = loop(((0, 0), (6, 0), (6, 4), (0, 4)))
    hole = loop(((1, 1), (2, 1), (2, 2), (1, 2)))
    misplaced = loop(((2, 1), (3, 1), (3, 2), (2, 2)))
    perforated = (outer, hole)
    rows.append(Task('hole-placement', 'Hole placement participates in whole-boundary correspondence',
                     body(face('seed', perforated), face('twin', shifted(perforated, dx=8)),
                          face('misplaced-hole', (outer, misplaced))),
                     ('seed',), ('seed', 'twin')))

    outer = (loop(((0, 0), (4, 0), (4, 3), (0, 3))),)
    inner = (loop(((.2, .2), (3.8, .2), (3.8, 2.8), (.2, 2.8)), z=.2),)
    shell = body(face('seed', outer, (0, 0, -1)), face('outer-twin', shifted(outer, dx=8, dz=2)),
                 face('inner-seed', inner), face('inner-twin', shifted(inner, dx=8, dz=1.6), (0, 0, -1)),
                 face('cavity-across', shifted(inner, dz=3), (0, 0, -1)),
                 wall_pairs=(('seed', 'inner-seed'), ('outer-twin', 'inner-twin')))
    first = ('seed', 'outer-twin')
    second = first + ('inner-seed',)
    third = second + ('inner-twin',)
    rows.append(Task('wall-sequence', 'Analog, own material wall partner, then analog partner',
                     shell, ('seed',), third, checkpoints=(first, second, third)))
    rows.append(Task('wall-vs-cavity-feedback', 'Second example identifies wall family; empty gap is not a wall',
                     shell, ('seed', 'inner-seed'), third, ('cavity-across',),
                     feedback_actions=2))

    # Same family within dimensional tolerance; tiny numeric differences should
    # not create dozens of levels. Two distinct scale families remain separate.
    rows.append(Task('equivalent-scale-family', 'Equivalent near-dimensions join as one range group',
                     body(edge('seed'), edge('one-a', 1.15), edge('one-b', 1.151),
                          edge('one-c', 1.152), edge('two-a', 2), edge('two-b', 2.001)),
                     ('seed',), ('seed', 'one-a', 'one-b', 'one-c')))
    return tuple(rows)


def transformed(task, *, mirror=False):
    """One exact axis permutation and translation, with optional reflection."""
    def vector(v):
        if v is None:
            return None
        x, y, z = v
        return (z, -x if mirror else x, y)

    def point(v):
        return tuple(x+t for x, t in zip(vector(v), (19, -7, 11)))

    entities = tuple(replace(d, normal=vector(d.normal), direction=vector(d.direction),
                             position=point(d.position) if d.position is not None else None,
                             contours=tuple(tuple(point(p) for p in ring) for ring in d.contours))
                     for d in reversed(task.snapshot.entities))
    return replace(task, snapshot=BodySnapshot(task.snapshot.scope_key, task.snapshot.revision,
                   entities, task.snapshot.links, wall_pairs=task.snapshot.wall_pairs),
                   examples=tuple(reversed(task.examples)), exclusions=tuple(reversed(task.exclusions)))


def holdout_tasks():
    """Additional adversarial labels, kept separate from development examples."""
    core = {task.key: task for task in tasks()}
    shapes = core['equal-area-perimeter'].snapshot
    seed, twin, false = (shapes.by_key[k] for k in ('seed', 'twin', 'false-shape'))
    turned_contours = tuple(tuple((z+3, x+8, y-4) for x, y, z in ring)
                            for ring in seed.contours)
    turned = replace(seed, key='turned', contours=turned_contours,
                     position=turned_contours[0][0], normal=(1, 0, 0))
    yield Task('holdout-spatial-rotation', 'Identical planar profile rotated onto another coordinate plane',
               body(seed, twin, turned, false), ('seed',), ('seed', 'twin', 'turned'))
    curved = replace(false, key='cylinder', geometry='cylinder', contours=(),
                     normal=None, radius=.8)
    yield Task('holdout-curved-distractor', 'Curved support surface is not a planar boundary analog',
               body(seed, twin, curved), ('seed',), ('seed', 'twin'))
    unknown = replace(false, key='unknown-trim', contours=())
    yield Task('holdout-unknown-candidate', 'Unknown trim is not promoted to proven shape analog',
               body(seed, twin, unknown), ('seed',), ('seed', 'twin'))
    missing = replace(seed, contours=())
    yield Task('holdout-unknown-seed', 'Without seed trim, scalar ties cannot prove shape: request clarification',
               body(missing, twin, false), ('seed',), ('seed',))
    clone = replace(twin, key='other-twin', contours=shifted(twin.contours, dx=6),
                    position=tuple(v+t for v, t in zip(twin.position, (6, 0, 0))))
    yield Task('holdout-identical-exclude', 'Identical translated analog excluded: no invented discriminator',
               body(seed, twin, clone, false), ('seed',), ('seed',), ('twin',),
               feedback_actions=1)
    small = (loop(((0, 0), (2, 0), (2, 1), (0, 1))),)
    second = face('second-seed', small)
    second_twin = face('second-twin', shifted(small, dy=9))
    yield Task('holdout-two-shape-families', 'Two distinct repeated profiles and an excluded third parallel profile',
               body(seed, twin, second, second_twin, false), ('seed', 'second-seed'),
               ('seed', 'twin', 'second-seed', 'second-twin'), ('false-shape',),
               feedback_actions=2)
