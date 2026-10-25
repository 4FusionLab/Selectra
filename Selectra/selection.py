# SPDX-License-Identifier: GPL-3.0-only
"""Ranked selection state, feedback, reversible cutoff and stale-body guards."""
from dataclasses import dataclass, replace

from .matching import Tolerance, infer
from .ranking import rank


@dataclass(frozen=True)
class Feedback:
    examples: tuple = ()
    exclusions: tuple = ()
    tolerance: Tolerance = Tolerance()
    criterion: str = 'auto'
    level: object = None  # None: automatic cutoff; integer: included score tiers.


class SelectionSession:
    def __init__(self, snapshot, examples=()):
        self.snapshot = snapshot
        self.feedback = Feedback(snapshot.require_keys(examples))
        self.inference, self.ranking = self._evaluate(self.feedback)
        self._undo, self._redo = [], []

    def _evaluate(self, feedback):
        inference = infer([self.snapshot.by_key[k] for k in feedback.examples],
                          self.snapshot.entities, feedback.tolerance,
                          excluded=[self.snapshot.by_key[k] for k in feedback.exclusions])
        ranking = rank(self.snapshot, feedback.examples, feedback.exclusions,
                       feedback.tolerance, criterion=feedback.criterion)
        return inference, ranking

    @staticmethod
    def _meaning(feedback):
        return feedback.examples, feedback.exclusions, feedback.tolerance, feedback.criterion

    def _change(self, feedback):
        feedback = replace(feedback,
                           examples=self.snapshot.require_keys(feedback.examples),
                           exclusions=self.snapshot.require_keys(feedback.exclusions))
        if set(feedback.examples) & set(feedback.exclusions):
            raise ValueError('An entity cannot be an example and an exclusion.')
        if feedback == self.feedback:
            return
        if self._meaning(feedback) == self._meaning(self.feedback):
            inference, ranking = self.inference, self.ranking
        else:
            inference, ranking = self._evaluate(feedback)
        if feedback.level is not None and (type(feedback.level) is not int or not 0 <= feedback.level <= len(ranking.tiers)):
            raise ValueError('Similarity range is outside the ranking.')
        self._undo.append(self.feedback)
        self._undo = self._undo[-128:]
        self._redo.clear()
        self.feedback, self.inference, self.ranking = feedback, inference, ranking

    def add_example(self, key):
        self._change(replace(self.feedback, examples=self.feedback.examples + (key,), level=None))

    def exclude(self, key):
        self._change(replace(self.feedback, exclusions=self.feedback.exclusions + (key,), level=None))

    def remove_example(self, key):
        self._change(replace(self.feedback, examples=tuple(k for k in self.feedback.examples if k != key), level=None))

    def remove_exclusion(self, key):
        self._change(replace(self.feedback, exclusions=tuple(k for k in self.feedback.exclusions if k != key), level=None))

    def replace_examples(self, keys):
        keys = self.snapshot.require_keys(keys)
        self._change(replace(self.feedback, examples=keys,
                             exclusions=tuple(k for k in self.feedback.exclusions if k not in keys), level=None))

    def replace_exclusions(self, keys):
        self._change(replace(self.feedback, exclusions=tuple(keys), level=None))

    def set_tolerance(self, tolerance):
        self._change(replace(self.feedback, tolerance=tolerance, level=None))

    def set_criterion(self, criterion):
        self._change(replace(self.feedback, criterion=criterion, level=None))

    @property
    def level(self):
        return self.ranking.automatic_level if self.feedback.level is None else self.feedback.level

    @property
    def result(self):
        if not self.feedback.examples:
            return ()
        keys = set(self.feedback.examples)
        for tier in self.ranking.tiers[:self.level]:
            keys.update(tier)
        return tuple(sorted(keys))

    @property
    def additional_result(self):
        return tuple(k for k in self.result if k not in self.feedback.examples)

    def adjust_similarity(self, steps):
        if type(steps) is not int or abs(steps) > 10000:
            raise ValueError('Similarity steps must be an integer in [-10000, 10000].')
        if self.feedback.examples and steps:
            self._change(replace(self.feedback, level=max(0, min(len(self.ranking.tiers), self.level + steps))))

    def set_level(self, level):
        self._change(replace(self.feedback, level=level))

    def reset_preview(self):
        self._change(replace(self.feedback, level=None))

    def clear_feedback(self):
        self._change(Feedback(tolerance=self.feedback.tolerance))

    def undo(self):
        if self._undo:
            self._redo.append(self.feedback)
            feedback = self._undo.pop()
            if self._meaning(feedback) != self._meaning(self.feedback):
                self.inference, self.ranking = self._evaluate(feedback)
            self.feedback = feedback

    def redo(self):
        if self._redo:
            self._undo.append(self.feedback)
            feedback = self._redo.pop()
            if self._meaning(feedback) != self._meaning(self.feedback):
                self.inference, self.ranking = self._evaluate(feedback)
            self.feedback = feedback

    def selection_to_apply(self, scope_key, revision):
        if (scope_key, revision) != (self.snapshot.scope_key, self.snapshot.revision):
            raise ValueError('Body context or geometry changed; refresh before applying.')
        return self.result
