#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import gtk
import gobject

from interface import WidgetInterface
from tryton.common.selection import SelectionMixin, selection_shortcuts, \
    PopdownMixin


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
        child.connect('activate', lambda *a: self._focus_out())
        child.connect('focus-out-event', lambda *a: self._focus_out())
        self.entry.connect('changed', self.changed)
        self.widget.pack_start(self.entry)
        self.widget.set_focus_chain([child])

        self.selection = attrs.get('selection', [])[:]
        self.attrs = attrs
        self.init_selection()
        self.set_popdown(self.selection, self.entry)

    def changed(self, combobox):
        def focus_out():
            if combobox.props.window:
                self._focus_out()
        # Must be deferred because it triggers a display of the form
        gobject.idle_add(focus_out)

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
        return self.get_popdown_value(self.entry)

    @property
    def modified(self):
        if self.record and self.field:
            return self.field.get(self.record) != self.get_value()
        return False

    def set_value(self, record, field):
        value = self.get_value()
        if 'relation' in self.attrs and value:
            value = (value, self.entry.get_active_text())
        field.set_client(record, value)

    def display(self, record, field):
        self.update_selection(record, field)
        self.set_popdown(self.selection, self.entry)
        if not field:
            self.entry.set_active(-1)
            return
        super(Selection, self).display(record, field)
        value = field.get(record)
        if isinstance(value, (list, tuple)):
            # Compatibility with Many2One
            value = value[0]

        if not self.set_popdown_value(self.entry, value):
            text = self.get_inactive_selection(value)
            self.set_popdown(self.selection[:] + [(value, text)], self.entry)
            self.set_popdown_value(self.entry, value)
