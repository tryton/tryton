# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from gi.repository import Gtk

from .char import Char
from tryton.common import IconFactory
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

    def set_value(self):
        # avoid modification because different encoding
        value = self.get_encoded_value()
        previous = self.field.get_client(self.record)
        if (previous
                and value == self.encoder.encode(
                    self.decoder.decode(previous))):
            value = previous
        self.field.set_client(self.record, value)

    def get_client_value(self):
        value = super(PYSON, self).get_client_value()
        if value:
            value = repr(self.decoder.decode(value))
        return value

    def validate_pyson(self, *args):
        icon = 'tryton-ok'
        if self.get_encoded_value() is None:
            icon = 'tryton-error'
        pixbuf = IconFactory.get_pixbuf(icon, Gtk.IconSize.MENU)
        self.entry.set_icon_from_pixbuf(
            Gtk.EntryIconPosition.SECONDARY, pixbuf)

    def _focus_out(self):
        self.validate_pyson()
        super(PYSON, self)._focus_out()
