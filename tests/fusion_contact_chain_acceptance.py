# SPDX-License-Identifier: GPL-3.0-only
"""Exact split-contact acceptance in a disposable rotated occurrence."""
import builtins
import math
import importlib
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
    def box(x=0,y=0,width=4,height=3):
        return manager.createBox(adsk.core.OrientedBoundingBox3D.create(adsk.core.Point3D.create(x,y,0),
            adsk.core.Vector3D.create(1,0,0),adsk.core.Vector3D.create(0,1,0),width,height,.4))
    shape=box()
    hole=manager.createCylinderOrCone(adsk.core.Point3D.create(0,0,-1),.5,adsk.core.Point3D.create(0,0,1),.5)
    assert manager.booleanOperation(shape,hole,adsk.fusion.BooleanTypes.DifferenceBooleanType)
    left,right=manager.copy(shape),manager.copy(shape)
    assert manager.booleanOperation(left,box(-1,width=2),adsk.fusion.BooleanTypes.IntersectionBooleanType)
    assert manager.booleanOperation(right,box(1,width=2),adsk.fusion.BooleanTypes.IntersectionBooleanType)
    contact=importlib.import_module(entry.adapter.__package__+'.contact_chains')
    assert contact.exact_contact(left,right,manager,contact.Budget())
    for gap in (1e-5,1e-7,1e-8):
        moved=manager.copy(right);t=adsk.core.Matrix3D.create();t.translation=adsk.core.Vector3D.create(gap,0,0)
        assert manager.transform(moved,t)
        assert not contact.exact_contact(left,moved,manager,contact.Budget()),gap
    assert not contact.exact_contact(box(-1,width=2),box(1,y=1e-8,width=2),manager,contact.Budget())
    assert not contact.exact_contact(box(-1,width=2),box(1,y=2.9,width=2),manager,contact.Budget())
    assert not contact.exact_contact(box(-1,width=2),box(1,y=3,width=2),manager,contact.Budget())
    assert not contact.exact_contact(box(-1,width=2),box(.9,width=2),manager,contact.Budget())
    pose=adsk.core.Matrix3D.create()
    pose.setToRotation(.37,adsk.core.Vector3D.create(0,1,0),adsk.core.Point3D.create(0,0,0))
    pose.translation=adsk.core.Vector3D.create(4,7,-3)
    occurrence=design.rootComponent.occurrences.addNewComponent(pose)
    native=tuple(occurrence.component.bRepBodies.add(copy) for copy in (left,right))
    bodies=tuple(body.createForAssemblyContext(occurrence) for body in native)
    edges=[];faces=[];local_edges=[]
    for body in native:
        edge=next(e for e in body.edges if adsk.core.Arc3D.cast(e.geometry) and abs(e.geometry.center.z-.2)<1e-7)
        edges.append(edge.createForAssemblyContext(occurrence))
        cap=next(f for f in body.faces if adsk.core.Plane.cast(f.geometry) and abs(f.pointOnFace.z-.2)<1e-7)
        local_edges.append(tuple(e.createForAssemblyContext(occurrence) for e in cap.loops.item(0).edges))
        face=next(f for f in body.faces if adsk.core.Cylinder.cast(f.geometry))
        faces.append(face.createForAssemblyContext(occurrence))
    builtins._selectra_contact_test=dict(entry=entry,original=original,selection=selection,document=doc,
        design=design,bodies=bodies,edges=tuple(edges),faces=tuple(faces),local_edges=tuple(local_edges))
    app.activeViewport.fit()
    return {'exact_contact':True,'gaps_rejected':3,'partial_edge_overlap_rejected':True,'rotated':True}


def open_command(kind, single=False):
    state=builtins._selectra_contact_test
    app=adsk.core.Application.get()
    assert app.activeDocument==state['document'] and app.userInterface.activeCommand=='SelectCommand'
    app.userInterface.activeSelections.clear()
    examples = state['edges'][:1] if kind=='edge' and single else state['edges'] if kind=='edge' else state['faces'][:1]
    for entity in examples:
        app.userInterface.activeSelections.add(entity)
    state['kind']=kind
    return app.userInterface.commandDefinitions.itemById(state['entry'].CHAIN_COMMAND_ID).execute()


def inspect(enabled=True):
    state=builtins._selectra_contact_test
    session=state['entry']._sessions[-1]
    assert session.chain and session.across_contact==enabled and session.contact_input.value==enabled
    assert not session.preview_error,session.preview_error
    seeds=set(session.controller.feedback.examples)
    eligible=tuple(c for c in session.controller.chains if seeds<=set(c.keys))
    allowed={k for c in eligible for k in c.keys} or seeds
    ranked=seeds.union(*(set(t) for t in session.controller.ranking.tiers))
    assert ranked==allowed, (ranked,allowed)
    result=tuple(session.refs[k] for k in session.chosen_keys())
    expected=state['edges' if state['kind']=='edge' else 'faces']
    if enabled:
        assert len(result)==2 and all(entity in result for entity in expected),(len(result),session.chosen_keys())
        assert session.controller.can_apply
        assert session.controller.ranking.plane_groups[0]=='coplanar'
    elif state['kind']=='edge':
        assert not session.controller.can_apply
        assert all(entity in result for entity in expected)
    else:
        assert all(entity.body==state['faces'][0].body for entity in result)
    assert session.renderer.keys==(session.chosen_keys() if session.controller.can_apply else ())
    state['expected_ok']=result
    return {'kind':state['kind'],'enabled':enabled,'count':len(result),'can_apply':session.controller.can_apply}


def finish():
    state=builtins._selectra_contact_test
    app=adsk.core.Application.get()
    assert app.activeDocument==state['document'] and app.userInterface.activeCommand=='SelectCommand'
    actual=tuple(s.entity for s in app.userInterface.activeSelections)
    assert len(actual)==len(state['expected_ok']) and all(f in actual for f in state['expected_ok'])
    assert state['design'].rootComponent.customGraphicsGroups.count==0
    state['original'].activate();state['document'].close(False)
    app.userInterface.activeSelections.clear()
    for entity in state['selection']:
        if entity.isValid: app.userInterface.activeSelections.add(entity)
    return {'exact_ok':len(actual),'graphics_clean':True,'restored':True}


def inspect_local_variant():
    state=builtins._selectra_contact_test
    session=state['entry']._sessions[-1]
    assert state['kind']=='edge' and len(session.controller.feedback.examples)==1
    expected=state['local_edges'][0]
    actual=tuple(session.refs[k] for k in session.chosen_keys())
    assert len(actual)==len(expected) and all(e in actual for e in expected)
    assert all(e.body==state['bodies'][0] for e in actual)
    assert session.controller.result==session.controller.ranking.tiers[session.controller.level-1]
    for renderer in session.renderer.renderers:
        for key,graphic in renderer.graphics.items():
            assert graphic.isVisible==(key in session.chosen_keys())
    state['expected_ok']=actual
    return {'local_variant_found':True,'count':len(actual),'level':session.controller.level,'no_accumulation':True}
