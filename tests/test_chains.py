# SPDX-License-Identifier: GPL-3.0-only
import unittest
from dataclasses import replace
from math import sin, cos
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
        self.assertEqual(s.result,tuple('aef'))
        s.adjust_similarity(-1)
        self.assertEqual(s.result,tuple('abcd'))
        self.assertNotIn('g',s.result)

    def test_multiple_examples_require_one_closed_contour_through_all(self):
        chains=(ClosedChain(tuple('abc'),3,True), ClosedChain(tuple('adef'),5,True))
        s=ChainSelection(snapshot(),chains,('a','f'))
        self.assertEqual(s.result,tuple('adef'))
        self.assertTrue(s.can_apply)
        bad=ChainSelection(snapshot(),chains,('b','f'))
        self.assertFalse(bad.can_apply)
        self.assertEqual(bad.result,('b','f'))

    def test_coplanar_contours_outrank_shorter_spatial_loops(self):
        plane=lambda n,z=0: ((n,(0,0,z)),)
        keys=tuple('sabcdefghxyuv')
        entities=tuple(Descriptor(k,'edge','line',1,scope_key='s',
                       planes=plane((0,0,1)) if k=='s' else ()) for k in keys)
        snap=BodySnapshot('s','r',entities,(('s','a'),('s','b'),('a','c'),('a','d'),('b','e'),('b','f'),('s','x'),('s','y'),('s','u'),('s','v')))
        chains=(ClosedChain(('s','x','y'),2,False,plane((1,0,0))),
                ClosedChain(('s','a','b'),10,True,plane((0,0,-1))),
                ClosedChain(('a','c','d'),12,True,plane((0,0,1))),
                ClosedChain(('b','e','f'),3,True,plane((0,0,1),2)),
                ClosedChain(('s','u','v'),1))
        s=ChainSelection(snap,chains,('s',))
        self.assertEqual(s.result,('a','b','s'))
        self.assertEqual(s.ranking.plane_groups,('coplanar','other','unknown'))
        s.adjust_similarity(1)
        self.assertEqual(s.result,('s','x','y'))
        self.assertEqual(s.ranking,ChainSelection(snap,reversed(chains),('s',)).ranking)

    def test_plane_priority_is_invariant_to_rotated_reflected_world_frame(self):
        plane=lambda z: (((0,0,1),(0,0,z)),)
        entities=tuple(Descriptor(k,'edge','line',1,scope_key='s',planes=plane(0) if k=='a' else ()) for k in 'abcde')
        snap=BodySnapshot('s','r',entities,(('a','b'),('a','c'),('b','d'),('b','e')))
        chains=(ClosedChain(('a','b','c'),8,True,plane(0)),ClosedChain(('b','d','e'),4,True,plane(2)))
        def vector(v):
            return (-v[0],cos(.37)*v[1]-sin(.37)*v[2],sin(.37)*v[1]+cos(.37)*v[2])
        def moved(planes):
            return tuple((vector(n),tuple(a+b for a,b in zip(vector(p),(300,-500,120)))) for n,p in planes)
        rotated=replace(snap,entities=tuple(replace(d,planes=moved(d.planes)) for d in entities))
        transformed=tuple(replace(c,planes=moved(c.planes)) for c in chains)
        self.assertEqual(ChainSelection(snap,chains,('a',)).ranking,ChainSelection(rotated,transformed,('a',)).ranking)

    def test_first_contour_still_passes_through_the_example(self):
        entities=tuple(Descriptor(k,'edge','line',1,scope_key='s',planes=(((0,0,1),(0,0,0)),) if k=='a' else ()) for k in 'abcdef')
        snap=BodySnapshot('s','r',entities,(('a','b'),('b','c'),('c','d'),('a','e'),('e','f')))
        chains=(ClosedChain(('a','e','f'),3),ClosedChain(('b','c','d'),5,True,(((0,0,1),(0,0,0)),)))
        s=ChainSelection(snap,chains,('a',))
        self.assertEqual(s.result,('a','e','f'))
        self.assertTrue(s.can_apply)
        s.adjust_similarity(1)
        self.assertEqual(s.result,('a','e','f'))
        self.assertEqual(len(s.ranking.tiers),1)

    def test_every_range_excludes_contours_not_passing_through_all_examples(self):
        chains=(ClosedChain(('a','b','c'),8,True),ClosedChain(('a','b','e'),10),
                ClosedChain(('b','d'),1,True),ClosedChain(('a','f'),2,True))
        s=ChainSelection(snapshot(),chains,('a','b'))
        for level in range(len(s.ranking.tiers)+1):
            s.set_level(level)
            self.assertFalse({'d','f'} & set(s.result))
            self.assertTrue({'a','b'} <= set(s.result))
        self.assertEqual(s.result,('a','b','e'))

    def test_later_variant_is_not_lost_when_all_its_edges_were_seen_before(self):
        chains=(ClosedChain(('a','b','c'),3),ClosedChain(('a','d','e'),4),ClosedChain(('a','b','d'),5))
        s=ChainSelection(snapshot(),chains,('a',))
        for level,chain in enumerate(chains,1):
            s.set_level(level)
            self.assertEqual(s.result,chain.keys)
            self.assertEqual(s.boundary_group,chain.keys)
        self.assertEqual(len(s.ranking.tiers),3)

    def test_local_split_boundary_remains_an_alternative_to_contact_contour(self):
        plane=(((0,0,1),(0,0,0)),)
        keys=('0:seed','0:rim','0:seam','1:other')
        entities=tuple(Descriptor(k,'edge','line',1,scope_key='s',planes=plane) for k in keys)
        snap=BodySnapshot('s','r',entities)
        local=ClosedChain(('0:seed','0:rim','0:seam'),10,False,plane)
        sewn=ClosedChain(('0:seed','0:rim','1:other'),5,True,plane)
        s=ChainSelection(snap,(local,sewn),('0:seed',))
        self.assertEqual(s.result,sewn.keys)
        s.adjust_similarity(1)
        self.assertEqual(s.result,local.keys)
        self.assertNotIn('1:other',s.result)
        self.assertEqual(ChainSelection(snap,(local,sewn),('0:seam',)).result,local.keys)

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

    def test_equal_evidence_duplicates_and_input_order(self):
        chains=(ClosedChain(tuple('abc'),4,True),ClosedChain(tuple('abc'),5),ClosedChain(tuple('ade'),4,True))
        a=ChainSelection(snapshot(),chains,('a',)); b=ChainSelection(snapshot(),reversed(chains),('a',))
        self.assertEqual(a.ranking,b.ranking)
        self.assertEqual(a.result,tuple('abc'))
        a.adjust_similarity(1)
        self.assertEqual(a.result,tuple('ade'))
        self.assertEqual(len(a.ranking.tiers),2)

    def test_intermediate_patches_preserve_existing_variants_within_plane_class(self):
        old=ClosedChain(('a','b','c'),10)
        extra=ClosedChain(('a','d','e'),1,supplemental=True)
        s=ChainSelection(snapshot(),(extra,old),('a',))
        self.assertEqual(s.ranking.tiers,(old.keys,extra.keys))
        s.replace_examples(('a','e'))
        self.assertEqual(s.result,extra.keys)
