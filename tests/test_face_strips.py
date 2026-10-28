# SPDX-License-Identifier: GPL-3.0-only
import json
from pathlib import Path
import unittest

from Selectra.face_strips import find_face_strips
from Selectra.chains import ClosedChain, ChainSelection
from Selectra.matching import Descriptor
from Selectra.snapshot import BodySnapshot


class FaceStripTests(unittest.TestCase):
    def test_selected_rim_is_first_on_representative_topology(self):
        data = json.loads((Path(__file__).parent / 'fixtures' / 'face_rim_topology.json').read_text())
        strips = find_face_strips(data['faces'], data['edges'], ('56',))
        self.assertTrue(strips)
        self.assertEqual(set(strips[0][0]), set(data['expected']))
        for seed in data['expected']:
            self.assertEqual(set(find_face_strips(data['faces'], data['edges'], (seed,))[0][0]), set(data['expected']))
        keys = set(data['faces']) | {'162', '170'}
        snapshot = BodySnapshot('s', 'r', tuple(Descriptor(k, 'face', 'plane', 1, scope_key='s') for k in sorted(keys)))
        new = tuple(ClosedChain(keys, perimeter, strip_ratio=ratio) for keys, perimeter, ratio in strips)
        old = ClosedChain(('56', '124', '162', '170'), 10, True, (((0, 0, 1), (0, 0, 0)),))
        controller = ChainSelection(snapshot, (old,) + new, ('56',))
        self.assertEqual(set(controller.result), set(data['expected']))
        self.assertIn(old.keys, controller.ranking.tiers)
        controller.replace_examples(('56', '74'))
        self.assertTrue(all({'56', '74'} <= set(tier) for tier in controller.ranking.tiers))

    def test_budget_fails_without_partial_result(self):
        data = json.loads((Path(__file__).parent / 'fixtures' / 'face_rim_topology.json').read_text())
        with self.assertRaises(ValueError):
            find_face_strips(data['faces'], data['edges'], ('56',), max_states=1)

    def test_open_strip_is_not_a_ring(self):
        faces = {'a': ('x', 'a1', 'a2'), 'b': ('x', 'b1', 'b2')}
        edges = {'x': {'vertices': (0, 1), 'length': 1, 'faces': ('a', 'b')},
                 'a1': {'vertices': (0, 2), 'length': 2, 'faces': ('a',)},
                 'a2': {'vertices': (2, 1), 'length': 2, 'faces': ('a',)},
                 'b1': {'vertices': (0, 3), 'length': 2, 'faces': ('b',)},
                 'b2': {'vertices': (3, 1), 'length': 2, 'faces': ('b',)}}
        self.assertEqual(find_face_strips(faces, edges, ('a',)), ())
