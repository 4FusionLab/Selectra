# SPDX-License-Identifier: GPL-3.0-only
"""Bounded read-only BRep snapshots. Initial spike: one root-component body."""
from time import monotonic
from dataclasses import replace
from uuid import uuid4
from math import hypot

import adsk.core
import adsk.fusion

from .matching import Descriptor
from .snapshot import BodySnapshot
from .walls import PlanarPatch, wall_probe_points, confirm_wall

MAX_ENTITIES = 10000
READ_BUDGET_SECONDS = 2.0
MAX_TOPOLOGY_LINKS = 100000
MAX_PLANAR_FACES = 160
MAX_CONTOUR_POINTS = 512
CONTOUR_TOLERANCE = 1e-4  # cm: numeric strokes, not exact BRep congruence.


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
            raise ValueError('Material ray analysis exceeded the time budget.')
        hits = adsk.core.ObjectCollection.create()
        entities = body.parentComponent.findBRepUsingRay(
            adsk.core.Point3D.create(*start), adsk.core.Vector3D.create(*delta),
            adsk.fusion.BRepEntityTypes.BRepFaceEntityType, 1e-6, False, hits)
        if not entities or entities.count != hits.count:
            raise ValueError('Could not read complete material segment intersections.')
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
            raise ValueError('Material ray did not reach the opposite trimmed face.')
    return True


def _contours(face):
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
            ok, stroke = evaluator.getStrokes(low, high, CONTOUR_TOLERANCE)
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
                raise ValueError('Trimmed boundary exceeds the contour analysis budget.')
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
    if entity_kind == 'edge':
        if entity.isDegenerate:
            raise ValueError('Degenerate edges are not supported.')
        measure = entity.length
        if family == 'line':
            direction = _vector(geometry.startPoint.vectorTo(geometry.endPoint))
    elif entity_kind == 'face':
        measure = entity.area
        perimeter = sum(entity.edges.item(i).length for i in range(entity.edges.count))
        sides, loops = entity.edges.count, entity.loops.count
        if family == 'plane':
            sign = -1 if entity.isParamReversed else 1
            normal = tuple(sign * x for x in _vector(geometry.normal))
            position = _vector(geometry.origin)
            contours = _contours(entity)
        elif family == 'cylinder':
            direction = _vector(geometry.axis)
    else:
        raise ValueError('Select BRep edges or faces.')
    if family in ('arc', 'circle', 'cylinder', 'sphere'):
        radius = geometry.radius
    # tempId is only session-local and only used within this unchanged body.
    return Descriptor(str(entity.tempId), entity_kind, family, measure,
                      perimeter, radius, direction, normal, sides, loops,
                      position=position, contours=contours,
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
    if any(e.assemblyContext is not None or e.body != body for e in entities):
        raise ValueError('This prototype searches one root-component body at a time.')
    if body.parentComponent != design.rootComponent:
        raise ValueError('Component occurrences are planned; select a root-component body for now.')
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


def read_snapshot(entities):
    """Prepare same-body topology for the pure command controller.

    Native extraction is source-prepared only until Fusion CAD acceptance.
    Each opaque scope is local to this command, never an entityToken hash.
    """
    if not entities:
        raise ValueError('Select an edge or a face first.')
    total_started = monotonic()
    source_body = entities[0].body
    revision = source_body.revisionId
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
    topology_seconds = monotonic() - started
    relationship_started = monotonic()
    patches = [PlanarPatch(d.key, d.normal, d.position, d.contours)
               for d in scoped if d.geometry == 'plane' and d.contours]
    if len(patches) > MAX_PLANAR_FACES:
        raise ValueError('Planar relationship analysis exceeds the body budget (160 faces).')
    for index, patch in enumerate(patches):
        for other in patches[index+1:]:
            if monotonic() - started > READ_BUDGET_SECONDS:
                raise ValueError('Wall relationship analysis exceeded the time budget.')
            probe = wall_probe_points(patch, other)
            if not probe.complete:
                raise ValueError('Wall relationship analysis is incomplete: ' + probe.reason)
            if not probe.points:
                continue
            material = []
            for point in probe.points:
                if monotonic() - started > READ_BUDGET_SECONDS:
                    raise ValueError('Material confirmation exceeded the time budget.')
                material.append(source_body.pointContainment(adsk.core.Point3D.create(*point))
                                == adsk.fusion.PointContainment.PointInsidePointContainment)
            if confirm_wall(probe, material) is not None and _unbroken_material_traces(source_body, probe, started):
                wall_pairs.append((patch.key, other.key))
    if monotonic() - started > READ_BUDGET_SECONDS:
        raise ValueError('Wall relationship analysis exceeded the time budget.')
    if not source_body.isValid or source_body.revisionId != revision:
        raise ValueError('Geometry changed during relationship analysis. Please retry.')
    snapshot = BodySnapshot(scope, revision, scoped, tuple(links), tuple(wall_pairs))
    snapshot.require_keys(d.key for d in examples)
    read_snapshot.last_timings = {'brep_seconds': read_seconds, 'topology_seconds': topology_seconds,
                                  'relationships_seconds': monotonic()-relationship_started,
                                  'total_read_seconds': monotonic()-total_started}
    return snapshot, tuple(d.key for d in examples), refs, skipped, source_body
