#This file is part of Tryton.  The COPYRIGHT file at the top level of this repository contains the full copyright notices and license terms.
import gtk
import math
import locale
from interface import WidgetInterface


class FloatTime(WidgetInterface):

    def __init__(self, window, parent, model, attrs=None):
        super(FloatTime, self).__init__(window, parent, model=model,
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

    def _color_widget(self):
        return self.entry

    def grab_focus(self):
        return self.entry.grab_focus()

    def text_to_float(self, text):
        try:
            if text and ':' in text:
                # assume <hours>:<minutes>
                h, m = text.split(':')
                h = h or 0
                m = m or 0
                return round(int(h) + int(m)/60.0, 2)
            else:
                # try float in locale notion
                return locale.atof(text)
        except:
            return 0.0

    def set_value(self, model, model_field):
        value = self.entry.get_text()
        if not value:
            return model_field.set_client(model, 0.0)
        return model_field.set_client(model, self.text_to_float(value))

    def display(self, model, model_field):
        super(FloatTime, self).display(model, model_field)
        if not model_field:
            self.entry.set_text('00:00')
            return False
        val = model_field.get(model)
        value = '%02d:%02d' % (math.floor(abs(val)),
                round(abs(val)%1+0.01, 2) * 60)
        if val < 0:
            value = '-' + value
        self.entry.set_text(value)

    def display_value(self):
        return self.entry.get_text()

    def _readonly_set(self, value):
        super(FloatTime, self)._readonly_set(value)
        self.entry.set_editable(not value)
        if value:
            self.widget.set_focus_chain([])
        else:
            self.widget.set_focus_chain([self.entry])
