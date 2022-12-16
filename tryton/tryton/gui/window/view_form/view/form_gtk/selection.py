# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from gi.repository import GLib, Gtk

from .widget import Widget
from tryton.common.selection import SelectionMixin, selection_shortcuts, \
    PopdownMixin


class Selection(Widget, SelectionMixin, PopdownMixin):

    def __init__(self, view, attrs):
        super(Selection, self).__init__(view, attrs)

        self.widget = Gtk.HBox(spacing=3)
        self.entry = Gtk.ComboBox(has_entry=True)
        child = self.mnemonic_widget = self.entry.get_child()
        child.set_property('activates_default', True)
        child.set_max_length(int(attrs.get('size', 0)))
        child.set_width_chars(self.default_width_chars)

        selection_shortcuts(self.entry)
        child.connect('activate', lambda *a: self._focus_out())
        child.connect('focus-out-event', lambda *a: self._focus_out())
        self.entry.connect('changed', self.changed)
        self.entry.connect('move-active', self._move_active)
        self.entry.connect(
            'scroll-event',
            lambda c, e: c.stop_emission_by_name('scroll-event'))
        self.widget.pack_start(self.entry, expand=True, fill=True, padding=0)

        self.selection = attrs.get('selection', [])[:]
        self.attrs = attrs
        self.init_selection()
        self.set_popdown(self.selection, self.entry)

    def changed(self, combobox):
        def focus_out():
            if combobox.props.window:
                self._focus_out()
        # Must be deferred because it triggers a display of the form
        GLib.idle_add(focus_out)

    def _move_active(self, combobox, scroll_type):
        if not combobox.get_child().get_editable():
            combobox.stop_emission_by_name('move-active')

    def _readonly_set(self, value):
        super(Selection, self)._readonly_set(value)
        self.entry.get_child().set_editable(not value)
        self.entry.set_button_sensitivity(
            Gtk.SensitivityType.OFF if value else Gtk.SensitivityType.AUTO)

    def get_value(self):
        if not self.entry.get_child():  # entry is destroyed
            return
        return self.get_popdown_value(self.entry)

    @property
    def modified(self):
        if self.record and self.field:
            return self.field.get(self.record) != self.get_value()
        return False

    def set_value(self):
        value = self.get_value()
        if 'relation' in self.attrs and value:
            value = (value, self.get_popdown_text(self.entry))
        self.field.set_client(self.record, value)

    def display(self):
        self.update_selection(self.record, self.field)
        self.set_popdown(self.selection, self.entry)
        if not self.field:
            self.entry.set_active(-1)
            # When setting no item GTK doesn't clear the entry
            self.entry.get_child().set_text('')
            return
        super(Selection, self).display()
        value = self.field.get(self.record)
        if isinstance(value, (list, tuple)):
            # Compatibility with Many2One
            value = value[0]

        self.entry.handler_block_by_func(self.changed)
        if not self.set_popdown_value(self.entry, value):
            text = self.get_inactive_selection(value)
            self.set_popdown(self.selection[:] + [(value, text)], self.entry)
            self.set_popdown_value(self.entry, value)
        self.entry.handler_unblock_by_func(self.changed)
