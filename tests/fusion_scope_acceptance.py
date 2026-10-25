# SPDX-License-Identifier: GPL-3.0-only
"""Sequential live CAD checks for scopes and transformed component instances."""
import builtins
import math

import adsk.core
import adsk.fusion


def prepare(entry, height=1):
    app = adsk.core.Application.get()
    assert app.userInterface.activeCommand == 'SelectCommand'
    original = app.activeDocument
    document = app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    design = adsk.fusion.Design.cast(app.activeProduct)
    design.designType = adsk.fusion.DesignTypes.DirectDesignType
    root, manager = design.rootComponent, adsk.fusion.TemporaryBRepManager.get()

    def transform(x, y, angle=0):
        m = adsk.core.Matrix3D.create()
        m.setToRotation(angle, adsk.core.Vector3D.create(0, 0, 1), adsk.core.Point3D.create(0, 0, 0))
        m.translation = adsk.core.Vector3D.create(x, y, 0)
        return m

    def box(x=0):
        return manager.createBox(adsk.core.OrientedBoundingBox3D.create(
            adsk.core.Point3D.create(x, 0, 0), adsk.core.Vector3D.create(1, 0, 0),
            adsk.core.Vector3D.create(0, 1, 0), 4, 3, height))

    root.bRepBodies.add(box(-20))
    source = root.occurrences.addNewComponent(transform(15, 0, .4))
    source.component.name = 'Scope test component'
    source.component.bRepBodies.add(box())
    source.component.bRepBodies.add(box(6))
    root.occurrences.addExistingComponent(source.component, transform(-15, 10, -.6))
    parent = root.occurrences.addNewComponent(transform(0, 20, .7))
    parent.component.name = 'Nested parent'
    parent.component.occurrences.addExistingComponent(source.component, transform(0, 6, -.3))
    body = source.bRepBodies.item(0)
    seed = next(f for f in body.faces if math.isclose(f.area, 12) and f.pointOnFace.z > height*.4)
    builtins._selectra_scope_test = dict(entry=entry, original=original, document=document, design=design,
                                       source=source, seed=seed, height=height, results=[], expected_counts={'body': 2, 'component': 4, 'all': 14})
    app.userInterface.activeSelections.clear()
    app.userInterface.activeSelections.add(seed)
    app.activeViewport.fit()
    return {'prepared': True, 'root_bodies': root.bRepBodies.count, 'occurrences': root.allOccurrences.count}


def open_command():
    state = builtins._selectra_scope_test
    app = adsk.core.Application.get()
    assert app.activeDocument == state['document']
    assert app.userInterface.activeCommand == 'SelectCommand'
    app.userInterface.activeSelections.clear()
    app.userInterface.activeSelections.add(state['seed'])
    return app.userInterface.commandDefinitions.itemById(state['entry'].COMMAND_ID).execute()


def add_nested_source_child():
    state = builtins._selectra_scope_test
    app = adsk.core.Application.get()
    assert app.activeDocument == state['document'] and app.userInterface.activeCommand == 'SelectCommand'
    matrix = adsk.core.Matrix3D.create()
    matrix.setToRotation(.5, adsk.core.Vector3D.create(0, 1, 0), adsk.core.Point3D.create(0, 0, 0))
    matrix.translation = adsk.core.Vector3D.create(0, 6, 2)
    child = state['source'].component.occurrences.addNewComponent(matrix)
    child.component.name = 'Inside selected component'
    manager = adsk.fusion.TemporaryBRepManager.get()
    child.component.bRepBodies.add(manager.createBox(adsk.core.OrientedBoundingBox3D.create(
        adsk.core.Point3D.create(0, 0, 0), adsk.core.Vector3D.create(1, 0, 0),
        adsk.core.Vector3D.create(0, 1, 0), 4, 3, 1)))
    state['seed'] = next(f for f in state['source'].bRepBodies.item(0).faces
                         if math.isclose(f.area, 12) and f.pointOnFace.z > state['height']*.4)
    state['expected_counts'].update(component=6, all=20)
    return {'nested_added': True, 'occurrences': state['design'].rootComponent.allOccurrences.count}


def inspect():
    state = builtins._selectra_scope_test
    s = state['entry']._sessions[-1]
    assert not s.preview_error, s.preview_error
    assert s.renderer.keys == s.chosen_keys()
    assert len(s.chosen_keys()) == state['expected_counts'][s.scope_mode], (s.scope_mode, s.chosen_keys())
    assert len(set(s.refs)) == len(s.snapshot.entities)
    renderers = s.renderer.renderers if hasattr(s.renderer, 'renderers') else (s.renderer,)
    maximum_error, outline_error = 0, 0
    for renderer in renderers:
        for key in renderer.keys:
            expected = s.refs[key].boundingBox
            actual = renderer.graphics[key].bRepBody.boundingBox
            error = max(expected.minPoint.distanceTo(actual.minPoint), expected.maxPoint.distanceTo(actual.maxPoint))
            maximum_error = max(error, maximum_error)
        for key, graphic in renderer.outlines.items():
            if not graphic.isVisible:
                continue
            values = graphic.coordinates.coordinates
            expected = s.refs[key].boundingBox
            low = adsk.core.Point3D.create(*(min(values[i::3]) for i in range(3)))
            high = adsk.core.Point3D.create(*(max(values[i::3]) for i in range(3)))
            outline_error = max(outline_error, low.distanceTo(expected.minPoint), high.distanceTo(expected.maxPoint))
    assert maximum_error < 1e-6, maximum_error
    assert outline_error < 1e-5, outline_error  # Graphics coordinates are float32.
    state['expected_ok'] = tuple(s.refs[k] for k in s.chosen_keys())
    result = {'scope': s.scope_mode, 'count': len(s.chosen_keys()), 'bodies': len(s.scope_guards),
              'world_highlight_error_cm': maximum_error, 'world_outline_error_cm': outline_error,
              'entities': len(s.snapshot.entities)}
    state['results'].append(result)
    return result


def finish():
    state = builtins._selectra_scope_test
    app = adsk.core.Application.get()
    assert app.activeDocument == state['document']
    assert app.userInterface.activeCommand == 'SelectCommand'
    assert state['design'].rootComponent.customGraphicsGroups.count == 0
    state['original'].activate()
    state['document'].close(False)
    return {'restored': app.activeDocument == state['original'], 'graphics_clean': True}


def inspect_guards_and_hidden_instances():
    state = builtins._selectra_scope_test
    app = adsk.core.Application.get()
    assert app.activeDocument == state['document'] and app.userInterface.activeCommand == 'SelectCommand'
    adapter, source = state['entry'].adapter, state['source']
    guard = ((source.bRepBodies.item(0), adapter.body_stamp(source.bRepBodies.item(0))),)
    original = source.transform2
    moved = adsk.core.Matrix3D.create()
    moved.setWithArray(original.asArray())
    position = moved.translation
    position.x += 1
    moved.translation = position
    try:
        source.transform2 = moved
        assert not adapter.scope_current(guard), 'Occurrence motion must invalidate the snapshot.'
    finally:
        source.transform2 = original
    hidden = state['design'].rootComponent.occurrences.addExistingComponent(source.component, adsk.core.Matrix3D.create())
    hidden.isLightBulbOn = False
    snap, _, refs, _, _, guards = adapter.read_search_scope((state['seed'],), 'all')
    assert len(guards) == 10, len(guards)
    assert len(snap.entities) == 60
    assert all(not (e.assemblyContext and e.assemblyContext.fullPathName.startswith(hidden.fullPathName)) for e in refs.values())
    root_body = state['design'].rootComponent.bRepBodies.item(0)
    root_seed = next(f for f in root_body.faces if math.isclose(f.area, 12))
    root_snap, keys, _, _, _, root_guards = adapter.read_search_scope((root_seed,), 'component')
    assert len(root_guards) == 10
    assert len(state['entry'].SelectionSession(root_snap, keys).result) == 20
    return {'movement_invalidates_scope': True, 'hidden_subtree_excluded': True, 'root_component_includes_assembly': True}
