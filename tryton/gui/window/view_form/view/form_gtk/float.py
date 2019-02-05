# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import gtk
import locale
from .integer import Integer, IntegerMixin


class FloatMixin(IntegerMixin):
    default_width_chars = 18

    def _prepare_entry(self, entry):
        super()._prepare_entry(entry)
        entry.connect('key-press-event', self._key_press_event)

    def _insert_text(self, entry, new_text, new_text_length, position):
        value = entry.get_text()
        position = entry.get_position()
        new_value = value[:position] + new_text + value[position:]
        decimal_point = locale.localeconv()['decimal_point']
        if new_value in ['-', decimal_point]:
            return
        try:
            value = locale.atof(new_value)
        except ValueError:
            entry.stop_emission('insert-text')
            return
        digits = self.digits
        if digits and not (round(value, digits[1]) == float(value)):
            entry.stop_emission('insert-text')

    def _key_press_event(self, entry, event):
        for name in ['KP_Decimal', 'KP_Separator']:
            if event.keyval == gtk.gdk.keyval_from_name(name):
                event.keyval = int(gtk.gdk.unicode_to_keyval(
                    ord(locale.localeconv()['decimal_point'])))

    @property
    def digits(self):
        return NotImplementedError

    def _set_entry_width(self, entry):
        digits = self.digits
        if digits:
            width = sum(digits)
        else:
            width = self.default_width_chars
        entry.set_width_chars(width)


class Float(FloatMixin, Integer):
    "Float"

    @property
    def digits(self):
        if self.field and self.record:
            return self.field.digits(self.record, factor=self.factor)

    def display(self):
        super(Float, self).display()
        self._set_entry_width(self.entry)
