#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import gtk
from .widget import Widget
import tryton.common as common
import tryton.rpc as rpc


class FloatTime(Widget):

    def __init__(self, view, attrs):
        super(FloatTime, self).__init__(view, attrs)

        self.widget = gtk.HBox()
        self.entry = gtk.Entry()
        self.entry.set_alignment(1.0)
        self.entry.set_property('activates_default', True)

        self.entry.connect('activate', self.sig_activate)
        self.entry.connect('focus-out-event', lambda x, y: self._focus_out())
        self.entry.connect('key-press-event', self.send_modified)
        self.widget.pack_start(self.entry)

        self.conv = None
        if attrs and attrs.get('float_time'):
            self.conv = rpc.CONTEXT.get(attrs['float_time'])

    def _color_widget(self):
        return self.entry

    @property
    def modified(self):
        if self.record and self.field:
            value = self.entry.get_text()
            return common.float_time_to_text(self.field.get(self.record),
                self.conv) != value
        return False

    def set_value(self, record, field):
        value = self.entry.get_text()
        digits = field.digits(record)
        return field.set_client(record,
            common.text_to_float_time(value, self.conv, digits[1]))

    def get_value(self):
        return self.entry.get_text()

    def display(self, record, field):
        super(FloatTime, self).display(record, field)
        if not field:
            self.entry.set_text('')
            return False
        val = field.get(record)

        self.entry.set_text(common.float_time_to_text(val, self.conv))

    def _readonly_set(self, value):
        super(FloatTime, self)._readonly_set(value)
        self.entry.set_editable(not value)
        if value:
            self.widget.set_focus_chain([])
        else:
            self.widget.set_focus_chain([self.entry])
