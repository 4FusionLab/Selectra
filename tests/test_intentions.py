# SPDX-License-Identifier: GPL-3.0-only
from dataclasses import replace
import unittest

from Selectra.matching import Descriptor
from Selectra.selection import SelectionSession
from Selectra.snapshot import BodySnapshot


def face(key, width, height, x=0, z=0, normal=(0, 0, 1)):
    points = ((x, 0, z), (x+width, 0, z), (x+width, height, z), (x, height, z))
    return Descriptor(key, 'face', 'plane', width*height, perimeter=2*(width+height),
                      normal=normal, position=points[0], contours=(points,), scope_key='A')


class IntentTests(unittest.TestCase):
    def test_wall_motif_rejects_different_tangential_arrangement(self):
        a = face('a', 4, 3)
        b = face('b', 3.6, 2.6, .2, -.2, (0, 0, -1))
        c = face('c', 4, 3, 10)
        d = face('d', 3.6, 2.6, 11.2, -.2, (0, 0, -1))
        e = face('e', 4, 3, 20)
        f = face('f', 3.6, 2.6, 20.2, -.2, (0, 0, -1))
        snapshot = BodySnapshot('A', 'r1', (a, b, c, d, e, f),
                                wall_pairs=(('a', 'b'), ('c', 'd'), ('e', 'f')))
        session = SelectionSession(snapshot, ('a', 'b'))
        self.assertEqual(session.ranking.hypothesis, 'wall_sides')
        self.assertEqual(session.result, ('a', 'b', 'e', 'f'))

    def test_connected_examples_find_whole_repeated_node(self):
        a, b = face('a', 4, 3), face('b', 2, 1, 4)
        c, d = face('c', 4, 3, 10), face('d', 2, 1, 14)
        # Same graph and face dimensions, different node arrangement.
        e, f = face('e', 4, 3, 20), face('f', 2, 1, 25)
        snapshot = BodySnapshot('A', 'r1', (a, b, c, d, e, f),
                                (('a', 'b'), ('c', 'd'), ('e', 'f')))
        session = SelectionSession(snapshot, ('a', 'b'))
        self.assertEqual(session.ranking.hypothesis, 'repeated_region')
        self.assertEqual(session.result, ('a', 'b', 'c', 'd'))
        session.exclude('d')
        self.assertNotEqual(session.ranking.hypothesis, 'repeated_region')
        self.assertNotIn('d', session.result)

    def test_disconnected_different_shapes_do_not_collapse_to_all_parallel_faces(self):
        a, b = face('a', 4, 3), face('b', 2, 1, 10)
        c, d = face('c', 4, 3, 20), face('d', 2, 1, 30)
        distractor = face('large-wall', 20, 10, 40)
        snap = BodySnapshot('A', 'r1', (a, b, c, d, distractor))
        session = SelectionSession(snap, ('a', 'b'))
        self.assertEqual(session.result, ('a', 'b', 'c', 'd'))
        self.assertEqual(session.ranking.hypothesis, 'shape_families')
        self.assertEqual(session.ranking, SelectionSession(snap, ('b', 'a')).ranking)

    def test_unknown_planar_seed_preserves_examples_with_warning(self):
        a = replace(face('a', 4, 3), contours=())
        session = SelectionSession(BodySnapshot('A', 'r1', (a, face('b', 4, 3))), ('a',))
        self.assertEqual(session.result, ('a',))
        self.assertTrue(session.ranking.ambiguous)
        self.assertEqual(session.boundary_group, ())
        session.adjust_similarity(1)
        self.assertEqual(session.boundary_group, ('b',))

    def test_wall_pair_serialization_and_scope_guard(self):
        a, b = face('a', 4, 3), face('b', 3.6, 2.6, .2, -.2, (0, 0, -1))
        snapshot = BodySnapshot('A', 'r1', (a, b), wall_pairs=(('b', 'a'),))
        self.assertEqual(BodySnapshot.from_dict(snapshot.to_dict()), snapshot)
        with self.assertRaises(ValueError):
            BodySnapshot('A', 'r1', (a, b), wall_pairs=(('a', 'foreign'),))


if __name__ == '__main__':
    unittest.main()
