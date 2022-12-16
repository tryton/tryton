# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from gi.repository import Gtk

from tryton.common.entry_position import reset_position
from tryton.common.number_entry import NumberEntry
from .widget import Widget


class Integer(Widget):
    "Integer"

    def __init__(self, view, attrs):
        super(Integer, self).__init__(view, attrs)
        self.widget = Gtk.HBox()
        self.entry = self.mnemonic_widget = NumberEntry()
        self.entry.props.activates_default = True
        self.entry.connect('activate', self.sig_activate)
        self.entry.connect('focus-out-event', lambda *a: self._focus_out())
        self.entry.connect('key-press-event', self.send_modified)
        self.symbol = attrs.get('symbol')
        if self.symbol:
            self.symbol_start = Gtk.Entry(editable=False)
            self.widget.pack_start(
                self.symbol_start, expand=False, fill=False, padding=1)
        self.widget.pack_start(self.entry, expand=False, fill=False, padding=0)
        self.factor = float(attrs.get('factor', 1))
        if self.symbol:
            self.symbol_end = Gtk.Entry(editable=False)
            self.widget.pack_start(
                self.symbol_end, expand=False, fill=False, padding=1)

    @property
    def modified(self):
        if self.record and self.field:
            value = self.get_client_value()
            return value != self.get_value()
        return False

    def set_value(self):
        return self.field.set_client(
            self.record, self.entry.get_text(), factor=self.factor)

    def get_value(self):
        return self.entry.get_text()

    def get_client_value(self):
        if not self.field:
            value = ''
        else:
            value = self.field.get_client(self.record, factor=self.factor)
        return value

    @property
    def width(self):
        return 8

    def display(self):
        def set_symbol(entry, text):
            if text:
                entry.set_text(text)
                entry.set_width_chars(len(text) + 1)
                entry.show()
            else:
                entry.set_text('')
                entry.hide()
        super().display()
        self.entry.set_width_chars(self.width)
        if self.field and self.symbol:
            symbol, position = self.field.get_symbol(self.record, self.symbol)
            if position < 0.5:
                set_symbol(self.symbol_start, symbol)
                set_symbol(self.symbol_end, '')
            else:
                set_symbol(self.symbol_start, '')
                set_symbol(self.symbol_end, symbol)
        value = self.get_client_value()
        self.entry.set_text(value)
        reset_position(self.entry)

    def _readonly_set(self, value):
        super()._readonly_set(value)
        self.entry.set_editable(not value)
