# SPDX-License-Identifier: GPL-3.0-only
import unittest
from Selectra.chains import ClosedChain, ChainSelection
from Selectra.matching import Descriptor
from Selectra.snapshot import BodySnapshot


def snapshot():
    return BodySnapshot('s','r',tuple(Descriptor(k,'face','plane',1,scope_key='s') for k in 'abcdefghi'),
                        (('a','b'),('b','c'),('c','d'),('d','a'),('a','e'),('e','f')))


class ChainTests(unittest.TestCase):
    def test_nearest_inner_closed_ring_then_broader_whole_ring(self):
        chains = (ClosedChain(tuple('abcd'),8,True),ClosedChain(tuple('aef'),6),ClosedChain(tuple('ghi'),2,True))
        s=ChainSelection(snapshot(),chains,('a',))
        self.assertEqual(s.result,tuple('abcd'))
        s.adjust_similarity(1)
        self.assertEqual(s.result,tuple('abcdef'))
        s.adjust_similarity(-1)
        self.assertEqual(s.result,tuple('abcd'))
        self.assertNotIn('g',s.result)

    def test_single_closed_edge_does_not_expand_to_unrelated_loops_immediately(self):
        s=ChainSelection(snapshot(),(ClosedChain(('a',),1,True),ClosedChain(('a','b','c'),4)),('a',))
        self.assertEqual(s.result,('a',))
        self.assertTrue(s.can_apply)
        s.adjust_similarity(1)
        self.assertEqual(s.result,('a','b','c'))

    def test_no_closed_chain_keeps_example_but_disables_apply(self):
        s=ChainSelection(snapshot(),(),('a',))
        self.assertEqual(s.result,('a',))
        self.assertFalse(s.can_apply)
        with self.assertRaises(ValueError): s.replace_examples(('a','b'))

    def test_equal_evidence_duplicates_and_input_order(self):
        chains=(ClosedChain(tuple('abc'),4,True),ClosedChain(tuple('abc'),5),ClosedChain(tuple('ade'),4,True))
        a=ChainSelection(snapshot(),chains,('a',)); b=ChainSelection(snapshot(),reversed(chains),('a',))
        self.assertEqual(a.ranking,b.ranking)
        self.assertEqual(a.result,tuple('abcde'))
