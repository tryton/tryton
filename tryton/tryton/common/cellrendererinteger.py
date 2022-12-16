# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import gobject
from .cellrenderertext import CellRendererText
import locale


class CellRendererInteger(CellRendererText):

    def on_editing_started(self, editable, path):
        super().on_editing_started(editable, path)
        editable.set_alignment(1.0)
        editable.connect('insert_text', self.sig_insert_text)

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


gobject.type_register(CellRendererInteger)
