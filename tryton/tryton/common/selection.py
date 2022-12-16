# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import operator
import math

from gi.repository import Gdk, GLib, GObject, Gtk

from tryton.common import RPCExecute, RPCException
from tryton.common import eval_domain


class SelectionMixin(object):

    def __init__(self, *args, **kwargs):
        super(SelectionMixin, self).__init__(*args, **kwargs)
        self.nullable_widget = True
        self.selection = None
        self.inactive_selection = []
        self._last_domain = None
        self._values2selection = {}
        self._domain_cache = {}

    def init_selection(self, value=None):
        if value is None:
            value = dict((k, None)
                for k in self.attrs.get('selection_change_with') or [])
        key = freeze_value(value)
        selection = self.attrs.get('selection', [])[:]
        if (not isinstance(selection, (list, tuple))
                and key not in self._values2selection):
            try:
                if self.attrs.get('selection_change_with'):
                    selection = RPCExecute('model', self.model_name, selection,
                        value)
                else:
                    selection = RPCExecute('model', self.model_name, selection)
            except RPCException:
                selection = []
            self._values2selection[key] = selection
        elif key in self._values2selection:
            selection = self._values2selection[key]
        if self.attrs.get('sort', True):
            selection.sort(key=operator.itemgetter(1))
        self.selection = selection[:]
        self.inactive_selection = []

    def update_selection(self, record, field):
        if not field:
            return

        domain = field.domain_get(record)
        if 'relation' not in self.attrs:
            change_with = self.attrs.get('selection_change_with') or []
            value = record._get_on_change_args(change_with)
            value.pop('id', None)
            self.init_selection(value)
            self.filter_selection(domain, record, field)
        else:
            context = field.get_context(record)
            domain_cache_key = (freeze_value(domain), freeze_value(context))
            if domain_cache_key in self._domain_cache:
                self.selection = self._domain_cache[domain_cache_key]
                self._last_domain = (domain, context)
            if (domain, context) == self._last_domain:
                return

            try:
                result = RPCExecute('model', self.attrs['relation'],
                    'search_read', domain, 0, None, None, ['rec_name'],
                    context=context)
            except RPCException:
                result = False
            if isinstance(result, list):
                selection = [(x['id'], x['rec_name']) for x in result]
                if self.nullable_widget:
                    selection.append((None, ''))
                self._last_domain = (domain, context)
                self._domain_cache[domain_cache_key] = selection
            else:
                selection = []
                self._last_domain = None
            self.selection = selection[:]
            self.inactive_selection = []

    def filter_selection(self, domain, record, field):
        if not domain:
            return

        def _value_evaluator(value):
            return eval_domain(domain, {
                    self.field_name: value[0],
                    })

        def _model_evaluator(allowed_models):
            def test(value):
                return value[0] in allowed_models or not allowed_models
            return test

        if field.attrs['type'] == 'reference':
            allowed_models = field.get_models(record)
            evaluator = _model_evaluator(allowed_models)
        else:
            evaluator = _value_evaluator
        self.selection = list(filter(evaluator, self.selection))

    def get_inactive_selection(self, value):
        if 'relation' not in self.attrs:
            return ''
        for val, text in self.inactive_selection:
            if str(val) == str(value):
                return text
        else:
            try:
                result, = RPCExecute('model', self.attrs['relation'], 'read',
                    [value], ['rec_name'])
                self.inactive_selection.append((result['id'],
                        result['rec_name']))
                return result['rec_name']
            except RPCException:
                return ''


def selection_shortcuts(entry):
    def key_press(widget, event):
        if (event.type == Gdk.EventType.KEY_PRESS
                and event.state & Gdk.ModifierType.CONTROL_MASK
                and event.keyval == Gdk.KEY_space):
            widget.popup()
    entry.connect('key_press_event', key_press)
    return entry


def freeze_value(value):
    if isinstance(value, dict):
        return tuple(sorted((k, freeze_value(v))
                for k, v in value.items()))
    elif isinstance(value, (list, set)):
        return tuple(freeze_value(v) for v in value)
    else:
        return value


class PopdownMixin(object):

    def set_popdown(self, selection, entry):
        child = entry.get_child()
        if not child:  # entry is destroyed
            return
        model, lengths = self.get_popdown_model(selection)
        entry.set_model(model)
        entry.set_entry_text_column(0)
        completion = Gtk.EntryCompletion()
        completion.set_inline_selection(True)
        completion.set_model(model)
        child.set_completion(completion)
        if lengths:
            pop = sorted(lengths, reverse=True)
            average = sum(pop) / len(pop)
            deviation = int(
                math.sqrt(sum((x - average) ** 2 for x in pop)
                    / len(pop)))
            width = max(next((x for x in pop if x < (deviation * 4)), 10), 10)
        else:
            width = 10
        child.set_width_chars(width)
        if lengths:
            child.set_max_length(max(lengths))
        completion.set_text_column(0)
        completion.connect('match-selected', self.match_selected, entry)

    def get_popdown_model(self, selection):
        model = Gtk.ListStore(GObject.TYPE_STRING, GObject.TYPE_PYOBJECT)
        lengths = []
        for (value, name) in selection:
            name = str(name)
            model.append((name, value))
            lengths.append(len(name))
        return model, lengths

    def match_selected(self, completion, model, iter_, entry):
        value, = model.get(iter_, 1)
        model = entry.get_model()
        for i, values in enumerate(model):
            if values[1] == value:
                GLib.idle_add(entry.set_active, i)
                break

    def get_popdown_value(self, entry, index=1):
        active = entry.get_active()
        if active < 0:
            return None
        else:
            model = entry.get_model()
            return model[active][index]

    def get_popdown_text(self, entry):
        return self.get_popdown_value(entry, index=0)

    def set_popdown_value(self, entry, value):
        active = -1
        model = entry.get_model()
        for i, selection in enumerate(model):
            if selection[1] == value:
                active = i
                break
        else:
            if value:
                return False
        entry.set_active(active)
        if active == -1:
            # When setting no item GTK doesn't clear the entry
            entry.get_child().set_text('')
        return True
