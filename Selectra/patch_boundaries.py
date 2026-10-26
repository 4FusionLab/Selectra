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


def connected_patches(face_coedges, *, max_states=100000):
    """Proper connected multi-face subsets; full patches are handled first."""
    owners=defaultdict(set)
    for i,edges in enumerate(face_coedges):
        for edge in edges:
            owners[edge].add(i)
    neighbors=[set() for _ in face_coedges]
    for group in owners.values():
        for i in group:
            neighbors[i].update(group-{i})
    seen={frozenset((i,)) for i in range(len(face_coedges))}
    todo=list(sorted(seen,key=lambda p:tuple(p)))
    result=[]
    while todo:
        patch=todo.pop()
        frontier=set().union(*(neighbors[i] for i in patch))-patch
        for i in sorted(frontier):
            expanded=patch|{i}
            if expanded in seen:
                continue
            seen.add(expanded)
            if len(seen)>max_states:
                raise ValueError('Connected-patch analysis exceeded its topology budget.')
            if len(expanded)<len(face_coedges):
                result.append(tuple(sorted(expanded)))
                todo.append(expanded)
    return tuple(sorted(result,key=lambda p:(len(p),p)))
