# SPDX-License-Identifier: GPL-3.0-only
from dataclasses import replace
import math
import unittest

from Selectra.walls import PlanarPatch, wall_probe_points, confirm_wall


def rectangle(x0=0, y0=0, x1=4, y1=3, z=0):
    return ((x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z))


def patch(key, z, normal, outer=None, holes=()):
    return PlanarPatch(key, normal, (0, 0, z),
                       (outer or rectangle(z=z),) + tuple(holes))


class WallTests(unittest.TestCase):
    def setUp(self):
        self.a = patch('outer', 0, (0, 0, 1))
        self.b = patch('inner', -.2, (0, 0, -1))

    def test_material_is_mandatory_and_discrete(self):
        probe = wall_probe_points(self.a, self.b)
        self.assertTrue(probe.complete)
        self.assertAlmostEqual(probe.thickness, .2)
        self.assertAlmostEqual(probe.overlap_area, 12)
        self.assertEqual(len(probe.points), 5)
        self.assertTrue(all(-.2 < p[2] < 0 for p in probe.points))
        self.assertIsNone(confirm_wall(probe, ()))
        relation = confirm_wall(probe, [True]*len(probe.points))
        self.assertEqual(relation.evidence, 'sampled_material')
        self.assertEqual(relation.probe_count, 5)

    def test_empty_gap_unknown_and_boundary_are_not_material(self):
        probe = wall_probe_points(self.a, self.b)
        for failure in (False, None, 0, 1, 'inside'):
            evidence = [True]*len(probe.points)
            evidence[2] = failure
            self.assertIsNone(confirm_wall(probe, evidence))

    def test_cavity_facing_normals_rejected_before_material(self):
        cavity = patch('cavity', .2, (0, 0, -1))
        probe = wall_probe_points(self.a, cavity)
        self.assertTrue(probe.complete)
        self.assertFalse(probe.points)
        self.assertEqual(probe.reason, 'not_behind_outward_normal')

    def test_axes_and_signed_normals_must_agree(self):
        for normal in ((0, 0, 1), (1, 0, 0), (.1, 0, -1)):
            self.assertEqual(wall_probe_points(self.a, replace(self.b, normal=normal)).reason,
                             'normals_not_opposed')

    def test_nonoverlap_and_edge_contact_are_rejected(self):
        for x in (4, 5):
            other = patch('elsewhere', -.2, (0, 0, -1), rectangle(x, 0, x+2, 2, -.2))
            self.assertEqual(wall_probe_points(self.a, other).reason, 'no_trimmed_overlap')

    def test_partial_overlap_uses_local_geometry_not_centers(self):
        other = patch('small', -.2, (0, 0, -1), rectangle(3, 1, 5, 2, -.2))
        probe = wall_probe_points(self.a, other)
        self.assertTrue(probe.complete)
        self.assertAlmostEqual(probe.overlap_area, 1)
        self.assertTrue(all(3 < x < 4 and 1 < y < 2 for x, y, _ in probe.points))

    def test_hole_containing_entire_other_face_is_not_overlap(self):
        a = patch('holed', 0, (0, 0, 1), holes=(rectangle(1, 1, 3, 2),))
        b = patch('inside-hole', -.2, (0, 0, -1), rectangle(1.2, 1.2, 2.8, 1.8, -.2))
        self.assertEqual(wall_probe_points(a, b).reason, 'no_trimmed_overlap')

    def test_holes_are_subtracted_and_probes_avoid_them(self):
        a = patch('holed', 0, (0, 0, 1), holes=(rectangle(1, 1, 3, 2),))
        probe = wall_probe_points(a, self.b)
        self.assertAlmostEqual(probe.overlap_area, 10)
        for x, y, _ in probe.points:
            self.assertFalse(1 <= x <= 3 and 1 <= y <= 2)

    def test_holes_in_both_faces_and_winding_do_not_change_area(self):
        a = patch('holed', 0, (0, 0, 1), holes=(rectangle(1, 1, 2, 2),))
        b = patch('also-holed', -.2, (0, 0, -1),
                  tuple(reversed(rectangle(z=-.2))),
                  (tuple(reversed(rectangle(2, 1, 3, 2, -.2))),))
        self.assertAlmostEqual(wall_probe_points(a, b).overlap_area, 10)

    def test_concave_boundary_does_not_fill_bounding_box(self):
        shape = ((0, 0, 0), (4, 0, 0), (4, 1, 0), (1, 1, 0), (1, 3, 0), (0, 3, 0))
        a = patch('concave', 0, (0, 0, 1), shape)
        self.assertAlmostEqual(wall_probe_points(a, self.b).overlap_area, 6)

    def test_crossing_edges_add_scan_events(self):
        a = patch('triangle-a', 0, (0, 0, 1), ((0, 0, 0), (4, 0, 0), (0, 4, 0)))
        b = patch('triangle-b', -.2, (0, 0, -1),
                  ((0, 0, -.2), (4, 4, -.2), (4, 0, -.2)))
        # Intersection triangle: (0,0), (2,2), (4,0).
        self.assertAlmostEqual(wall_probe_points(a, b).overlap_area, 4)

    def test_locality_limit_and_zero_thickness(self):
        self.assertEqual(wall_probe_points(self.a, self.b, max_thickness=.1).reason,
                         'thickness_limit')
        self.assertEqual(wall_probe_points(self.a, replace(self.a, key='same-plane',
                                                          normal=(0, 0, -1))).reason,
                         'not_behind_outward_normal')

    def test_default_locality_is_scale_invariant_and_rejects_solid_block(self):
        far = patch('far', -2, (0, 0, -1))
        rejected = wall_probe_points(self.a, far)
        self.assertTrue(rejected.complete)
        self.assertEqual(rejected.reason, 'thickness_limit')
        self.assertTrue(wall_probe_points(self.a, far, max_thickness=3).points)
        for scale in (.01, 100):
            def scaled(p):
                return PlanarPatch(p.key, p.normal, tuple(c*scale for c in p.position),
                                   tuple(tuple(tuple(c*scale for c in q) for q in loop)
                                         for loop in p.contours))
            self.assertTrue(wall_probe_points(scaled(self.a), scaled(self.b)).points)
            self.assertEqual(wall_probe_points(scaled(self.a), scaled(far)).reason,
                             'thickness_limit')

    def test_tiny_overlap_is_not_a_wall_hypothesis(self):
        sliver = patch('sliver', -.2, (0, 0, -1), rectangle(3.9, 0, 7.9, 3, -.2))
        probe = wall_probe_points(self.a, sliver)
        self.assertTrue(probe.complete)
        self.assertEqual(probe.reason, 'insufficient_trimmed_overlap')
        self.assertIsNone(confirm_wall(probe, ()))

    def test_far_high_segment_pair_is_negative_before_arrangement_budget(self):
        count = 600
        outer = tuple((math.cos(i*math.tau/count), math.sin(i*math.tau/count), 0)
                      for i in range(count))
        far = tuple((x, y, -2) for x, y, _ in outer)
        a = patch('round-a', 0, (0, 0, 1), outer)
        b = patch('round-b', -2, (0, 0, -1), far)
        probe = wall_probe_points(a, b)
        self.assertTrue(probe.complete)
        self.assertEqual(probe.reason, 'thickness_limit')
        self.assertEqual(probe.points, ())

    def test_typical_stroked_circular_wall_fits_default_budgets(self):
        # Roughly the stroke count for radius=1cm and a 1e-4cm chord tolerance.
        count = 224
        outer = tuple((math.cos(i*math.tau/count), math.sin(i*math.tau/count), 0)
                      for i in range(count))
        inner = tuple((x, y, -.1) for x, y, _ in outer)
        probe = wall_probe_points(patch('round-a', 0, (0, 0, 1), outer),
                                  patch('round-b', -.1, (0, 0, -1), inner))
        self.assertTrue(probe.complete)
        self.assertGreater(probe.trace_count, 16)
        self.assertAlmostEqual(probe.thickness, .1)
        self.assertIsNotNone(confirm_wall(probe, [True]*len(probe.points)))

    def test_missing_nonplanar_and_budget_fail_closed(self):
        self.assertEqual(wall_probe_points(self.a, replace(self.b, contours=())).reason,
                         'missing_contours')
        broken = replace(self.b, contours=(((0, 0, 0), (4, 0, -.2), (0, 3, -.2)),))
        self.assertEqual(wall_probe_points(self.a, broken).reason, 'nonplanar_contour')
        self.assertEqual(wall_probe_points(self.a, self.b, max_segments=6).reason,
                         'segment_budget')

    def test_trace_budget_bounds_material_queries(self):
        holes = tuple(rectangle(x, .5, x+.2, 2.5) for x in (.5, 1, 1.5, 2, 2.5, 3))
        a = patch('many-holes', 0, (0, 0, 1), holes=holes)
        probe = wall_probe_points(a, self.b, max_probes=3)
        self.assertFalse(probe.complete)
        self.assertEqual(probe.reason, 'trace_budget')
        self.assertEqual(probe.points, ())
        probe = wall_probe_points(a, self.b, max_probes=64)
        self.assertTrue(probe.complete)
        self.assertEqual(len(probe.points), probe.trace_count*5)
        self.assertAlmostEqual(probe.overlap_area, 9.6)

    def test_rigid_rotation_translation_and_reflection_preserve_relation(self):
        reference = wall_probe_points(self.a, self.b)
        # Orthogonal transform, including a reflection, without a world-axis dependency.
        def vector(p):
            x, y, z = p
            angle = .6
            return (-x, y*math.cos(angle)-z*math.sin(angle),
                    y*math.sin(angle)+z*math.cos(angle))
        def point(p):
            return tuple(x+y for x, y in zip(vector(p), (10, -3, 8)))
        def transform(p):
            return PlanarPatch(p.key, vector(p.normal), point(p.position),
                               tuple(tuple(point(q) for q in loop) for loop in p.contours))
        result = wall_probe_points(transform(self.a), transform(self.b))
        self.assertTrue(result.complete)
        self.assertAlmostEqual(result.thickness, reference.thickness)
        self.assertAlmostEqual(result.overlap_area, reference.overlap_area)
        self.assertEqual(result.trace_count, reference.trace_count)

    def test_reverse_pair_has_same_geometric_evidence(self):
        forward, backward = wall_probe_points(self.a, self.b), wall_probe_points(self.b, self.a)
        self.assertTrue(backward.complete)
        self.assertEqual(forward.keys, backward.keys)
        self.assertAlmostEqual(forward.overlap_area, backward.overlap_area)
        self.assertAlmostEqual(forward.thickness, backward.thickness)

    def test_validation_and_immutable_coordinates(self):
        source = [[list(point) for point in rectangle()]]
        patch_a = PlanarPatch('A', [0, 0, 2], [0, 0, 0], source)
        source[0][0][0] = 10
        self.assertEqual(patch_a.contours[0][0], (0, 0, 0))
        for normal in ((0, 0, 0), (0, 0, float('nan'))):
            with self.assertRaises(ValueError):
                replace(patch_a, normal=normal)
        for kwargs in ({'max_probes': 0}, {'max_segments': 2}, {'max_thickness': -1}):
            with self.assertRaises(ValueError):
                wall_probe_points(self.a, self.b, **kwargs)


if __name__ == '__main__':
    unittest.main()
