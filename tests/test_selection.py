# SPDX-License-Identifier: GPL-3.0-only
from dataclasses import replace
import json
import unittest

from Selectra.matching import Descriptor as D, Tolerance, infer
from Selectra.snapshot import BodySnapshot
from Selectra.selection import SelectionSession
from Selectra.criteria import select_similar
from Selectra import topology


def line(key, size=1, direction=(1, 0, 0), scope='body-A'):
    return D(key, 'edge', 'line', size, direction=direction, scope_key=scope)


def body():
    return BodySnapshot('body-A', 'revision-1', (
        line('a'), line('both'), line('size', direction=(0, 1, 0)), line('axis', 3)))


class FeedbackTests(unittest.TestCase):
    def test_native_preview_partitions_do_not_duplicate_example_entities(self):
        session = SelectionSession(body(), ('a',))
        self.assertFalse(set(session.additional_result) & set(session.feedback.examples))
        self.assertEqual(set(session.additional_result) | set(session.feedback.examples), set(session.result))
        session.add_example('axis')
        self.assertNotIn('axis', session.additional_result)
        self.assertEqual(set(session.additional_result) | set(session.feedback.examples), set(session.result))

    def test_exclusion_selects_an_explanation_not_just_subtraction(self):
        snapshot = body()
        session = SelectionSession(snapshot, ('a',))
        session.exclude('axis')
        # Length+direction is more specific; excluding a size-only item makes
        # it the sole explanation, not a broad length query minus one key.
        session.exclude('size')
        self.assertEqual(session.result, ('a', 'both'))
        self.assertEqual(len(session.inference.proposals), 1)

    def test_exclusion_changes_an_ambiguous_family(self):
        snapshot = body()
        session = SelectionSession(snapshot, ('a',))
        session.add_example('axis')
        self.assertEqual(session.inference.proposals[0].intent, 'direction')
        self.assertEqual(session.result, ('a', 'axis', 'both'))
        session.exclude('both')
        self.assertFalse(session.inference.proposals)
        self.assertEqual(session.result, ('a', 'axis'))
        self.assertIn('separates', session.inference.explanation)

    def test_suggestion_splits_competing_sets(self):
        session = SelectionSession(body(), ('a',))
        suggested = session.inference.suggested_key
        self.assertIn(suggested, ('size', 'axis'))
        votes = [suggested in h.keys for h in session.inference.proposals]
        self.assertTrue(any(votes))
        self.assertFalse(all(votes))

    def test_feedback_is_atomic_and_cannot_escape_body(self):
        session = SelectionSession(body(), ('a',))
        initial = session.feedback
        for operation in (lambda: session.exclude('a'), lambda: session.add_example('other-body')):
            with self.assertRaises(ValueError):
                operation()
            self.assertEqual(session.feedback, initial)

    def test_undo_redo_cover_feedback_tolerance_and_alternatives(self):
        session = SelectionSession(body(), ('a',))
        first = session.feedback
        session.adjust_similarity(1)
        second = session.feedback
        session.set_tolerance(Tolerance(relative=.05))
        third = session.feedback
        session.add_example('axis')
        fourth = session.feedback
        for expected in (third, second, first):
            session.undo()
            self.assertEqual(session.feedback, expected)
        for expected in (second, third, fourth):
            session.redo()
            self.assertEqual(session.feedback, expected)
        session.undo()
        session.exclude('size')
        final = session.feedback
        session.redo()
        self.assertEqual(session.feedback, final)

    def test_guard_binds_selection_to_body_and_revision(self):
        session = SelectionSession(body(), ('a',))
        self.assertEqual(session.selection_to_apply('body-A', 'revision-1'), session.result)
        for scope, revision in (('body-B', 'revision-1'), ('body-A', 'revision-2')):
            with self.assertRaises(ValueError):
                session.selection_to_apply(scope, revision)

    def test_legacy_infer_rejects_a_mixed_body_pool(self):
        with self.assertRaises(ValueError):
            infer([line('a')], [line('a'), line('b', scope='body-B')])


class SnapshotTests(unittest.TestCase):
    def test_json_roundtrip_is_canonical(self):
        snapshot = body()
        decoded = BodySnapshot.from_dict(json.loads(snapshot.to_json()))
        self.assertEqual(decoded, snapshot)
        self.assertEqual(decoded.to_json(), snapshot.to_json())

    def test_scope_and_invalid_adjacency_are_rejected(self):
        for entities, links in (((line('a', scope='B'),), ()),
                                ((line('a'),), (('a', 'external'),)),
                                ((line('a'), line('a')), ())):
            with self.assertRaises(ValueError):
                BodySnapshot('body-A', 'r1', entities, links)

    def test_vectors_and_lookups_are_immutable(self):
        vector = [1, 0, 0]
        descriptor = line('a', direction=vector)
        vector[0] = 0
        self.assertEqual(descriptor.direction, (1, 0, 0))
        with self.assertRaises(TypeError):
            body().by_key['outside'] = descriptor

    def test_invalid_schema_and_measurements_are_rejected(self):
        data = body().to_dict()
        data['schema_version'] = 99
        with self.assertRaises(ValueError):
            BodySnapshot.from_dict(data)
        with self.assertRaises(ValueError):
            BodySnapshot('body-A', 'r1', (replace(line('a'), adjacent_faces=-1),))


class CriterionTests(unittest.TestCase):
    def test_length_comparison_is_inclusive_and_keeps_examples(self):
        a, small, big = line('a', 2), line('small'), line('big', 3)
        pool = (a, small, big, line('equal', 2))
        self.assertEqual(select_similar([a], pool, 'length', 'greater'), ('a', 'big', 'equal'))
        self.assertEqual(select_similar([a], pool, 'length', 'less'), ('a', 'equal', 'small'))

    def test_explicit_criteria_use_union_of_examples(self):
        a, b, c = line('a'), line('b', 2), line('c', 3)
        self.assertEqual(select_similar([a, c], [a, b, c, line('d', 3)], 'length'), ('a', 'c', 'd'))

    def test_counts_and_perimeter_work_without_same_geometry(self):
        a = D('a', 'face', 'plane', 1, perimeter=4, sides=4, scope_key='body-A')
        b = replace(a, key='b', geometry='nurbs', measure=3)
        c = replace(a, key='c', perimeter=9, sides=3)
        self.assertEqual(select_similar([a], [a, b, c], 'perimeter'), ('a', 'b'))
        self.assertEqual(select_similar([a], [a, b, c], 'sides'), ('a', 'b'))

    def test_direction_is_axial_and_scale_invariant(self):
        a = line('a', direction=(1e300, 0, 0))
        b = line('b', direction=(-1e-300, 0, 0))
        c = line('c', direction=(0, 0, 1))
        self.assertEqual(select_similar([a], [a, b, c], 'direction'), ('a', 'b'))

    def test_face_angle_and_connected_face_count(self):
        a = replace(line('a'), face_angle=1.2, adjacent_faces=2)
        b = replace(line('b'), face_angle=1.21, adjacent_faces=2)
        boundary = replace(line('boundary'), face_angle=None, adjacent_faces=1)
        self.assertEqual(select_similar([a], [a, b, boundary], 'face_angle'), ('a', 'b'))
        self.assertEqual(select_similar([a], [a, b, boundary], 'adjacent_faces'), ('a', 'b'))

    def test_invalid_ordering_and_scope_are_explicit(self):
        with self.assertRaises(ValueError):
            select_similar([line('a')], [], 'direction', 'greater')
        with self.assertRaises(ValueError):
            select_similar([line('a')], [line('b', scope='B')], 'length')


class TopologyTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = BodySnapshot('body-A', 'r1', tuple(line(k) for k in 'abcde'),
                                     (('a', 'b'), ('b', 'c'), ('a', 'd'), ('d', 'c')))

    def test_more_less_and_linked_do_not_mean_tolerance(self):
        self.assertEqual(topology.grow(self.snapshot, ('a',)), ('a', 'b', 'd'))
        self.assertEqual(topology.shrink(self.snapshot, ('a', 'b', 'd')), ('a',))
        self.assertEqual(topology.linked(self.snapshot, ('a',)), ('a', 'b', 'c', 'd'))
        self.assertEqual(topology.linked(self.snapshot, ('e',)), ('e',))

    def test_shrink_can_protect_examples_and_empty_selection(self):
        self.assertEqual(topology.shrink(self.snapshot, ('b',), protected=('b',)), ('b',))
        self.assertEqual(topology.shrink(self.snapshot, ()), ())

    def test_shortest_hop_and_weighted_paths_differ(self):
        self.assertEqual(topology.shortest_path(self.snapshot, 'a', 'c'), ('a', 'b', 'c'))
        weights = {('a', 'b'): 10, ('b', 'c'): 10, ('a', 'd'): 1, ('c', 'd'): 1}
        self.assertEqual(topology.shortest_path(self.snapshot, 'a', 'c', weights=weights), ('a', 'd', 'c'))
        self.assertEqual(topology.shortest_path(self.snapshot, 'a', 'e'), ())
        self.assertEqual(topology.shortest_path(self.snapshot, 'a', 'a'), ('a',))

    def test_path_rejects_incomplete_weights_and_external_entities(self):
        with self.assertRaises(ValueError):
            topology.shortest_path(self.snapshot, 'a', 'c', weights={('a', 'b'): 1})
        with self.assertRaises(ValueError):
            topology.grow(self.snapshot, ('outside',))

    def test_linked_flat_can_accumulate_neighbour_angles(self):
        from math import cos, sin
        faces = tuple(D(k, 'face', 'plane', 1, normal=(sin(a), 0, cos(a)), scope_key='body-A')
                      for k, a in zip('abcd', (0, .1, .2, .5)))
        snapshot = BodySnapshot('body-A', 'r1', faces, (('a', 'b'), ('b', 'c'), ('c', 'd')))
        self.assertEqual(topology.linked_flat(snapshot, ('a',), .11), ('a', 'b', 'c'))
        self.assertEqual(select_similar([faces[0]], faces, 'normal', tolerance=Tolerance(angle=.11)), ('a', 'b'))


if __name__ == '__main__':
    unittest.main()
