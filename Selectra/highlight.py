# SPDX-License-Identifier: GPL-3.0-only
"""Transient, nonselectable exact BRep highlights; no CAD bodies or attributes."""
from time import monotonic

import adsk.core
import adsk.fusion


class HighlightRenderer:
    MAX_ENTITIES = 2000
    BUILD_SECONDS = 2.0
    OPACITY = .35

    def __init__(self, body, revision):
        self.body, self.revision = body, revision
        self.group = None
        self.graphics = {}
        self.geometry = {}
        self.outlines = {}
        self.focus_keys = ()
        self.keys = ()
        self.frames = 0
        self.last_seconds = 0.0

    def clear(self):
        if self.group and self.group.isValid:
            self.group.deleteMe()
        self.group = None
        self.graphics.clear()
        self.geometry.clear()
        self.outlines.clear()
        self.keys = ()
        self.focus_keys = ()

    def show(self, references, keys, focus_keys=()):
        keys = tuple(sorted(keys))
        started = monotonic()
        focus_keys = tuple(sorted(set(focus_keys) & set(keys)))
        line_keys = tuple(sorted(set(focus_keys) | {key for key in keys if adsk.fusion.BRepEdge.cast(references[key])}))
        if not self.body.isValid or self.body.revisionId != self.revision:
            self.clear()
            raise ValueError('Body geometry changed. Restart Select Similar.')
        if len(keys) > self.MAX_ENTITIES:
            self.clear()
            raise ValueError('Highlight exceeds 2,000 entities. Refine the selection first.')
        if (keys == self.keys and focus_keys == self.focus_keys and self.group and self.group.isValid
                and all(graphic.isValid for graphic in self.graphics.values())
                and all(graphic.isValid for graphic in self.outlines.values())):
            self.group.isVisible = True
            for key, graphic in self.graphics.items():
                graphic.isVisible = key in keys
            for key, graphic in self.outlines.items():
                graphic.isVisible = key in line_keys
                graphic.weight = 3.0 if key in focus_keys else 1.5
            self.last_seconds = monotonic() - started
            return
        try:
            # Reuse a valid overlay. Hiding cached members avoids destructive
            # per-object deletes and the blank frame of clear/rebuild updates.
            if (not self.group or not self.group.isValid
                    or any(not graphic.isValid for graphic in self.graphics.values())
                    or any(not graphic.isValid for graphic in self.outlines.values())
                    or len(set(self.graphics) | set(keys)) > self.MAX_ENTITIES):
                self.clear()
                component = (adsk.fusion.Design.cast(adsk.core.Application.get().activeProduct).rootComponent
                             if self.body.assemblyContext else self.body.parentComponent)
                self.group = component.customGraphicsGroups.add()
                self.group.isSelectable = False
            desired = set(keys)
            for key, graphic in self.graphics.items():
                graphic.isVisible = key in desired
            manager = adsk.fusion.TemporaryBRepManager.get()
            magenta = adsk.core.Color.create(255, 0, 255, 255)
            color = adsk.fusion.CustomGraphicsShowThroughColorEffect.create(magenta, self.OPACITY)
            for key in keys:
                if monotonic() - started > self.BUILD_SECONDS:
                    raise ValueError('Highlight exceeded the time budget. Refine the selection.')
                if key in self.graphics:
                    self.graphics[key].isVisible = True
                    continue
                entity = references[key]
                if not entity.isValid or entity.body != self.body:
                    raise ValueError('Highlight entity is outside the original body.')
                context = entity.assemblyContext
                temporary = manager.copy(entity.nativeObject if context else entity)
                if not temporary:
                    raise RuntimeError('Could not copy BRep geometry for highlighting.')
                if context and not manager.transform(temporary, context.transform2):
                    raise RuntimeError('Could not transform the occurrence highlight.')
                graphic = self.group.addBRepBody(temporary)
                if not graphic:
                    raise RuntimeError('Could not display the highlight.')
                graphic.isSelectable = False
                graphic.color = color
                graphic.depthPriority = 10
                if not graphic.setOpacity(self.OPACITY, True):
                    raise RuntimeError('Could not set the highlight transparency.')
                self.graphics[key] = graphic
                self.geometry[key] = temporary
            for key, graphic in self.outlines.items():
                graphic.isVisible = key in line_keys
                graphic.weight = 3.0 if key in focus_keys else 1.5
            for key in line_keys:
                if key in self.outlines:
                    self.outlines[key].isVisible = True
                    continue
                entity = references[key]
                edges = (entity,) if adsk.fusion.BRepEdge.cast(entity) else tuple(
                    entity.edges.item(i) for i in range(entity.edges.count))
                coordinates, lengths = [], []
                for edge in edges:
                    if monotonic() - started > self.BUILD_SECONDS:
                        raise ValueError('Outline exceeded the time budget. Refine the selection.')
                    ok, low, high = edge.evaluator.getParameterExtents()
                    if not ok:
                        raise ValueError('Could not read the highlighted boundary.')
                    ok, points = edge.evaluator.getStrokes(low, high, 1e-4)
                    if not ok or len(points) < 2:
                        raise ValueError('Could not draw the highlighted boundary.')
                    if len(coordinates)//3 + len(points) > 100000:
                        raise ValueError('Outline exceeds the graphics point budget.')
                    lengths.append(len(points))
                    coordinates.extend(value for point in points for value in (point.x, point.y, point.z))
                graphic = self.group.addLines(adsk.fusion.CustomGraphicsCoordinates.create(coordinates), [], True, lengths)
                if not graphic:
                    raise RuntimeError('Could not display the boundary outline.')
                graphic.color = adsk.fusion.CustomGraphicsShowThroughColorEffect.create(magenta, 1.0)
                graphic.weight = 3.0 if key in focus_keys else 1.5
                graphic.depthPriority = 20
                graphic.isSelectable = False
                self.outlines[key] = graphic
            self.keys = keys
            self.focus_keys = focus_keys
            self.frames += 1
            adsk.core.Application.get().activeViewport.refresh()
            self.last_seconds = monotonic() - started
        except Exception:
            self.clear()
            raise


class ScopeHighlightRenderer:
    """One atomic preview composed from separate body/occurrence renderers."""
    def __init__(self, guards):
        self.renderers = tuple(HighlightRenderer(body, body.revisionId) for body, _ in guards)
        self.keys, self.focus_keys = (), ()
        self.last_seconds = 0.0

    def clear(self):
        for renderer in self.renderers:
            renderer.clear()
        self.keys, self.focus_keys = (), ()

    def show(self, references, keys, focus_keys=()):
        started = monotonic()
        try:
            if len(keys) > HighlightRenderer.MAX_ENTITIES:
                raise ValueError('Highlight exceeds 2,000 entities. Narrow the search scope.')
            for renderer in self.renderers:
                own = tuple(k for k in keys if references[k].body == renderer.body)
                if own or renderer.keys:
                    renderer.show(references, own, focus_keys)
                if monotonic()-started > HighlightRenderer.BUILD_SECONDS:
                    raise ValueError('Scope highlight exceeded the time budget. Narrow the selection.')
            self.keys, self.focus_keys = tuple(sorted(keys)), tuple(sorted(set(keys) & set(focus_keys)))
            self.last_seconds = monotonic()-started
        except Exception:
            self.clear()
            raise
