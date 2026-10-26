# SPDX-License-Identifier: GPL-3.0-only
import json
import unittest
from dataclasses import replace
from math import sin, cos
from Selectra.matching import Descriptor
from Selectra.snapshot import BodySnapshot
from Selectra.selection import SelectionSession
from Selectra.curved_regions import matches, Budget
from Selectra.matching import Tolerance


def patch(key, points, family='nurbs', axis=None):
    return Descriptor(key, 'face', family, 1, perimeter=4, direction=axis, scope_key='s',
                      patch=(points, points, ((0, 1, 2),), ((0, 0, 1),)*3))


def pattern():
    return (patch('a', ((0, 0, 0), (1, 0, 0), (0, 1, 0)), 'cylinder', (0, 0, 1)),
            patch('b', ((0, 0, 0), (-1, 0, 0), (0, 1, .3))))


def moved(d, key, shift=(5, 0, 0), angle=0, mirror=False):
    def vector(p):
        x, y, z = p
        x = -x if mirror else x
        return x, cos(angle)*y-sin(angle)*z, sin(angle)*y+cos(angle)*z
    def point(p):
        return tuple(a+b for a, b in zip(vector(p), shift))
    landmarks, points, triangles, normals = d.patch
    return replace(d, key=key, direction=vector(d.direction) if d.direction else None,
                   patch=(tuple(map(point, landmarks)), tuple(map(point, points)), triangles, tuple(map(vector, normals))))


class CurvedRegionTests(unittest.TestCase):
    def test_curved_group_is_found_as_a_whole(self):
        a, b = pattern()
        c, d = moved(a, 'c'), moved(b, 'd')
        s = SelectionSession(BodySnapshot('s', 'r', (a, b, c, d), (('a', 'b'), ('c', 'd'))), ('a', 'b'))
        self.assertEqual(s.result, ('a', 'b', 'c', 'd'))
        self.assertEqual(s.ranking.hypothesis, 'curved_regions')

    def test_whole_groups_expand_coplanar_parallel_other(self):
        a, b = pattern()
        entities, links = [a, b], [('a', 'b')]
        for names, shift, angle in ((('c', 'd'), (5, 0, 0), 0), (('e', 'f'), (10, 0, 2), 0),
                                     (('g', 'h'), (15, 0, 0), 1.5707963267948966)):
            entities += [moved(a, names[0], shift, angle), moved(b, names[1], shift, angle)]
            links.append(names)
        snap = BodySnapshot('s', 'r', tuple(entities), tuple(links))
        s = SelectionSession(snap, ('a', 'b'))
        self.assertEqual(s.ranking.plane_groups[:3], ('coplanar', 'parallel', 'other'))
        self.assertEqual(s.result, ('a', 'b', 'c', 'd'))
        s.adjust_similarity(1)
        self.assertEqual(s.result, ('a', 'b', 'c', 'd', 'e', 'f'))
        s.adjust_similarity(1)
        self.assertEqual(len(s.result), 8)
        self.assertEqual(s.ranking, SelectionSession(snap, ('b', 'a')).ranking)
        s.exclude('d')
        self.assertNotIn('c', s.result)
        self.assertNotIn('d', s.result)

    def test_same_sizes_and_graph_with_wrong_arrangement_are_rejected(self):
        a, b = pattern()
        c, d = moved(a, 'c'), moved(b, 'd', (7, 0, 0))
        s = SelectionSession(BodySnapshot('s', 'r', (a, b, c, d), (('a', 'b'), ('c', 'd'))), ('a', 'b'))
        self.assertEqual(s.result, ('a', 'b'))
        self.assertEqual(s.level, 0)

    def test_sampled_surface_bulge_is_rejected_even_with_identical_landmarks(self):
        a, b = pattern()
        landmarks, points, triangles, normals = a.patch
        bent = replace(a, key='bad', patch=(landmarks, points+((.3, .3, .5),),
                                            ((0, 1, 3), (1, 2, 3), (2, 0, 3)), normals+((0, 0, 1),)))
        self.assertFalse(matches((a, b), (bent, b), Tolerance(), Budget(), {}))

    def test_rigid_reflection_and_facing_are_verified(self):
        a, b = pattern()
        target = (moved(a, 'c', angle=.4, mirror=True), moved(b, 'd', angle=.4, mirror=True))
        self.assertTrue(matches((a, b), target, Tolerance(), Budget(), {}))
        def reverse(d):
            landmarks, points, tris, normals = d.patch
            return replace(d, patch=(landmarks, points, tris, tuple(tuple(-x for x in n) for n in normals)))
        self.assertFalse(matches((a, b), tuple(map(reverse, target)), Tolerance(), Budget(), {}))

    def test_missing_mesh_and_budget_cannot_apply_partial_groups(self):
        a, b = pattern()
        c, d = moved(a, 'c'), moved(b, 'd')
        with self.assertRaisesRegex(ValueError, 'budget'):
            matches((a, b), (c, d), Tolerance(), Budget(limit=1), {})
        with self.assertRaisesRegex(ValueError, 'unavailable'):
            SelectionSession(BodySnapshot('s', 'r', (a, b, c, replace(d, patch=())), (('a', 'b'), ('c', 'd'))), ('a', 'b'))

    def test_surface_mesh_roundtrip_and_immutable_input(self):
        a, b = pattern()
        snap = BodySnapshot('s', 'r', (a, b), (('a', 'b'),))
        self.assertEqual(BodySnapshot.from_dict(json.loads(snap.to_json())), snap)
        with self.assertRaises(ValueError):
            replace(a, patch=((), ((0, 0, 0),), ((0, 1, 2),), ((0, 0, 1),)))
