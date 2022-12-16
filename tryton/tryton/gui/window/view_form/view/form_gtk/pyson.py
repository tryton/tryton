# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import gtk
from .char import Char
from tryton.pyson import CONTEXT, PYSONEncoder, PYSONDecoder


class PYSON(Char):

    def __init__(self, view, attrs):
        super(PYSON, self).__init__(view, attrs)
        self.encoder = PYSONEncoder()
        self.decoder = PYSONDecoder(noeval=True)
        self.entry.connect('key-release-event', self.validate_pyson)

    def get_encoded_value(self):
        value = self.get_value()
        if not value:
            return value
        try:
            return self.encoder.encode(eval(value, CONTEXT))
        except Exception:
            return None

    def set_value(self, record, field):
        field.set_client(record, self.get_encoded_value())

    def get_client_value(self, record, field):
        value = super(PYSON, self).get_client_value(record, field)
        if value:
            value = repr(self.decoder.decode(value))
        return value

    def validate_pyson(self, *args):
        icon = gtk.STOCK_OK
        if self.get_encoded_value() is None:
            icon = gtk.STOCK_CANCEL
        self.entry.set_icon_from_stock(gtk.ENTRY_ICON_SECONDARY, icon)

    def _focus_out(self):
        self.validate_pyson()
        super(PYSON, self)._focus_out()
