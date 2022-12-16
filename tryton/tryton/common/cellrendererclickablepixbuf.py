# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from gi.repository import Gtk, GObject


class CellRendererClickablePixbuf(Gtk.CellRendererPixbuf):
    __gsignals__ = {
        'clicked': (GObject.SignalFlags.RUN_LAST, GObject.TYPE_NONE,
            (GObject.TYPE_STRING, )),
        }

    def __init__(self):
        Gtk.CellRendererPixbuf.__init__(self)
        self.set_property('mode', Gtk.CellRendererMode.ACTIVATABLE)

    def do_activate(
            self, event, widget, path, background_area, cell_area, flags):
        self.emit('clicked', path)


GObject.type_register(CellRendererClickablePixbuf)
