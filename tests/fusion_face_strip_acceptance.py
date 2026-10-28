# SPDX-License-Identifier: GPL-3.0-only
"""Native acceptance on a disposable copy of the currently selected face ring."""
import builtins
import adsk.core
import adsk.fusion


def prepare(entry, expected_faces=None):
    app = adsk.core.Application.get()
    ui = app.userInterface
    assert ui.activeCommand == 'SelectCommand'
    original = app.activeDocument
    selected = tuple(ui.activeSelections.item(i).entity for i in range(ui.activeSelections.count))
    source = tuple(expected_faces) if expected_faces is not None else selected
    assert len(source) >= 3 and all(adsk.fusion.BRepFace.cast(f) and f.body == source[0].body for f in source)
    copied = adsk.fusion.TemporaryBRepManager.get().copy(source[0].body)
    points = tuple((f.centroid.asArray(), f.area) for f in source)
    doc = app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    design = adsk.fusion.Design.cast(app.activeProduct)
    design.designType = adsk.fusion.DesignTypes.DirectDesignType
    body = design.rootComponent.bRepBodies.add(copied)
    def distance(face, point, area):
        p = face.centroid.asArray()
        return sum((a-b)**2 for a,b in zip(p,point)) + abs(face.area-area)**2
    expected = tuple(min(body.faces, key=lambda f: distance(f, p, a)) for p,a in points)
    assert len(set(f.tempId for f in expected)) == len(expected)
    assert all(distance(f, p, a) < 1e-10 for f,(p,a) in zip(expected,points))
    builtins._selectra_face_strip_test = dict(entry=entry, original=original, selection=selected,
        document=doc, design=design, body=body, expected=expected)
    ui.activeSelections.clear()
    assert ui.activeSelections.add(expected[0])
    app.activeViewport.fit()
    return {'faces': len(expected), 'body_faces': body.faces.count}


def open_command():
    state = builtins._selectra_face_strip_test
    ui = adsk.core.Application.get().userInterface
    assert adsk.core.Application.get().activeDocument == state['document']
    return ui.commandDefinitions.itemById(state['entry'].CHAIN_COMMAND_ID).execute()


def inspect(first=True):
    state = builtins._selectra_face_strip_test
    session = state['entry']._sessions[-1]
    assert not session.preview_error, session.preview_error
    actual = tuple(session.refs[k] for k in session.chosen_keys())
    if first:
        assert {f.tempId for f in actual} == {f.tempId for f in state['expected']}
    else:
        assert {f.tempId for f in actual} != {f.tempId for f in state['expected']}
        assert state['expected'][0] in actual
    assert session.renderer.keys == session.chosen_keys()
    state['last'] = actual
    return {'count': len(actual), 'level': session.controller.level,
            'variants': len(session.controller.ranking.tiers), 'renderer_matches': True}


def check_ok():
    state = builtins._selectra_face_strip_test
    ui = adsk.core.Application.get().userInterface
    assert ui.activeCommand == 'SelectCommand'
    selected = tuple(ui.activeSelections.item(i).entity for i in range(ui.activeSelections.count))
    assert {f.tempId for f in selected} == {f.tempId for f in state['last']}
    assert state['design'].rootComponent.customGraphicsGroups.count == 0
    return {'selected': len(selected), 'graphics_clean': True}


def finish():
    state = builtins._selectra_face_strip_test
    app = adsk.core.Application.get()
    assert app.userInterface.activeCommand == 'SelectCommand'
    state['original'].activate()
    state['document'].close(False)
    app.userInterface.activeSelections.clear()
    for entity in state['selection']:
        if entity.isValid:
            assert app.userInterface.activeSelections.add(entity)
    return {'restored_document': app.activeDocument == state['original'],
            'restored_selection': app.userInterface.activeSelections.count}
