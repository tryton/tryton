#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import gtk
from interface import WidgetInterface
import gettext

_ = gettext.gettext


class CheckBox(WidgetInterface):

    def __init__(self, field_name, model_name, attrs=None):
        super(CheckBox, self).__init__(field_name, model_name, attrs=attrs)
        self.widget = gtk.CheckButton()
        self.widget.connect('focus-out-event', lambda x, y: self._focus_out())
        self.widget.connect_after('toggled', self.sig_activate)

    def _readonly_set(self, value):
        super(CheckBox, self)._readonly_set(value)
        self.widget.set_sensitive(not value)

    def set_value(self, record, field):
        field.set_client(record, self.widget.get_active())

    def display(self, record, field):
        super(CheckBox, self).display(record, field)
        if not field:
            self.widget.set_active(False)
            return False
        self.widget.set_active(bool(field.get(record)))
