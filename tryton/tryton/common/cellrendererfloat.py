# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import locale

from gi.repository import Gdk, GObject

from .cellrendererinteger import CellRendererInteger


class CellRendererFloat(CellRendererInteger):

    def __init__(self):
        super().__init__()
        self.digits = None
        self.monetary = False
        self.convert = float

    def on_editing_started(self, editable, path):
        super().on_editing_started(editable, path)
        editable.connect('key-press-event', self.key_press_event)

    @property
    def __decimal_point(self):
        return locale.localeconv()['decimal_point']

    @property
    def __thousands_sep(self):
        return locale.localeconv()['thousands_sep']

    def key_press_event(self, widget, event):
        for name in ('KP_Decimal', 'KP_Separator'):
            if event.keyval == Gdk.keyval_from_name(name):
                text = self.__decimal_point
                try:
                    start_pos, end_pos = widget.get_selection_bounds()
                except ValueError:
                    start_pos = widget.get_position()
                    end_pos = None
                if self._can_insert_text(widget, text, start_pos, end_pos):
                    buffer_ = widget.get_buffer()
                    if end_pos:
                        buffer_.delete_text(start_pos, end_pos - start_pos)
                    buffer_.insert_text(start_pos, text, len(text))
                    widget.set_position(widget.get_position() + len(text))
                return True

    def _can_insert_text(self, entry, new_text, start_pos, end_pos=None):
        value = entry.get_text()
        if end_pos is None:
            end_pos = start_pos
        new_value = value[:start_pos] + new_text + value[end_pos:]
        if new_value not in {'-', self.__decimal_point, self.__thousands_sep}:
            try:
                value = self.convert(
                    locale.delocalize(new_value, self.monetary))
            except ValueError:
                return False
            if (value and self.digits is not None
                    and round(value, self.digits[1]) != value):
                return False
        return True


GObject.type_register(CellRendererFloat)
