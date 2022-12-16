# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import gettext

from gi.repository import Gtk

from .widget import Widget

_ = gettext.gettext


class CheckBox(Widget):

    def __init__(self, view, attrs):
        super(CheckBox, self).__init__(view, attrs)
        self.widget = self.mnemonic_widget = Gtk.CheckButton()
        self.widget.connect('focus-out-event', lambda x, y: self._focus_out())
        self.widget.connect_after('toggled', self.sig_activate)

    def _readonly_set(self, value):
        super(CheckBox, self)._readonly_set(value)
        # TODO find a better solution to accept focus
        self.widget.set_sensitive(not value)

    def set_value(self):
        self.field.set_client(self.record, self.widget.get_active())

    def display(self):
        super(CheckBox, self).display()
        if not self.field:
            self.widget.set_active(False)
            return False
        self.widget.handler_block_by_func(self.sig_activate)
        try:
            self.widget.set_active(bool(self.field.get(self.record)))
        finally:
            self.widget.handler_unblock_by_func(self.sig_activate)
