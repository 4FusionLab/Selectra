# SPDX-License-Identifier: GPL-3.0-only
from dataclasses import replace
import unittest

from Selectra.matching import Descriptor as D
from Selectra.ranking import rank
from Selectra.snapshot import BodySnapshot
from Selectra.selection import SelectionSession


def fixture():
    return BodySnapshot('A', 'r1', (
        D('seed', 'edge', 'line', 1, direction=(1, 0, 0), scope_key='A'),
        D('same', 'edge', 'line', 1, direction=(-1, 0, 0), scope_key='A'),
        D('near', 'edge', 'line', 1.15, direction=(1, 0, 0), scope_key='A'),
        D('larger', 'edge', 'line', 2, direction=(1, 0, 0), scope_key='A'),
        D('turned', 'edge', 'line', 1, direction=(0, 1, 0), scope_key='A'),
        D('circle', 'edge', 'circle', 1, radius=.2, scope_key='A')),
        # Deliberately place the least similar circle next to the example.
        (('seed', 'circle'), ('circle', 'same')))


class RankingTests(unittest.TestCase):
    def test_shell_face_prefers_parallel_inner_wall_before_crosswise_wall(self):
        # Minimized from a real thin-wall part: opposing inner/outer normals
        # must not put a perpendicular wall ahead of the parallel inner wall.
        snapshot = BodySnapshot('A', 'r1', (
            D('seed', 'face', 'plane', 1,
              perimeter=4, normal=(-1, -1, 0), sides=4, loops=1, scope_key='A'),
            D('outer-twin', 'face', 'plane', 1,
              perimeter=4, normal=(1, -1, 0), sides=4, loops=1, scope_key='A'),
            D('far-crosswise', 'face', 'plane', .83,
              perimeter=3.65, normal=(-1, 1, 0), sides=7, loops=1, scope_key='A'),
            D('near-parallel', 'face', 'plane', .83,
              perimeter=3.65, normal=(1, 1, 0), sides=7, loops=1, scope_key='A')))
        result = rank(snapshot, ('seed',))
        self.assertEqual(tuple(tier[0] for tier in result.tiers),
                         ('outer-twin', 'near-parallel', 'far-crosswise'))

    def test_every_entity_of_the_body_is_ranked(self):
        snapshot = fixture()
        result = rank(snapshot, ('seed',))
        self.assertEqual({r.key for r in result.items}, set(snapshot.by_key))
        distances = {r.key: r.distance for r in result.items}
        self.assertLess(distances['same'], distances['near'])
        self.assertLess(distances['near'], distances['larger'])
        self.assertLess(distances['near'], distances['circle'])
        self.assertTrue(all(0 <= d <= 1 for d in distances.values()))

    def test_automatic_plane_orientation_is_axial_but_explicit_facing_is_signed(self):
        snapshot = BodySnapshot('A', 'r1', (
            D('seed', 'face', 'plane', 1, normal=(1, 0, 0), scope_key='A'),
            D('opposite', 'face', 'plane', 1, normal=(-1, 0, 0), scope_key='A'),
            D('crosswise', 'face', 'plane', 1, normal=(0, 1, 0), scope_key='A')))
        automatic = {r.key: r.distance for r in rank(snapshot, ('seed',)).items}
        facing = {r.key: r.distance for r in rank(snapshot, ('seed',), criterion='normal').items}
        self.assertEqual(automatic['opposite'], 0)
        self.assertGreater(automatic['crosswise'], 0)
        self.assertGreater(facing['opposite'], facing['crosswise'])
        self.assertIn('normal', rank(snapshot, ('seed', 'opposite')).features)
        self.assertNotIn('normal', rank(snapshot, ('seed', 'crosswise')).features)

    def test_initial_range_is_first_nonempty_group_even_above_old_cutoff(self):
        snapshot = BodySnapshot('A', 'r1', (
            D('seed', 'edge', 'line', 1, direction=(1, 0, 0), scope_key='A'),
            D('closest', 'edge', 'line', 1.3, direction=(1, 0, 0), scope_key='A'),
            D('closest-twin', 'edge', 'line', 1.3, direction=(1, 0, 0), scope_key='A'),
            D('further', 'edge', 'line', 2, direction=(1, 0, 0), scope_key='A')))
        session = SelectionSession(snapshot, ('seed',))
        self.assertEqual(session.level, 1)
        self.assertEqual(session.result, ('closest', 'closest-twin', 'seed'))
        session.adjust_similarity(1)
        session.reset_preview()
        self.assertEqual(session.result, ('closest', 'closest-twin', 'seed'))
        session.replace_exclusions(('closest', 'closest-twin', 'further'))
        self.assertEqual(session.level, 0)
        self.assertEqual(session.result, ('seed',))

    def test_page_steps_expand_by_similarity_not_neighbourhood(self):
        session = SelectionSession(fixture(), ('seed',))
        self.assertEqual(session.result, ('same', 'seed'))
        session.adjust_similarity(1)
        self.assertEqual(session.result, ('near', 'same', 'seed'))
        self.assertNotIn('circle', session.result)
        session.adjust_similarity(-1)
        self.assertEqual(session.result, ('same', 'seed'))

    def test_ties_are_added_and_removed_together(self):
        snapshot = fixture()
        same = replace(snapshot.by_key['near'], key='near-twin')
        snapshot = BodySnapshot('A', 'r1', snapshot.entities + (same,), snapshot.links)
        session = SelectionSession(snapshot, ('seed',))
        session.adjust_similarity(1)
        self.assertTrue({'near', 'near-twin'} <= set(session.result))
        session.adjust_similarity(-1)
        self.assertFalse({'near', 'near-twin'} & set(session.result))

    def test_expansion_is_nested_complete_and_reversible(self):
        session = SelectionSession(fixture(), ('seed',))
        session.exclude('circle')
        previous = set(session.result)
        for _ in range(len(session.ranking.tiers)+1):
            session.adjust_similarity(1)
            self.assertTrue(previous <= set(session.result))
            previous = set(session.result)
        self.assertEqual(set(session.result), set(session.snapshot.by_key) - {'circle'})
        session.adjust_similarity(-10000)
        self.assertEqual(session.result, ('seed',))
        session.adjust_similarity(-1)
        self.assertEqual(session.result, ('seed',))

    def test_examples_teach_invariant_properties(self):
        result = rank(fixture(), ('seed', 'larger'))
        self.assertNotIn('measure', result.features)
        self.assertIn('direction', result.features)
        distances = {r.key: r.distance for r in result.items}
        self.assertEqual(distances['near'], 0)
        self.assertGreater(distances['turned'], 0)

    def test_exclusions_are_ranked_but_never_selected(self):
        session = SelectionSession(fixture(), ('seed',))
        session.exclude('same')
        self.assertTrue(next(r for r in session.ranking.items if r.key == 'same').blocked)
        self.assertTrue(session.ranking.ambiguous)
        session.adjust_similarity(10000)
        self.assertNotIn('same', session.result)
        self.assertIn('seed', session.result)

    def test_feedback_restarts_cutoff_and_undo_restores_it(self):
        session = SelectionSession(fixture(), ('seed',))
        session.adjust_similarity(1)
        previous = session.feedback
        session.add_example('larger')
        self.assertIsNone(session.feedback.level)
        session.undo()
        self.assertEqual(session.feedback, previous)
        session.redo()
        self.assertIn('larger', session.feedback.examples)

    def test_ranking_does_not_depend_on_identifier_or_input_order(self):
        snapshot = fixture()
        reverse = BodySnapshot('A', 'r1', tuple(reversed(snapshot.entities)), snapshot.links)
        self.assertEqual(rank(snapshot, ('seed', 'larger')), rank(reverse, ('larger', 'seed')))

    def test_explicit_criterion_and_empty_session(self):
        result = rank(fixture(), ('seed',), criterion='measure')
        distances = {r.key: r.distance for r in result.items}
        self.assertEqual(distances['turned'], 0)
        session = SelectionSession(fixture())
        session.adjust_similarity(1)
        self.assertEqual(session.result, ())
        with self.assertRaises(ValueError):
            session.set_criterion('bad')

    def test_explicit_criterion_keeps_multiple_example_families(self):
        result = rank(fixture(), ('seed', 'turned'), criterion='direction')
        distances = {r.key: r.distance for r in result.items}
        self.assertEqual(distances['near'], 0)
        self.assertEqual(distances['larger'], 0)
        self.assertGreater(distances['circle'], 0)

    def test_cutoff_steps_reuse_the_existing_ranking(self):
        class Counted(SelectionSession):
            evaluations = 0

            def _evaluate(self, feedback):
                self.evaluations += 1
                return super()._evaluate(feedback)

        session = Counted(fixture(), ('seed',))
        original = session.ranking
        session.adjust_similarity(1)
        session.adjust_similarity(-1)
        self.assertIs(session.ranking, original)
        self.assertEqual(session.evaluations, 1)
        session.exclude('turned')
        self.assertEqual(session.evaluations, 2)


if __name__ == '__main__':
    unittest.main()
