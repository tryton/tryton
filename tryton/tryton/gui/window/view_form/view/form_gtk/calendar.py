#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import gtk
import gettext

from interface import WidgetInterface
from tryton.common.date_widget import DateEntry
from tryton.translate import date_format

_ = gettext.gettext


class Calendar(WidgetInterface):
    "Calendar"

    def __init__(self, field_name, model_name, attrs=None):
        super(Calendar, self).__init__(field_name, model_name, attrs=attrs)

        self.widget = gtk.HBox()
        self.entry = DateEntry('')
        self.entry.set_property('activates_default', True)
        self.entry.connect('key_press_event', self.sig_key_press)
        self.entry.connect('activate', self.sig_activate)
        self.entry.connect('focus-out-event', lambda x, y: self._focus_out())
        self.widget.pack_start(self.entry, expand=False, fill=False)

    def _color_widget(self):
        return self.entry

    def _readonly_set(self, value):
        self.entry.set_editable(not value)
        if value:
            self.widget.set_focus_chain([])
        else:
            self.widget.set_focus_chain([self.entry])

    @property
    def modified(self):
        if self.record and self.field:
            value = self.entry.compute_date(self.entry.get_text())
            return self.field.get_client(self.record) != value
        return False

    def sig_key_press(self, widget, event):
        self.send_modified()

    def grab_focus(self):
        return self.entry.grab_focus()

    def set_value(self, record, field):
        field.set_client(record, self.get_value())

    def get_value(self):
        return self.entry.date_get(set_text=False)

    def get_format(self, record, field):
        return date_format()

    def display(self, record, field):
        if not field:
            self.entry.set_format('')
            self.entry.clear()
            return False
        self.entry.set_format(self.get_format(record, field))
        super(Calendar, self).display(record, field)
        value = field.get_client(record)
        if not value:
            self.entry.clear()
        else:
            if len(value) > self.entry.get_width_chars():
                self.entry.set_width_chars(len(value))
            self.entry.set_text(value)
        return True


class DateTime(Calendar):
    "DateTime"

    def __init__(self, field_name, model_name, attrs=None):
        super(DateTime, self).__init__(field_name, model_name, attrs=attrs)

    def get_format(self, record, field):
        return date_format() + ' ' + field.time_format(record)


class Time(Calendar):
    "Time"

    def __init__(self, field_name, model_name, attrs=None):
        super(Time, self).__init__(field_name, model_name, attrs=attrs)
        if hasattr(self.entry, 'set_icon_from_stock'):
            self.entry.set_icon_from_stock(gtk.ENTRY_ICON_SECONDARY, None)

    def get_format(self, record, field):
        return field.time_format(record)
