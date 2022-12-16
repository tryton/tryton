#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import operator
import gtk
import gobject
import math
from interface import WidgetInterface
from tryton.common import RPCExecute, RPCException


class Selection(WidgetInterface):

    def __init__(self, field_name, model_name, attrs=None):
        super(Selection, self).__init__(field_name, model_name, attrs=attrs)

        self.widget = gtk.HBox(spacing=3)
        ev_box = gtk.EventBox()
        ev_box.connect('enter-notify-event', self.enter)
        self.entry = gtk.ComboBoxEntry()
        child = self.entry.child
        child.set_property('activates_default', True)
        child.set_max_length(int(attrs.get('size', 0)))
        child.set_width_chars(10)

        child.connect('key_press_event', self.sig_key_press)
        child.connect('activate', self.sig_activate)
        child.connect_after('focus-out-event', self.sig_activate)
        child.connect('changed', self.send_modified)
        self.entry.connect('notify::active', lambda *a: self._focus_out())
        ev_box.add(self.entry)
        self.widget.pack_start(ev_box)
        self.widget.set_focus_chain([child])

        self._selection = {}
        self.selection = attrs.get('selection', [])[:]
        self.attrs = attrs
        self._last_domain = None
        self.init_selection()

    def init_selection(self):
        selection = self.attrs.get('selection', [])[:]
        if not isinstance(selection, (list, tuple)):
            try:
                selection = RPCExecute('model', self.model_name, selection)
            except RPCException:
                selection = []
        self.selection = selection[:]
        if self.attrs.get('sort', True):
            selection.sort(key=operator.itemgetter(1))
        self.set_popdown(selection)

    def update_selection(self, record):
        if not self.field:
            return
        if 'relation' not in self.attrs:
            return

        domain = self.field.domain_get(record)
        if domain == self._last_domain:
            return

        try:
            result = RPCExecute('model', self.attrs['relation'], 'search_read',
                domain, 0, None, None, ['rec_name'])
        except RPCException:
            result = False
        if isinstance(result, list):
            selection = [(x['id'], x['rec_name']) for x in result]
            selection.append((False, ''))
            self._last_domain = domain
        else:
            selection = []
            self._last_domain = None
        self.selection = selection[:]
        self.set_popdown(selection)

    def grab_focus(self):
        return self.entry.grab_focus()

    def set_popdown(self, selection):
        model = gtk.ListStore(gobject.TYPE_STRING)
        self._selection = {}
        lst = []
        for (value, name) in selection:
            name = str(name)
            lst.append(name)
            self._selection[name] = value
            i = model.append()
            model.set(i, 0, name)
        self.entry.set_model(model)
        self.entry.set_text_column(0)
        completion = gtk.EntryCompletion()
        #Only available in PyGTK 2.6 and above.
        if hasattr(completion, 'set_inline_selection'):
            completion.set_inline_selection(True)
        completion.set_model(model)
        self.entry.child.set_completion(completion)
        if self._selection:
            pop = sorted((len(x) for x in self._selection), reverse=True)
            average = sum(pop) / len(pop)
            deviation = int(math.sqrt(sum((x - average) ** 2 for x in pop) /
                    len(pop)))
            width = max(next((x for x in pop if x < (deviation * 4)), 10), 10)
        else:
            width = 10
        self.entry.child.set_width_chars(width)
        if self._selection:
            self.entry.child.set_max_length(
                max(len(x) for x in self._selection))
        completion.set_text_column(0)
        completion.connect('match-selected', lambda *a: self._focus_out())
        return lst

    def _readonly_set(self, value):
        super(Selection, self)._readonly_set(value)
        self.entry.set_sensitive(not value)

    def _color_widget(self):
        return self.entry.child

    def value_get(self):
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
        return value

    def sig_key_press(self, widget, event):
        if event.type == gtk.gdk.KEY_PRESS \
                and event.state & gtk.gdk.CONTROL_MASK \
                and event.keyval == gtk.keysyms.space:
            self.entry.popup()
        self.send_modified()

    def sig_activate(self, widget, event=None):
        if not self.field:
            return
        self.field.set_client(self.record, self.value_get())

    @property
    def modified(self):
        if self.record and self.field:
            return self.field.get(self.record) != self.value_get()
        return False

    def set_value(self, record, field):
        field.set_client(record, self.value_get())

    def _menu_sig_default_set(self, reset=False):
        self.set_value(self.record, self.field)
        super(Selection, self)._menu_sig_default_set(reset=reset)

    def display(self, record, field):
        self.update_selection(record)
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
                child.set_text('')
