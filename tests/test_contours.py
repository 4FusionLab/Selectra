# SPDX-License-Identifier: GPL-3.0-only
import math
import unittest

from Selectra.contours import compare_contours, contours_match, normalize_contours
from Selectra.matching import Tolerance


def polygon(points, z=0):
    return tuple((x, y, z) for x, y in points)


def rectangle(x=0, y=0, width=8, height=5):
    return polygon(((x, y), (x+width, y), (x+width, y+height), (x, y+height)))


def transform(loops, *, reflect=False):
    # Proper arbitrary 3D rotation followed by optional reflection and shift.
    c, s = math.cos(.73), math.sin(.73)
    result = []
    for loop in loops:
        row = []
        for x, y, z in loop:
            if reflect:
                x = -x
            x, y = c*x-s*y, s*x+c*y
            y, z = .6*y-.8*z, .8*y+.6*z
            row.append((x+71.2, y-8.3, z+13.4))
        result.append(tuple(row))
    return tuple(result)


class ContourTests(unittest.TestCase):
    def test_same_boundary_under_translation_rotation_and_reflection(self):
        loops = (polygon(((0, 0), (4, 0), (4, 1), (1, 1), (1, 3), (0, 3))),)
        for reflection in (False, True):
            result = compare_contours(loops, transform(loops, reflect=reflection))
            self.assertTrue(result.matched)
            self.assertTrue(result.complete)

    def test_same_area_and_perimeter_do_not_prove_congruence(self):
        # All cuts remove one 1x1 corner of a 4x4 square: area 15, perimeter 16.
        # A centred notch changes perimeter; these unequal L-arms instead use
        # two removed 1x1 corner squares versus one 1x2 corner rectangle.
        a = polygon(((0, 0), (4, 0), (4, 4), (1, 4), (1, 2), (0, 2)))
        b = polygon(((1, 0), (4, 0), (4, 3), (3, 3), (3, 4), (0, 4), (0, 1), (1, 1)))
        # Both area=14, perimeter=16; number of vertices also is not shape.
        def area(loop):
            return abs(sum(p[0]*q[1]-q[0]*p[1] for p, q in zip(loop, loop[1:]+loop[:1])))/2
        def perimeter(loop):
            return sum(math.dist(p, q) for p, q in zip(loop, loop[1:]+loop[:1]))
        self.assertEqual(area(a), area(b))
        self.assertEqual(perimeter(a), perimeter(b))
        result = compare_contours((a,), (b,))
        self.assertFalse(result.matched)
        self.assertTrue(result.complete)

    def test_equal_area_perimeter_and_side_count_do_not_prove_shape(self):
        a = polygon(((0, 0), (5, 0), (5, 4), (1, 4), (1, 2), (0, 2)))
        b = polygon(((0, 0), (5, 0), (5, 4), (2, 4), (2, 3), (0, 3)))
        # Both are six-sided L shapes of area 18 and perimeter 18.
        self.assertFalse(contours_match((a,), (b,)))

    def test_equal_vertex_count_and_dimensions_still_require_shape(self):
        a = polygon(((0, 0), (4, 0), (4, 3), (0, 3)))
        b = polygon(((0, 0), (4, 0), (5, 3), (1, 3)))
        self.assertFalse(contours_match((a,), (b,)))

    def test_scale_is_preserved(self):
        loops = (rectangle(),)
        doubled = tuple(tuple(tuple(2*x for x in p) for p in loop) for loop in loops)
        self.assertFalse(contours_match(loops, doubled))

    def test_collinear_step_splits_and_closing_point_are_ignored(self):
        a = (rectangle(),)
        split = polygon(((0, 0), (2, 0), (8, 0), (8, 1), (8, 5), (4, 5), (0, 5), (0, 2), (0, 0)))
        self.assertTrue(contours_match(a, transform((split,))))

    def test_hole_order_winding_and_loop_start_do_not_matter(self):
        a = (rectangle(), rectangle(1, 1, 1, 1), rectangle(5, 2, 2, 1))
        b = transform(a)
        b = (b[0][2:]+b[0][:2], tuple(reversed(b[2])), b[1][1:]+b[1][:1])
        self.assertTrue(contours_match(a, b))

    def test_holes_cannot_move_independently(self):
        a = (rectangle(), rectangle(1, 1, 1, 1), rectangle(5, 2, 2, 1))
        b = (rectangle(), rectangle(2, 1, 1, 1), rectangle(5, 2, 2, 1))
        self.assertFalse(contours_match(a, b))

    def test_hole_reflection_uses_one_transform_for_all_loops(self):
        a = (rectangle(), rectangle(1, 1, 1, 1), rectangle(5, 2, 2, 1))
        self.assertTrue(contours_match(a, transform(a, reflect=True)))

    def test_missing_hole_never_matches(self):
        a = (rectangle(), rectangle(1, 1, 1, 1))
        self.assertFalse(contours_match(a, a[:1]))

    def test_nonplanar_and_missing_data_are_incomplete(self):
        nonplanar = (((0, 0, 0), (1, 0, 0), (1, 1, 1), (0, 1, 0)),)
        for bad in ((), None, (((0, 0, 0), (1, 0, 0)),), nonplanar,
                    (((0, 0, 0), (1, 0, 0), (float('nan'), 1, 0)),)):
            result = compare_contours(bad, (rectangle(),))
            self.assertFalse(result.matched)
            self.assertFalse(result.complete)

    def test_invalid_topology_cannot_prove_a_match(self):
        bowtie = polygon(((0, 0), (3, 3), (0, 3), (2, 0)))
        for loops in ((bowtie,), (rectangle(), rectangle(20, 1, 1, 1)),
                      (rectangle(), rectangle(1, 1, 3, 3), rectangle(2, 2, 1, 1)),
                      (rectangle(), rectangle(0, 1, 1, 1))):
            result = compare_contours(loops, loops)
            self.assertFalse(result.matched)
            self.assertFalse(result.complete)

    def test_budget_hit_is_explicit_and_cannot_match(self):
        result = compare_contours((rectangle(),), (rectangle(),), max_states=1)
        self.assertFalse(result.matched)
        self.assertFalse(result.complete)
        self.assertLessEqual(result.states, 1)
        self.assertFalse(contours_match((rectangle(),), (rectangle(),), max_points=3))
        with self.assertRaises(ValueError):
            compare_contours((rectangle(),), (rectangle(),), max_states=0)

    def test_normalization_copies_nested_input(self):
        a = [[[0, 0, 0], [1, 0, 0], [0, 1, 0]]]
        result = normalize_contours(a)
        a[0][0][0] = 100
        self.assertEqual(result[0][0], (0, 0, 0))

    def test_tolerance_is_geometric_and_does_not_erase_corners(self):
        a = (rectangle(),)
        close = (polygon(((0, 0), (8.00001, 0), (8, 5), (0, 5))),)
        self.assertTrue(contours_match(a, close))
        strict = Tolerance(relative=0, length=1e-8)
        self.assertFalse(contours_match(a, close, strict))
        notch = (polygon(((0, 0), (8, 0), (8, 5), (4, 5), (4, 4), (3, 4), (3, 5), (0, 5))),)
        self.assertFalse(contours_match(a, notch))


if __name__ == '__main__':
    unittest.main()
