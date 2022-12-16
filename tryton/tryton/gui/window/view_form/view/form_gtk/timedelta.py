# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from gi.repository import Gtk

from tryton.common.entry_position import reset_position
from .widget import Widget


class TimeDelta(Widget):

    def __init__(self, view, attrs):
        super(TimeDelta, self).__init__(view, attrs)

        self.widget = Gtk.HBox()
        self.entry = self.mnemonic_widget = Gtk.Entry()
        self.entry.set_alignment(1.0)
        self.entry.set_property('activates_default', True)

        self.entry.connect('activate', self.sig_activate)
        self.entry.connect('focus-out-event', lambda x, y: self._focus_out())
        self.entry.connect('key-press-event', self.send_modified)
        self.widget.pack_start(self.entry, expand=True, fill=True, padding=0)

    @property
    def modified(self):
        if self.record and self.field:
            value = self.entry.get_text()
            return self.field.get_client(self.record) != value
        return False

    def set_value(self):
        value = self.entry.get_text()
        return self.field.set_client(self.record, value)

    def get_value(self):
        return self.entry.get_text()

    def display(self):
        super(TimeDelta, self).display()
        if not self.field:
            value = ''
        else:
            value = self.field.get_client(self.record)
        self.entry.set_text(value)
        reset_position(self.entry)

    def _readonly_set(self, value):
        super(TimeDelta, self)._readonly_set(value)
        self.entry.set_editable(not value)
