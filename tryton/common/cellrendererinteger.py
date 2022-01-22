# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import locale

from gi.repository import GObject

from .cellrenderertext import CellRendererText


class CellRendererInteger(CellRendererText):

    def on_editing_started(self, editable, path):
        super().on_editing_started(editable, path)
        editable.set_alignment(1.0)
        editable.connect('insert_text', self.sig_insert_text)

    def _can_insert_text(self, entry, new_text, position):
        value = entry.get_text()
        new_value = value[:position] + new_text + value[position:]
        if new_value != '-':
            try:
                locale.atoi(new_value)
            except ValueError:
                return False
        return True

    def sig_insert_text(self, entry, new_text, new_text_length, position):
        position = entry.get_position()
        if not self._can_insert_text(entry, new_text, position):
            entry.stop_emission_by_name('insert-text')


GObject.type_register(CellRendererInteger)
