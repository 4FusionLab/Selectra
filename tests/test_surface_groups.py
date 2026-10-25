# SPDX-License-Identifier: GPL-3.0-only
from dataclasses import replace
import unittest

from Selectra.contours import compare_contours
from Selectra.matching import Descriptor
from Selectra.snapshot import BodySnapshot
from Selectra.surface_groups import surface_groups


def loop(points, z=0):
    return tuple((x, y, z) for x, y in points)


def rect(x0, y0, x1, y1, z=0):
    return loop(((x0, y0), (x1, y0), (x1, y1), (x0, y1)), z)


def face(key, outer, *holes, normal=(0, 0, 1)):
    return Descriptor(key, 'face', 'plane', 1, normal=normal, position=outer[0],
                      scope_key='one-body', contours=(outer,)+holes)


def snapshot(*faces, links=()):
    return BodySnapshot('one-body', 'r1', faces, links)


class SurfaceGroupTests(unittest.TestCase):
    def assert_contours(self, actual, expected):
        result = compare_contours(actual, expected)
        self.assertTrue(result.complete)
        self.assertTrue(result.matched, actual)

    def test_two_fragments_union_and_source_keys_preserved(self):
        result = surface_groups(snapshot(face('a', rect(0, 0, 1, 2)),
                                         face('b', rect(1, 0, 3, 2)), links=(('a', 'b'),)))
        self.assertTrue(result.complete)
        self.assertEqual(result.selection_keys(), ('a', 'b'))
        self.assertEqual(len(result.groups), 1)
        self.assertEqual(result.groups[0].source_keys, ('a', 'b'))
        self.assert_contours(result.groups[0].contours, (rect(0, 0, 3, 2),))

    def test_collinear_subdivisions_and_t_junction(self):
        left = loop(((0, 0), (1, 0), (1, .4), (1, 2), (0, 2)))
        result = surface_groups(snapshot(face('a', left), face('b', rect(1, 0, 2, 1)),
                                         face('c', rect(1, 1, 2, 2)),
                                         links=(('a', 'b'), ('a', 'c'), ('b', 'c'))))
        self.assertTrue(result.complete, result)
        self.assert_contours(result.groups[0].contours, (rect(0, 0, 2, 2),))
        self.assertEqual(result.selection_keys(), ('a', 'b', 'c'))

    def test_four_fragments_form_outer_and_hole(self):
        # Four bars around a central rectangular opening.
        result = surface_groups(snapshot(face('bottom', rect(0, 0, 4, 1)),
                                         face('top', rect(0, 3, 4, 4)),
                                         face('left', rect(0, 1, 1, 3)),
                                         face('right', rect(3, 1, 4, 3)),
                                         links=(('bottom', 'left'), ('bottom', 'right'),
                                                ('top', 'left'), ('top', 'right'))))
        self.assertTrue(result.complete, result)
        self.assertEqual(len(result.groups[0].contours), 2)
        self.assert_contours(result.groups[0].contours, (rect(0, 0, 4, 4), rect(1, 1, 3, 3)))

    def test_fragment_can_fill_existing_hole(self):
        result = surface_groups(snapshot(face('ring', rect(0, 0, 4, 4), rect(1, 1, 3, 3)),
                                         face('fill', rect(1, 1, 3, 3)), links=(('ring', 'fill'),)))
        self.assertTrue(result.complete, result)
        self.assert_contours(result.groups[0].contours, (rect(0, 0, 4, 4),))

    def test_different_support_planes_and_unlinked_faces_stay_separate(self):
        result = surface_groups(snapshot(face('a', rect(0, 0, 1, 1)),
                                         face('b', rect(1, 0, 2, 1, z=1)),
                                         face('c', rect(2, 0, 3, 1)), links=(('a', 'b'),)))
        self.assertTrue(result.complete, result)
        self.assertEqual(tuple(group.source_keys for group in result.groups), (('a',), ('b',), ('c',)))

    def test_relative_similarity_tolerance_does_not_weld_a_real_gap(self):
        result = surface_groups(snapshot(face('a', rect(0, 0, 1, 1)),
                                         face('b', rect(1.001, 0, 2, 1)), links=(('a', 'b'),)))
        self.assertFalse(result.complete)
        self.assertEqual(result.rejected[0].source_keys, ('a', 'b'))
        with self.assertRaises(ValueError):
            result.selection_keys()

    def test_overlap_duplicate_and_containment_rejected(self):
        for second in (rect(.5, 0, 1.5, 1), rect(0, 0, 1, 1), rect(.2, .2, .8, .8)):
            with self.subTest(second=second):
                result = surface_groups(snapshot(face('a', rect(0, 0, 1, 1)),
                                                 face('b', second), links=(('a', 'b'),)))
                self.assertFalse(result.complete, result)
                self.assertFalse(result.groups)
                self.assertEqual(result.rejected[0].source_keys, ('a', 'b'))

    def test_point_contact_is_not_an_edge_connected_surface(self):
        result = surface_groups(snapshot(face('a', rect(0, 0, 1, 1)),
                                         face('b', rect(1, 1, 2, 2)), links=(('a', 'b'),)))
        self.assertFalse(result.complete)

    def test_invalid_trim_and_nonplanar_vertices_rejected(self):
        invalid = (loop(((0, 0), (2, 2), (0, 2), (2, 0))),
                   ((0, 0, 0), (1, 0, 0), (1, 1, .1), (0, 1, 0)))
        for outer in invalid:
            result = surface_groups(snapshot(face('a', outer)))
            self.assertFalse(result.complete, result)
        result = surface_groups(snapshot(face('a', rect(0, 0, 1, 1), rect(2, 2, 3, 3))))
        self.assertFalse(result.complete)

    def test_unknown_data_is_retained_as_rejected_source(self):
        missing = Descriptor('missing', 'face', 'plane', 1, scope_key='one-body')
        result = surface_groups(snapshot(face('a', rect(0, 0, 1, 1)), missing))
        self.assertFalse(result.complete)
        self.assertEqual(result.groups[0].source_keys, ('a',))
        self.assertEqual(result.rejected[0].source_keys, ('missing',))
        with self.assertRaises(ValueError):
            result.selection_keys()

    def test_budget_does_not_drop_any_source_reference(self):
        source = snapshot(face('a', rect(0, 0, 1, 1)), face('b', rect(1, 0, 2, 1)),
                          links=(('a', 'b'),))
        for maximum in (1, 2, 10, 50):
            result = surface_groups(source, max_states=maximum)
            self.assertFalse(result.complete)
            self.assertLessEqual(result.states, maximum)
            accounted = [key for group in result.groups for key in group.source_keys]
            accounted += [key for group in result.rejected for key in group.source_keys]
            self.assertCountEqual(accounted, ('a', 'b'))
        result = surface_groups(source, max_fragments=1)
        self.assertFalse(result.complete)
        self.assertEqual(result.rejected[0].source_keys, ('a', 'b'))
        self.assertFalse(surface_groups(source, max_points=3).complete)

    def test_rigid_transform_winding_order_and_normal_sign(self):
        source = snapshot(face('a', rect(0, 0, 1, 2)),
                          face('b', tuple(reversed(rect(1, 0, 3, 2))), normal=(0, 0, -1)),
                          links=(('a', 'b'),))
        def transform(p):
            x, y, z = p
            return z+7, x-3, y+5
        moved = replace(source, entities=tuple(replace(d, normal=(d.normal[2], d.normal[0], d.normal[1]),
                        position=transform(d.position),
                        contours=tuple(tuple(transform(p) for p in ring) for ring in d.contours))
                         for d in reversed(source.entities)))
        result = surface_groups(moved)
        self.assertTrue(result.complete, result)
        self.assertEqual(result.groups[0].source_keys, ('a', 'b'))
        expected = (tuple(transform(p) for p in rect(0, 0, 3, 2)),)
        self.assert_contours(result.groups[0].contours, expected)

    def test_limits_and_entity_kind_validated(self):
        empty = snapshot()
        for kwargs in ({'max_states': 0}, {'max_points': 2}, {'max_fragments': True}):
            with self.assertRaises(ValueError):
                surface_groups(empty, **kwargs)
        edge = Descriptor('e', 'edge', 'line', 1, scope_key='one-body')
        with self.assertRaises(ValueError):
            surface_groups(snapshot(edge))
        self.assertEqual(surface_groups(empty).selection_keys(), ())


if __name__ == '__main__':
    unittest.main()
