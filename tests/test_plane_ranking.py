# SPDX-License-Identifier: GPL-3.0-only
import unittest
from dataclasses import replace
import json
from math import sin, cos, pi

from Selectra.matching import Descriptor
from Selectra.snapshot import BodySnapshot
from Selectra.selection import SelectionSession
from Selectra.ranking import rank
from Selectra.plane_order import plane_class
from Selectra.matching import Tolerance


def circle(key, center, normal=(0, 0, 1)):
    return Descriptor(key, 'edge', 'circle', 6.283185307179586, radius=1,
                      normal=normal, position=center, scope_key='scope')


class PlaneRankingTests(unittest.TestCase):
    def test_identical_circles_expand_by_support_plane_before_orientation_changes(self):
        snapshot = BodySnapshot('scope', 'r1', (
            circle('seed', (0, 0, 0)), circle('outer', (4, 0, 0)),
            circle('outer-reversed', (8, 0, 0), (0, 0, -1)),
            circle('inner', (0, 0, -.2)), circle('inner-other', (4, 0, -.2)),
            circle('turned', (0, 0, 0), (1, 0, 0))))
        session = SelectionSession(snapshot, ('seed',))
        self.assertEqual(session.result, ('outer', 'outer-reversed', 'seed'))
        session.adjust_similarity(1)
        self.assertEqual(session.result, ('inner', 'inner-other', 'outer', 'outer-reversed', 'seed'))
        session.adjust_similarity(1)
        self.assertEqual(set(session.result), set(snapshot.by_key))

    def test_different_size_coplanar_circle_does_not_outrank_a_rotated_exact_match(self):
        a, b = circle('seed', (0, 0, 0)), circle('turned', (0, 0, 0), (1, 0, 0))
        c = replace(circle('larger', (4, 0, 0)), measure=12.566370614359172, radius=2)
        session = SelectionSession(BodySnapshot('scope', 'r1', (a, b, c)), ('seed',))
        self.assertEqual(session.result, ('seed', 'turned'))

    def test_plane_comparison_is_axial_strict_and_scale_safe(self):
        seed = circle('seed', (1e6, 0, 0), (0, 0, 1e300))
        self.assertEqual(plane_class(circle('a', (1e6+4, 0, 0), (0, 0, -1e-300)), (seed,), Tolerance()), 'coplanar')
        self.assertEqual(plane_class(circle('b', (1e6, 0, -.2)), (seed,), Tolerance()), 'parallel')
        angle = pi/180
        self.assertEqual(plane_class(circle('c', (1e6, 0, 0), (0, sin(angle), cos(angle))), (seed,), Tolerance()), 'other')

    def test_explicit_radius_does_not_implicitly_add_a_plane_criterion(self):
        snap = BodySnapshot('scope', 'r1', (circle('seed', (0, 0, 0)), circle('inner', (0, 0, -.2)),
                                           circle('outer', (3, 0, 0))))
        result = rank(snap, ('seed',), criterion='radius')
        self.assertEqual(set(result.tiers[0]), {'inner', 'outer'})
        self.assertFalse(result.plane_groups)

    def test_excluding_parallel_identical_circle_is_explained_by_plane(self):
        snap = BodySnapshot('scope', 'r1', (circle('seed', (0, 0, 0)), circle('inner', (0, 0, -.2)),
                                           circle('outer', (3, 0, 0))))
        session = SelectionSession(snap, ('seed',))
        session.exclude('inner')
        self.assertEqual(session.result, ('outer', 'seed'))
        self.assertFalse(session.ranking.ambiguous)
        session.replace_exclusions(('outer',))
        self.assertTrue(session.ranking.ambiguous)
        self.assertEqual(session.result, ('seed',))

    def test_explicit_examples_in_two_planes_preserve_both_plane_families(self):
        snap = BodySnapshot('scope', 'r1', (circle('seed', (0, 0, 0)), circle('inner', (0, 0, -.2)),
                                           circle('outer', (3, 0, 0)), circle('inner-twin', (3, 0, -.2))))
        a, b = rank(snap, ('seed', 'inner')), rank(snap, ('inner', 'seed'))
        self.assertEqual(a, b)
        self.assertEqual(set(SelectionSession(snap, ('seed', 'inner')).result), set(snap.by_key))

    def test_planar_shape_family_is_split_and_parallel_exclusion_has_an_explanation(self):
        def face(key, x=0, z=0):
            loop = ((x, 0, z), (x+4, 0, z), (x+4, 3, z), (x, 3, z))
            return Descriptor(key, 'face', 'plane', 12, perimeter=14, normal=(0, 0, 1),
                              position=loop[0], contours=(loop,), scope_key='scope')
        session = SelectionSession(BodySnapshot('scope', 'r1', (
            face('seed'), face('same', 10), face('parallel', z=-.2))), ('seed',))
        self.assertEqual(session.result, ('same', 'seed'))
        session.adjust_similarity(1)
        self.assertEqual(session.result, ('parallel', 'same', 'seed'))
        session.exclude('parallel')
        self.assertEqual(session.ranking.hypothesis, 'shape')
        self.assertFalse(session.ranking.ambiguous)
        self.assertEqual(session.result, ('same', 'seed'))
        session.replace_exclusions(('same',))
        self.assertTrue(session.ranking.ambiguous)
        self.assertEqual(session.result, ('seed',))

    def test_support_planes_are_immutable_and_roundtrip(self):
        planes = [([0, 0, 1], [0, 0, 0])]
        d = replace(circle('a', (0, 0, 0)), planes=planes)
        planes[0][0][2] = 0
        self.assertEqual(d.planes, (((0, 0, 1), (0, 0, 0)),))
        snap = BodySnapshot('scope', 'r1', (d,))
        self.assertEqual(BodySnapshot.from_dict(json.loads(snap.to_json())), snap)

    def test_rotated_reflected_translated_scene_preserves_all_tiers(self):
        entities = (circle('seed', (0, 0, 0)), circle('outer', (3, 0, 0)),
                    circle('inner', (0, 0, -.2)), circle('turned', (0, 0, 0), (1, 0, 0)))
        source = BodySnapshot('scope', 'r1', entities)
        def vector(v):
            return (-v[0], v[1]*cos(.37)-v[2]*sin(.37), v[1]*sin(.37)+v[2]*cos(.37))
        def point(p):
            return tuple(a+b for a, b in zip(vector(p), (300, -500, 120)))
        moved = BodySnapshot('scope', 'r1', tuple(replace(d, normal=vector(d.normal), position=point(d.position)) for d in entities))
        a, b = rank(source, ('seed',)), rank(moved, ('seed',))
        self.assertEqual(a.tiers, b.tiers)
        self.assertEqual(a.plane_groups, b.plane_groups)
        self.assertEqual(a.automatic_level, b.automatic_level)
        self.assertEqual(a, rank(source, (key for key in ('seed',))))

    def test_straight_edge_uses_adjacent_face_planes_and_unknowns_stay_last(self):
        seed = Descriptor('seed', 'edge', 'line', 2, direction=(1, 0, 0), scope_key='scope',
                          planes=(((0, 0, 1), (0, 0, 0)),))
        same = replace(seed, key='same', planes=(((0, 0, -1), (4, 0, 0)),))
        parallel = replace(seed, key='parallel', planes=(((0, 0, 1), (0, 0, -.2)),))
        other = replace(seed, key='other', planes=(((0, 1, 0), (0, 0, 0)),))
        unknown = replace(seed, key='unknown', planes=())
        result = rank(BodySnapshot('scope', 'r1', (seed, same, parallel, other, unknown)), ('seed',))
        self.assertEqual(result.tiers, (('same',), ('parallel',), ('other',), ('unknown',)))
        self.assertEqual(result.plane_groups, ('coplanar', 'parallel', 'other', 'unknown'))


if __name__ == '__main__':
    unittest.main()
