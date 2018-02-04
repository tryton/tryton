# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import gtk
import gobject

from .widget import Widget
from tryton.common.selection import SelectionMixin, selection_shortcuts, \
    PopdownMixin
from tryton.config import CONFIG


class Selection(Widget, SelectionMixin, PopdownMixin):

    def __init__(self, view, attrs):
        super(Selection, self).__init__(view, attrs)

        self.widget = gtk.HBox(spacing=3)
        self.entry = gtk.ComboBoxEntry()
        child = self.mnemonic_widget = self.entry.child
        child.set_property('activates_default', True)
        child.set_max_length(int(attrs.get('size', 0)))
        child.set_width_chars(10)

        selection_shortcuts(self.entry)
        child.connect('activate', lambda *a: self._focus_out())
        child.connect('focus-out-event', lambda *a: self._focus_out())
        self.entry.connect('changed', self.changed)
        self.entry.connect('move-active', self._move_active)
        self.entry.connect(
            'scroll-event', lambda c, e: c.emit_stop_by_name('scroll-event'))
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

    def _move_active(self, combobox, scroll_type):
        if not combobox.child.get_editable():
            combobox.emit_stop_by_name('move-active')

    def _readonly_set(self, value):
        super(Selection, self)._readonly_set(value)
        self.entry.child.set_editable(not value)
        self.entry.set_button_sensitivity(
            gtk.SENSITIVITY_OFF if value else gtk.SENSITIVITY_AUTO)
        if value and CONFIG['client.fast_tabbing']:
            self.widget.set_focus_chain([])
        else:
            self.widget.unset_focus_chain()

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
            # When setting no item GTK doesn't clear the entry
            self.entry.child.set_text('')
            return
        super(Selection, self).display(record, field)
        value = field.get(record)
        if isinstance(value, (list, tuple)):
            # Compatibility with Many2One
            value = value[0]

        self.entry.handler_block_by_func(self.changed)
        if not self.set_popdown_value(self.entry, value):
            text = self.get_inactive_selection(value)
            self.set_popdown(self.selection[:] + [(value, text)], self.entry)
            self.set_popdown_value(self.entry, value)
        self.entry.handler_unblock_by_func(self.changed)
