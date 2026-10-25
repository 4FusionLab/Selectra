# SPDX-License-Identifier: GPL-3.0-only
import unittest

from evaluation.baseline_c5ac432 import rank as baseline
from evaluation.corpus import tasks, transformed, holdout_tasks, face, body
from evaluation.metrics import evaluate, measure, selected
from Selectra.ranking import rank


class EvaluationTests(unittest.TestCase):
    def test_corpus_has_independent_equal_signature_counterexample(self):
        task = next(t for t in tasks() if t.key == 'equal-area-perimeter')
        seed, false = (task.snapshot.by_key[k] for k in ('seed', 'false-shape'))
        self.assertEqual((seed.measure, seed.perimeter, seed.sides, seed.loops),
                         (false.measure, false.perimeter, false.sides, false.loops))
        row = measure(task, baseline, repeats=1)
        self.assertFalse(row['first_exact'])
        self.assertFalse(row['target_reachable'])
        self.assertEqual(row['precision_additional'], .5)
        self.assertEqual(row['recall_additional'], 1)

    def test_known_examples_are_not_free_precision(self):
        task = next(t for t in tasks() if t.key == 'contradictory-feedback')
        row = measure(task, baseline, repeats=1)
        self.assertTrue(row['first_exact'])
        self.assertEqual(row['precision_additional'], 1)
        self.assertEqual(row['recall_additional'], 1)
        self.assertEqual(row['range_steps'], 0)

    def test_complete_maximum_and_scope_in_corpus(self):
        for task in tasks():
            ranking = baseline(task.snapshot, task.examples, task.exclusions)
            self.assertEqual(set(selected(task, ranking, len(ranking.tiers))),
                             set(task.snapshot.by_key)-set(task.exclusions))
            self.assertTrue(set(task.examples) <= set(task.target))
            self.assertFalse(set(task.exclusions) & set(task.target))
            self.assertTrue(set(task.target) <= set(task.snapshot.by_key))

    def test_transforms_preserve_labels_and_measurements(self):
        for task in tasks():
            moved = transformed(task)
            self.assertEqual(moved.target, task.target)
            self.assertEqual(moved.snapshot.wall_pairs, task.snapshot.wall_pairs)
            for key in task.snapshot.by_key:
                self.assertEqual(moved.snapshot.by_key[key].measure,
                                 task.snapshot.by_key[key].measure)

    def test_wall_checkpoints_have_independently_labelled_sequence(self):
        task = next(t for t in tasks() if t.key == 'wall-sequence')
        first, second, third = map(set, task.checkpoints)
        self.assertLess(first, second)
        self.assertLess(second, third)
        self.assertNotIn('cavity-across', third)
        row = measure(task, baseline, repeats=1)
        self.assertFalse(all(row['checkpoints_reachable']))

    def test_summary_matches_detail(self):
        report = evaluate(tasks(), baseline, repeats=1)
        self.assertEqual(report['summary']['tasks'], len(report['rows']))
        self.assertEqual(report['summary']['first_exact'],
                         sum(r['first_exact'] for r in report['rows']))

    def test_geometric_corpus_contract(self):
        for task in tasks():
            with self.subTest(task=task.key):
                row = measure(task, rank, repeats=1)
                self.assertTrue(row['first_exact'], row)
                self.assertTrue(row['target_reachable'], row)
                self.assertTrue(row['invariant'], row)
                self.assertTrue(all(row['checkpoints_reachable']), row)

    def test_holdout_preserves_complete_scope_and_feedback(self):
        for task in holdout_tasks():
            with self.subTest(task=task.key):
                ranking = rank(task.snapshot, task.examples, task.exclusions)
                self.assertEqual({item.key for item in ranking.items}, set(task.snapshot.by_key))
                self.assertEqual(set(selected(task, ranking, len(ranking.tiers))),
                                 set(task.snapshot.by_key)-set(task.exclusions))

    def test_oversize_contour_is_controlled_failure_without_partial_ranking(self):
        from math import cos, sin, pi
        from Selectra.contours import compare_contours
        contour = (tuple((cos(i*2*pi/513), sin(i*2*pi/513), 0) for i in range(513)),)
        result = compare_contours(contour, contour)
        self.assertFalse(result.complete)
        self.assertFalse(result.matched)
        snapshot = body(face('seed', contour), face('twin', contour))
        with self.assertRaisesRegex(ValueError, 'incomplete|budget'):
            rank(snapshot, ('seed',))


if __name__ == '__main__':
    unittest.main()
