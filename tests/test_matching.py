# SPDX-License-Identifier: GPL-3.0-only
"""Intent behavior, false positives and numerical boundaries (no adsk mocks)."""
from dataclasses import replace
from math import nan
import unittest

from Selectra.matching import Descriptor as D, Tolerance, infer


def line(key, length=1, direction=(1, 0, 0)):
    return D(key, 'edge', 'line', length, direction=direction)


def plane(key, area=2, perimeter=6, normal=(0, 0, 1), sides=4, loops=1):
    return D(key, 'face', 'plane', area, perimeter=perimeter,
             normal=normal, sides=sides, loops=loops)


class IntentTests(unittest.TestCase):
    def test_two_different_lengths_teach_parallel_intent(self):
        a, b = line('a'), line('b', 2, (-1, 0, 0))
        c, wrong = line('c', 3), line('wrong', 1, (0, 1, 0))
        result = infer([a, b], [wrong, c, b, a])
        self.assertEqual(result.proposals[0].intent, 'direction')
        self.assertEqual(result.proposals[0].keys, ('a', 'b', 'c'))

    def test_two_different_directions_teach_length_intent(self):
        a, b = line('a'), line('b', direction=(0, 1, 0))
        c, wrong = line('c', direction=(0, 0, 1)), line('wrong', 2)
        result = infer([a, b], [a, b, c, wrong])
        self.assertEqual(result.proposals[0].intent, 'length')
        self.assertEqual(result.proposals[0].keys, ('a', 'b', 'c'))

    def test_single_example_reports_ambiguity_for_different_sets(self):
        a, both = line('a'), line('both')
        length, direction = line('length', direction=(0, 1, 0)), line('direction', 3)
        result = infer([a], [a, both, length, direction])
        self.assertTrue(result.ambiguous)
        self.assertGreaterEqual(len(result.proposals), 2)
        self.assertEqual(result.proposals[0].keys, ('a', 'both'))

    def test_circle_radius_is_preferred_to_circumference_coincidence(self):
        a = D('a', 'edge', 'circle', 6.28, radius=1)
        b = replace(a, key='b')
        arc = D('arc', 'edge', 'arc', 6.28, radius=2)
        result = infer([a], [a, b, arc])
        self.assertEqual(result.proposals[0].keys, ('a', 'b'))
        self.assertEqual(result.proposals[0].intent, 'radius_size')

    def test_cylinders_with_different_areas_teach_radius(self):
        a = D('a', 'face', 'cylinder', 10, radius=1)
        b, c = replace(a, key='b', measure=20), replace(a, key='c', measure=30)
        wrong = replace(a, key='wrong', radius=2)
        result = infer([a, b], [a, b, c, wrong])
        self.assertEqual(result.proposals[0].intent, 'radius')
        self.assertEqual(result.proposals[0].keys, ('a', 'b', 'c'))

    def test_boundary_signature_rejects_equal_area_different_shape(self):
        a, b = plane('a'), plane('b')
        rectangle = plane('rectangle', perimeter=10)
        result = infer([a], [a, b, rectangle])
        self.assertEqual(result.proposals[0].keys, ('a', 'b'))
        self.assertTrue(any('rectangle' in h.keys for h in result.proposals))

    def test_face_normals_are_oriented_not_axial(self):
        a, b = plane('a'), plane('b', area=3)
        back = plane('back', area=4, normal=(0, 0, -1))
        result = infer([a, b], [a, b, back, plane('c', area=5)])
        self.assertEqual(result.proposals[0].intent, 'normal')
        self.assertNotIn('back', result.proposals[0].keys)

    def test_curved_faces_do_not_get_a_global_normal(self):
        a = D('a', 'face', 'nurbs', 10)
        b = replace(a, key='b', measure=20)
        self.assertFalse(infer([a], [a, b]).proposals)

    def test_near_zero_dimensions_use_absolute_tolerance(self):
        a, b = line('a', 1e-7), line('b', 2e-7)
        self.assertTrue(infer([a], [a, b]).proposals)

    def test_no_transitive_seed_drift(self):
        a = D('a', 'edge', 'arc', 1, radius=1)
        b = replace(a, key='b', radius=1.009, measure=2)
        c = replace(a, key='c', radius=1.018, measure=3)
        extra = replace(a, key='extra', radius=1.009, measure=4)
        self.assertFalse(infer([a, b, c], [a, b, c, extra]).proposals)

    def test_duplicate_result_sets_are_collapsed(self):
        a, b = line('a'), line('b')
        result = infer([a], [b, a])
        self.assertEqual(len(result.proposals), 1)
        self.assertFalse(result.ambiguous)

    def test_order_independent(self):
        a, b, c = line('a'), line('b', 2), line('c', 3)
        self.assertEqual(infer([a, b], [a, b, c]), infer([b, a], [c, b, a]))

    def test_seed_is_preserved_even_if_absent_from_pool(self):
        a, b = line('a'), line('b')
        self.assertEqual(infer([a], [b]).proposals[0].keys, ('a', 'b'))

    def test_no_growth_does_not_invent_a_result(self):
        self.assertFalse(infer([line('a')], []).proposals)

    def test_mixed_entity_kinds_are_rejected(self):
        self.assertFalse(infer([line('a'), plane('b')], []).proposals)

    def test_missing_radii_are_not_equal(self):
        a = D('a', 'face', 'cylinder', 10)
        b = replace(a, key='b', measure=20)
        self.assertFalse(infer([a], [a, b]).proposals)

    def test_invalid_inputs_are_explicit(self):
        with self.assertRaises(ValueError):
            Tolerance(relative=nan)
        with self.assertRaises(ValueError):
            infer([line('a')], [line('b'), line('b')])
        with self.assertRaises(ValueError):
            infer([line('a')], [line('a', 2)])
        for measure in (0, -1, nan):
            self.assertFalse(infer([line('a', measure)], [line('b')]).proposals)

    def test_unknown_entities_do_not_use_length_intent(self):
        self.assertFalse(infer([D('a', 'mesh', 'triangle', 1)], []).proposals)


if __name__ == '__main__':
    unittest.main()
