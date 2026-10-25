# SPDX-License-Identifier: GPL-3.0-only
"""Native context-menu spike. Requires real Fusion acceptance before release."""
import html
import traceback
from collections import deque
from threading import Timer

import adsk.core
import adsk.fusion

from . import fusion_adapter as adapter
from .matching import Tolerance
from .selection import SelectionSession
from .highlight import HighlightRenderer, ScopeHighlightRenderer
from .search_scope import SCOPES

COMMAND_ID = 'DiegoV_Selectra_SelectSimilar'
EVENT_ID = 'DiegoV_Selectra_ApplySelection'
_bindings = []
_sessions = []
_pending = None
_event_registered = False
_running = False
_diagnostics = deque(maxlen=100)
_pending_timer = None
_launch_context = None


def _bind(event, handler, bindings):
    if not event.add(handler):
        raise RuntimeError('Could not subscribe to ' + type(event).__name__)
    bindings.append((event, handler))


def _log():
    detail = traceback.format_exc()
    _diagnostics.append({'error': detail})
    adsk.core.Application.get().log('Selectra: ' + detail)


def _active_entities(ui):
    selections = ui.activeSelections
    return tuple(selections.item(i).entity for i in range(selections.count))


class Session:
    def __init__(self, command, preselected=None):
        self.app = adsk.core.Application.get()
        self.document = self.app.activeDocument
        self.original = tuple(preselected) if preselected is not None else _active_entities(self.app.userInterface)
        self.command, self.bindings = command, []
        self.accepted, self.accepted_keys = False, ()
        self.preview_error = ''
        self.updating = False
        self.scope_mode = 'component'
        self.scope_notice = ''
        self.snapshot, examples, self.refs, self.skipped, self.source_body, self.scope_guards = adapter.read_search_scope(self.original, self.scope_mode)
        self.original = tuple(self.refs[key] for key in examples)
        self.original_guards = tuple((body, stamp) for body, stamp in self.scope_guards
                                     if any(e.body == body for e in self.original))
        from time import monotonic
        self.timings = dict(adapter.read_search_scope.last_timings)
        analysis_started = monotonic()
        self.controller = SelectionSession(self.snapshot, examples)
        self.timings['initial_analysis_seconds'] = monotonic() - analysis_started
        self.renderer = self.make_renderer()
        command.isRepeatable = False
        command.isExecutedWhenPreEmpted = False
        command.okButtonText = 'OK'
        command.setDialogInitialSize(380, 440)
        inputs = command.commandInputs
        self.info = inputs.addTextBoxCommandInput('selectra_info', '', '', 3, True)
        self.info.isFullWidth = True
        self.scope_input = inputs.addDropDownCommandInput('selectra_scope', 'Search Scope', adsk.core.DropDownStyles.TextListDropDownStyle)
        for mode, label in SCOPES:
            self.scope_input.listItems.add(label, mode == self.scope_mode, '')
        self.scope_input.tooltip = 'This Component includes the selected instance and its nested components. All Components searches the entire assembly.'
        selection_filter = 'Edges' if self.snapshot.entities[0].kind == 'edge' else 'Faces'
        self.examples_input = inputs.addSelectionInput('selectra_examples', 'Examples', 'Add another example from this search scope')
        self.examples_input.addSelectionFilter(selection_filter)
        self.examples_input.setSelectionLimits(1, 0)
        self.exclusions_input = inputs.addSelectionInput('selectra_exclusions', 'Exclude', 'Show an item that should not be included')
        self.exclusions_input.addSelectionFilter(selection_filter)
        self.exclusions_input.setSelectionLimits(0, 0)
        self.range_input = inputs.addIntegerSliderCommandInput(
            'selectra_range', 'Similarity', 0, max(1, len(self.controller.ranking.tiers)), False)
        self.range_input.setText('Closest', 'Broader')
        self.range_input.tooltip = 'Include less similar items with PgUp; remove the least similar items with PgDown.'
        hint = inputs.addTextBoxCommandInput('selectra_hint', '', 'PgUp / =: more | PgDown / -: fewer', 1, True)
        hint.isFullWidth = True
        group = inputs.addGroupCommandInput('selectra_refine', 'Refine')
        group.isExpanded = False
        children = group.children
        self.criterion_options = [('auto', 'Automatic'),
            ('measure', 'Length' if self.snapshot.entities[0].kind == 'edge' else 'Area')]
        for key, label in (('direction', 'Direction'), ('normal', 'Orientation'),
                           ('radius', 'Radius'), ('perimeter', 'Perimeter')):
            if all(getattr(self.snapshot.by_key[k], key) is not None for k in examples):
                self.criterion_options.append((key, label))
        self.criterion_input = children.addDropDownCommandInput(
            'selectra_criterion', 'Match', adsk.core.DropDownStyles.TextListDropDownStyle)
        for key, label in self.criterion_options:
            self.criterion_input.listItems.add(label, key == 'auto', '')
        self.reset_input = children.addBoolValueInput('selectra_reset', 'Reset Range', False, '', False)
        self.sync_controls()
        _bind(command.activate, Activated(self), self.bindings)
        _bind(command.inputChanged, Changed(self), self.bindings)
        _bind(command.preSelect, AllowedSelection(self), self.bindings)
        _bind(command.keyDown, KeyPressed(self), self.bindings)
        _bind(command.executePreview, Previewed(self), self.bindings)
        _bind(command.validateInputs, Validated(self), self.bindings)
        _bind(command.execute, Executed(self), self.bindings)
        _bind(command.destroy, Destroyed(self), self.bindings)

    def make_renderer(self):
        if len(self.scope_guards) == 1:
            return HighlightRenderer(self.source_body, self.source_body.revisionId)
        return ScopeHighlightRenderer(self.scope_guards)

    def entity_key(self, entity):
        for index, (body, _) in enumerate(self.scope_guards):
            if entity.body == body:
                key = '{}:{}'.format(index, entity.tempId) if len(self.scope_guards) > 1 else str(entity.tempId)
                return key if key in self.refs else None
        return None

    def change_scope(self, mode):
        old = self.controller.feedback
        examples = tuple(self.refs[k] for k in old.examples)
        exclusions = tuple(self.refs[k] for k in old.exclusions)
        snapshot, _, refs, skipped, source, guards = adapter.read_search_scope(self.original[:1], mode)
        lookup = lambda entity: next((key for key, ref in refs.items() if ref == entity), None)
        example_keys = tuple(lookup(e) for e in examples)
        if None in example_keys:
            raise ValueError('Remove examples outside the requested scope before narrowing it.')
        controller = SelectionSession(snapshot, example_keys)
        controller.set_tolerance(old.tolerance)
        controller.set_criterion(old.criterion)
        controller.replace_exclusions(tuple(k for e in exclusions if (k := lookup(e)) is not None))
        self.renderer.clear()
        self.snapshot, self.refs, self.skipped = snapshot, refs, skipped
        self.source_body, self.scope_guards, self.scope_mode = source, guards, mode
        self.controller, self.renderer = controller, self.make_renderer()
        self.scope_notice = ''
        self.timings = dict(adapter.read_search_scope.last_timings)
        self.updating = True
        try:
            self.exclusions_input.clearSelection()
            for key in controller.feedback.exclusions:
                self.exclusions_input.addSelection(refs[key])
        finally:
            self.updating = False

    def sync_controls(self):
        previous, self.updating = self.updating, True
        try:
            maximum = max(1, len(self.controller.ranking.tiers))
            self.range_input.valueOne = min(self.range_input.valueOne, maximum)
            self.range_input.maximumValue = maximum
            self.range_input.valueOne = self.controller.level
            self.range_input.isEnabled = bool(self.controller.feedback.examples and self.controller.ranking.tiers)
        finally:
            self.updating = previous

    def chosen_keys(self):
        return self.controller.result

    def input_keys(self, control):
        entities = tuple(control.selection(i).entity for i in range(control.selectionCount))
        keys = tuple(self.entity_key(e) for e in entities)
        if None in keys:
            raise ValueError('Selection is outside the current search scope.')
        return self.snapshot.require_keys(keys)

    def preview(self):
        self.preview_error = ''
        self.sync_controls()
        if not self.controller.feedback.examples:
            self.renderer.clear()
            self.info.text = 'Select an example on ' + html.escape(self.source_body.name) + '.'
        # CommandInput changes schedule Fusion's own preview pass. Requesting
        # a second pass here rolls back/redraws the overlay twice per gesture.

    def draw_preview(self):
        if not adapter.scope_current(self.scope_guards):
            raise RuntimeError('Body geometry changed. Cancel and restart Select Similar.')
        previous, self.updating = self.updating, True
        try:
            keys = self.chosen_keys()
            self.renderer.show(self.refs, keys, self.controller.boundary_group)
            self.preview_error = ''
            noun = 'edges' if self.snapshot.entities[0].kind == 'edge' else 'faces'
            status = '{} of {} {} · {}'.format(len(keys), len(self.snapshot.entities), noun, dict(SCOPES)[self.scope_mode])
            labels = {'shape': 'Same trimmed shape and size',
                      'shape_families': 'Matching shapes and sizes of the examples', 'direct_wall': 'Opposite side of the example wall',
                      'analog_wall': 'Opposite side of a shape analog', 'wall_sides': 'Matching wall pairs',
                      'repeated_region': 'Repeated group with matching shape and arrangement',
                      'parallel_planes': 'Parallel planes', 'same_area': 'Same area; shape may differ',
                      'approximate': 'Broader geometric similarity; shape not confirmed'}
            ranking = self.controller.ranking
            if self.controller.level and ranking.explanations:
                status += '\n' + labels.get(ranking.explanations[self.controller.level-1], 'Geometric similarity')
            if self.controller.level and ranking.plane_groups:
                plane_labels = {'coplanar': 'In the example plane', 'parallel': 'In parallel planes',
                                'other': 'In other planes', 'unknown': 'Support plane unavailable'}
                status += '\n' + plane_labels[ranking.plane_groups[self.controller.level-1]]
            if self.controller.level == len(ranking.tiers) and self.controller.level:
                status += '\nAll permitted items of this type in the search scope.'
            if self.controller.ranking.ambiguous:
                status += '\nAdd an example or exclude an unwanted item.'
            if not self.snapshot.relations_complete:
                status += '\nShape matching available; wall-side search limited.'
            if any(d.geometry == 'plane' and not d.contours for d in self.snapshot.entities):
                status += '\nSome complex boundaries could not be compared by shape.'
            if self.scope_notice:
                status += '\n' + self.scope_notice
            self.info.text = status
        finally:
            self.updating = previous


class Menu(adsk.core.MarkingMenuEventHandler):
    def notify(self, args):
        try:
            app = adsk.core.Application.get()
            ui = app.userInterface
            _diagnostics.append({'event': 'menu', 'command': ui.activeCommand,
                                 'selection_count': ui.activeSelections.count})
            if ui.activeCommand != 'SelectCommand' or not adsk.fusion.Design.cast(app.activeProduct):
                return
            entities = _active_entities(ui)
            if entities and all(adapter.kind(e) for e in entities):
                if len({adapter.kind(e) for e in entities}) == 1:
                    args.linearMarkingMenu.controls.addCommand(ui.commandDefinitions.itemById(COMMAND_ID))
                    _diagnostics.append({'event': 'menu_added'})
        except Exception:
            _log()


class Starting(adsk.core.ApplicationCommandEventHandler):
    def notify(self, args):
        global _launch_context
        if args.commandId == COMMAND_ID:
            app = adsk.core.Application.get()
            _launch_context = (app.activeDocument, _active_entities(app.userInterface))


class Created(adsk.core.CommandCreatedEventHandler):
    def notify(self, args):
        global _launch_context
        _diagnostics.append({'event': 'created'})
        try:
            context, _launch_context = _launch_context, None
            selected = context[1] if context and context[0] == adsk.core.Application.get().activeDocument else None
            session = Session(args.command, selected)
            _sessions.append(session)
            _diagnostics.append({'event': 'session_ready', 'examples': session.controller.feedback.examples})
        except Exception as error:
            _log()
            args.command.commandInputs.addTextBoxCommandInput(
                'selectra_error', '', html.escape(str(error)), 4, True)
            args.command.isOKButtonVisible = False
            args.command.isExecutedWhenPreEmpted = False


class Activated(adsk.core.CommandEventHandler):
    def __init__(self, session):
        super().__init__()
        self.session = session

    def notify(self, args):
        _diagnostics.append({'event': 'activate'})
        try:
            self.session.updating = True
            self.session.examples_input.clearSelection()
            for key in self.session.controller.feedback.examples:
                if not self.session.examples_input.addSelection(self.session.refs[key]):
                    raise RuntimeError('Could not restore an example.')
            self.session.preview()
        except Exception:
            _log()
        finally:
            self.session.updating = False


class Changed(adsk.core.InputChangedEventHandler):
    def __init__(self, session):
        super().__init__()
        self.session = session

    def notify(self, args):
        s = self.session
        if s.updating:
            return
        try:
            key = args.input.id
            if key == 'selectra_scope':
                s.change_scope(SCOPES[s.scope_input.selectedItem.index][0])
            elif key == 'selectra_range':
                s.controller.set_level(s.range_input.valueOne)
            elif key == 'selectra_criterion':
                s.controller.set_criterion(s.criterion_options[s.criterion_input.selectedItem.index][0])
            elif key == 'selectra_examples':
                s.controller.replace_examples(s.input_keys(s.examples_input))
            elif key == 'selectra_exclusions':
                s.controller.replace_exclusions(s.input_keys(s.exclusions_input))
            elif key == 'selectra_reset':
                s.controller.reset_preview()
            else:
                return
            s.preview()
        except Exception as error:
            if args.input.id == 'selectra_scope':
                s.scope_notice = str(error)
                s.updating = True
                try:
                    s.scope_input.listItems.item(next(i for i, (mode, _) in enumerate(SCOPES) if mode == s.scope_mode)).isSelected = True
                finally:
                    s.updating = False
            s.info.text = html.escape(str(error))
            _log()


class AllowedSelection(adsk.core.SelectionEventHandler):
    def __init__(self, session):
        super().__init__()
        self.session = session

    def notify(self, args):
        try:
            control, entity = args.activeInput, args.selection.entity
            s = self.session
            valid = (entity.isValid
                     and adapter.kind(entity) == s.snapshot.entities[0].kind
                     and any(entity.body == body for body, _ in s.scope_guards))
            key = s.entity_key(entity) if valid else None
            if control.id == 'selectra_examples' and key in s.controller.feedback.exclusions:
                valid = False
            if control.id == 'selectra_exclusions' and key in s.controller.feedback.examples:
                valid = False
            args.isSelectable = valid and key in s.refs
        except Exception:
            args.isSelectable = False


class KeyPressed(adsk.core.KeyboardEventHandler):
    def __init__(self, session):
        super().__init__()
        self.session = session

    def notify(self, args):
        steps = {adsk.core.KeyCodes.PageUpKeyCode: 1, adsk.core.KeyCodes.PageDownKeyCode: -1,
                 adsk.core.KeyCodes.EqualKeyCode: 1, adsk.core.KeyCodes.PlusKeyCode: 1,
                 adsk.core.KeyCodes.MinusKeyCode: -1}
        printable = {adsk.core.KeyCodes.EqualKeyCode, adsk.core.KeyCodes.PlusKeyCode, adsk.core.KeyCodes.MinusKeyCode}
        if args.modifierMask and not (args.keyCode in printable and args.modifierMask == adsk.core.KeyboardModifiers.ShiftKeyboardModifier):
            return
        if args.keyCode not in steps:
            return
        s = self.session
        try:
            s.controller.adjust_similarity(steps[args.keyCode])
            _diagnostics.append({'event': 'similarity_key', 'key': args.keyCode,
                                 'level': s.controller.level, 'count': len(s.chosen_keys())})
            s.preview()
        except Exception as error:
            s.info.text = html.escape(str(error))
            _log()


class Previewed(adsk.core.CommandEventHandler):
    def __init__(self, session):
        super().__init__()
        self.session = session

    def notify(self, args):
        args.isValidResult = False
        try:
            self.session.draw_preview()
        except Exception as error:
            self.session.preview_error = str(error)
            self.session.info.text = html.escape(str(error))
            _log()


class Validated(adsk.core.ValidateInputsEventHandler):
    def __init__(self, session):
        super().__init__()
        self.session = session

    def notify(self, args):
        s = self.session
        try:
            args.areInputsValid = (bool(s.controller.feedback.examples) and not s.preview_error
                                   and adapter.scope_current(s.scope_guards)
                                   and s.input_keys(s.examples_input) == s.controller.feedback.examples
                                   and s.input_keys(s.exclusions_input) == s.controller.feedback.exclusions
                                   and all(s.refs[k].isValid for k in s.chosen_keys()))
        except Exception:
            args.areInputsValid = False


class Executed(adsk.core.CommandEventHandler):
    def __init__(self, session):
        super().__init__()
        self.session = session

    def notify(self, args):
        s = self.session
        if not adapter.scope_current(s.scope_guards):
            raise RuntimeError('Body changed before confirming the selection.')
        if s.renderer.keys != s.chosen_keys():
            s.draw_preview()
        s.accepted_keys = tuple(s.chosen_keys())
        s.accepted = True
        _diagnostics.append({'event': 'execute', 'keys': s.accepted_keys})


class Destroyed(adsk.core.CommandEventHandler):
    def __init__(self, session):
        super().__init__()
        self.session = session

    def notify(self, args):
        global _pending, _pending_timer
        s = self.session
        try:
            _diagnostics.append({'event': 'destroy', 'reason': args.terminationReason})
            s.renderer.clear()
            completed = args.terminationReason == adsk.core.CommandTerminationReason.CompletedTerminationReason
            entities = (tuple(s.refs[k] for k in s.accepted_keys)
                        if s.accepted and completed else s.original)
            if _running:
                guards = s.scope_guards if s.accepted and completed else s.original_guards
                _pending = (s.document, guards, entities)
                if _pending_timer:
                    _pending_timer.cancel()
                def queue():
                    queued = s.app.fireCustomEvent(EVENT_ID)
                    _diagnostics.append({'event': 'transfer_queued', 'return_value': queued})
                _pending_timer = Timer(.05, queue)
                _pending_timer.daemon = True
                _pending_timer.start()
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
        document, guards, entities = pending
        _diagnostics.append({'event': 'apply_selection', 'command': ui.activeCommand, 'count': len(entities)})
        # A deferred callback must never overwrite a different document or
        # another tool's selections. No retries that could surprise the user.
        if app.activeDocument != document or ui.activeCommand != 'SelectCommand':
            _diagnostics.append({'event': 'apply_skipped', 'reason': 'context_changed'})
            app.log('Selectra: selection transfer skipped because context changed.')
            return
        if not adapter.scope_current(guards) or any(not e.isValid for e in entities):
            _diagnostics.append({'event': 'apply_skipped', 'reason': 'geometry_changed'})
            app.log('Selectra: selection transfer skipped because geometry changed.')
            return
        previous = _active_entities(ui)
        try:
            if not ui.activeSelections.clear():
                raise RuntimeError('Could not clear the selection.')
            for entity in entities:
                if not ui.activeSelections.add(entity):
                    raise RuntimeError('Could not apply the complete selection.')
            _diagnostics.append({'event': 'apply_completed', 'count': ui.activeSelections.count})
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
        _bind(ui.commandStarting, Starting(), _bindings)
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
    global _pending, _event_registered, _running, _pending_timer, _launch_context
    app = adsk.core.Application.get()
    _running = False
    _pending = None
    _launch_context = None
    if _pending_timer:
        _pending_timer.cancel()
        _pending_timer = None
    for session in tuple(_sessions):
        session.renderer.clear()
    for event, handler in reversed(_bindings):
        event.remove(handler)
    _bindings.clear()
    if _event_registered:
        app.unregisterCustomEvent(EVENT_ID)
        _event_registered = False
    definition = app.userInterface.commandDefinitions.itemById(COMMAND_ID)
    if definition:
        definition.deleteMe()
