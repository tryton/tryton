#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import gtk
import gobject
from interface import WidgetInterface
import tryton.rpc as rpc
import tryton.common as common


class Selection(WidgetInterface):

    def __init__(self, window, parent, model, attrs=None):
        super(Selection, self).__init__(window, parent, model, attrs)

        self.widget = gtk.HBox(spacing=3)
        self.entry = gtk.ComboBoxEntry()
        child = self.entry.get_child()
        child.set_property('activates_default', True)
        child.set_max_length(int(attrs.get('size', 0)))
        child.set_width_chars(5)

        child.connect('changed', self.sig_changed)
        self.changed = True
        child.connect('button_press_event', self._menu_open)
        child.connect('key_press_event', self.sig_key_press)
        child.connect('activate', self.sig_activate)
        child.connect_after('focus-out-event', self.sig_activate)
        self.entry.set_size_request(int(attrs.get('widget_size', -1)), -1)
        self.widget.pack_start(self.entry, expand=True, fill=True)
        self.widget.set_focus_chain([child])

        self._selection = {}
        selection = attrs.get('selection', [])[:]
        self.selection = selection[:]
        if 'relation' in attrs:
            try:
                result = rpc.execute('model',
                        attrs['relation'], 'search_read',
                        attrs.get('domain', []), 0, None, None, rpc.CONTEXT,
                        ['rec_name'])
                selection = [(x['id'], x['rec_name']) for x in result]
            except Exception, exception:
                common.process_exception(exception, self._window)
                selection = []
            self.selection = selection[:]
        else:
            if not isinstance(selection, (list, tuple)):
                try:
                    selection = rpc.execute('model',
                            self.model, selection, rpc.CONTEXT)
                except Exception, exception:
                    common.process_exception(exception, self._window)
                    selection = []
                self.selection = selection[:]

            for dom in common.filter_domain(attrs.get('domain', [])):
                if dom[1] in ('=', '!='):
                    todel = []
                    for i in range(len(selection)):
                        if (dom[1] == '=' \
                                and selection[i][0] != dom[2]) \
                                or (dom[1] == '!=' \
                                and selection[i][0] == dom[2]):
                            todel.append(i)
                    for i in todel[::-1]:
                        del selection[i]

        if attrs.get('sort', True):
            selection.sort(lambda x, y: cmp(x[1], y[1]))
        self.set_popdown(selection)
        self.last_key = (None, 0)

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
        self.entry.get_child().set_completion(completion)
        completion.set_text_column(0)
        return lst

    def _readonly_set(self, value):
        super(Selection, self)._readonly_set(value)
        self.entry.set_sensitive(not value)

    def _color_widget(self):
        return self.entry.get_child()

    def value_get(self):
        child = self.entry.get_child()
        res = child.get_text()
        return self._selection.get(res, False), res

    def sig_key_press(self, widget, event):
        if event.type == gtk.gdk.KEY_PRESS \
                and event.state & gtk.gdk.CONTROL_MASK \
                and event.keyval == gtk.keysyms.space:
            self.entry.popup()

    def sig_activate(self, widget, event=None):
        text = self.entry.child.get_text()
        value = False
        if text:
            for txt, val in self._selection.items():
                if not val:
                    continue
                if txt[:len(text)].lower() == text.lower():
                    value = val
                    if len(txt) == len(text):
                        break
        self._view.modelfield.set_client(self._view.model, value, force_change=True)
        self.display(self._view.model, self._view.modelfield)

    def set_value(self, model, model_field):
        model_field.set_client(model, self.value_get())

    def _menu_sig_default_set(self, reset=False):
        self.set_value(self._view.model, self._view.modelfield)
        super(Selection, self)._menu_sig_default_set(reset=reset)

    def display(self, model, model_field):
        child = self.entry.get_child()
        self.changed = False
        if not model_field:
            child.set_text('')
            return False
        super(Selection, self).display(model, model_field)
        value = model_field.get(model)
        if isinstance(value, (list, tuple)):
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
        self.changed = True

    def display_value(self):
        return self.entry.get_child().get_text()

    def sig_changed(self, *args):
        if self.changed:
            self._focus_out()
