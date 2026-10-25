# SPDX-License-Identifier: GPL-3.0-only
"""Live circular-hole plane priority in a rotated, repeated component."""
import builtins
import math

import adsk.core
import adsk.fusion


def prepare(entry):
    app = adsk.core.Application.get()
    assert app.userInterface.activeCommand == 'SelectCommand'
    original = app.activeDocument
    document = app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    design = adsk.fusion.Design.cast(app.activeProduct)
    design.designType = adsk.fusion.DesignTypes.DirectDesignType
    root, manager = design.rootComponent, adsk.fusion.TemporaryBRepManager.get()
    transform = adsk.core.Matrix3D.create()
    transform.setToRotation(.35, adsk.core.Vector3D.create(0, 1, 0), adsk.core.Point3D.create(0, 0, 0))
    transform.translation = adsk.core.Vector3D.create(10, 0, 0)
    source = root.occurrences.addNewComponent(transform)
    source.component.name = 'Hole plane fixture'
    plate = manager.createBox(adsk.core.OrientedBoundingBox3D.create(
        adsk.core.Point3D.create(0, 0, 0), adsk.core.Vector3D.create(1, 0, 0),
        adsk.core.Vector3D.create(0, 1, 0), 4, 3, .2))
    for x, y in ((-1, -.5), (1, -.5), (-1, .5), (1, .5)):
        tool = manager.createCylinderOrCone(adsk.core.Point3D.create(x, y, -1), .2,
                                           adsk.core.Point3D.create(x, y, 1), .2)
        assert manager.booleanOperation(plate, tool, adsk.fusion.BooleanTypes.DifferenceBooleanType)
    source.component.bRepBodies.add(plate)
    perpendicular = manager.createCylinderOrCone(adsk.core.Point3D.create(5, 0, 0), .2,
                                                  adsk.core.Point3D.create(5.2, 0, 0), .2)
    source.component.bRepBodies.add(perpendicular)
    other = adsk.core.Matrix3D.create()
    other.setToRotation(math.pi/2, adsk.core.Vector3D.create(1, 0, 0), adsk.core.Point3D.create(0, 0, 0))
    other.translation = adsk.core.Vector3D.create(0, 8, 3)
    root.occurrences.addExistingComponent(source.component, other)
    native_seed = next(e for e in source.component.bRepBodies.item(0).edges
                       if adsk.core.Circle3D.cast(e.geometry) and e.geometry.center.z > .09)
    seed = native_seed.createForAssemblyContext(source)
    builtins._selectra_plane_test = dict(entry=entry, original=original, document=document, design=design,
                                        seed=seed, results=[])
    app.userInterface.activeSelections.clear()
    app.userInterface.activeSelections.add(seed)
    app.activeViewport.fit()
    return {'prepared': True, 'holes': 4, 'occurrences': root.allOccurrences.count}


def open_command():
    state = builtins._selectra_plane_test
    app = adsk.core.Application.get()
    assert app.activeDocument == state['document'] and app.userInterface.activeCommand == 'SelectCommand'
    app.userInterface.activeSelections.clear()
    app.userInterface.activeSelections.add(state['seed'])
    return app.userInterface.commandDefinitions.itemById(state['entry'].COMMAND_ID).execute()


def inspect():
    state = builtins._selectra_plane_test
    session = state['entry']._sessions[-1]
    q = session.controller
    assert not session.preview_error, session.preview_error
    assert q.ranking.plane_groups[:3] == ('coplanar', 'parallel', 'other'), q.ranking
    expected = (4, 8, 20) if session.scope_mode == 'all' else (4, 8, 10)
    assert q.level in (1, 2, 3) and len(q.result) == expected[q.level-1], (q.level, q.result)
    assert session.renderer.keys == q.result
    for renderer in session.renderer.renderers:
        for key in renderer.keys:
            graphic = renderer.outlines[key]
            assert graphic.isVisible
            assert graphic.weight == (3.0 if key in renderer.focus_keys else 1.5)
    for key in q.result:
        descriptor = session.snapshot.by_key[key]
        assert descriptor.geometry == 'circle' and math.isclose(descriptor.radius, .2)
    state['expected_ok'] = tuple(session.refs[k] for k in q.result)
    result = {'scope': session.scope_mode, 'level': q.level, 'count': len(q.result),
              'plane_groups': q.ranking.plane_groups[:3]}
    state['results'].append(result)
    return result


def finish():
    state = builtins._selectra_plane_test
    app = adsk.core.Application.get()
    assert app.activeDocument == state['document'] and app.userInterface.activeCommand == 'SelectCommand'
    assert state['design'].rootComponent.customGraphicsGroups.count == 0
    state['original'].activate()
    state['document'].close(False)
    return {'restored': app.activeDocument == state['original'], 'graphics_clean': True}
