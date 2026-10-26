# SPDX-License-Identifier: GPL-3.0-only
"""Closed boundaries of a face patch from exact BRep incidence, without adsk."""
from collections import Counter, defaultdict


def closed_boundary_loops(face_coedges, edge_vertices, *, max_edges=100000):
    counts=Counter()
    total=0
    for edges in face_coedges:
        for edge in edges:
            total+=1
            if total>max_edges:
                raise ValueError('Smooth patch exceeds the topology budget.')
            counts[edge]+=1
    if any(count>2 for count in counts.values()):
        return ()
    boundary={edge for edge,count in counts.items() if count==1}
    incidence=defaultdict(list)
    for edge in boundary:
        if edge not in edge_vertices or len(edge_vertices[edge])!=2:
            raise ValueError('A patch boundary needs complete endpoint topology.')
        for vertex in edge_vertices[edge]:
            incidence[vertex].append(edge)
    remaining=set(boundary)
    loops=[]
    while remaining:
        first=min(remaining)
        component={first}
        todo=[first]
        nodes=set()
        while todo:
            edge=todo.pop()
            for vertex in edge_vertices[edge]:
                nodes.add(vertex)
                for other in incidence[vertex]:
                    if other not in component:
                        component.add(other)
                        todo.append(other)
        remaining-=component
        # A finite connected 2-regular multigraph is one closed cycle.
        # A self-loop contributes two incidences, as a circular BRep edge does.
        if all(len(incidence[vertex])==2 for vertex in nodes):
            loops.append(tuple(sorted(component)))
    return tuple(sorted(loops))
