#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import gtk
import gettext
from interface import Interface
import tryton.rpc as rpc
import tryton.common as common
import gobject

_ = gettext.gettext


class Reference(Interface):

    def __init__(self, name, parent, attrs=None, context=None):
        super(Reference, self).__init__(name, parent, attrs=attrs,
                context=context)

        self.widget = gtk.HBox()

        self.liststore = gtk.ListStore(gobject.TYPE_STRING, gobject.TYPE_STRING)
        self.combo = gtk.ComboBox(self.liststore)
        cell = gtk.CellRendererText()
        self.combo.pack_start(cell, True)
        self.combo.add_attribute(cell, 'text', 1)
        for oper in (['like', _('equals')],
                ['not like', _('is different')],
                ):
            self.liststore.append(oper)
        self.combo.set_active(0)
        self.widget.pack_start(self.combo, False, False)

        self.entry = gtk.combo_box_entry_new_text()
        self.entry.child.set_editable(True)
        self.entry.child.set_property('activates_default', True)
        self.entry.child.connect('key_press_event', self.sig_key_press)
        self.entry.set_focus_chain([self.entry.child])
        self._selection = {}
        selection = self.attrs.get('selection', [])
        if 'relation' in self.attrs:
            try:
                result = rpc.execute('model',
                        self.attrs['relation'], 'search_read',
                        self.attrs.get('domain', []),
                        0, None, None, rpc.CONTEXT, ['rec_name'])
                selection = [(x['id'], x['rec_name']) for x in result]
            except Exception, exception:
                common.process_exception(exception, parent)
                selection = []
        else:
            if not isinstance(selection, (list, tuple)):
                try:
                    selection = rpc.execute('model',
                            self.attrs['model'], selection, rpc.CONTEXT)
                except Exception, exception:
                    common.process_exception(exception, parent)
                    selection = []
        selection.sort(lambda x, y: cmp(x[1], y[1]))
        self.attrs['selection'] = selection
        self.set_popdown(selection)
        self.widget.pack_start(self.entry, True, True)
        self.widget.show_all()

    def set_popdown(self, selection):
        model = self.entry.get_model()
        model.clear()
        lst = []
        for (i, j) in selection:
            name = str(j)
            if type(i) == type(1):
                name += ' (' + str(i) + ')'
            lst.append(name)
            self._selection[name] = i
        self.entry.append_text('')
        for name in lst:
            self.entry.append_text(name)
        completion = gtk.EntryCompletion()
        #Only available in PyGTK 2.6 and above.
        if hasattr(completion, 'set_inline_selection'):
            completion.set_inline_selection(True)
        completion.set_model(model)
        self.entry.child.set_completion(completion)
        completion.set_text_column(0)
        return lst

    def sig_key_press(self, widget, event):
        if event.type == gtk.gdk.KEY_PRESS \
                and event.state & gtk.gdk.CONTROL_MASK \
                and event.keyval == gtk.keysyms.space:
            self.entry.popup()

    def _value_get(self):
        value = self._selection.get(self.entry.child.get_text(), False)
        oper = self.liststore.get_value(self.combo.get_active_iter(), 0)
        if value or oper != 'like':
            return [(self.name, oper, value + ',%')]
        else:
            self.entry.child.set_text('')
            return []

    def _value_set(self, value):
        i = self.liststore.get_iter_root()
        while i:
            if self.liststore.get_value(i, 0) == value[0]:
                self.combo.set_active_iter(i)
                break
            i = self.liststore.iter_next(i)
        if value[1] == False:
            self.entry.child.set_text('')
            return
        for long_text, sel_value in self._selection.items():
            if sel_value == value[1]:
                self.entry.child.set_text(long_text)
                break

    value = property(_value_get, _value_set, None,
            'The content of the widget or ValueError if not valid')

    def clear(self):
        self.value = ['like', False]

    def _readonly_set(self, value):
        self.combo.set_sensitive(not value)
        self.entry.set_sensitive(not value)

    def sig_activate(self, fct):
        self.entry.child.connect_after('activate', fct)
