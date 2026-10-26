# SPDX-License-Identifier: GPL-3.0-only
"""Read exact face contacts and virtual union chains; never alter a document."""
from dataclasses import replace
from itertools import combinations
from math import hypot
from time import monotonic
from uuid import uuid4
import json
import adsk.core
import adsk.fusion
from .snapshot import BodySnapshot
from .search_scope import merge_snapshots
from .chains import ClosedChain

CONTACT_TOLERANCE = 1e-9  # cm; no user-facing snap or proximity tolerance.


class Budget:
    def __init__(self):
        self.until, self.calls = monotonic()+8, 0

    def step(self):
        self.calls += 1
        if self.calls > 1000000 or monotonic() > self.until:
            raise ValueError('Exact-contact analysis exceeded its budget. No partial chain was applied.')


def bounds(entity):
    box = entity.boundingBox
    return (tuple(box.minPoint.asArray()), tuple(box.maxPoint.asArray()))


def overlaps(a, b):
    return all(a[0][i] <= b[1][i]+CONTACT_TOLERANCE and b[0][i] <= a[1][i]+CONTACT_TOLERANCE for i in range(3))


def world_copy(entity, manager):
    copy = manager.copy(entity.nativeObject or entity)
    if not copy:
        raise ValueError('Could not copy BRep for exact-contact analysis.')
    if entity.assemblyContext and not manager.transform(copy, entity.assemblyContext.transform2):
        raise ValueError('Could not place the exact-contact copy in world coordinates.')
    return copy


def _on_face(point, face):
    geometry = face.geometry
    plane = adsk.core.Plane.cast(geometry)
    if plane:
        normal = plane.normal.asArray()
        delta = tuple(a-b for a,b in zip(point.asArray(),plane.origin.asArray()))
        return abs(sum(a*b for a,b in zip(normal,delta)))/hypot(*normal) <= CONTACT_TOLERANCE
    cylinder = adsk.core.Cylinder.cast(geometry)
    if cylinder:
        axis = cylinder.axis.asArray();length=hypot(*axis)
        axis=tuple(v/length for v in axis)
        delta=tuple(a-b for a,b in zip(point.asArray(),cylinder.origin.asArray()))
        along=sum(a*b for a,b in zip(delta,axis))
        radius=hypot(*(v-along*n for v,n in zip(delta,axis)))
        return abs(radius-cylinder.radius) <= CONTACT_TOLERANCE
    ok, parameter = face.evaluator.getParameterAtPoint(point)
    if not ok or not face.evaluator.isParameterOnFace(parameter):
        return False
    ok, actual = face.evaluator.getPointAtParameter(parameter)
    return ok and actual.distanceTo(point) <= CONTACT_TOLERANCE


def _normal(face):
    ok, n = face.geometry.evaluator.getNormalAtPoint(face.pointOnFace)
    if not ok:
        return None
    sign = -1 if face.isParamReversed else 1
    return tuple(sign*v for v in n.asArray())


def _boolean(manager, target, tool, operation):
    # Noncoincident sheet/curve booleans can be unsupported by ASM. Failure
    # means no geometric proof and is never treated as a positive contact.
    try:
        return manager.booleanOperation(target, tool, operation)
    except RuntimeError:
        return False


def fully_contains(manager, source, target, edge=False):
    remainder = manager.copy(source)
    if not _boolean(manager, remainder, manager.copy(target), adsk.fusion.BooleanTypes.DifferenceBooleanType):
        return False
    return remainder.edges.count == 0 if edge else remainder.faces.count == 0


def _boundary_point(point, edges):
    for edge, box in edges:
        coordinates=point.asArray()
        if any(coordinates[i] < box[0][i]-CONTACT_TOLERANCE or coordinates[i] > box[1][i]+CONTACT_TOLERANCE for i in range(3)):
            continue
        if any(v is not None and v.geometry.distanceTo(point) <= CONTACT_TOLERANCE for v in (edge.startVertex,edge.endVertex)):
            return True
        if adsk.core.Circle3D.cast(edge.geometry):
            if _on_edge((point,),edge):
                return True
            continue
        # Trimmed arcs and splines must include this parameter, not merely
        # lie on the same unbounded circle or underlying surface.
        ok, low, high=edge.evaluator.getParameterExtents()
        if not ok:
            continue
        ok, parameter=edge.evaluator.getParameterAtPoint(point)
        if not ok or not low-1e-12 <= parameter <= high+1e-12:
            continue
        ok, actual=edge.evaluator.getPointAtParameter(parameter)
        if ok and actual.distanceTo(point) <= CONTACT_TOLERANCE:
            return True
    return False


def same_boundaries(a,b,work):
    if a.loops.count != b.loops.count:
        return False
    for source,target in ((a,b),(b,a)):
        edges=tuple((edge,bounds(edge)) for edge in target.edges)
        for edge in source.edges:
            work.step()
            for point in _edge_probe(edge):
                if not _boundary_point(point,edges):
                    return False
    return True


def exact_contact(a, b, manager, work):
    if not a.isSolid or not b.isSolid or not overlaps(bounds(a), bounds(b)):
        return False
    af = tuple((f, bounds(f)) for f in a.faces)
    bf = tuple((f, bounds(f)) for f in b.faces)
    for p, pb in af:
        for q, qb in bf:
            work.step()
            if not overlaps(pb, qb) or abs(p.area-q.area) > 1e-7*max(1, p.area, q.area):
                continue
            n, m = _normal(p), _normal(q)
            if n is None or m is None or sum(x*y for x,y in zip(n,m)) > -.999999999*hypot(*n)*hypot(*m):
                continue
            if not _on_face(p.pointOnFace, q) or not _on_face(q.pointOnFace, p):
                continue
            # Strict separation check supplements ASM's broader model tolerance.
            if not all(_on_face(v.geometry, q) for v in p.vertices) or not all(_on_face(v.geometry, p) for v in q.vertices):
                continue
            if not same_boundaries(p,q,work):
                continue
            if not fully_contains(manager, p, q) or not fully_contains(manager, q, p):
                continue
            intersection = manager.copy(a)
            if not _boolean(manager, intersection, b, adsk.fusion.BooleanTypes.IntersectionBooleanType):
                continue
            if intersection.isSolid and intersection.faces.count:
                continue  # Interpenetration is not split-body contact.
            return True
    return False


def _edge_probe(edge):
    evaluator = edge.evaluator
    ok, low, high = evaluator.getParameterExtents()
    if not ok:
        raise ValueError('Could not read an exact curve parameter interval.')
    points = [v.geometry for v in (edge.startVertex, edge.endVertex) if v is not None]
    for u in (.25, .5, .75):
        ok, point = evaluator.getPointAtParameter(low+(high-low)*u)
        if not ok:
            raise ValueError('Could not read the original curve.')
        points.append(point)
    return tuple(points)


def _on_edge(points, edge):
    curve = adsk.core.Circle3D.cast(edge.geometry) or adsk.core.Arc3D.cast(edge.geometry)
    if curve:
        normal=curve.normal.asArray();length=hypot(*normal)
        normal=tuple(v/length for v in normal)
        for point in points:
            delta=tuple(a-b for a,b in zip(point.asArray(),curve.center.asArray()))
            if abs(sum(a*b for a,b in zip(delta,normal))) > CONTACT_TOLERANCE or abs(hypot(*delta)-curve.radius) > CONTACT_TOLERANCE:
                return False
        # Trimming/range is proved by the subsequent wire difference. ASM's
        # inverse evaluator can clamp at a periodic seam to the wrong endpoint.
        return True
    evaluator = edge.evaluator
    ok, low, high = evaluator.getParameterExtents()
    if not ok:
        return False
    for point in points:
        ok, parameter = evaluator.getParameterAtPoint(point)
        if not ok or not low-1e-10 <= parameter <= high+1e-10:
            return False
        ok, actual = evaluator.getPointAtParameter(parameter)
        if not ok or point.distanceTo(actual) > CONTACT_TOLERANCE:
            return False
    return True


def map_originals(refs, virtual, manager, work, edge):
    targets = tuple(virtual.edges if edge else virtual.faces)
    target_boxes = {str(t.tempId): bounds(t) for t in targets}
    mapped = {str(t.tempId): [] for t in targets}
    sources = {}
    for key, original in refs.items():
        work.step()
        source = world_copy(original, manager)
        entity = source.edges.item(0) if edge else source.faces.item(0)
        sources[key] = source
        box = bounds(entity)
        probe = _edge_probe(entity) if edge else (entity.pointOnFace,)
        for target in targets:
            work.step()
            if not overlaps(box, target_boxes[str(target.tempId)]):
                continue
            if edge:
                if entity.length > target.length+1e-6 or not _on_edge(probe, target):
                    continue
            elif not _on_face(probe[0], target):
                continue
            if fully_contains(manager, entity, target, edge):
                mapped[str(target.tempId)].append(key)
    # A virtual entity is usable only when its entire geometry maps back to
    # original pieces. Never return a partially mapped, visually open loop.
    for target in targets:
        work.step()
        key = str(target.tempId)
        remainder = manager.copy(target)
        for original in mapped[key]:
            if not _boolean(manager, remainder, sources[original], adsk.fusion.BooleanTypes.DifferenceBooleanType):
                mapped[key] = []
                break
        if (remainder.edges.count if edge else remainder.faces.count):
            mapped[key] = []
    return {key: tuple(sorted(values)) for key, values in mapped.items()}


def read(entities, single_reader):
    from . import fusion_adapter as adapter
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    if not entities or not design or any(adapter.kind(e) != adapter.kind(entities[0]) for e in entities):
        raise ValueError('Select only BRep edges or only BRep faces.')
    candidates = [entities[0].body]
    for e in entities:
        if e.body not in candidates:
            candidates.append(e.body)
    pool = list(design.rootComponent.bRepBodies)
    for occurrence in design.rootComponent.allOccurrences:
        if occurrence.isVisible:
            pool.extend(occurrence.bRepBodies)
    for body in pool:
        if body.isVisible and body.isSelectable and body not in candidates:
            candidates.append(body)
    if len(candidates) > 128:
        raise ValueError('Exact-contact scope exceeds 128 visible bodies.')
    work, manager = Budget(), adsk.fusion.TemporaryBRepManager.get()
    all_guards = tuple((body, adapter.body_stamp(body)) for body in candidates)
    copies = {0: world_copy(candidates[0], manager)}
    joined, group = copies[0], [0]
    remaining = set(range(1, len(candidates)))
    while remaining:
        added = False
        for index in sorted(remaining):
            work.step()
            if not overlaps(bounds(joined), bounds(candidates[index])):
                continue
            if index not in copies:
                copies[index] = world_copy(candidates[index], manager)
            if not any(exact_contact(copies[owner], copies[index], manager, work) for owner in group):
                continue
            trial = manager.copy(joined)
            if not _boolean(manager, trial, copies[index], adsk.fusion.BooleanTypes.UnionBooleanType) or trial.lumps.count != 1:
                raise ValueError('Could not sew the exactly touching bodies into one temporary solid.')
            joined = trial
            group.append(index)
            remaining.remove(index)
            added = True
            if len(group) > 16:
                raise ValueError('Exact-contact chain exceeds 16 joined bodies.')
            break
        if not added:
            break
    if any(not any(e.body == candidates[i] for i in group) for e in entities):
        raise ValueError('The examples do not share complete exact body contact. Gaps, partial contact and overlap are not joined.')
    if len(group) == 1:
        result = single_reader(entities)
        return result, all_guards
    snapshots, own_refs, guards = [], [], []
    for index in group:
        work.step()
        body = candidates[index]
        collection = body.edges if adapter.kind(entities[0]) == 'edge' else body.faces
        seeds = tuple(e for e in entities if e.body == body) or (collection.item(0),)
        snap, _, refs, _, _ = adapter.read_snapshot(seeds, include_relations=False)
        snapshots.append(snap)
        own_refs.append(refs)
        guards.append((body, adapter.body_stamp(body)))
    snapshot, maps = merge_snapshots(snapshots, uuid4().hex, json.dumps([s.revision for s in snapshots]))
    refs = {maps[i][k]: entity for i, own in enumerate(own_refs) for k,entity in own.items()}
    examples = tuple(next(key for key,value in refs.items() if value == e) for e in entities)
    edge = adapter.kind(entities[0]) == 'edge'
    mapped = map_originals(refs, joined, manager, work, edge)
    links = set(snapshot.links)
    for parts in mapped.values():
        links.update(combinations(parts,2))
    virtual_links = []
    if edge:
        for vertex in joined.vertices:
            es = tuple(str(e.tempId) for e in vertex.edges)
            virtual_links.extend(combinations(es,2))
    else:
        for e in joined.edges:
            fs = tuple(str(f.tempId) for f in e.faces)
            virtual_links.extend(combinations(fs,2))
    for a,b in virtual_links:
        links.update((p,q) for p in mapped[a] for q in mapped[b] if p != q)
    snapshot = replace(snapshot, links=tuple(links))
    neighbours = {str(f.tempId): set() for f in joined.faces}
    for e in joined.edges:
        for a,b in combinations(tuple(str(f.tempId) for f in e.faces),2):
            neighbours[a].add(b);neighbours[b].add(a)
    chains = []
    for cap in joined.faces:
        for loop in cap.loops:
            work.step()
            edges = tuple(c.edge for c in loop.coEdges)
            if edge:
                ids = tuple(str(e.tempId) for e in edges)
                if len(set(ids)) != len(ids):
                    continue
            else:
                walls = [tuple(f for f in e.faces if f != cap) for e in edges]
                if any(len(faces) != 1 for faces in walls):
                    continue
                ids = tuple(str(faces[0].tempId) for faces in walls)
                if any(a != b and b not in neighbours[a] for a,b in zip(ids,ids[1:]+ids[:1])):
                    continue
            if any(not mapped[key] for key in ids):
                continue
            keys = tuple(sorted({key for item in ids for key in mapped[item]}))
            chains.append(ClosedChain(keys, sum(e.length for e in edges), not loop.isOuter))
    if not adapter.scope_current(all_guards):
        raise ValueError('The assembly changed while reading exact contacts.')
    return (snapshot, examples, refs, 0, candidates[0], tuple(guards), tuple(chains)), all_guards
