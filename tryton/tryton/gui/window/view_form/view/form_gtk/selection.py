#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import gtk
import gobject
import math
from interface import WidgetInterface
from tryton.common.selection import SelectionMixin, selection_shortcuts


class PopdownMixin(object):

    def __init__(self, *args, **kwargs):
        super(PopdownMixin, self).__init__()
        self._selection = {}

    def set_popdown(self, selection, entry):
        if not entry.child:  # entry is destroyed
            return
        # Don't update popdown if not changed
        if (list(x[0] for x in entry.get_model() or [])
                == [x[1] for x in selection]):
            return
        model = gtk.ListStore(gobject.TYPE_STRING)
        self._selection.clear()
        for (value, name) in selection:
            name = str(name)
            self._selection[name] = value
            model.append((name,))
        entry.set_model(model)
        entry.set_text_column(0)
        completion = gtk.EntryCompletion()
        #Only available in PyGTK 2.6 and above.
        if hasattr(completion, 'set_inline_selection'):
            completion.set_inline_selection(True)
        completion.set_model(model)
        entry.child.set_completion(completion)
        if self._selection:
            pop = sorted((len(x) for x in self._selection), reverse=True)
            average = sum(pop) / len(pop)
            deviation = int(math.sqrt(sum((x - average) ** 2 for x in pop) /
                    len(pop)))
            width = max(next((x for x in pop if x < (deviation * 4)), 10), 10)
        else:
            width = 10
        entry.child.set_width_chars(width)
        if self._selection:
            entry.child.set_max_length(
                max(len(x) for x in self._selection))
        completion.set_text_column(0)
        completion.connect('match-selected', lambda *a: self._focus_out())


class Selection(WidgetInterface, SelectionMixin, PopdownMixin):

    def __init__(self, field_name, model_name, attrs=None):
        super(Selection, self).__init__(field_name, model_name, attrs=attrs)

        self.widget = gtk.HBox(spacing=3)
        self.entry = gtk.ComboBoxEntry()
        child = self.entry.child
        child.set_property('activates_default', True)
        child.set_max_length(int(attrs.get('size', 0)))
        child.set_width_chars(10)

        selection_shortcuts(self.entry)
        child.connect('key_press_event', self.sig_key_press)
        child.connect('activate', self.sig_activate)
        child.connect_after('focus-out-event', self.sig_activate)
        child.connect('changed', self.send_modified)
        self.entry.connect('notify::active', lambda *a: self._focus_out())
        self.widget.pack_start(self.entry)
        self.widget.set_focus_chain([child])

        self._selection = {}
        self.selection = attrs.get('selection', [])[:]
        self.attrs = attrs
        self.init_selection()
        self.set_popdown(self.selection, self.entry)

    def grab_focus(self):
        return self.entry.grab_focus()

    def _readonly_set(self, value):
        super(Selection, self)._readonly_set(value)
        self.entry.set_sensitive(not value)

    def _color_widget(self):
        return self.entry.child

    def get_value(self):
        if not self.entry.child:  # entry is destroyed
            return
        text = self.entry.child.get_text()
        value = None
        if text:
            for txt, val in self._selection.items():
                if not val:
                    continue
                if txt[:len(text)].lower() == text.lower():
                    value = val
                    if len(txt) == len(text):
                        break
            if not value:
                for val, txt in self.inactive_selection:
                    if txt == text:
                        value = val
                        break
        return value

    def sig_key_press(self, widget, event):
        self.send_modified()

    def sig_activate(self, widget, event=None):
        if not self.field:
            return
        self.field.set_client(self.record, self.get_value())

    @property
    def modified(self):
        if self.record and self.field:
            return self.field.get(self.record) != self.get_value()
        return False

    def set_value(self, record, field):
        field.set_client(record, self.get_value())

    def _menu_sig_default_set(self, reset=False):
        self.set_value(self.record, self.field)
        super(Selection, self)._menu_sig_default_set(reset=reset)

    def display(self, record, field):
        self.update_selection(record, field)
        self.set_popdown(self.selection, self.entry)
        child = self.entry.child
        if not field:
            child.set_text('')
            return False
        super(Selection, self).display(record, field)
        value = field.get(record)
        if isinstance(value, (list, tuple)):
            # Compatibility with Many2One
            value = value[0]
        if not value:
            child.set_text('')
        else:
            found = False
            for long_text, sel_value in self._selection.items():
                if str(sel_value) == str(value):
                    child.set_text(long_text)
                    found = True
                    break
            if not found:
                for sel_value, long_text in self.selection:
                    if str(sel_value) == str(value):
                        self._selection[long_text] = sel_value
                        model = self.entry.get_model()
                        i = model.append()
                        model.set(i, 0, long_text)
                        child.set_text(long_text)
                        found = True
                        break
            if not found:
                text = self.get_inactive_selection(value)
                if text:
                    child.set_text(text)
                    found = True
            if not found:
                child.set_text('')
