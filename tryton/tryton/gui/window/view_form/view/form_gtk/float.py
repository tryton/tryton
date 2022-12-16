#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import gtk
import locale
from integer import Integer


class Float(Integer):
    "Float"

    def __init__(self, field_name, model_name, attrs=None):
        super(Float, self).__init__(field_name, model_name, attrs=attrs)
        self.entry.connect('key-press-event', self.key_press_event)

    def set_value(self, record, field):
        return field.set_client(record, self.entry.get_text())

    def display(self, record, field):
        super(Float, self).display(record, field)
        if not field:
            self.entry.set_text('')
            return False
        digits = field.digits(record)
        self.entry.set_width_chars(sum(digits))
        self.entry.set_text(field.get_client(record))

    def key_press_event(self, widget, event):
        for name in ('KP_Decimal', 'KP_Separator'):
            if event.keyval == gtk.gdk.keyval_from_name(name):
                event.keyval = int(gtk.gdk.unicode_to_keyval(
                    ord(locale.localeconv()['decimal_point'])))

    def sig_insert_text(self, entry, new_text, new_text_length, position):
        if not self.record:
            entry.stop_emission('insert-text')
            return

        value = entry.get_text()
        position = entry.get_position()
        new_value = value[:position] + new_text + value[position:]
        decimal_point = locale.localeconv()['decimal_point']

        if new_value in ('-', decimal_point):
            return

        digits = self.field.digits(self.record)

        try:
            locale.atof(new_value)
        except ValueError:
            entry.stop_emission('insert-text')
            return

        new_int = new_value
        new_decimal = ''
        if decimal_point in new_value:
            new_int, new_decimal = new_value.rsplit(decimal_point, 1)

        if len(new_int) > digits[0] \
                or len(new_decimal) > digits[1]:
            entry.stop_emission('insert-text')
