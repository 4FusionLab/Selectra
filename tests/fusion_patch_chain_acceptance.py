# SPDX-License-Identifier: GPL-3.0-only
"""Disposable split capsule: one contour spans three tangent wall faces."""
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
    def box(x,y,z,width,height,depth):
        return manager.createBox(adsk.core.OrientedBoundingBox3D.create(adsk.core.Point3D.create(x,y,z),
            adsk.core.Vector3D.create(1,0,0),adsk.core.Vector3D.create(0,1,0),width,height,depth))
    plate=box(0,0,0,4,3,.4)
    tool=box(0,0,0,1.5,1,2)
    for x in (-.75,.75):
        cylinder=manager.createCylinderOrCone(adsk.core.Point3D.create(x,0,-1),.5,
                                             adsk.core.Point3D.create(x,0,1),.5)
        assert manager.booleanOperation(tool,cylinder,adsk.fusion.BooleanTypes.UnionBooleanType)
    assert manager.booleanOperation(plate,tool,adsk.fusion.BooleanTypes.DifferenceBooleanType)
    left,right=manager.copy(plate),manager.copy(plate)
    assert manager.booleanOperation(left,box(-1,0,0,2,3,1),adsk.fusion.BooleanTypes.IntersectionBooleanType)
    assert manager.booleanOperation(right,box(1,0,0,2,3,1),adsk.fusion.BooleanTypes.IntersectionBooleanType)
    pose=adsk.core.Matrix3D.create()
    pose.setToRotation(.41,adsk.core.Vector3D.create(0,1,0),adsk.core.Point3D.create(0,0,0))
    pose.translation=adsk.core.Vector3D.create(4,7,-3)
    occurrence=design.rootComponent.occurrences.addNewComponent(pose)
    bodies=tuple(occurrence.component.bRepBodies.add(shape) for shape in (left,right))
    expected=[]
    for edge in bodies[0].edges:
        ok,lo,hi=edge.evaluator.getParameterExtents();assert ok
        ok,p=edge.evaluator.getPointAtParameter((lo+hi)/2);assert ok
        arc=adsk.core.Arc3D.cast(edge.geometry)
        cap=abs(abs(p.z)-.2)<1e-7
        straight_rim=cap and -.7500001<=p.x<=1e-7 and abs(abs(p.y)-.5)<1e-7
        curved_rim=cap and arc and abs(arc.center.x+.75)<1e-7
        split_end=abs(p.x)<1e-7 and abs(abs(p.y)-.5)<1e-7 and abs(p.z)<1e-7
        if straight_rim or curved_rim or split_end:
            expected.append(edge.createForAssemblyContext(occurrence))
    assert len(expected)==8,len(expected)
    seed=next(e for e in expected if adsk.core.Arc3D.cast(e.nativeObject.geometry)
              and e.nativeObject.geometry.center.z>0)
    builtins._selectra_patch_test=dict(entry=entry,document=doc,original=original,selection=selection,
        design=design,expected=tuple(expected),seed=seed)
    app.activeViewport.fit()
    app.userInterface.activeSelections.clear();app.userInterface.activeSelections.add(seed)
    return app.userInterface.commandDefinitions.itemById(entry.CHAIN_COMMAND_ID).execute()


def locate():
    state=builtins._selectra_patch_test
    session=state['entry']._sessions[-1]
    assert not session.preview_error,session.preview_error
    expected=tuple(sorted(k for k,e in session.refs.items() if e in state['expected']))
    assert len(expected)==8 and expected in session.controller.ranking.tiers
    for variant in session.controller.ranking.tiers:
        assert set(session.controller.feedback.examples)<=set(variant)
    state['index']=session.controller.ranking.tiers.index(expected)+1
    return {'index':state['index'],'count':len(session.controller.ranking.tiers)}


def inspect():
    state=builtins._selectra_patch_test
    session=state['entry']._sessions[-1];q=session.controller
    refs=tuple(session.refs[k] for k in q.result)
    assert q.level==state['index'] and len(refs)==8 and all(e in refs for e in state['expected'])
    assert session.renderer.keys==q.result and q.result==q.ranking.tiers[q.level-1]
    for renderer in session.renderer.renderers:
        for key,graphic in renderer.graphics.items():
            assert graphic.isVisible==(key in q.result)
    return {'compound_patch_found':True,'faces':3,'edges':8,'no_accumulation':True}


def finish():
    state=builtins._selectra_patch_test
    app=adsk.core.Application.get()
    assert app.activeDocument==state['document'] and app.userInterface.activeCommand=='SelectCommand'
    selected=tuple(s.entity for s in app.userInterface.activeSelections)
    assert len(selected)==8 and all(e in selected for e in state['expected'])
    assert state['design'].rootComponent.customGraphicsGroups.count==0
    state['original'].activate();state['document'].close(False)
    app.userInterface.activeSelections.clear()
    for e in state['selection']:
        if e.isValid:app.userInterface.activeSelections.add(e)
    return {'exact_ok':8,'graphics_clean':True,'restored':True}
