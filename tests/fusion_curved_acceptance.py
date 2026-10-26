# SPDX-License-Identifier: GPL-3.0-only
"""Disposable native acceptance using copies of the selected curved-face groups.

The source document and bodies are never modified. Run prepare(entry), open(),
inspect(12), =, inspect(18), -, inspect(12), native OK, then finish(). Counts are
specific to the acceptance example; geometry is neither saved nor published.
"""
import builtins
import adsk.core
import adsk.fusion


def _points(face):
    points = []
    for vertex in face.vertices:
        p = vertex.geometry.copy()
        if face.assemblyContext:
            p.transformBy(face.assemblyContext.transform2)
        points.append((p.x, p.y, p.z))
    return points


def prepare(entry):
    app = adsk.core.Application.get()
    assert app.userInterface.activeCommand == 'SelectCommand'
    examples = tuple(s.entity for s in app.userInterface.activeSelections)
    assert len(examples) >= 2 and all(adsk.fusion.BRepFace.cast(f) for f in examples)
    original = app.activeDocument
    bodies = []
    for face in examples:
        if face.body not in bodies:
            bodies.append(face.body)
    guards = tuple((body, entry.adapter.body_stamp(body)) for body in bodies)
    modified = original.isModified
    manager = adsk.fusion.TemporaryBRepManager.get()
    copies = []
    for body in bodies:
        copy = manager.copy(body.nativeObject or body)
        if body.assemblyContext:
            assert manager.transform(copy, body.assemblyContext.transform2)
        copies.append(copy)
    document = app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    design = adsk.fusion.Design.cast(app.activeProduct)
    design.designType = adsk.fusion.DesignTypes.DirectDesignType
    root = design.rootComponent
    targets = [root.bRepBodies.add(copy) for copy in copies]
    seeds = []
    for face in examples:
        points = _points(face)
        choices = [candidate for candidate in targets[bodies.index(face.body)].faces
                   if abs(candidate.area-face.area) < 1e-7 and candidate.geometry.objectType == face.geometry.objectType
                   and len(_points(candidate)) == len(points)
                   and all(any(sum((x-y)**2 for x, y in zip(a, b)) < 1e-10 for b in _points(candidate)) for a in points)]
        assert len(choices) == 1, len(choices)
        seeds.append(choices[0])
    builtins._selectra_curved_acceptance = dict(entry=entry, document=document, design=design,
                                              original=original, examples=examples, seeds=tuple(seeds),
                                              guards=guards, modified=modified)
    app.activeViewport.fit()
    return {'copies': len(targets), 'examples': len(seeds)}


def open_command():
    state = builtins._selectra_curved_acceptance
    app = adsk.core.Application.get()
    assert app.activeDocument == state['document'] and app.userInterface.activeCommand == 'SelectCommand'
    app.userInterface.activeSelections.clear()
    for face in state['seeds']:
        assert app.userInterface.activeSelections.add(face)
    return app.userInterface.commandDefinitions.itemById(state['entry'].COMMAND_ID).execute()


def inspect(expected):
    state = builtins._selectra_curved_acceptance
    session = state['entry']._sessions[-1]
    q = session.controller
    assert not session.preview_error, session.preview_error
    assert q.ranking.hypothesis == 'curved_regions'
    assert len(q.result) == expected, (q.level, q.result)
    assert session.renderer.keys == q.result
    state['expected_ok'] = tuple(session.refs[k] for k in q.result)
    return {'count': len(q.result), 'level': q.level, 'planes': q.ranking.plane_groups[:2]}


def finish():
    state = builtins._selectra_curved_acceptance
    app = adsk.core.Application.get()
    assert app.activeDocument == state['document'] and app.userInterface.activeCommand == 'SelectCommand'
    actual = tuple(s.entity for s in app.userInterface.activeSelections)
    assert len(actual) == len(state['expected_ok']) and all(f in actual for f in state['expected_ok'])
    assert state['design'].rootComponent.customGraphicsGroups.count == 0
    assert state['original'].isModified == state['modified']
    assert state['entry'].adapter.scope_current(state['guards'])
    state['original'].activate()
    state['document'].close(False)
    app.userInterface.activeSelections.clear()
    for face in state['examples']:
        assert app.userInterface.activeSelections.add(face)
    return {'exact_ok': len(actual), 'graphics_clean': True, 'source_unchanged': True}
