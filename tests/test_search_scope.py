# SPDX-License-Identifier: GPL-3.0-only
import unittest

from Selectra.matching import Descriptor
from Selectra.search_scope import merge_snapshots, component_contains, SCOPES
from Selectra.selection import SelectionSession
from Selectra.snapshot import BodySnapshot


def body(scope, complete=True):
    loop = ((0, 0, 0), (4, 0, 0), (4, 3, 0), (0, 3, 0))
    entities = tuple(Descriptor(str(i), 'face', 'plane', 12, perimeter=14,
                               normal=(0, 0, 1), position=loop[0], contours=(loop,), scope_key=scope)
                     for i in range(2))
    return BodySnapshot(scope, 'rev-'+scope, entities, (('0', '1'),), (('0', '1'),) if complete else (), complete)


class SearchScopeTests(unittest.TestCase):
    def test_body_ids_do_not_collide_and_relationships_never_cross_bodies(self):
        result, maps = merge_snapshots((body('a'), body('b')), 'authorized', 'all-revisions')
        self.assertEqual(set(result.by_key), {'0:0', '0:1', '1:0', '1:1'})
        self.assertEqual(result.links, (('0:0', '0:1'), ('1:0', '1:1')))
        self.assertEqual(result.wall_pairs, result.links)
        session = SelectionSession(result, (maps[0]['0'],))
        self.assertEqual(set(session.result), set(result.by_key))
        session.add_example(maps[1]['1'])
        self.assertEqual(set(session.result), set(result.by_key))
        session.exclude(maps[1]['0'])
        session.set_level(len(session.ranking.tiers))
        self.assertNotIn(maps[1]['0'], session.result)
        self.assertIn(maps[0]['0'], session.result)

    def test_incomplete_optional_relations_do_not_leak_partial_wall_pairs(self):
        result, _ = merge_snapshots((body('a'), body('b', False)), 'authorized', 'revisions')
        self.assertFalse(result.relations_complete)
        self.assertFalse(result.wall_pairs)
        self.assertEqual(len(result.entities), 4)
        self.assertEqual(BodySnapshot.from_dict(result.to_dict()), result)

    def test_scope_names_are_the_requested_native_labels(self):
        self.assertEqual(tuple(label for _, label in SCOPES), ('This Body', 'This Component', 'All Components'))

    def test_partial_material_stage_cannot_be_replayed_as_confirmed_pairs(self):
        data = body('a').to_dict()
        data['relations_complete'] = False
        with self.assertRaises(ValueError):
            BodySnapshot.from_dict(data)

    def test_component_scope_is_the_selected_instance_subtree(self):
        self.assertTrue(component_contains('Assembly:1', 'Assembly:1'))
        self.assertTrue(component_contains('Assembly:1', 'Assembly:1+Part:2'))
        self.assertTrue(component_contains('Assembly:1', 'Assembly:1+Part:2+Inner:1'))
        self.assertFalse(component_contains('Assembly:1', 'Assembly:2+Part:2'))
        self.assertFalse(component_contains('Assembly:1', 'Assembly:10+Part:2'))
        self.assertFalse(component_contains('Assembly:1+Part:2', 'Assembly:1'))
        self.assertTrue(component_contains(None, 'Assembly:2+Part:2'))


if __name__ == '__main__':
    unittest.main()
