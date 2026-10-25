# SPDX-License-Identifier: GPL-3.0-only
from dataclasses import replace
import unittest

from Selectra.matching import Descriptor as D
from Selectra.snapshot import BodySnapshot
from Selectra.regions import similar_regions


def snapshot(nodes, links):
    return BodySnapshot('A', 'r1', tuple(D(k, 'face', 'plane', 1, scope_key='A') for k in nodes), tuple(links))


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
        entities = tuple(replace(d, measure=3) if d.key in 'cd' else d for d in body.entities)
        body = BodySnapshot('A', 'r1', entities, body.links)
        self.assertEqual(len(similar_regions(body, ('a', 'b')).regions), 2)
        self.assertEqual(similar_regions(body, ('a', 'b'), compare_geometry=True).regions, (('a', 'b'),))

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
