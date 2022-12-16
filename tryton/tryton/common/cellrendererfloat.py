# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import locale

from gi.repository import Gdk, GObject

from .cellrendererinteger import CellRendererInteger


class CellRendererFloat(CellRendererInteger):

    def __init__(self):
        super(CellRendererFloat, self).__init__()
        self.digits = None

    def on_editing_started(self, editable, path):
        super().on_editing_started(editable, path)
        editable.connect('key-press-event', self.key_press_event)

    def key_press_event(self, widget, event):
        for name in ('KP_Decimal', 'KP_Separator'):
            if event.keyval == Gdk.keyval_from_name(name):
                event.keyval = int(Gdk.unicode_to_keyval(
                    ord(locale.localeconv()['decimal_point'])))

    def sig_insert_text(self, entry, new_text, new_text_length, position):
        value = entry.get_text()
        position = entry.get_position()
        new_value = value[:position] + new_text + value[position:]
        decimal_point = locale.localeconv()['decimal_point']

        if new_value in ('-', decimal_point):
            return

        try:
            value = locale.atof(new_value)
        except ValueError:
            entry.stop_emission_by_name('insert-text')
            return

        if self.digits and not (round(value, self.digits[1]) == float(value)):
            entry.stop_emission_by_name('insert-text')


GObject.type_register(CellRendererFloat)
