# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import locale

from gi.repository import Gdk, GObject

from .cellrendererinteger import CellRendererInteger


class CellRendererFloat(CellRendererInteger):

    def __init__(self):
        super(CellRendererFloat, self).__init__()
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
                position = widget.props.cursor_position
                if self._can_insert_text(widget, text, position):
                    buffer_ = widget.get_buffer()
                    buffer_.insert_text(position, text, len(text))
                    widget.set_position(
                        widget.props.cursor_position + len(text))
                return True

    def _can_insert_text(self, entry, new_text, position):
        value = entry.get_text()
        position = entry.get_position()
        new_value = value[:position] + new_text + value[position:]
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
