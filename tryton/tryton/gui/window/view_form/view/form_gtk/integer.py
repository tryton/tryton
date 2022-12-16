# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from .char import Char
import locale


class Integer(Char):
    "Integer"

    def __init__(self, view, attrs):
        super(Integer, self).__init__(view, attrs)
        self.entry.set_width_chars(8)
        _, _, padding, pack_type = self.widget.query_child_packing(
            self.entry)
        self.widget.set_child_packing(self.entry, False, False,
            padding, pack_type)
        self.entry.set_max_length(0)
        self.entry.set_alignment(1.0)
        self.entry.connect('insert_text', self.sig_insert_text)
        self.factor = float(attrs.get('factor', 1))

    def set_value(self, record, field):
        return field.set_client(record, self.entry.get_text(),
            factor=self.factor)

    def get_client_value(self, record, field):
        if not field:
            value = ''
        else:
            value = field.get_client(record, factor=self.factor)
        return value

    def sig_insert_text(self, entry, new_text, new_text_length, position):
        value = entry.get_text()
        position = entry.get_position()
        new_value = value[:position] + new_text + value[position:]
        if new_value == '-':
            return
        try:
            locale.atoi(new_value)
        except ValueError:
            entry.stop_emission('insert-text')
