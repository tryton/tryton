# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from .char import Char
import locale


class IntegerMixin:
    default_width_chars = 8

    def _prepare_entry(self, entry):
        entry.set_width_chars(self.default_width_chars)
        entry.set_max_length(0)
        entry.set_alignment(1.0)
        entry.connect('insert-text', self._insert_text)

    def _insert_text(self, entry, new_text, new_text_length, position):
        value = entry.get_text()
        position = entry.get_position()
        new_value = value[:position] + new_text + value[position:]
        if new_value == '-':
            return
        try:
            locale.atoi(new_value)
        except ValueError:
            entry.stop_emission_by_name('insert-text')


class Integer(IntegerMixin, Char):
    "Integer"

    def __init__(self, view, attrs):
        super(Integer, self).__init__(view, attrs)
        _, _, padding, pack_type = self.widget.query_child_packing(
            self.entry)
        self.widget.set_child_packing(self.entry, False, False,
            padding, pack_type)
        self._prepare_entry(self.entry)
        self.factor = float(attrs.get('factor', 1))

    def set_value(self):
        return self.field.set_client(self.record, self.entry.get_text(),
            factor=self.factor)

    def get_client_value(self):
        if not self.field:
            value = ''
        else:
            value = self.field.get_client(self.record, factor=self.factor)
        return value
