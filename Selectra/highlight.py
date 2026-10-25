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
        self.keys = ()
        self.frames = 0

    def clear(self):
        if self.group and self.group.isValid:
            self.group.deleteMe()
        self.group = None
        self.graphics.clear()
        self.geometry.clear()
        self.keys = ()

    def show(self, references, keys):
        keys = tuple(sorted(keys))
        if not self.body.isValid or self.body.revisionId != self.revision:
            self.clear()
            raise ValueError('Body geometry changed. Restart Select Similar.')
        if len(keys) > self.MAX_ENTITIES:
            self.clear()
            raise ValueError('Highlight exceeds 2,000 entities. Refine the selection first.')
        if (keys == self.keys and self.group and self.group.isValid
                and all(graphic.isValid for graphic in self.graphics.values())):
            self.group.isVisible = True
            for key, graphic in self.graphics.items():
                graphic.isVisible = key in keys
            return
        started = monotonic()
        try:
            # Reuse a valid overlay. Hiding cached members avoids destructive
            # per-object deletes and the blank frame of clear/rebuild updates.
            if (not self.group or not self.group.isValid
                    or any(not graphic.isValid for graphic in self.graphics.values())
                    or len(set(self.graphics) | set(keys)) > self.MAX_ENTITIES):
                self.clear()
                self.group = self.body.parentComponent.customGraphicsGroups.add()
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
                temporary = manager.copy(entity)
                if not temporary:
                    raise RuntimeError('Could not copy BRep geometry for highlighting.')
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
            self.keys = keys
            self.frames += 1
            adsk.core.Application.get().activeViewport.refresh()
        except Exception:
            self.clear()
            raise
