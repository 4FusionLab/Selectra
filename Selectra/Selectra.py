# SPDX-License-Identifier: GPL-3.0-only
"""Native context-menu spike. Requires real Fusion acceptance before release."""
import html
import traceback

import adsk.core
import adsk.fusion

from . import fusion_adapter as adapter
from .matching import Tolerance, infer

COMMAND_ID = 'DiegoV_Selectra_SelectSimilar'
EVENT_ID = 'DiegoV_Selectra_ApplySelection'
_bindings = []
_sessions = []
_pending = None
_event_registered = False
_running = False


def _bind(event, handler, bindings):
    event.add(handler)
    bindings.append((event, handler))


def _log():
    adsk.core.Application.get().log('Selectra: ' + traceback.format_exc())


def _active_entities(ui):
    selections = ui.activeSelections
    return tuple(selections.item(i).entity for i in range(selections.count))


class Session:
    def __init__(self, command):
        self.app = adsk.core.Application.get()
        self.document = self.app.activeDocument
        self.original = _active_entities(self.app.userInterface)
        self.command = command
        self.bindings = []
        self.accepted = False
        self.updating = False
        self.inference = None
        self.examples, self.pool, self.refs, self.skipped = adapter.read_scope(self.original)
        command.isRepeatable = False
        command.isExecutedWhenPreEmpted = False
        command.okButtonText = 'Select'
        inputs = command.commandInputs
        self.info = inputs.addTextBoxCommandInput('selectra_info', '', '', 3, True)
        self.info.isFullWidth = True
        self.result = inputs.addSelectionInput('selectra_result', 'Preview', 'Proposed selection')
        self.result.addSelectionFilter('Edges' if self.examples[0].kind == 'edge' else 'Faces')
        self.result.setSelectionLimits(0, 0)
        self.result.tooltip = 'Review the highlighted result. To change examples, cancel and select another example.'
        group = inputs.addGroupCommandInput('selectra_refine', 'Refine')
        group.isExpanded = False
        children = group.children
        style = adsk.core.DropDownStyles.TextListDropDownStyle
        self.tolerance = children.addDropDownCommandInput('selectra_tolerance', 'Similarity', style)
        for label in ('Tight', 'Balanced', 'Broad'):
            self.tolerance.listItems.add(label, label == 'Balanced', '')
        self.interpretation = children.addDropDownCommandInput('selectra_interpretation', 'Interpretation', style)
        self._calculate()
        _bind(command.activate, Activated(self), self.bindings)
        _bind(command.inputChanged, Changed(self), self.bindings)
        _bind(command.preSelect, PreviewOnly(), self.bindings)
        _bind(command.validateInputs, Validated(self), self.bindings)
        _bind(command.execute, Executed(self), self.bindings)
        _bind(command.destroy, Destroyed(self), self.bindings)

    def _calculate(self):
        self.updating = True
        try:
            values = {'Tight': .001, 'Balanced': .01, 'Broad': .05}
            relative = values[self.tolerance.selectedItem.name]
            self.inference = infer(self.examples, self.pool, Tolerance(relative=relative))
            self.interpretation.listItems.clear()
            for i, proposal in enumerate(self.inference.proposals):
                self.interpretation.listItems.add(proposal.label, i == 0, '')
            if not self.inference.proposals:
                self.interpretation.listItems.add('No additional matches', True, '')
            self.interpretation.isEnabled = len(self.inference.proposals) > 1
        finally:
            self.updating = False

    def chosen_keys(self):
        if not self.inference.proposals:
            return tuple(d.key for d in self.examples)
        return self.inference.proposals[self.interpretation.selectedItem.index].keys

    def preview(self):
        self.result.clearSelection()
        keys = self.chosen_keys()
        for key in keys:
            entity = self.refs[key]
            if not entity.isValid or not self.result.addSelection(entity):
                raise RuntimeError('A preview entity is no longer selectable. Cancel and retry.')
        summary = self.inference.explanation
        if self.skipped:
            summary += ' {} unsupported entities skipped.'.format(self.skipped)
        self.info.text = html.escape('{} items, including {} examples. {}'.format(
            len(keys), len(self.examples), summary))


class Menu(adsk.core.MarkingMenuEventHandler):
    def notify(self, args):
        try:
            app = adsk.core.Application.get()
            ui = app.userInterface
            if ui.activeCommand != 'SelectCommand' or not adsk.fusion.Design.cast(app.activeProduct):
                return
            entities = _active_entities(ui)
            if entities and all(adapter.kind(e) for e in entities):
                if len({adapter.kind(e) for e in entities}) == 1:
                    args.linearMarkingMenu.controls.addCommand(ui.commandDefinitions.itemById(COMMAND_ID))
        except Exception:
            _log()


class Created(adsk.core.CommandCreatedEventHandler):
    def notify(self, args):
        try:
            session = Session(args.command)
            _sessions.append(session)
        except Exception as error:
            _log()
            adsk.core.Application.get().userInterface.messageBox(str(error), 'Selectra')
            # A no-input command auto-terminates. No model mutation is made.


class Activated(adsk.core.CommandEventHandler):
    def __init__(self, session):
        super().__init__()
        self.session = session

    def notify(self, args):
        try:
            self.session.preview()
        except Exception:
            _log()


class Changed(adsk.core.InputChangedEventHandler):
    def __init__(self, session):
        super().__init__()
        self.session = session

    def notify(self, args):
        s = self.session
        if s.updating:
            return
        try:
            if args.input.id == 'selectra_tolerance':
                s._calculate()
            if args.input.id in ('selectra_tolerance', 'selectra_interpretation'):
                s.preview()
        except Exception:
            _log()


class PreviewOnly(adsk.core.SelectionEventHandler):
    def notify(self, args):
        args.isSelectable = False


class Validated(adsk.core.ValidateInputsEventHandler):
    def __init__(self, session):
        super().__init__()
        self.session = session

    def notify(self, args):
        s = self.session
        args.areInputsValid = (bool(s.inference.proposals)
                               and s.result.selectionCount == len(s.chosen_keys())
                               and all(s.refs[k].isValid for k in s.chosen_keys()))


class Executed(adsk.core.CommandEventHandler):
    def __init__(self, session):
        super().__init__()
        self.session = session

    def notify(self, args):
        self.session.accepted = True


class Destroyed(adsk.core.CommandEventHandler):
    def __init__(self, session):
        super().__init__()
        self.session = session

    def notify(self, args):
        global _pending
        s = self.session
        try:
            completed = args.terminationReason == adsk.core.CommandTerminationReason.CompletedTerminationReason
            entities = (tuple(s.refs[k] for k in s.chosen_keys())
                        if s.accepted and completed else s.original)
            if _running:
                _pending = (s.document, entities)
                if not s.app.fireCustomEvent(EVENT_ID):
                    _pending = None
                    s.app.log('Selectra: could not queue selection transfer.')
        finally:
            if s in _sessions:
                _sessions.remove(s)
            # The command owns its event objects until destruction.
            s.bindings.clear()


class ApplySelection(adsk.core.CustomEventHandler):
    def notify(self, args):
        global _pending
        pending, _pending = _pending, None
        if not pending:
            return
        app = adsk.core.Application.get()
        ui = app.userInterface
        document, entities = pending
        # A deferred callback must never overwrite a different document or
        # another tool's selections. No retries that could surprise the user.
        if app.activeDocument != document or ui.activeCommand != 'SelectCommand':
            app.log('Selectra: selection transfer skipped because context changed.')
            return
        if any(not e.isValid for e in entities):
            app.log('Selectra: selection transfer skipped because geometry changed.')
            return
        previous = _active_entities(ui)
        try:
            if not ui.activeSelections.clear():
                raise RuntimeError('Could not clear the selection.')
            for entity in entities:
                if not ui.activeSelections.add(entity):
                    raise RuntimeError('Could not apply the complete selection.')
        except Exception:
            ui.activeSelections.clear()
            for entity in previous:
                if entity.isValid:
                    ui.activeSelections.add(entity)
            _log()


def run(context):
    global _event_registered, _running
    app = adsk.core.Application.get()
    try:
        if _running:
            return
        ui = app.userInterface
        definition = ui.commandDefinitions.addButtonDefinition(
            COMMAND_ID, 'Select Similar', 'Find similar edges or faces from your selection.')
        _bind(definition.commandCreated, Created(), _bindings)
        _bind(ui.markingMenuDisplaying, Menu(), _bindings)
        event = app.registerCustomEvent(EVENT_ID)
        if not event:
            raise RuntimeError('Could not register the selection transfer event.')
        _event_registered = True
        _bind(event, ApplySelection(), _bindings)
        _running = True
    except Exception:
        _log()
        stop(context)


def stop(context):
    global _pending, _event_registered, _running
    app = adsk.core.Application.get()
    _running = False
    _pending = None
    for event, handler in reversed(_bindings):
        event.remove(handler)
    _bindings.clear()
    if _event_registered:
        app.unregisterCustomEvent(EVENT_ID)
        _event_registered = False
    definition = app.userInterface.commandDefinitions.itemById(COMMAND_ID)
    if definition:
        definition.deleteMe()
