# SPDX-License-Identifier: GPL-3.0-only
"""Bounded read-only BRep snapshots. Initial spike: one root-component body."""
from time import monotonic
from dataclasses import replace
from uuid import uuid4
from math import hypot
import json

import adsk.core
import adsk.fusion

from .matching import Descriptor, _near
from .snapshot import BodySnapshot
from .walls import PlanarPatch, wall_probe_points, confirm_wall
from .search_scope import merge_snapshots, component_contains, SCOPES

MAX_ENTITIES = 10000
READ_BUDGET_SECONDS = 2.0
MAX_TOPOLOGY_LINKS = 100000
MAX_PLANAR_FACES = 160
MAX_CONTOUR_POINTS = 512
CONTOUR_TOLERANCE = 1e-4  # cm: numeric strokes, not exact BRep congruence.
MAX_SCOPE_BODIES = 128
SCOPE_BUDGET_SECONDS = 8.0


class WallAnalysisUnavailable(RuntimeError):
    """Optional relations are unavailable; mandatory shape reading may continue."""


class ContourBudgetExceeded(ValueError):
    pass


def body_stamp(body):
    context = body.assemblyContext
    return body.revisionId, tuple(context.transform2.asArray()) if context else ()


def scope_current(guards):
    return all(body.isValid and body.isVisible and body.isSelectable and body_stamp(body) == stamp for body, stamp in guards)


def _world_descriptor(descriptor, context):
    if context is None:
        return descriptor
    matrix = context.transform2

    def point(values):
        p = adsk.core.Point3D.create(*values)
        p.transformBy(matrix)
        return _vector(p)

    def vector(values):
        v = adsk.core.Vector3D.create(*values)
        v.transformBy(matrix)
        return _vector(v)

    return replace(descriptor, position=point(descriptor.position) if descriptor.position else None,
                   normal=vector(descriptor.normal) if descriptor.normal else None,
                   direction=vector(descriptor.direction) if descriptor.direction else None,
                   contours=tuple(tuple(point(p) for p in loop) for loop in descriptor.contours),
                   planes=tuple((vector(n), point(p)) for n, p in descriptor.planes))


def _unbroken_material_traces(body, probe, started):
    """Reject any intervening BRep boundary, including voids between probes.

    The whole overlap remains sampled in the lateral directions. Within each
    sampled trace the ray test covers the segment, rather than five depths.
    Other bodies/occurrences returned by the component query are ignored.
    """
    for index in range(0, len(probe.points), 5):
        first, last = probe.points[index], probe.points[index+4]
        delta = tuple((b-a)/.9 for a, b in zip(first, last))
        length = hypot(*delta)
        start = tuple(p-.05*d for p, d in zip(first, delta))
        if monotonic() - started > READ_BUDGET_SECONDS:
            raise WallAnalysisUnavailable('Material ray analysis exceeded the time budget.')
        hits = adsk.core.ObjectCollection.create()
        entities = body.parentComponent.findBRepUsingRay(
            adsk.core.Point3D.create(*start), adsk.core.Vector3D.create(*delta),
            adsk.fusion.BRepEntityTypes.BRepFaceEntityType, 1e-6, False, hits)
        if not entities or entities.count != hits.count:
            raise WallAnalysisUnavailable('Could not read complete material segment intersections.')
        endpoint_found = False
        for i in range(entities.count):
            entity = entities.item(i)
            if entity.body != body or entity.assemblyContext is not None:
                continue
            hit = _vector(hits.item(i))
            distance = sum((p-o)*d/length for p, o, d in zip(hit, start, delta))
            if abs(distance-length) <= 2e-6:
                endpoint_found = True
            if 2e-6 < distance < length-2e-6:
                return False
        if not endpoint_found:
            raise WallAnalysisUnavailable('Material ray did not reach the opposite trimmed face.')
    return True


def _contours(face, stroke_tolerance=CONTOUR_TOLERANCE):
    """Read coedge-oriented trimmed loops; never use the untrimmed surface."""
    loops, count = [], 0
    for i in range(face.loops.count):
        loop = face.loops.item(i)
        points = []
        previous_end = None
        for j in range(loop.coEdges.count):
            coedge = loop.coEdges.item(j)
            evaluator = coedge.edge.evaluator
            ok, low, high = evaluator.getParameterExtents()
            if not ok:
                raise ValueError('Could not read the trimmed boundary parameter range.')
            ok, stroke = evaluator.getStrokes(low, high, stroke_tolerance)
            if not ok or len(stroke) < 2:
                raise ValueError('Could not read the complete trimmed boundary.')
            stroke = list(stroke)
            # The curve evaluator's parameter order can oppose the BRep
            # edge direction. Compose BOTH reversals to follow the coedge.
            if coedge.isOpposedToEdge != coedge.edge.isParamReversed:
                stroke.reverse()
            start, end = _vector(stroke[0]), _vector(stroke[-1])
            if previous_end is not None and hypot(*(a-b for a, b in zip(previous_end, start))) > 1e-6:
                raise ValueError('Trimmed boundary segments do not form a continuous loop.')
            points.extend(_vector(p) for p in stroke[:-1])
            previous_end = end
            count += len(stroke)-1
            if count > MAX_CONTOUR_POINTS:
                raise ContourBudgetExceeded('Trimmed boundary exceeds the contour analysis budget.')
        if not points or hypot(*(a-b for a, b in zip(previous_end, points[0]))) > 1e-6:
            raise ValueError('Trimmed boundary is not closed.')
        loops.append((not loop.isOuter, tuple(points)))
    loops.sort(key=lambda item: item[0])
    return tuple(points for _, points in loops)


def kind(entity):
    if adsk.fusion.BRepEdge.cast(entity):
        return 'edge'
    if adsk.fusion.BRepFace.cast(entity):
        return 'face'
    return None


def _vector(vector):
    return vector.x, vector.y, vector.z


def describe(entity):
    # Numeric extraction and material queries use component-local native data.
    # Live references keep their exact occurrence; the snapshot is transformed
    # to world coordinates only after local relationships are confirmed.
    if entity.assemblyContext is not None:
        entity = entity.nativeObject
    entity_kind = kind(entity)
    geometry = entity.geometry
    family = geometry.objectType.rsplit('::', 1)[-1]
    names = {'Line3D': 'line', 'Circle3D': 'circle', 'Arc3D': 'arc',
             'Plane': 'plane', 'Cylinder': 'cylinder', 'Cone': 'cone',
             'Sphere': 'sphere', 'Torus': 'torus',
             'NurbsSurface': 'nurbs', 'NurbsCurve3D': 'nurbs'}
    family = names.get(family, family)
    direction = normal = radius = perimeter = sides = loops = position = None
    contours = ()
    planes = ()
    if entity_kind == 'edge':
        if entity.isDegenerate:
            raise ValueError('Degenerate edges are not supported.')
        measure = entity.length
        if family == 'line':
            direction = _vector(geometry.startPoint.vectorTo(geometry.endPoint))
        if family in ('circle', 'arc'):
            normal, position = _vector(geometry.normal), _vector(geometry.center)
            planes = ((normal, position),)
        else:
            support = []
            for face in entity.faces:
                plane = adsk.core.Plane.cast(face.geometry)
                if plane:
                    support.append((_vector(plane.normal), _vector(plane.origin)))
            planes = tuple(support)
    elif entity_kind == 'face':
        measure = entity.area
        perimeter = sum(entity.edges.item(i).length for i in range(entity.edges.count))
        sides, loops = entity.edges.count, entity.loops.count
        if family == 'plane':
            sign = -1 if entity.isParamReversed else 1
            normal = tuple(sign * x for x in _vector(geometry.normal))
            position = _vector(geometry.origin)
            # Scale the stroke deviation far below the 1% matching tolerance;
            # fixed micron strokes over-sample large project geometry.
            for factor in (1, 4, 16):
                try:
                    contours = _contours(entity, max(CONTOUR_TOLERANCE, perimeter*1e-5)*factor)
                    break
                except ContourBudgetExceeded:
                    continue
        elif family == 'cylinder':
            direction = _vector(geometry.axis)
    else:
        raise ValueError('Select BRep edges or faces.')
    if family in ('arc', 'circle', 'cylinder', 'sphere'):
        radius = geometry.radius
    # tempId is only session-local and only used within this unchanged body.
    return Descriptor(str(entity.tempId), entity_kind, family, measure,
                      perimeter, radius, direction, normal, sides, loops,
                      position=position, contours=contours, planes=planes,
                      adjacent_faces=entity.faces.count if entity_kind == 'edge' else None)


def read_scope(entities):
    """Return examples, pool and live references owned by this command only.

    Never strip assemblyContext: that would collapse occurrences. Assembly
    matching needs an explicit world-frame implementation in a later phase.
    """
    started = monotonic()
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    if not design or not entities:
        raise ValueError('Select an edge or a face in a Design document first.')
    if any(not e or not e.isValid or not kind(e) for e in entities):
        raise ValueError('Select only BRep edges or only BRep faces.')
    if len({kind(e) for e in entities}) != 1:
        raise ValueError('Use only edges or only faces in this prototype.')
    body = entities[0].body
    if any(e.body != body for e in entities):
        raise ValueError('Initial examples must belong to one body occurrence.')
    if not body.isVisible or not body.isSelectable:
        raise ValueError('The selected body must be visible and selectable.')
    examples = tuple(describe(e) for e in entities)
    collection = body.edges if examples[0].kind == 'edge' else body.faces
    if collection.count > MAX_ENTITIES:
        raise ValueError('Scope is too large for this prototype (10,000 entities maximum).')
    descriptors, references, skipped = [], {}, 0
    for i in range(collection.count):
        if monotonic() - started > READ_BUDGET_SECONDS:
            raise ValueError('Analysis exceeded the prototype time budget. No partial result was applied.')
        entity = collection.item(i)
        if kind(entity) == 'edge' and entity.isDegenerate:
            skipped += 1
            continue
        # An unread boundary cannot silently disappear from a complete body
        # ranking. Budget/API failures abort atomically with a visible message.
        descriptor = describe(entity)
        descriptors.append(descriptor)
        references[descriptor.key] = entity
        if monotonic() - started > READ_BUDGET_SECONDS:
            raise ValueError('Analysis exceeded the prototype time budget. No partial result was applied.')
    unique = {d.key: d for d in examples}
    return tuple(unique.values()), tuple(descriptors), references, skipped


def read_snapshot(entities, *, include_relations=True):
    """Prepare same-body topology for the pure command controller.

    Native extraction is source-prepared only until Fusion CAD acceptance.
    Each opaque scope is local to this command, never an entityToken hash.
    """
    if not entities:
        raise ValueError('Select an edge or a face first.')
    total_started = monotonic()
    source_body = entities[0].body
    revision = source_body.revisionId
    stamp = body_stamp(source_body)
    analysis_body = source_body.nativeObject if source_body.assemblyContext else source_body
    examples, pool, refs, skipped = read_scope(entities)
    read_seconds = monotonic() - total_started
    scope = uuid4().hex
    scoped = tuple(replace(d, scope_key=scope) for d in pool)
    links, started = set(), monotonic()
    for key, entity in refs.items():
        if monotonic() - started > READ_BUDGET_SECONDS:
            raise ValueError('Topology read exceeded the prototype time budget.')
        if kind(entity) == 'edge':
            neighbours = (vertex.edges for vertex in (entity.startVertex, entity.endVertex) if vertex)
        else:
            neighbours = (entity.edges.item(i).faces for i in range(entity.edges.count))
        for collection in neighbours:
            for i in range(collection.count):
                if monotonic() - started > READ_BUDGET_SECONDS:
                    raise ValueError('Topology read exceeded the prototype time budget.')
                other = collection.item(i)
                other_key = str(other.tempId)
                if other.body == source_body and other_key in refs and other_key != key:
                    links.add(tuple(sorted((key, other_key))))
                    if len(links) > MAX_TOPOLOGY_LINKS:
                        raise ValueError('Topology is too dense for the prototype budget.')
    if source_body.revisionId != revision:
        raise ValueError('Geometry changed while reading the body. Please retry.')
    wall_pairs = []
    relations_complete = include_relations and all(d.contours for d in scoped if d.geometry == 'plane')
    topology_seconds = monotonic() - started
    relationship_started = monotonic()
    patches = [PlanarPatch(d.key, d.normal, d.position, d.contours)
               for d in scoped if d.geometry == 'plane' and d.contours]
    if len(patches) > MAX_PLANAR_FACES:
        relations_complete = False
    for index, patch in enumerate(patches if relations_complete else ()):
        if not relations_complete:
            break
        for other in patches[index+1:]:
            if monotonic() - started > READ_BUDGET_SECONDS:
                relations_complete = False
                break
            probe = wall_probe_points(patch, other)
            if not probe.complete:
                relations_complete = False
                break
            if not probe.points:
                continue
            material = []
            for point in probe.points:
                if monotonic() - started > READ_BUDGET_SECONDS:
                    relations_complete = False
                    break
                material.append(analysis_body.pointContainment(adsk.core.Point3D.create(*point))
                                == adsk.fusion.PointContainment.PointInsidePointContainment)
            if not relations_complete:
                break
            if confirm_wall(probe, material) is not None:
                try:
                    if _unbroken_material_traces(analysis_body, probe, started):
                        wall_pairs.append((patch.key, other.key))
                except WallAnalysisUnavailable:
                    relations_complete = False
                    break
    if monotonic() - started > READ_BUDGET_SECONDS:
        relations_complete = False
    if not source_body.isValid or body_stamp(source_body) != stamp:
        raise ValueError('Geometry changed during relationship analysis. Please retry.')
    scoped = tuple(_world_descriptor(d, source_body.assemblyContext) for d in scoped)
    snapshot_revision = json.dumps(stamp) if source_body.assemblyContext else revision
    snapshot = BodySnapshot(scope, snapshot_revision, scoped, tuple(links), tuple(wall_pairs) if relations_complete else (), relations_complete)
    snapshot.require_keys(d.key for d in examples)
    if body_stamp(source_body) != stamp:
        raise ValueError('Body occurrence moved during geometry reading. Please retry.')
    read_snapshot.last_timings = {'brep_seconds': read_seconds, 'topology_seconds': topology_seconds,
                                  'relationships_seconds': monotonic()-relationship_started,
                                  'total_read_seconds': monotonic()-total_started}
    return snapshot, tuple(d.key for d in examples), refs, skipped, source_body


def read_search_scope(entities, mode='component'):
    if mode not in dict(SCOPES) or not entities:
        raise ValueError('Choose a valid search scope and an example.')
    if any(not e.isValid or not kind(e) or kind(e) != kind(entities[0]) for e in entities):
        raise ValueError('Select only BRep faces or only BRep edges.')
    source = entities[0].body
    design = adsk.fusion.Design.cast(adsk.core.Application.get().activeProduct)
    if source.assemblyContext is None and source.parentComponent != design.rootComponent:
        context = design.activeOccurrence
        if context is None or context.component != source.parentComponent:
            raise ValueError('Select the body in its assembly instance.')
        entities = tuple(e.createForAssemblyContext(context)
                         if e.assemblyContext is None and e.body.parentComponent == context.component else e
                         for e in entities)
        source = entities[0].body
    bodies = [source]
    if mode == 'component':
        collection = source.assemblyContext.bRepBodies if source.assemblyContext else source.parentComponent.bRepBodies
        candidates = list(collection)
        context = source.assemblyContext
        for occurrence in design.rootComponent.allOccurrences:
            if occurrence.isVisible and component_contains(context.fullPathName if context else None, occurrence.fullPathName):
                candidates.extend(occurrence.bRepBodies)
    elif mode == 'all':
        candidates = list(design.rootComponent.bRepBodies)
        for occurrence in design.rootComponent.allOccurrences:
            if occurrence.isVisible:
                candidates.extend(occurrence.bRepBodies)
    else:
        candidates = []
    for body in candidates:
        if body.isVisible and body.isSelectable and not any(body == known for known in bodies):
            bodies.append(body)
    if len(bodies) > MAX_SCOPE_BODIES:
        raise ValueError('Search scope exceeds 128 visible bodies. Choose a smaller scope.')
    started, snapshots, refs_by_body, guards, skipped, totals = monotonic(), [], [], [], 0, {}
    relations_available = True
    for body in bodies:
        if monotonic()-started > SCOPE_BUDGET_SECONDS:
            raise ValueError('Search scope analysis exceeded its time budget. No partial result was applied.')
        collection = body.faces if kind(entities[0]) == 'face' else body.edges
        seed = next((e for e in collection if kind(e) != 'edge' or not e.isDegenerate), None)
        if seed is None:
            continue
        local_examples = tuple(e for e in entities if e.body == body)
        snap, _, references, omitted, _ = read_snapshot(local_examples or (seed,), include_relations=relations_available)
        relations_available = relations_available and snap.relations_complete
        snapshots.append(snap)
        refs_by_body.append(references)
        guards.append((body, body_stamp(body)))
        skipped += omitted
        for key, value in read_snapshot.last_timings.items():
            totals[key] = totals.get(key, 0) + value
        if sum(len(s.entities) for s in snapshots) > MAX_ENTITIES:
            raise ValueError('Search scope exceeds 10,000 entities. No partial result was applied.')
        if sum(len(s.links) for s in snapshots) > MAX_TOPOLOGY_LINKS:
            raise ValueError('Search scope topology exceeds the analysis budget.')
    if not scope_current(guards) or monotonic()-started > SCOPE_BUDGET_SECONDS:
        raise ValueError('Search scope changed or exceeded its analysis budget. Please retry.')
    if len(snapshots) == 1:
        snapshot, references = snapshots[0], refs_by_body[0]
        maps = ({key: key for key in references},)
    else:
        snapshot, maps = merge_snapshots(snapshots, uuid4().hex, json.dumps([s.revision for s in snapshots]))
        references = {maps[i][key]: entity for i, refs in enumerate(refs_by_body) for key, entity in refs.items()}
    keys = []
    for entity in entities:
        owner = next((i for i, (body, _) in enumerate(guards) if entity.body == body), None)
        if owner is None:
            raise ValueError('Examples are outside this scope. Start within one component, then choose All Components.')
        keys.append(maps[owner][str(entity.tempId)])
    mesh_started = monotonic()
    snapshot = enrich_curved(snapshot, references, keys)
    totals['surface_mesh_seconds'] = monotonic()-mesh_started
    totals['total_read_seconds'] = monotonic()-started
    if not scope_current(guards) or monotonic()-started > SCOPE_BUDGET_SECONDS:
        raise ValueError('Geometry changed while reading curved groups.')
    read_search_scope.last_timings = totals
    return snapshot, tuple(keys), references, skipped, source, tuple(guards)


def enrich_curved(snapshot, references, examples):
    """Read bounded native meshes only for possible roles of curved examples."""
    seeds = tuple(snapshot.by_key[k] for k in examples)
    if len(seeds) < 2 or not any(d.kind == 'face' and d.geometry != 'plane' for d in seeds):
        return snapshot
    started, entities, changed, mesh_faces = monotonic(), [], False, 0
    for d in snapshot.entities:
        eligible = d.kind == 'face' and any(
            d.geometry == seed.geometry and _near(d.measure, seed.measure, .01, 1e-8)
            and _near(d.perimeter, seed.perimeter, .01, 1e-6) for seed in seeds)
        if eligible and not d.patch:
            if monotonic()-started > READ_BUDGET_SECONDS:
                raise ValueError('Curved-group reading exceeded its budget. No partial group was applied.')
            mesh_faces += 1
            if mesh_faces > 160:
                raise ValueError('Curved-group reading exceeds 160 faces. Narrow the scope.')
            face = references[d.key]
            native = face.nativeObject or face
            if native.vertices.count > 64:
                raise ValueError('Curved face exceeds 64 BRep landmarks.')
            calc = native.meshManager.createMeshCalculator()
            if not calc:
                raise ValueError('Could not create a curved-face mesh calculator.')
            calc.surfaceTolerance = max(1e-5, min(1e-3, d.perimeter*1e-4))
            mesh = calc.calculate()
            if not mesh or mesh.nodeCount > 1024 or mesh.triangleCount > 2048:
                raise ValueError('Curved face exceeds the supported surface mesh budget.')
            def point(p):
                if face.assemblyContext:
                    p = p.copy()
                    p.transformBy(face.assemblyContext.transform2)
                return _vector(p)
            def vector(v):
                if face.assemblyContext:
                    v = v.copy()
                    v.transformBy(face.assemblyContext.transform2)
                return _vector(v)
            indices = mesh.nodeIndices
            patch = (tuple(point(v.geometry) for v in native.vertices),
                     tuple(point(p) for p in mesh.nodeCoordinates),
                     tuple(tuple(indices[i:i+3]) for i in range(0, len(indices), 3)),
                     tuple(vector(n) for n in mesh.normalVectors))
            d, changed = replace(d, patch=patch), True
        entities.append(d)
    return replace(snapshot, entities=tuple(entities)) if changed else snapshot


def read_chains(entities):
    """Closed edge loops or adjacent wall rings, strictly in the source body."""
    from .chains import ClosedChain
    if len(entities) != 1:
        raise ValueError('Select one edge or one wall face for Select Chain.')
    snapshot, examples, refs, skipped, source = read_snapshot(entities, include_relations=False)
    started, chains, count = monotonic(), [], 0
    stamp = body_stamp(source)
    for cap in source.faces:
        for loop in cap.loops:
            count += 1
            if count > 10000 or monotonic()-started > READ_BUDGET_SECONDS:
                raise ValueError('Closed-chain analysis exceeded its budget. No partial chain was applied.')
            edges = tuple(c.edge for c in loop.coEdges)
            if not edges:
                continue
            perimeter = sum(edge.length for edge in edges)
            if kind(entities[0]) == 'edge':
                keys = tuple(str(edge.tempId) for edge in edges)
                if len(set(keys)) == len(keys) and all(key in refs for key in keys):
                    chains.append(ClosedChain(keys, perimeter, not loop.isOuter))
            else:
                walls = []
                for edge in edges:
                    others = tuple(face for face in edge.faces if face != cap)
                    if len(others) != 1:
                        break
                    walls.append(str(others[0].tempId))
                else:
                    if (all(key in refs for key in walls) and
                            all(a == b or b in snapshot.adjacency[a] for a,b in zip(walls,walls[1:]+walls[:1]))):
                        chains.append(ClosedChain(tuple(walls), perimeter, not loop.isOuter))
    if not source.isValid or body_stamp(source) != stamp:
        raise ValueError('Geometry changed while reading closed chains.')
    return snapshot, examples, refs, skipped, source, ((source, stamp),), tuple(chains)
