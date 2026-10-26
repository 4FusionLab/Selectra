# SPDX-License-Identifier: GPL-3.0-only
import unittest
from Selectra.patch_boundaries import closed_boundary_loops


class PatchBoundaryTests(unittest.TestCase):
    def test_three_wall_faces_produce_the_full_eight_edge_contour(self):
        faces=(('front-bottom','back-bottom','seam-bottom','join-bottom'),
               ('front-arc','back-arc','join-bottom','join-top'),
               ('front-top','back-top','join-top','seam-top'))
        ends={'front-bottom':(0,1),'front-arc':(1,2),'front-top':(2,3),'seam-top':(3,4),
              'back-top':(4,5),'back-arc':(5,6),'back-bottom':(6,7),'seam-bottom':(7,0),
              'join-bottom':(1,6),'join-top':(2,5)}
        result=closed_boundary_loops(faces,ends)
        self.assertEqual(result,(tuple(sorted(k for k in ends if not k.startswith('join-'))),))

    def test_separate_front_and_back_rings_do_not_get_joined_into_one_contour(self):
        faces=(('a','b','j1','j2'),('c','d','j2','j3'),('e','f','j3','j1'))
        ends={'a':(0,1),'c':(1,2),'e':(2,0),'b':(3,4),'d':(4,5),'f':(5,3),
              'j1':(0,3),'j2':(1,4),'j3':(2,5)}
        self.assertEqual(closed_boundary_loops(faces,ends),(('a','c','e'),('b','d','f')))

    def test_periodic_seam_is_removed_but_circular_boundary_remains(self):
        self.assertEqual(closed_boundary_loops((('circle','seam','seam'),),{'circle':(0,0)}),(('circle',),))

    def test_open_or_branched_boundaries_are_not_claimed_closed(self):
        self.assertEqual(closed_boundary_loops((('a','b'),),{'a':(0,1),'b':(1,2)}),())
        self.assertEqual(closed_boundary_loops((('a','b','c'),),{'a':(0,1),'b':(1,0),'c':(0,2)}),())

    def test_missing_data_or_budget_cannot_create_partial_contours(self):
        with self.assertRaises(ValueError): closed_boundary_loops((('a',),),{})
        with self.assertRaises(ValueError): closed_boundary_loops((('a','b'),),{},max_edges=1)

    def test_intermediate_patch_keeps_edge_hidden_inside_full_region(self):
        from Selectra.patch_boundaries import connected_patches
        faces=(('a','join1','b'),('join1','c','join2'),('join2','d','e'))
        patches=connected_patches(faces)
        self.assertIn((0,1),patches)
        self.assertIn((1,2),patches)
        self.assertNotIn((0,2),patches)
        ends={'a':(0,1),'join1':(1,2),'b':(2,0),'c':(1,3),'join2':(3,2),'d':(3,4),'e':(4,2)}
        boundary=closed_boundary_loops(tuple(faces[i] for i in (0,1)),ends)
        self.assertEqual(boundary,(('a','b','c','join2'),))
        self.assertNotIn('join2',closed_boundary_loops(faces,ends)[0])

    def test_connected_patch_budget_is_explicit(self):
        from Selectra.patch_boundaries import connected_patches
        with self.assertRaises(ValueError):
            connected_patches((('x',),('x','y'),('y',)),max_states=3)
