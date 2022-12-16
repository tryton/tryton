#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import gtk
from interface import WidgetInterface
import tryton.common as common
import tryton.rpc as rpc


class FloatTime(WidgetInterface):

    def __init__(self, field_name, model_name, window, attrs=None):
        super(FloatTime, self).__init__(field_name, model_name, window,
                attrs=attrs)

        self.widget = gtk.HBox()
        self.entry = gtk.Entry()
        self.entry.set_alignment(1.0)
        self.entry.set_property('activates_default', True)

        self.entry.connect('populate-popup', self._populate_popup)
        self.entry.connect('activate', self.sig_activate)
        self.entry.connect('focus-in-event', lambda x, y: self._focus_in())
        self.entry.connect('focus-out-event', lambda x, y: self._focus_out())
        self.widget.pack_start(self.entry)

        self.conv = None
        if attrs and attrs.get('float_time'):
            self.conv = rpc.CONTEXT.get(attrs['float_time'])

    def _color_widget(self):
        return self.entry

    def grab_focus(self):
        return self.entry.grab_focus()

    def set_value(self, record, field):
        value = self.entry.get_text()
        if not value:
            return field.set_client(record, 0.0)
        digits = record.expr_eval(field.attrs.get('digits', (16, 2)))
        return field.set_client(record,
                round(common.text_to_float_time(value, self.conv), digits[1]))

    def display(self, record, field):
        super(FloatTime, self).display(record, field)
        if not field:
            self.entry.set_text('00:00')
            return False
        val = field.get(record)

        self.entry.set_text(common.float_time_to_text(val, self.conv))

    def display_value(self):
        return self.entry.get_text()

    def _readonly_set(self, value):
        super(FloatTime, self)._readonly_set(value)
        self.entry.set_editable(not value)
        if value:
            self.widget.set_focus_chain([])
        else:
            self.widget.set_focus_chain([self.entry])
