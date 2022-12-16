#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from char import Char
import locale


class Integer(Char):
    "Integer"

    def __init__(self, field_name, model_name, window, attrs=None):
        super(Integer, self).__init__(field_name, model_name, window,
                attrs=attrs)
        self.entry.set_max_length(0)
        self.entry.set_alignment(1.0)
        self.entry.connect('insert_text', self.sig_insert_text)

    def set_value(self, record, field):
        try:
            value = locale.atoi(self.entry.get_text())
        except Exception:
            value = 0
        return field.set_client(record, value)

    def display(self, record, field):
        # skip Char call because set_text doesn't work with int
        super(Char, self).display(record, field)
        if not field:
            self.entry.set_text('')
            return False
        self.entry.set_text(locale.format('%d',
            field.get(record) or 0, True))

    def display_value(self):
        return self.entry.get_text()

    def sig_insert_text(self, entry, new_text, new_text_length, position):
        value = entry.get_text()
        position = entry.get_position()
        new_value = value[:position] + new_text + value[position:]
        try:
            if new_value == '-':
                return
            locale.atoi(new_value)
        except Exception:
            entry.stop_emission('insert-text')
