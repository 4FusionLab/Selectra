# SPDX-License-Identifier: GPL-3.0-only
"""Bounded read-only BRep snapshots. Initial spike: one root-component body."""
from time import monotonic
from dataclasses import replace
from uuid import uuid4

import adsk.core
import adsk.fusion

from .matching import Descriptor
from .snapshot import BodySnapshot

MAX_ENTITIES = 10000
READ_BUDGET_SECONDS = 2.0
MAX_TOPOLOGY_LINKS = 100000


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
    direction = normal = radius = perimeter = sides = loops = None
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
        elif family == 'cylinder':
            direction = _vector(geometry.axis)
    else:
        raise ValueError('Select BRep edges or faces.')
    if family in ('arc', 'circle', 'cylinder', 'sphere'):
        radius = geometry.radius
    # tempId is only session-local and only used within this unchanged body.
    return Descriptor(str(entity.tempId), entity_kind, family, measure,
                      perimeter, radius, direction, normal, sides, loops,
                      adjacent_faces=entity.faces.count if entity_kind == 'edge' else None)


def read_scope(entities):
    """Return examples, pool and live references owned by this command only.

    Never strip assemblyContext: that would collapse occurrences. Assembly
    matching needs an explicit world-frame implementation in a later phase.
    """
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
    started = monotonic()
    descriptors, references, skipped = [], {}, 0
    for i in range(collection.count):
        if monotonic() - started > READ_BUDGET_SECONDS:
            raise ValueError('Analysis exceeded the prototype time budget. No partial result was applied.')
        entity = collection.item(i)
        try:
            descriptor = describe(entity)
        except (RuntimeError, ValueError):
            skipped += 1
            continue
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
    source_body = entities[0].body
    revision = source_body.revisionId
    examples, pool, refs, skipped = read_scope(entities)
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
    snapshot = BodySnapshot(scope, revision, scoped, tuple(links))
    snapshot.require_keys(d.key for d in examples)
    return snapshot, tuple(d.key for d in examples), refs, skipped, source_body
