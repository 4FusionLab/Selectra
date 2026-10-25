# SPDX-License-Identifier: GPL-3.0-only
"""Bounded read-only BRep snapshots. Initial spike: one root-component body."""
from time import monotonic

import adsk.core
import adsk.fusion

from .matching import Descriptor

MAX_ENTITIES = 10000
READ_BUDGET_SECONDS = 2.0


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
                      perimeter, radius, direction, normal, sides, loops)


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
