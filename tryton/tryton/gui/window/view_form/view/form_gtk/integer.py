#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from char import Char
import locale


class Integer(Char):
    "Integer"

    def __init__(self, field_name, model_name, attrs=None):
        super(Integer, self).__init__(field_name, model_name, attrs=attrs)
        self.entry.set_width_chars(8)
        _, _, padding, pack_type = self.widget.query_child_packing(
            self.entry)
        self.widget.set_child_packing(self.entry, False, False,
            padding, pack_type)
        self.entry.set_max_length(0)
        self.entry.set_alignment(1.0)
        self.entry.connect('insert_text', self.sig_insert_text)

    def set_value(self, record, field):
        return field.set_client(record, self.entry.get_text())

    def display(self, record, field):
        # skip Char call because set_text doesn't work with int
        super(Char, self).display(record, field)
        if not field:
            self.entry.set_text('')
            return False
        self.entry.set_text(field.get_client(record))

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
