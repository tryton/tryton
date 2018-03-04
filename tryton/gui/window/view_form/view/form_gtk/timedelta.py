# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import gtk

from tryton.config import CONFIG
from tryton.common.entry_position import reset_position
from .widget import Widget


class TimeDelta(Widget):

    def __init__(self, view, attrs):
        super(TimeDelta, self).__init__(view, attrs)

        self.widget = gtk.HBox()
        self.entry = self.mnemonic_widget = gtk.Entry()
        self.entry.set_alignment(1.0)
        self.entry.set_property('activates_default', True)

        self.entry.connect('activate', self.sig_activate)
        self.entry.connect('focus-out-event', lambda x, y: self._focus_out())
        self.entry.connect('key-press-event', self.send_modified)
        self.widget.pack_start(self.entry)

    @property
    def modified(self):
        if self.record and self.field:
            value = self.entry.get_text()
            return self.field.get_client(self.record) != value
        return False

    def set_value(self, record, field):
        value = self.entry.get_text()
        return field.set_client(record, value)

    def get_value(self):
        return self.entry.get_text()

    def display(self, record, field):
        super(TimeDelta, self).display(record, field)
        if not field:
            value = ''
        else:
            value = field.get_client(record)
        self.entry.set_text(value)
        reset_position(self.entry)

    def _readonly_set(self, value):
        super(TimeDelta, self)._readonly_set(value)
        self.entry.set_editable(not value)
        if value and CONFIG['client.fast_tabbing']:
            self.widget.set_focus_chain([])
        else:
            self.widget.unset_focus_chain()
