# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import gtk
import locale
from .integer import Integer


class Float(Integer):
    "Float"

    def __init__(self, view, attrs):
        super(Float, self).__init__(view, attrs)
        self.entry.connect('key-press-event', self.key_press_event)

    def display(self, record, field):
        super(Float, self).display(record, field)
        if field:
            digits = field.digits(record, factor=self.factor)
            if digits:
                self.entry.set_width_chars(sum(digits))
            else:
                self.entry.set_width_chars(18)

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

        digits = self.field.digits(self.record, factor=self.factor)

        try:
            value = locale.atof(new_value)
        except ValueError:
            entry.stop_emission('insert-text')
            return

        if digits and not (round(value, digits[1]) == float(value)):
            entry.stop_emission('insert-text')
