# SPDX-License-Identifier: GPL-3.0-only
"""Adapter protocol regression: evaluator direction differs from BRep direction."""
import importlib.util
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch


class Collection:
    def __init__(self, items):
        self.items = tuple(items)
        self.count = len(self.items)

    def item(self, index):
        return self.items[index]


class Evaluator:
    def __init__(self, points):
        self.points = [SimpleNamespace(x=x, y=y, z=z) for x, y, z in points]

    def getParameterExtents(self):
        return True, 0, 1

    def getStrokes(self, low, high, tolerance):
        return True, self.points


def face(points, flags):
    coedges = []
    for i, (opposed, reversed_parameter) in enumerate(flags):
        a, b = points[i], points[(i+1) % len(points)]
        raw = (b, a) if opposed != reversed_parameter else (a, b)
        coedges.append(SimpleNamespace(isOpposedToEdge=opposed,
                                      edge=SimpleNamespace(isParamReversed=reversed_parameter,
                                                           evaluator=Evaluator(raw))))
    return SimpleNamespace(loops=Collection((SimpleNamespace(isOuter=True, coEdges=Collection(coedges)),)))


class NativeContourTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        adsk = ModuleType('adsk')
        adsk.core, adsk.fusion = ModuleType('adsk.core'), ModuleType('adsk.fusion')
        source = Path(__file__).resolve().parents[1] / 'Selectra/fusion_adapter.py'
        spec = importlib.util.spec_from_file_location('Selectra._contour_adapter_test', source)
        cls.adapter = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {'adsk': adsk, 'adsk.core': adsk.core, 'adsk.fusion': adsk.fusion}):
            spec.loader.exec_module(cls.adapter)

    def test_mixed_parameter_reversals_preserve_the_actual_trim(self):
        points = ((0, 0, 0), (4, 0, 0), (4, 3, 0), (1, 4, 0), (0, 2, 0))
        flags = ((True, False), (False, True), (True, True), (False, False), (False, True))
        self.assertEqual(self.adapter._contours(face(points, flags)), (points,))


if __name__ == '__main__':
    unittest.main()
