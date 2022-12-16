#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import gobject
from cellrendererinteger import CellRendererInteger
import locale


class CellRendererFloat(CellRendererInteger):

    def __init__(self):
        super(CellRendererFloat, self).__init__()
        self.digits = (16, 2)

    def sig_insert_text(self, entry, new_text, new_text_length, position):
        value = entry.get_text()
        position = entry.get_position()
        new_value = value[:position] + new_text + value[position:]
        try:
            decimal_point = locale.localeconv()['decimal_point']

            if new_value in ('-', decimal_point):
                return

            locale.atof(new_value)

            new_int = new_value
            new_decimal = ''
            if decimal_point in new_value:
                new_int, new_decimal = new_value.rsplit(decimal_point, 1)

            if len(new_int) > self.digits[0] \
                    or len(new_decimal) > self.digits[1]:
                entry.stop_emission('insert-text')

        except:
            entry.stop_emission('insert-text')

gobject.type_register(CellRendererFloat)
