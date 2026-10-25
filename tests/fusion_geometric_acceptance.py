# SPDX-License-Identifier: GPL-3.0-only
"""Authorized sequential CAD fixture. Never discovered by Python unittest.

Call prepare(entry), open_command(), inspect_preview() in SEPARATE UI turns.
The entry must belong to the registered running add-in. Only this disposable
document receives geometry. User documents are fingerprinted, never saved.
"""
import builtins
from time import perf_counter, monotonic

import adsk.core
import adsk.fusion


def fingerprint(design):
    return {'timeline': design.timeline.count,
            'bodies': [(b.faces.count, b.edges.count, b.volume, b.area, b.revisionId)
                       for b in design.rootComponent.bRepBodies]}


def prepare(entry):
    app = adsk.core.Application.get()
    if app.userInterface.activeCommand != 'SelectCommand':
        raise RuntimeError('Finish the current command before creating the fixture.')
    original = app.activeDocument
    original_design = adsk.fusion.Design.cast(app.activeProduct)
    original_state = fingerprint(original_design) if original_design else None
    document = app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    design = adsk.fusion.Design.cast(app.activeProduct)
    root, manager = design.rootComponent, adsk.fusion.TemporaryBRepManager.get()

    def box(x, y, z):
        return manager.createBox(adsk.core.OrientedBoundingBox3D.create(
            adsk.core.Point3D.create(0, 0, 0), adsk.core.Vector3D.create(1, 0, 0),
            adsk.core.Vector3D.create(0, 1, 0), x, y, z))

    shell = box(10, 6, 2)
    assert manager.booleanOperation(shell, box(9.6, 5.6, 1.6),
                                    adsk.fusion.BooleanTypes.DifferenceBooleanType)
    feature = root.features.baseFeatures.add()
    feature.startEdit()
    body = root.bRepBodies.add(shell, feature)
    body.name = 'Selectra closed thin shell'
    second = root.bRepBodies.add(manager.copy(shell), feature)
    second.name = 'Out-of-scope identical body'
    second.isVisible = False
    feature.finishEdit()
    # BaseFeature edit bodies are source objects; use the computed result
    # bodies after finishEdit, exactly as a user's viewport selection does.
    body = next(b for b in root.bRepBodies if b.name == 'Selectra closed thin shell')
    second = next(b for b in root.bRepBodies if b.name == 'Out-of-scope identical body')
    second.isVisible = False
    # Select geometrically, never reuse tempIds across bodies or revisions.
    faces = tuple(body.faces)
    seed = next(f for f in faces if abs(f.area-60) < 1e-6 and f.pointOnFace.z > .9)
    analog = next(f for f in faces if abs(f.area-60) < 1e-6 and f.pointOnFace.z < -.9)
    inner = next(f for f in faces if abs(f.area-53.76) < 1e-6 and f.pointOnFace.z > .7)
    far_inner = next(f for f in faces if abs(f.area-53.76) < 1e-6 and f.pointOnFace.z < -.7)
    builtins._selectra_geometry_acceptance = dict(
        entry=entry, original=original, original_design=original_design, original_state=original_state,
        document=document, design=design, body=body, second=second, seed=seed,
        expected=(str(analog.tempId), str(inner.tempId), str(far_inner.tempId)),
        fingerprint=fingerprint(design), results=[])
    app.activeViewport.fit()
    return {'prepared': True, 'faces': body.faces.count, 'edges': body.edges.count,
            'documents_untouched': original_state == fingerprint(original_design) if original_design else True}


def open_command(examples=None):
    state = builtins._selectra_geometry_acceptance
    app = adsk.core.Application.get()
    assert app.activeDocument == state['document']
    ui = app.userInterface
    assert ui.activeCommand == 'SelectCommand'
    ui.activeSelections.clear()
    for example in examples or (state['seed'],):
        ui.activeSelections.add(example)
    state['opened'] = perf_counter()
    return ui.commandDefinitions.itemById(state['entry'].COMMAND_ID).execute()


def inspect_preview():
    state = builtins._selectra_geometry_acceptance
    entry = state['entry']
    session = entry._sessions[-1]
    assert session.document == state['document']
    assert not session.preview_error, session.preview_error
    assert all(e.body == state['body'] for e in session.refs.values())
    expected = state['expected']
    seed_key = str(state['seed'].tempId)
    assert session.controller.ranking.tiers[:3] == tuple((key,) for key in expected), session.controller.ranking
    assert session.controller.result == tuple(sorted((seed_key, expected[0])))
    assert session.renderer.keys == session.controller.result
    assert session.renderer.focus_keys == (expected[0],)
    opacity = [graphic.getOpacity() for graphic in session.renderer.graphics.values()]
    report = dict(first_set=True, wall_order=True, scope=True, timings=session.timings,
                  highlight_seconds=session.renderer.last_seconds, opacity=opacity,
                  outlines=len(session.renderer.outlines), groups=len(session.controller.ranking.tiers))
    state['results'].append(report)
    return report


def check_narrow_void():
    """A cavity between depth samples must be caught by the native ray test."""
    state = builtins._selectra_geometry_acceptance
    app = adsk.core.Application.get()
    assert app.activeDocument == state['document']
    assert app.userInterface.activeCommand == 'SelectCommand'
    root, manager = state['design'].rootComponent, adsk.fusion.TemporaryBRepManager.get()

    def box(z, height):
        return manager.createBox(adsk.core.OrientedBoundingBox3D.create(
            adsk.core.Point3D.create(20, 0, z), adsk.core.Vector3D.create(1, 0, 0),
            adsk.core.Vector3D.create(0, 1, 0), 4 if height == .2 else 3,
            4 if height == .2 else 3, height))

    slab = box(0, .2)
    assert manager.booleanOperation(slab, box(-.015, .01), adsk.fusion.BooleanTypes.DifferenceBooleanType)
    feature = root.features.baseFeatures.add()
    feature.startEdit()
    body = root.bRepBodies.add(slab, feature)
    body.name = 'Narrow cavity between sample depths'
    feature.finishEdit()
    body = next(b for b in root.bRepBodies if b.name == 'Narrow cavity between sample depths')
    adapter = state['entry'].adapter
    top = next(f for f in body.faces if abs(f.area-16) < 1e-6 and f.pointOnFace.z > 0)
    bottom = next(f for f in body.faces if abs(f.area-16) < 1e-6 and f.pointOnFace.z < 0)
    descriptors = tuple(adapter.describe(f) for f in (top, bottom))
    patches = tuple(adapter.PlanarPatch(d.key, d.normal, d.position, d.contours) for d in descriptors)
    probe = adapter.wall_probe_points(*patches)
    assert probe.complete and probe.points
    material = tuple(body.pointContainment(adsk.core.Point3D.create(*p)) ==
                     adsk.fusion.PointContainment.PointInsidePointContainment for p in probe.points)
    assert adapter.confirm_wall(probe, material) is not None
    assert not adapter._unbroken_material_traces(body, probe, monotonic())
    snap, _, _, _, _ = adapter.read_snapshot((top,))
    assert tuple(sorted((str(top.tempId), str(bottom.tempId)))) not in snap.wall_pairs
    state['fingerprint'] = fingerprint(state['design'])
    return {'sample_only_misses_cavity': True, 'ray_rejects_cavity': True,
            'no_false_wall_pair': True}


def finish():
    state = builtins._selectra_geometry_acceptance
    app = adsk.core.Application.get()
    assert app.activeDocument == state['document']
    assert app.userInterface.activeCommand == 'SelectCommand'
    assert fingerprint(state['design']) == state['fingerprint']
    assert state['design'].rootComponent.customGraphicsGroups.count == 0
    if state['original_design']:
        assert fingerprint(state['original_design']) == state['original_state']
    state['original'].activate()
    state['document'].close(False)
    return {'geometry_unchanged': True, 'graphics_clean': True, 'original_restored': app.activeDocument == state['original']}
