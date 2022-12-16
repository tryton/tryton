#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from char import Char
from integer import Integer
import locale


class Float(Integer):
    "Float"

    def __init__(self, window, parent, model, attrs=None):
        super(Float, self).__init__(window, parent, model=model, attrs=attrs)
        self.digits = attrs.get('digits', (16, 2))

    def set_value(self, model, model_field):
        try:
            value = locale.atof(self.entry.get_text())
        except:
            value = 0.0
        return model_field.set_client(model, value)

    def display(self, model, model_field):
        super(Char, self).display(model, model_field)
        if not model_field:
            self.entry.set_text('')
            return False
        if isinstance(self.digits, str):
            digits = self._view.model.expr_eval(self.digits)
        else:
            digits = self.digits
        self.entry.set_text(locale.format('%.' + str(digits[1]) + 'f',
            model_field.get(model) or 0.0, True))

    def sig_insert_text(self, entry, new_text, new_text_length, position):
        value = entry.get_text()
        position = entry.get_position()
        new_value = value[:position] + new_text + value[position:]
        try:
            decimal_point = locale.localeconv()['decimal_point']

            if new_value in ('-', decimal_point):
                return

            if isinstance(self.digits, str):
                digits = self._view.model.expr_eval(self.digits)
            else:
                digits = self.digits

            locale.atof(new_value)

            new_int = new_value
            new_decimal = ''
            if decimal_point in new_value:
                new_int, new_decimal = new_value.rsplit(decimal_point, 1)

            if len(new_int) > digits[0] \
                    or len(new_decimal) > digits[1]:
                entry.stop_emission('insert-text')

        except:
            entry.stop_emission('insert-text')
