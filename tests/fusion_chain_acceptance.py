# SPDX-License-Identifier: GPL-3.0-only
"""Disposable pocket for native Select Chain faces, edges and range keys."""
import builtins
import adsk.core
import adsk.fusion


def prepare(entry):
    app=adsk.core.Application.get()
    assert app.userInterface.activeCommand=='SelectCommand'
    original=app.activeDocument
    selection=tuple(s.entity for s in app.userInterface.activeSelections)
    doc=app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    design=adsk.fusion.Design.cast(app.activeProduct)
    design.designType=adsk.fusion.DesignTypes.DirectDesignType
    manager=adsk.fusion.TemporaryBRepManager.get()
    def box(center,x,y,z):
        return manager.createBox(adsk.core.OrientedBoundingBox3D.create(adsk.core.Point3D.create(*center),
            adsk.core.Vector3D.create(1,0,0),adsk.core.Vector3D.create(0,1,0),x,y,z))
    shape=box((0,0,0),6,5,3)
    assert manager.booleanOperation(shape,box((0,0,1.5),4,3,4),adsk.fusion.BooleanTypes.DifferenceBooleanType)
    root=design.rootComponent
    body=root.bRepBodies.add(shape)
    copy=manager.copy(shape)
    matrix=adsk.core.Matrix3D.create()
    matrix.translation=adsk.core.Vector3D.create(10,0,0)
    assert manager.transform(copy,matrix)
    root.bRepBodies.add(copy)
    walls=tuple(f for f in body.faces if abs(abs(f.pointOnFace.x)-2)<1e-7 or abs(abs(f.pointOnFace.y)-1.5)<1e-7)
    assert len(walls)==4
    seed=walls[0]
    rim=next(f for f in body.faces if isinstance(f.geometry,adsk.core.Plane) and abs(f.pointOnFace.z-1.5)<1e-7)
    loop=next(loop for loop in rim.loops if not loop.isOuter)
    edges=tuple(loop.edges)
    builtins._selectra_chain_test=dict(entry=entry,original=original,selection=selection,document=doc,
        design=design,body=body,walls=walls,faces_seed=seed,edges=edges,edge_seed=edges[0])
    app.activeViewport.fit()
    return {'walls':len(walls),'edges':len(edges)}


def open_command(kind):
    state=builtins._selectra_chain_test
    app=adsk.core.Application.get()
    assert app.activeDocument==state['document'] and app.userInterface.activeCommand=='SelectCommand'
    app.userInterface.activeSelections.clear()
    app.userInterface.activeSelections.add(state['faces_seed' if kind=='face' else 'edge_seed'])
    state['kind']=kind
    return app.userInterface.commandDefinitions.itemById(state['entry'].CHAIN_COMMAND_ID).execute()


def inspect(first=True):
    state=builtins._selectra_chain_test
    session=state['entry']._sessions[-1]
    assert session.chain and not session.preview_error,session.preview_error
    refs=tuple(session.refs[k] for k in session.chosen_keys())
    assert all(entity.body==state['body'] for entity in refs)
    if first:
        expected=state['walls' if state['kind']=='face' else 'edges']
        assert len(refs)==len(expected) and all(entity in refs for entity in expected)
    else:
        assert session.controller.level>1
        first=state['walls' if state['kind']=='face' else 'edges']
        assert set(refs)!=set(first)
        assert all(session.refs[k] in refs for k in session.controller.feedback.examples)
        assert tuple(sorted(session.chosen_keys()))==session.controller.ranking.tiers[session.controller.level-1]
    assert session.renderer.keys==session.chosen_keys()
    state['expected_ok']=refs
    return {'kind':state['kind'],'count':len(refs),'level':session.controller.level}


def check_ok():
    state=builtins._selectra_chain_test
    app=adsk.core.Application.get()
    assert app.userInterface.activeCommand=='SelectCommand'
    actual=tuple(s.entity for s in app.userInterface.activeSelections)
    assert len(actual)==len(state['expected_ok']) and all(f in actual for f in state['expected_ok'])
    assert state['design'].rootComponent.customGraphicsGroups.count==0
    return {'exact_ok':len(actual),'graphics_clean':True}


def finish():
    state=builtins._selectra_chain_test
    app=adsk.core.Application.get()
    assert app.userInterface.activeCommand=='SelectCommand'
    assert state['design'].rootComponent.customGraphicsGroups.count==0
    state['original'].activate()
    state['document'].close(False)
    app.userInterface.activeSelections.clear()
    for entity in state['selection']:
        if entity.isValid: app.userInterface.activeSelections.add(entity)
    return {'restored':app.activeDocument==state['original']}
