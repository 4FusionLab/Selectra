# SPDX-License-Identifier: GPL-3.0-only
from dataclasses import replace
import unittest

from Selectra.matching import Descriptor as D
from Selectra.snapshot import BodySnapshot
from Selectra.regions import similar_regions


def snapshot(nodes, links):
    return BodySnapshot('A', 'r1', tuple(D(k, 'face', 'plane', 1, scope_key='A') for k in nodes), tuple(links))


def square(x=0, y=0, z=0):
    return ((x, y, z), (x+1, y, z), (x+1, y+1, z), (x, y+1, z))


def region_snapshot(groups):
    entities, links = [], []
    for name, contours in groups:
        for i, loops in enumerate(contours):
            entities.append(D(name+str(i), 'face', 'plane', 1, scope_key='A', contours=loops))
            if i:
                links.append((name+str(i-1), name+str(i)))
    return BodySnapshot('A', 'r1', tuple(entities), tuple(links))


class RegionTests(unittest.TestCase):
    def test_repeated_region_matches_regardless_of_names_or_external_neighbours(self):
        body = snapshot('abcdefx', (('a', 'b'), ('b', 'c'), ('a', 'c'),
                                    ('d', 'e'), ('e', 'f'), ('d', 'f'), ('f', 'x')))
        result = similar_regions(body, ('b', 'a', 'c'))
        self.assertTrue(result.complete)
        self.assertEqual(result.regions, (('a', 'b', 'c'), ('d', 'e', 'f')))
        self.assertEqual(result.selection_keys(), tuple('abcdef'))

    def test_equal_counts_and_degrees_do_not_prove_equal_topology(self):
        # Triangular prism and K3,3: six vertices, nine links, degree three.
        prism = [('a', 'b'), ('b', 'c'), ('c', 'a'), ('d', 'e'), ('e', 'f'), ('f', 'd'),
                 ('a', 'd'), ('b', 'e'), ('c', 'f')]
        bipartite = [(a, b) for a in 'ghi' for b in 'jkl']
        body = snapshot('abcdefghijkl', prism + bipartite)
        result = similar_regions(body, tuple('abcdef'), max_states=100000)
        self.assertTrue(result.complete)
        self.assertEqual(result.regions, (tuple('abcdef'),))

    def test_induced_region_rejects_an_extra_internal_link(self):
        body = snapshot('abcdef', (('a', 'b'), ('b', 'c'), ('d', 'e'), ('e', 'f'), ('d', 'f')))
        result = similar_regions(body, tuple('abc'))
        self.assertTrue(result.complete)
        self.assertNotIn(tuple('def'), result.regions)

    def test_geometry_is_an_explicit_optional_refinement(self):
        body = snapshot('abcd', (('a', 'b'), ('c', 'd')))
        entities = tuple(replace(d, measure=3 if d.key in 'cd' else 1,
                                 contours=(square(ord(d.key)-ord('a'), 0),)) for d in body.entities)
        body = BodySnapshot('A', 'r1', entities, body.links)
        self.assertEqual(len(similar_regions(body, ('a', 'b')).regions), 2)
        self.assertEqual(similar_regions(body, ('a', 'b'), compare_geometry=True).regions, (('a', 'b'),))

    def test_geometry_requires_complete_contours(self):
        body = snapshot('abcd', (('a', 'b'), ('c', 'd')))
        result = similar_regions(body, ('a', 'b'), compare_geometry=True)
        self.assertFalse(result.complete)
        self.assertEqual(result.regions, ())
        with self.assertRaises(RuntimeError):
            result.selection_keys()

    def test_region_geometry_rejects_same_graph_with_wrong_spacing(self):
        body = region_snapshot((('a', ((square(),), (square(2),))),
                                ('b', ((square(10),), (square(12),))),
                                ('c', ((square(20),), (square(23),)))))
        result = similar_regions(body, ('a0', 'a1'), compare_geometry=True)
        self.assertTrue(result.complete)
        self.assertEqual(result.regions, (('a0', 'a1'), ('b0', 'b1')))

    def test_region_geometry_rejects_independent_face_rotation(self):
        vertical = ((2, 0, 0), (2, 1, 0), (2, 1, 1), (2, 0, 1))
        body = region_snapshot((('a', ((square(),), (square(2),))),
                                ('b', ((square(10),), (tuple((x+10, y, z) for x, y, z in vertical),)))))
        result = similar_regions(body, ('a0', 'a1'), compare_geometry=True)
        self.assertTrue(result.complete)
        self.assertEqual(result.regions, (('a0', 'a1'),))

    def test_region_accepts_one_shared_rotation_reflection_and_translation(self):
        def transform(p):
            x, y, z = p
            return (-y+10, z+5, x+3)
        first = ((square(),), (square(2, 1, 2),))
        second = tuple(tuple(tuple(transform(p) for p in loop) for loop in face) for face in first)
        body = region_snapshot((('a', first), ('b', second)))
        result = similar_regions(body, ('a0', 'a1'), compare_geometry=True)
        self.assertTrue(result.complete)
        self.assertEqual(result.regions, (('a0', 'a1'), ('b0', 'b1')))

    def test_strict_geometry_rejects_equal_scalar_different_contours(self):
        # Six sides, equal area/perimeter, unequal L-shaped trims.
        a = ((0, 0, 0), (5, 0, 0), (5, 4, 0), (1, 4, 0), (1, 2, 0), (0, 2, 0))
        b = ((0, 0, 0), (5, 0, 0), (5, 4, 0), (2, 4, 0), (2, 3, 0), (0, 3, 0))
        body = region_snapshot((('a', ((a,),)), ('b', ((b,),))))
        result = similar_regions(body, ('a0',), compare_geometry=True)
        self.assertTrue(result.complete)
        self.assertEqual(result.regions, (('a0',),))

    def test_relative_face_facing_must_share_the_common_transform(self):
        body = region_snapshot((('a', ((square(),), (square(2),))),
                                ('b', ((square(10),), (square(12),)))))
        entities = tuple(replace(d, normal=(0, 0, -1) if d.key == 'b1' else (0, 0, 1))
                         for d in body.entities)
        body = BodySnapshot('A', 'r1', entities, body.links)
        result = similar_regions(body, ('a0', 'a1'), compare_geometry=True)
        self.assertTrue(result.complete)
        self.assertEqual(result.regions, (('a0', 'a1'),))

    def test_collinear_step_divisions_do_not_change_region_geometry(self):
        split = ((0, 0, 0), (.5, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0))
        first = ((square(),), (square(2),))
        second = ((tuple((x+10, y, z) for x, y, z in split),), (square(12),))
        body = region_snapshot((('a', first), ('b', second)))
        result = similar_regions(body, ('a0', 'a1'), compare_geometry=True)
        self.assertTrue(result.complete)
        self.assertEqual(result.regions, (('a0', 'a1'), ('b0', 'b1')))

    def test_geometry_budget_includes_proof_not_only_graph_search(self):
        body = region_snapshot((('a', ((square(),), (square(2),))),
                                ('b', ((square(10),), (square(12),)))))
        result = similar_regions(body, ('a0', 'a1'), compare_geometry=True, max_states=50)
        self.assertFalse(result.complete)
        self.assertLessEqual(result.states, 50)
        with self.assertRaises(RuntimeError):
            result.selection_keys()

    def test_budget_exhaustion_cannot_be_applied_as_complete_selection(self):
        body = snapshot('abcdef', (('a', 'b'), ('b', 'c'), ('c', 'd'), ('d', 'e'), ('e', 'f')))
        result = similar_regions(body, ('a', 'b'), max_states=2)
        self.assertFalse(result.complete)
        self.assertLessEqual(result.states, 2)
        with self.assertRaises(RuntimeError):
            result.selection_keys()

    def test_result_limit_and_disconnected_patterns_are_explicit(self):
        body = snapshot('abcdef', (('a', 'b'), ('b', 'c'), ('c', 'd'), ('d', 'e'), ('e', 'f')))
        self.assertFalse(similar_regions(body, ('a', 'b'), max_results=1).complete)
        with self.assertRaises(ValueError):
            similar_regions(body, ('a', 'f'))
        with self.assertRaises(ValueError):
            similar_regions(body, ('outside',))


if __name__ == '__main__':
    unittest.main()
