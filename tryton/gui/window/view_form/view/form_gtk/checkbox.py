# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import gtk
from .widget import Widget
import gettext

_ = gettext.gettext


class CheckBox(Widget):

    def __init__(self, view, attrs):
        super(CheckBox, self).__init__(view, attrs)
        self.widget = self.mnemonic_widget = gtk.CheckButton()
        self.widget.connect('focus-out-event', lambda x, y: self._focus_out())
        self.widget.connect_after('toggled', self.sig_activate)

    def _readonly_set(self, value):
        super(CheckBox, self)._readonly_set(value)
        # TODO find a better solution to accept focus
        self.widget.set_sensitive(not value)

    def set_value(self, record, field):
        field.set_client(record, self.widget.get_active())

    def display(self, record, field):
        super(CheckBox, self).display(record, field)
        if not field:
            self.widget.set_active(False)
            return False
        self.widget.set_active(bool(field.get(record)))
